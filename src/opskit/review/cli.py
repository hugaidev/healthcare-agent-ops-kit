"""CLI: ``opskit-review scan <paths>`` and ``opskit-review llm <diff-file>``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from opskit.review import engine
from opskit.review.findings import Severity


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opskit-review")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="deterministic rules over files or directories")
    scan.add_argument("paths", nargs="+", type=Path)
    scan.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    scan.add_argument("--fail-on", choices=["low", "medium", "high", "critical"], default="high")
    scan.add_argument("--output", type=Path, help="write report here instead of stdout")

    llm = sub.add_parser("llm", help="advisory LLM review of a unified diff (never gates)")
    llm.add_argument("diff", type=Path)

    args = parser.parse_args(argv)

    if args.cmd == "scan":
        findings = engine.scan_paths(args.paths)
        render = {"text": engine.to_text, "json": engine.to_json, "sarif": engine.to_sarif}
        report = render[args.format](findings)
        if args.output:
            args.output.write_text(report, encoding="utf-8")
        else:
            print(report)
        return 1 if engine.exceeds(findings, Severity.parse(args.fail_on)) else 0

    from opskit.review import llm as llm_mod

    print(llm_mod.review_diff(args.diff.read_text(encoding="utf-8", errors="replace")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
