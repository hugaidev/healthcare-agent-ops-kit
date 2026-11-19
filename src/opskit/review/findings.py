"""Finding model, severity ordering and suppression handling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: str) -> Severity:
        return cls[value.upper()]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    path: str
    line: int
    message: str
    remediation: str


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: Severity
    title: str
    control: str  # regulatory / framework reference shown in SARIF help text


RULES: dict[str, Rule] = {
    r.rule_id: r
    for r in (
        Rule(
            "PHI001",
            Severity.HIGH,
            "PHI-like identifier in log or print call",
            "HIPAA 164.312(b); minimum necessary 164.502(b)",
        ),
        Rule(
            "MCP001",
            Severity.HIGH,
            "print() in MCP server code",
            "stdout is the stdio protocol channel; output corrupts it and may leak payloads",
        ),
        Rule(
            "AUD001",
            Severity.HIGH,
            "MCP tool bypasses the guarded service layer",
            "HIPAA 164.312(a)(1), 164.312(b)",
        ),
        Rule(
            "SEC001",
            Severity.CRITICAL,
            "Hardcoded secret-like literal",
            "HIPAA 164.312(d); SOC 2 CC6.1",
        ),
        Rule(
            "TF001",
            Severity.HIGH,
            "IAM policy grants wildcard action",
            "Least privilege, HIPAA 164.308(a)(4)",
        ),
        Rule("TF002", Severity.CRITICAL, "S3 bucket publicly accessible", "HIPAA 164.312(a)(1)"),
        Rule(
            "TF003", Severity.HIGH, "Database without encryption at rest", "HIPAA 164.312(a)(2)(iv)"
        ),
        Rule("TF004", Severity.CRITICAL, "Database publicly accessible", "HIPAA 164.312(e)(1)"),
        Rule("TF005", Severity.HIGH, "Security group open to the internet", "HIPAA 164.312(e)(1)"),
        Rule(
            "SUP001",
            Severity.MEDIUM,
            "Suppression without a written reason",
            "Auditable changes: every exception must be justified",
        ),
    )
}

_SUPPRESS = re.compile(r"#\s*phi-review:\s*ignore\[([A-Z0-9, ]+)\]\s*(.*)$")


def suppressions(lines: list[str]) -> tuple[dict[int, set[str]], list[Finding]]:
    """Return {line -> suppressed rule ids} and findings for suppressions lacking a reason.

    A suppression comment applies to its own line and the line immediately after it.
    """
    active: dict[int, set[str]] = {}
    invalid: list[Finding] = []
    for idx, text in enumerate(lines, start=1):
        m = _SUPPRESS.search(text)
        if not m:
            continue
        ids = {part.strip() for part in m.group(1).split(",") if part.strip()}
        if not m.group(2).strip():
            invalid.append(
                Finding(
                    "SUP001",
                    Severity.MEDIUM,
                    "",
                    idx,
                    "Suppression has no written reason.",
                    "Add a reason, e.g. '# phi-review: ignore[PHI001] synthetic'.",
                )
            )
            continue
        for target in (idx, idx + 1):
            active.setdefault(target, set()).update(ids)
    return active, invalid
