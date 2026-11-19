from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from opskit.audit import AuditLog, verify_chain
from opskit.models import ToolStatus
from opskit.payer_sim import SyntheticPayer
from opskit.policy import (
    ConfigError,
    Principal,
    RateLimiter,
    principal_from_env,
)
from opskit.service import BenefitsService
from tests.conftest import ServiceFactory

ELIG: dict[str, Any] = {
    "patient_ref": "pt_demo000001",
    "payer_id": "acme_health",
    "service_line": "ABA_THERAPY",
    "date_of_service": "2026-06-15",
}


def test_every_call_is_audited_including_denials(
    make_service: ServiceFactory, audit: AuditLog
) -> None:
    make_service("billing_specialist").verify_eligibility(ELIG)
    make_service("compliance_auditor").verify_eligibility(ELIG)
    make_service("billing_specialist").verify_eligibility({"patient_ref": "bad"})
    lines = audit.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert verify_chain(audit.path).ok
    assert '"outcome": "denied"' in lines[1]
    assert '"outcome": "invalid"' in lines[2]


def test_invalid_error_never_echoes_input(make_service: ServiceFactory) -> None:
    result = make_service().verify_eligibility({**ELIG, "patient_ref": "Jane Doe 03/14/2015"})
    assert result.status is ToolStatus.INVALID
    assert "Jane" not in (result.error or "")
    assert "patient_ref" in (result.error or "")


def test_rate_limit_blocks_enumeration(make_service: ServiceFactory) -> None:
    now = [0.0]
    svc = make_service(limiter=RateLimiter(max_calls=2, window_s=60, clock=lambda: now[0]))
    assert svc.verify_eligibility(ELIG).status is ToolStatus.OK
    assert svc.verify_eligibility(ELIG).status is ToolStatus.OK
    assert svc.verify_eligibility(ELIG).status is ToolStatus.RATE_LIMITED
    now[0] = 61.0
    assert svc.verify_eligibility(ELIG).status is ToolStatus.OK


def test_audit_failure_fails_closed(tmp_path: Path) -> None:
    class BrokenAudit(AuditLog):
        def record(self, **_: Any) -> dict[str, Any]:
            raise OSError("disk full")

    svc = BenefitsService(
        SyntheticPayer(), BrokenAudit(tmp_path / "x.jsonl"), Principal("t", "billing_specialist")
    )
    result = svc.verify_eligibility(ELIG)
    assert result.status is ToolStatus.ERROR
    assert result.data == {}


def test_unexpected_exception_is_generic(tmp_path: Path) -> None:
    class Exploding(SyntheticPayer):
        def lookup_member(self, patient_ref: str) -> Any:
            raise RuntimeError("secret internal detail pt_demo000001")

    svc = BenefitsService(
        Exploding(), AuditLog(tmp_path / "x.jsonl"), Principal("t", "billing_specialist")
    )
    result = svc.verify_eligibility(ELIG)
    assert result.status is ToolStatus.ERROR
    assert "secret" not in result.model_dump_json()


def test_audit_chain_tool_requires_auditor(make_service: ServiceFactory) -> None:
    make_service("billing_specialist").verify_eligibility(ELIG)
    assert make_service("billing_specialist").verify_audit_chain().status is ToolStatus.DENIED
    ok = make_service("compliance_auditor").verify_audit_chain()
    assert ok.status is ToolStatus.OK
    assert ok.data["ok"] is True


def test_principal_fail_closed() -> None:
    with pytest.raises(ConfigError):
        principal_from_env({})
    with pytest.raises(ConfigError):
        principal_from_env({"OPS_ACTOR": "a", "OPS_ROLE": "root"})
    assert principal_from_env({"OPS_ACTOR": "a", "OPS_ROLE": "billing_specialist"}).actor == "a"
