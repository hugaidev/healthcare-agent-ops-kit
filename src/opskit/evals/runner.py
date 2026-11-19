"""Eval runner: executes JSONL cases against the guarded service and enforces thresholds.

Metrics tracked (see docs/EVALS.md):
* accuracy overall and per category
* unsafe-action rate: failures among cases tagged ``safety_critical`` (must stay 0)
* PHI leak count: forbidden strings that appeared in any tool output (must stay 0)
* latency p50 / p95
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opskit.audit import AuditLog
from opskit.models import ToolResult
from opskit.payer_sim import SyntheticPayer
from opskit.policy import Principal, RateLimiter
from opskit.service import BenefitsService

_TOOLS = {"verify_eligibility", "check_prior_auth_required", "draft_appeal"}


@dataclass
class CaseResult:
    case_id: str
    category: str
    passed: bool
    safety_critical: bool
    leaks: int
    latency_ms: float
    reason: str = ""


@dataclass
class Report:
    results: list[CaseResult] = field(default_factory=list)

    def metrics(self) -> dict[str, Any]:
        total = len(self.results)
        by_cat: dict[str, list[bool]] = defaultdict(list)
        for r in self.results:
            by_cat[r.category].append(r.passed)
        safety = [r for r in self.results if r.safety_critical]
        lat = sorted(r.latency_ms for r in self.results)
        return {
            "total": total,
            "accuracy": sum(r.passed for r in self.results) / total if total else 0.0,
            "accuracy_by_category": {k: sum(v) / len(v) for k, v in sorted(by_cat.items())},
            "unsafe_action_rate": (
                sum(not r.passed for r in safety) / len(safety) if safety else 0.0
            ),
            "safety_critical_cases": len(safety),
            "phi_leaks": sum(r.leaks for r in self.results),
            "latency_ms_p50": statistics.median(lat) if lat else 0.0,
            "latency_ms_p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else 0.0,
            "failures": [
                {"id": r.case_id, "reason": r.reason} for r in self.results if not r.passed
            ],
        }


def _subset(expected: dict[str, Any], actual: dict[str, Any]) -> str:
    for key, want in expected.items():
        if actual.get(key) != want:
            return f"data.{key}: expected {want!r}, got {actual.get(key)!r}"
    return ""


def run_case(case: dict[str, Any], audit_dir: Path) -> CaseResult:
    service = BenefitsService(
        SyntheticPayer(),
        AuditLog(audit_dir / f"{case['id']}.jsonl", hmac_key=b"eval-key"),
        Principal(actor="eval-runner", role=case["role"]),
        RateLimiter(max_calls=10_000),
    )
    tool = case["tool"]
    if tool not in _TOOLS:
        raise ValueError(f"unknown tool in case {case['id']}: {tool}")
    start = time.perf_counter()
    result: ToolResult = getattr(service, tool)(case["input"])
    latency = (time.perf_counter() - start) * 1000

    expect = case["expect"]
    reason = ""
    if result.status.value != expect["status"]:
        reason = f"status: expected {expect['status']}, got {result.status.value}"
    if not reason and "review" in expect and result.requires_human_review != expect["review"]:
        reason = f"requires_human_review: expected {expect['review']}"
    if not reason and "data" in expect:
        reason = _subset(expect["data"], result.data)
    blob = result.model_dump_json()
    leaks = sum(1 for s in expect.get("absent_in_output", []) if s in blob)
    if leaks and not reason:
        reason = f"{leaks} forbidden string(s) present in output"
    return CaseResult(
        case_id=case["id"],
        category=case["category"],
        passed=not reason,
        safety_critical=bool(case.get("safety_critical")),
        leaks=leaks,
        latency_ms=latency,
        reason=reason,
    )


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def check_thresholds(metrics: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    problems: list[str] = []
    if metrics["accuracy"] < thresholds["min_accuracy"]:
        problems.append(f"accuracy {metrics['accuracy']:.3f} < {thresholds['min_accuracy']}")
    if metrics["unsafe_action_rate"] > thresholds["max_unsafe_action_rate"]:
        problems.append(f"unsafe_action_rate {metrics['unsafe_action_rate']:.3f} above limit")
    if metrics["phi_leaks"] > thresholds["max_phi_leaks"]:
        problems.append(f"phi_leaks {metrics['phi_leaks']} above limit")
    if metrics["latency_ms_p95"] > thresholds["max_p95_latency_ms"]:
        problems.append(f"p95 latency {metrics['latency_ms_p95']:.1f}ms above limit")
    return problems


def to_markdown(metrics: dict[str, Any], problems: list[str]) -> str:
    lines = [
        "# Eval report",
        "",
        f"- Cases: {metrics['total']} ({metrics['safety_critical_cases']} safety-critical)",
        f"- Accuracy: {metrics['accuracy']:.1%}",
        f"- Unsafe-action rate: {metrics['unsafe_action_rate']:.1%}",
        f"- PHI leaks: {metrics['phi_leaks']}",
        f"- Latency p50/p95: {metrics['latency_ms_p50']:.2f} / {metrics['latency_ms_p95']:.2f} ms",
        "",
        "| Category | Accuracy |",
        "|---|---|",
        *[f"| {k} | {v:.0%} |" for k, v in metrics["accuracy_by_category"].items()],
        "",
        "**Result: " + ("FAIL**" if problems else "PASS**"),
        *[f"- {p}" for p in problems],
        *[f"- failing case `{f['id']}`: {f['reason']}" for f in metrics["failures"]],
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    default_dir = Path(__file__).resolve().parents[3] / "evals"
    parser = argparse.ArgumentParser(prog="opskit-evals")
    parser.add_argument("--cases", type=Path, default=default_dir / "data" / "cases.jsonl")
    parser.add_argument("--thresholds", type=Path, default=default_dir / "thresholds.json")
    parser.add_argument("--report-dir", type=Path, default=default_dir / "reports")
    args = parser.parse_args(argv)

    report = Report()
    with tempfile.TemporaryDirectory() as tmp:
        for case in load_cases(args.cases):
            report.results.append(run_case(case, Path(tmp)))
    metrics = report.metrics()
    problems = check_thresholds(metrics, json.loads(args.thresholds.read_text(encoding="utf-8")))

    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "latest.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    markdown = to_markdown(metrics, problems)
    (args.report_dir / "latest.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
