"""Line/block rules for Terraform. Deliberately simple: complements, not replaces, tfsec/Checkov."""

from __future__ import annotations

import re
from collections.abc import Iterator

from opskit.review.findings import Finding, Severity

_WILDCARD_ACTION = re.compile(r'["\']?[Aa]ction["\']?\s*[=:]\s*(\[\s*)?["\']\*["\']')
_PUBLIC_ACL = re.compile(r'\bacl\s*=\s*"public-read(-write)?"')
_PUBLIC_BLOCK_OFF = re.compile(r"\b(block_public_acls|block_public_policy)\s*=\s*false")
_PUBLICLY_ACCESSIBLE = re.compile(r"\bpublicly_accessible\s*=\s*true")
_OPEN_CIDR = re.compile(r"0\.0\.0\.0/0|::/0")
_DB_RESOURCE = re.compile(r'resource\s+"(aws_db_instance|aws_rds_cluster)"\s+"[^"]+"\s*\{')
_INGRESS = re.compile(r"\bingress\s*\{")


def _blocks(text: str, opener: re.Pattern[str]) -> Iterator[tuple[int, str]]:
    """Yield (1-based start line, body text) for each brace-balanced block matching opener."""
    for m in opener.finditer(text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        yield text.count("\n", 0, m.start()) + 1, text[m.start() : i]


def check_terraform(path: str, source: str) -> list[Finding]:
    out: list[Finding] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        code = line.split("#", 1)[0]
        if _WILDCARD_ACTION.search(code):
            out.append(
                Finding(
                    "TF001",
                    Severity.HIGH,
                    path,
                    lineno,
                    'IAM statement allows Action "*".',
                    "Enumerate the specific actions required (least privilege).",
                )
            )
        if _PUBLIC_ACL.search(code) or _PUBLIC_BLOCK_OFF.search(code):
            out.append(
                Finding(
                    "TF002",
                    Severity.CRITICAL,
                    path,
                    lineno,
                    "S3 configuration allows public access.",
                    "Use private ACLs and enable all public access block settings.",
                )
            )
        if _PUBLICLY_ACCESSIBLE.search(code):
            out.append(
                Finding(
                    "TF004",
                    Severity.CRITICAL,
                    path,
                    lineno,
                    "Database is publicly accessible.",
                    "Set publicly_accessible = false and use private subnets.",
                )
            )
    for start, body in _blocks(source, _DB_RESOURCE):
        if not re.search(r"\bstorage_encrypted\s*=\s*true", body):
            out.append(
                Finding(
                    "TF003",
                    Severity.HIGH,
                    path,
                    start,
                    "Database resource lacks storage_encrypted = true.",
                    "Enable encryption at rest with a customer-managed KMS key.",
                )
            )
    for start, body in _blocks(source, _INGRESS):
        if _OPEN_CIDR.search(body):
            out.append(
                Finding(
                    "TF005",
                    Severity.HIGH,
                    path,
                    start,
                    "Ingress rule open to the whole internet.",
                    "Restrict to known CIDRs or security-group references.",
                )
            )
    return out
