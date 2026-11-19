"""PreToolUse hook: stop PHI, secrets and irreversible commands before they happen.

Claude Code passes the tool call as JSON on stdin. Exit code 2 blocks the call and returns
stderr to the model so it can correct course. Allowed test-data locations are listed in
``PHI_ALLOWED_PREFIXES``; everywhere else, writing PHI-like strings is refused.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from opskit.phi import phi_categories

PHI_ALLOWED_PREFIXES = ("tests/", "evals/data/")
_BLOCKING_CATEGORIES = {"ssn", "email", "phone", "mrn", "member_id", "dob"}
_SAFE_EMAIL = re.compile(r"[\w.+-]+@(?:example\.(?:com|org|net)|users\.noreply\.github\.com)")

_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
)

_BASH_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgit\s+push\b.*(--force|-f\b)"), "force-push is blocked; open a PR instead"),
    (re.compile(r"\bgit\s+commit\b.*--no-verify"), "skipping hooks is blocked"),
    (re.compile(r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\.\.?)(\s|$)"), "destructive rm is blocked"),
    (re.compile(r"\b(terraform|tofu)\s+(apply|destroy)\b"), "infra changes go through CI review"),
    (re.compile(r"(curl|wget)\b[^|]*\|\s*(ba)?sh"), "piping downloads to a shell is blocked"),
    (re.compile(r"\b(cat|type|less|more|head|tail)\s+[^|;&]*\.env\b"), "reading .env is blocked"),
)


def _is_allowed_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(f"/{p}" in f"/{norm}" for p in PHI_ALLOWED_PREFIXES)


def _written_text(tool_input: dict[str, Any]) -> str:
    parts = [
        tool_input.get("content"),
        tool_input.get("new_string"),
        *[e.get("new_string") for e in tool_input.get("edits", []) if isinstance(e, dict)],
    ]
    return "\n".join(p for p in parts if isinstance(p, str))


def check_tool_call(payload: dict[str, Any]) -> str | None:
    """Return a refusal message, or None if the call is allowed."""
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool in {"Write", "Edit", "MultiEdit"}:
        text = _written_text(tool_input)
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                return "Blocked: content looks like a credential. Use environment variables."
        path = str(tool_input.get("file_path", ""))
        if not _is_allowed_path(path):
            scrubbed = _SAFE_EMAIL.sub("", text)
            hits = _BLOCKING_CATEGORIES & set(phi_categories(scrubbed))
            if hits:
                return (
                    f"Blocked: content contains PHI-like data ({', '.join(sorted(hits))}). "
                    "Use synthetic opaque refs (pt_demo000001); real-looking test data is only "
                    "allowed under tests/ and evals/data/."
                )
    elif tool == "Bash":
        command = str(tool_input.get("command", ""))
        for pattern, message in _BASH_RULES:
            if pattern.search(command):
                return f"Blocked: {message}."
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        # Fail closed: a guard that cannot read its input must not silently allow the call.
        print("Blocked: guard hook received unreadable input.", file=sys.stderr)
        return 2
    message = check_tool_call(payload)
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
