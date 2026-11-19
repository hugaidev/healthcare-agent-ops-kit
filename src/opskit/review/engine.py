"""Run rules over files, apply suppressions, and render text / JSON / SARIF."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from opskit import __version__
from opskit.review.findings import RULES, Finding, Severity, suppressions
from opskit.review.rules_python import check_python
from opskit.review.rules_terraform import check_terraform

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".terraform"}


def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not (set(f.parts) & _SKIP_DIRS) and f.suffix in {".py", ".tf"}:
                    yield f
        elif p.is_file():
            yield p


def scan_source(path: str, source: str) -> list[Finding]:
    if path.endswith(".py"):
        raw = check_python(path, source)
    elif path.endswith(".tf"):
        raw = check_terraform(path, source)
    else:
        return []
    active, invalid = suppressions(source.splitlines())
    kept = [f for f in raw if f.rule_id not in active.get(f.line, set())]
    kept += [
        Finding(f.rule_id, f.severity, path, f.line, f.message, f.remediation) for f in invalid
    ]
    return sorted(kept, key=lambda f: (f.path, f.line, f.rule_id))


def scan_paths(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for f in iter_files(paths):
        findings += scan_source(f.as_posix(), f.read_text(encoding="utf-8", errors="replace"))
    return findings


def exceeds(findings: Iterable[Finding], threshold: Severity) -> bool:
    return any(f.severity >= threshold for f in findings)


def to_text(findings: list[Finding]) -> str:
    if not findings:
        return "No findings."
    rows = [
        f"{f.path}:{f.line}  [{f.severity.name}] {f.rule_id}  {f.message}\n    fix: {f.remediation}"
        for f in findings
    ]
    return "\n".join(rows)


def to_json(findings: list[Finding]) -> str:
    return json.dumps(
        [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.name,
                "path": f.path,
                "line": f.line,
                "message": f.message,
                "remediation": f.remediation,
            }
            for f in findings
        ],
        indent=2,
    )


_SARIF_LEVEL = {
    Severity.LOW: "note",
    Severity.MEDIUM: "warning",
    Severity.HIGH: "error",
    Severity.CRITICAL: "error",
}


def to_sarif(findings: list[Finding]) -> str:
    """SARIF 2.1.0, consumable by GitHub code scanning."""
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "opskit-review",
                        "version": __version__,
                        "rules": [
                            {
                                "id": r.rule_id,
                                "shortDescription": {"text": r.title},
                                "help": {"text": r.control},
                            }
                            for r in RULES.values()
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": f.rule_id,
                        "level": _SARIF_LEVEL[f.severity],
                        "message": {"text": f"{f.message} Fix: {f.remediation}"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": f.path},
                                    "region": {"startLine": f.line},
                                }
                            }
                        ],
                    }
                    for f in findings
                ],
            }
        ],
    }
    return json.dumps(doc, indent=2)
