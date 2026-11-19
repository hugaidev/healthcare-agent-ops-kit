"""PostToolUse hook: run the compliance rules on every Python/Terraform file Claude edits.

Findings of severity HIGH or above are returned to the model (exit 2) so it fixes them in the
same turn instead of leaving them for CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from opskit.review.engine import scan_source
from opskit.review.findings import Severity


def review_edit(payload: dict[str, Any]) -> str | None:
    if payload.get("tool_name") not in {"Write", "Edit", "MultiEdit"}:
        return None
    raw = str((payload.get("tool_input") or {}).get("file_path", ""))
    path = Path(raw)
    if path.suffix not in {".py", ".tf"} or not path.is_file():
        return None
    findings = [
        f
        for f in scan_source(path.as_posix(), path.read_text(encoding="utf-8", errors="replace"))
        if f.severity >= Severity.HIGH
    ]
    if not findings:
        return None
    lines = [f"Compliance review found {len(findings)} issue(s) in {path.name}:"]
    lines += [f"  line {f.line} [{f.rule_id}] {f.message} Fix: {f.remediation}" for f in findings]
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    message = review_edit(payload)
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
