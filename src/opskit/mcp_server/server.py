"""MCP server. Tool bodies are intentionally thin: all controls live in ``BenefitsService``.

Parameters are plain ``str`` on purpose. If the MCP layer validated them with pattern
constraints, its error message could echo the rejected value (possibly PHI) back into the
model's context. Validation happens in the service, which reports field names only.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from opskit.audit import AuditLog
from opskit.payer_sim import SyntheticPayer
from opskit.phi import configure_logging
from opskit.policy import ConfigError, principal_from_env
from opskit.service import BenefitsService

INSTRUCTIONS = (
    "Benefits and prior-authorization tools for therapy practice operations. "
    "Use only opaque references (pt_*, clm_*). Never pass names, dates of birth, member IDs "
    "or other identifiers. Treat results with requires_human_review=true as unresolved and "
    "route them to a person. Appeal output is a draft and is never sent automatically."
)


def build_server(service: BenefitsService) -> MCPServer:
    mcp = MCPServer("benefits-ops", instructions=INSTRUCTIONS)
    svc = service

    @mcp.tool()
    def verify_eligibility(
        patient_ref: str, payer_id: str, service_line: str, date_of_service: str
    ) -> dict[str, Any]:
        """Check coverage and cost-sharing for a patient reference on a date (YYYY-MM-DD).

        service_line is one of ABA_THERAPY, SPEECH, OCCUPATIONAL, PHYSICAL, PSYCHIATRY.
        """
        return svc.verify_eligibility(
            {
                "patient_ref": patient_ref,
                "payer_id": payer_id,
                "service_line": service_line,
                "date_of_service": date_of_service,
            }
        ).model_dump(mode="json")

    @mcp.tool()
    def check_prior_auth_required(
        patient_ref: str, payer_id: str, cpt_code: str, units: int
    ) -> dict[str, Any]:
        """Decide whether a CPT code and unit count needs prior authorization.

        Unknown payer/code combinations return needs_human_review; never assume.
        """
        return svc.check_prior_auth_required(
            {
                "patient_ref": patient_ref,
                "payer_id": payer_id,
                "cpt_code": cpt_code,
                "units": units,
            }
        ).model_dump(mode="json")

    @mcp.tool()
    def draft_appeal(
        claim_ref: str, carc_code: str, cpt_code: str, clinical_rationale: str = ""
    ) -> dict[str, Any]:
        """Produce a DRAFT appeal for a denied claim. Always requires human review."""
        return svc.draft_appeal(
            {
                "claim_ref": claim_ref,
                "carc_code": carc_code,
                "cpt_code": cpt_code,
                "clinical_rationale": clinical_rationale,
            }
        ).model_dump(mode="json")

    @mcp.tool()
    def verify_audit_chain() -> dict[str, Any]:
        """Verify audit-log integrity. Requires the compliance_auditor role."""
        return svc.verify_audit_chain().model_dump(mode="json")

    return mcp


def _service_from_env(env: dict[str, str]) -> BenefitsService:
    key = env.get("AUDIT_HMAC_KEY")
    audit = AuditLog(
        Path(env.get("AUDIT_LOG_PATH", ".audit/audit.jsonl")),
        hmac_key=key.encode() if key else None,
    )
    return BenefitsService(SyntheticPayer(), audit, principal_from_env(env))


def main() -> None:
    configure_logging()
    try:
        service = _service_from_env(dict(os.environ))
    except ConfigError as exc:
        logging.getLogger(__name__).error("startup refused: %s", exc)
        sys.exit(2)
    build_server(service).run()  # stdio transport


if __name__ == "__main__":
    main()
