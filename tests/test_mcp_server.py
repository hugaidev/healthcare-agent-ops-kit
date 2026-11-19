from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import Client

from opskit.mcp_server import server
from tests.conftest import ServiceFactory


def _call(service_factory: ServiceFactory, name: str, args: dict[str, Any]) -> dict[str, Any]:
    mcp = server.build_server(service_factory())

    async def run() -> dict[str, Any]:
        async with Client(mcp) as client:
            result = await client.call_tool(name, args)
            if result.structured_content is not None:
                return dict(result.structured_content)
            return json.loads(result.content[0].text)  # type: ignore[union-attr,no-any-return]

    return anyio.run(run)


def test_tools_are_listed(make_service: ServiceFactory) -> None:
    mcp = server.build_server(make_service())

    async def run() -> set[str]:
        async with Client(mcp) as client:
            return {t.name for t in (await client.list_tools()).tools}

    assert anyio.run(run) == {
        "verify_eligibility",
        "check_prior_auth_required",
        "draft_appeal",
        "verify_audit_chain",
    }


def test_end_to_end_eligibility(make_service: ServiceFactory) -> None:
    out = _call(
        make_service,
        "verify_eligibility",
        {
            "patient_ref": "pt_demo000001",
            "payer_id": "acme_health",
            "service_line": "ABA_THERAPY",
            "date_of_service": "2026-06-15",
        },
    )
    assert out["status"] == "ok"
    assert out["data"]["coverage_active"] is True


def test_end_to_end_pa_and_appeal(make_service: ServiceFactory) -> None:
    pa = _call(
        make_service,
        "check_prior_auth_required",
        {
            "patient_ref": "pt_demo000001",
            "payer_id": "acme_health",
            "cpt_code": "97153",
            "units": 5,
        },
    )
    assert pa["data"]["decision"] == "required"
    appeal = _call(
        make_service,
        "draft_appeal",
        {"claim_ref": "clm_abc123456", "carc_code": "CO-197", "cpt_code": "97153"},
    )
    assert appeal["requires_human_review"] is True


def test_bad_input_does_not_echo_value(make_service: ServiceFactory) -> None:
    out = _call(
        make_service,
        "verify_eligibility",
        {
            "patient_ref": "123-45-6789",
            "payer_id": "acme_health",
            "service_line": "ABA_THERAPY",
            "date_of_service": "2026-06-15",
        },
    )
    assert out["status"] == "invalid"
    assert "123-45-6789" not in json.dumps(out)


def test_audit_chain_tool_role_gate(make_service: ServiceFactory) -> None:
    assert _call(make_service, "verify_audit_chain", {})["status"] == "denied"


def test_startup_refuses_without_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPS_ROLE", raising=False)
    monkeypatch.delenv("OPS_ACTOR", raising=False)
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "a.jsonl"))
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 2


def test_service_from_env_builds(tmp_path: Path) -> None:
    svc = server._service_from_env(
        {
            "OPS_ACTOR": "a",
            "OPS_ROLE": "billing_specialist",
            "AUDIT_LOG_PATH": str(tmp_path / "a.jsonl"),
            "AUDIT_HMAC_KEY": "k",
        }
    )
    assert svc is not None
