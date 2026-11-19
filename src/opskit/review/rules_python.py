"""AST-based rules for Python source."""

from __future__ import annotations

import ast
import re

from opskit.review.findings import Finding, Severity

_PHI_NAME = re.compile(
    r"(ssn|social_?security|dob|birth|member_?id|subscriber|mrn|patient_?name|first_?name|"
    r"last_?name|full_?name|address|phone|email|diagnos|insurance_?id|policy_?number|"
    r"clinical_?rationale)",
    re.IGNORECASE,
)
_SECRET_NAME = re.compile(r"(secret|passw(or)?d|api_?key|token|private_?key)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"(example|placeholder|changeme|dummy|test|<.*>|\$\{)", re.IGNORECASE)
_LOG_OBJECTS = {"logger", "log", "logging", "_log", "_logger"}
_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


def _names_in(node: ast.AST) -> list[str]:
    found: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found.append(sub.id)
        elif isinstance(sub, ast.Attribute):
            found.append(sub.attr)
        elif isinstance(sub, ast.keyword) and sub.arg:
            found.append(sub.arg)
    return found


def _is_log_call(call: ast.Call) -> bool:
    f = call.func
    return (
        isinstance(f, ast.Attribute)
        and f.attr in _LOG_METHODS
        and isinstance(f.value, ast.Name)
        and f.value.id in _LOG_OBJECTS
    )


def _is_tool_decorated(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == "tool":
            return True
    return False


def _calls_service(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for sub in ast.walk(fn):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and isinstance(sub.func.value, ast.Name)
            and sub.func.value.id in {"svc", "service"}
        ):
            return True
    return False


def check_python(path: str, source: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    norm = path.replace("\\", "/")
    in_mcp = "/mcp_server/" in norm or norm.startswith("mcp_server/")
    out: list[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_print = isinstance(node.func, ast.Name) and node.func.id == "print"
            if is_print and in_mcp:
                out.append(
                    Finding(
                        "MCP001",
                        Severity.HIGH,
                        path,
                        node.lineno,
                        "print() in MCP server code writes to the stdio protocol channel.",
                        "Use the module logger; logs go to stderr via configure_logging().",
                    )
                )
            if _is_log_call(node) or is_print:
                bad = sorted({n for n in _names_in(node) if _PHI_NAME.search(n)})
                if bad:
                    out.append(
                        Finding(
                            "PHI001",
                            Severity.HIGH,
                            path,
                            node.lineno,
                            f"Log/print call references PHI-like names: {', '.join(bad)}.",
                            "Log opaque refs (pt_*, trace_id) and error types only.",
                        )
                    )
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if (
                isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and len(value.value) >= 8
                and not _PLACEHOLDER.search(value.value)
            ):
                for t in targets:
                    name = t.id if isinstance(t, ast.Name) else getattr(t, "attr", "")
                    if name and _SECRET_NAME.search(name):
                        out.append(
                            Finding(
                                "SEC001",
                                Severity.CRITICAL,
                                path,
                                node.lineno,
                                f"Secret-like literal assigned to '{name}'.",
                                "Load from the environment or a secrets manager; rotate it.",
                            )
                        )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            in_mcp and _is_tool_decorated(node) and not _calls_service(node)
        ):
            out.append(
                Finding(
                    "AUD001",
                    Severity.HIGH,
                    path,
                    node.lineno,
                    f"MCP tool '{node.name}' does not delegate to the guarded service.",
                    "Call svc.<tool>(...) so authz, rate limit and audit always apply.",
                )
            )
    return out
