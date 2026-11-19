"""PHI detection and redaction.

This is a *defense-in-depth* heuristic layer, not a de-identification engine. The primary
control is architectural: agents only ever handle opaque references (see ``models``), so
free text is the only place identifiers could leak. Pattern coverage targets the HIPAA
Safe Harbor identifiers that commonly appear in operational text (45 CFR 164.514(b)(2)).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

# Order matters: more specific patterns first so one identifier yields one finding.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")),
    (
        "dob",
        re.compile(
            r"\b(?:dob|date of birth|born(?: on)?)\b[:\s]*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
            re.IGNORECASE,
        ),
    ),
    (
        "date",
        re.compile(r"\b(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b"),
    ),
    (
        "mrn",
        re.compile(
            r"\b(?:mrn|medical record(?: number)?)\b[:#\s]*(?=[A-Z0-9-]*\d)[A-Z0-9-]{5,}",
            re.IGNORECASE,
        ),
    ),
    (
        "member_id",
        re.compile(
            r"\b(?:member|subscriber|policy|insurance)\s*(?:id|#|no\.?|number)?[:#\s]+"
            r"(?=[A-Z0-9]*\d)[A-Z0-9]{8,}\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class Redaction:
    """Result of a redaction pass. ``findings`` lists the categories matched, never values."""

    text: str
    findings: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.findings)


def redact(text: str) -> Redaction:
    """Replace PHI-like substrings with ``[REDACTED:<category>]`` markers."""
    findings: list[str] = []
    out = text
    for name, pattern in _PATTERNS:

        def _sub(_m: re.Match[str], _name: str = name) -> str:
            findings.append(_name)
            return f"[REDACTED:{_name}]"

        out = pattern.sub(_sub, out)
    return Redaction(text=out, findings=tuple(findings))


def contains_phi(text: str) -> bool:
    return any(p.search(text) for _, p in _PATTERNS)


def phi_categories(text: str) -> tuple[str, ...]:
    return tuple(name for name, p in _PATTERNS if p.search(text))


class PhiLogFilter(logging.Filter):
    """Last line of defense: scrub formatted log messages before any handler sees them."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage()).text
        record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Route logs to **stderr** (stdout is the MCP stdio protocol channel) with scrubbing."""
    handler = logging.StreamHandler()  # defaults to stderr
    handler.addFilter(PhiLogFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
