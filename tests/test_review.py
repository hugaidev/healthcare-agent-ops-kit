from __future__ import annotations

import json
from pathlib import Path

import pytest

from opskit.review import engine, llm
from opskit.review.cli import main
from opskit.review.findings import Finding, Severity

BAD_PY = """
import logging
log = logging.getLogger(__name__)

api_key = "sk-live-9f8a7b6c5d4e3f2a"

def lookup(patient_name, member_id):
    log.info("looking up %s", patient_name)
    print(f"member {member_id}")
"""

BAD_MCP = """
mcp = object()

@mcp.tool()
def leaky(patient_ref: str):
    print("called")
    return {"ok": True}
"""

GOOD_MCP = """
@mcp.tool()
def fine(patient_ref: str):
    return svc.verify_eligibility({"patient_ref": patient_ref})
"""

BAD_TF = """
resource "aws_iam_policy" "p" {
  policy = jsonencode({ Statement = [{ Effect = "Allow", Action = "*", Resource = "*" }] })
}
resource "aws_s3_bucket_acl" "a" {
  acl = "public-read"
}
resource "aws_db_instance" "db" {
  engine = "postgres"
  publicly_accessible = true
}
resource "aws_security_group" "sg" {
  ingress {
    from_port = 5432
    cidr_blocks = ["0.0.0.0/0"]
  }
}
"""

GOOD_TF = """
resource "aws_db_instance" "db" {
  engine            = "postgres"
  storage_encrypted = true
}
"""


def _ids(findings: list[Finding]) -> set[str]:
    return {f.rule_id for f in findings}


def test_python_rules_fire() -> None:
    ids = _ids(engine.scan_source("src/svc.py", BAD_PY))
    assert {"PHI001", "SEC001"} <= ids


def test_print_in_mcp_and_missing_service_call() -> None:
    ids = _ids(engine.scan_source("src/opskit/mcp_server/x.py", BAD_MCP))
    assert {"MCP001", "AUD001"} <= ids
    assert engine.scan_source("src/opskit/mcp_server/x.py", GOOD_MCP) == []


def test_print_outside_mcp_is_not_mcp001() -> None:
    assert "MCP001" not in _ids(engine.scan_source("src/cli.py", "print('hi')"))


def test_terraform_rules_fire() -> None:
    ids = _ids(engine.scan_source("infra/main.tf", BAD_TF))
    assert {"TF001", "TF002", "TF003", "TF004", "TF005"} <= ids
    assert engine.scan_source("infra/ok.tf", GOOD_TF) == []


def test_suppression_with_reason_is_honored_without_reason_is_flagged() -> None:
    ok = (
        "log = None\n"
        "# phi-review: ignore[SEC001] synthetic fixture value\n"
        'api_key = "sk-live-9f8a7b6c"\n'
    )
    assert engine.scan_source("a.py", ok) == []
    bare = 'api_key = "sk-live-9f8a7b6c"  # phi-review: ignore[SEC001]\n'
    ids = _ids(engine.scan_source("a.py", bare))
    assert ids == {"SEC001", "SUP001"}


def test_placeholders_and_syntax_errors_are_ignored() -> None:
    assert engine.scan_source("a.py", 'api_key = "example-placeholder-value"') == []
    assert engine.scan_source("a.py", "def broken(:") == []
    assert engine.scan_source("notes.md", "api_key") == []


def test_outputs_and_threshold() -> None:
    findings = engine.scan_source("a.py", BAD_PY)
    assert engine.exceeds(findings, Severity.CRITICAL)
    sarif = json.loads(engine.to_sarif(findings))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"]
    assert json.loads(engine.to_json(findings))[0]["rule_id"]
    assert engine.to_text([]) == "No findings."
    assert "fix:" in engine.to_text(findings)


def test_cli_exit_codes_and_output_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(BAD_PY, encoding="utf-8")
    out = tmp_path / "r.sarif"
    assert main(["scan", str(bad), "--format", "sarif", "--output", str(out)]) == 1
    assert out.exists()
    assert main(["scan", str(bad), "--fail-on", "critical"]) == 1
    good = tmp_path / "good.tf"
    good.write_text(GOOD_TF, encoding="utf-8")
    assert main(["scan", str(tmp_path / "good.tf")]) == 0
    assert main(["scan", str(tmp_path), "--format", "json"]) == 1  # directory walk


def test_project_source_is_clean_under_its_own_rules() -> None:
    root = Path(__file__).resolve().parents[1]
    assert engine.scan_paths([root / "src"]) == []


class _FakeBlock:
    type = "text"
    text = "no concerns"


class _FakeMessages:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs

        class _Resp:
            content = (_FakeBlock(),)

        return _Resp()


class _FakeClient:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


def test_llm_pass_redacts_phi_before_sending() -> None:
    client = _FakeClient()
    out = llm.review_diff("+ log.info('ssn 123-45-6789')", client=client, model="m")
    assert out == "no concerns"
    sent = json.dumps(client.messages.kwargs["messages"])
    assert "123-45-6789" not in sent
    assert "REDACTED:ssn" in sent


def test_llm_model_comes_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEW_MODEL", "custom-model")
    client = _FakeClient()
    llm.review_diff("+x", client=client)
    assert client.messages.kwargs["model"] == "custom-model"
