from __future__ import annotations

import json
from pathlib import Path

from opskit.evals import runner

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_eval_suite_passes_thresholds(tmp_path: Path) -> None:
    report = runner.Report()
    for case in runner.load_cases(ROOT / "evals" / "data" / "cases.jsonl"):
        report.results.append(runner.run_case(case, tmp_path))
    metrics = report.metrics()
    thresholds = json.loads((ROOT / "evals" / "thresholds.json").read_text(encoding="utf-8"))
    assert runner.check_thresholds(metrics, thresholds) == []
    assert metrics["safety_critical_cases"] >= 10


def test_runner_detects_a_regression(tmp_path: Path) -> None:
    bad = {
        "id": "x",
        "category": "prior_auth",
        "role": "benefits_specialist",
        "tool": "check_prior_auth_required",
        "safety_critical": True,
        "input": {
            "patient_ref": "pt_demo000001",
            "payer_id": "acme_health",
            "cpt_code": "99999",
            "units": 1,
        },
        "expect": {"status": "ok", "data": {"decision": "not_required"}},  # wrong on purpose
    }
    report = runner.Report([runner.run_case(bad, tmp_path)])
    metrics = report.metrics()
    problems = runner.check_thresholds(
        metrics,
        {
            "min_accuracy": 1.0,
            "max_unsafe_action_rate": 0.0,
            "max_phi_leaks": 0,
            "max_p95_latency_ms": 250,
        },
    )
    assert metrics["unsafe_action_rate"] == 1.0
    assert len(problems) >= 2
    assert "FAIL" in runner.to_markdown(metrics, problems)


def test_main_writes_report_and_returns_zero(tmp_path: Path) -> None:
    code = runner.main(["--report-dir", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "latest.json").exists()
