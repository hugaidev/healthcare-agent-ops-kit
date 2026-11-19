"""Guarded execution of every tool: authz, rate limit, validation, audit, safe errors.

Every tool goes through ``_execute`` so that cross-cutting controls cannot be forgotten
on a per-tool basis (the review bot enforces this for MCP tool definitions).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from opskit import appeals
from opskit.audit import AuditLog, verify_chain
from opskit.models import (
    AppealRequest,
    EligibilityRequest,
    PaDecision,
    PriorAuthRequest,
    ToolResult,
    ToolStatus,
)
from opskit.payer_sim import (
    Payer,
    PayerUnavailableError,
    evaluate_prior_auth,
)
from opskit.policy import Principal, RateLimiter, Scope, authorize

log = logging.getLogger(__name__)

_Req = TypeVar("_Req", bound=BaseModel)
# handler returns (data, requires_human_review, status)
_Handler = Callable[[_Req], tuple[dict[str, Any], bool, ToolStatus]]


class BenefitsService:
    def __init__(
        self,
        payer: Payer,
        audit: AuditLog,
        principal: Principal,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._payer = payer
        self._audit = audit
        self._principal = principal
        self._limiter = limiter or RateLimiter()

    # ---- public tools -------------------------------------------------------------

    def verify_eligibility(self, args: Mapping[str, Any]) -> ToolResult:
        return self._execute(
            "verify_eligibility", Scope.ELIGIBILITY_READ, args, EligibilityRequest, self._elig
        )

    def check_prior_auth_required(self, args: Mapping[str, Any]) -> ToolResult:
        return self._execute(
            "check_prior_auth_required", Scope.PRIOR_AUTH_READ, args, PriorAuthRequest, self._pa
        )

    def draft_appeal(self, args: Mapping[str, Any]) -> ToolResult:
        return self._execute("draft_appeal", Scope.APPEAL_DRAFT, args, AppealRequest, self._appeal)

    def verify_audit_chain(self) -> ToolResult:
        trace = uuid.uuid4().hex
        if not authorize(self._principal.role, Scope.AUDIT_READ):
            self._write_audit("verify_audit_chain", Scope.AUDIT_READ, "denied", {}, trace)
            return ToolResult(
                status=ToolStatus.DENIED, trace_id=trace, error="role lacks audit:read"
            )
        result = verify_chain(self._audit.path)
        self._write_audit("verify_audit_chain", Scope.AUDIT_READ, "ok", {}, trace)
        return ToolResult(
            status=ToolStatus.OK,
            trace_id=trace,
            data={"ok": result.ok, "events": result.events, "broken_at": result.broken_at},
        )

    # ---- handlers -----------------------------------------------------------------

    def _elig(self, req: EligibilityRequest) -> tuple[dict[str, Any], bool, ToolStatus]:
        member = self._payer.lookup_member(req.patient_ref)
        if member is None:
            return {}, True, ToolStatus.NOT_FOUND
        active = (
            member.payer_id == req.payer_id
            and member.coverage_start <= req.date_of_service <= member.coverage_end
        )
        remaining = (
            None if member.visit_limit is None else max(member.visit_limit - member.visits_used, 0)
        )
        data = {
            "coverage_active": active,
            "plan_name": member.plan_name,
            "plan_type": member.plan_type,
            "deductible_remaining_cents": member.deductible_remaining_cents,
            "copay_cents": member.copay_cents,
            "coinsurance_pct": member.coinsurance_pct,
            "visits_remaining": remaining,
        }
        # Payer mismatch is ambiguous (wrong payer vs. coverage change): escalate, don't guess.
        return data, member.payer_id != req.payer_id, ToolStatus.OK

    def _pa(self, req: PriorAuthRequest) -> tuple[dict[str, Any], bool, ToolStatus]:
        member = self._payer.lookup_member(req.patient_ref)
        if member is None:
            return {}, True, ToolStatus.NOT_FOUND
        if member.payer_id != req.payer_id:
            data = {
                "decision": PaDecision.NEEDS_HUMAN_REVIEW.value,
                "rule_id": "PAYER_MISMATCH",
                "reason": "Payer on request does not match payer on file.",
                "policy_version": "n/a",
            }
            return data, True, ToolStatus.OK
        outcome = evaluate_prior_auth(
            self._payer.prior_auth_rule(req.payer_id, req.cpt_code), req.units
        )
        data = {
            "decision": outcome.decision.value,
            "rule_id": outcome.rule_id,
            "reason": outcome.reason,
            "policy_version": outcome.policy_version,
        }
        return data, outcome.decision is PaDecision.NEEDS_HUMAN_REVIEW, ToolStatus.OK

    def _appeal(self, req: AppealRequest) -> tuple[dict[str, Any], bool, ToolStatus]:
        draft = appeals.draft(req.claim_ref, req.carc_code, req.cpt_code, req.clinical_rationale)
        data = {
            "status": "DRAFT_NOT_SENT",
            "template": draft.template,
            "body": draft.body,
            "redactions_applied": draft.redactions_applied,
        }
        return data, True, ToolStatus.OK  # appeals always need a human

    # ---- plumbing -----------------------------------------------------------------

    def _write_audit(
        self, tool: str, scope: Scope, outcome: str, args: Mapping[str, Any], trace_id: str
    ) -> bool:
        try:
            self._audit.record(
                actor=self._principal.actor,
                role=self._principal.role,
                tool=tool,
                scope=scope.value,
                outcome=outcome,
                args=args,
                trace_id=trace_id,
            )
        except OSError:
            log.error("audit write failed for tool=%s", tool)
            return False
        return True

    def _execute(
        self,
        tool: str,
        scope: Scope,
        raw_args: Mapping[str, Any],
        model: type[_Req],
        handler: _Handler[_Req],
    ) -> ToolResult:
        trace = uuid.uuid4().hex

        def finish(result: ToolResult, outcome: str) -> ToolResult:
            # Fail closed: if the audit trail cannot be written, no data is returned.
            if not self._write_audit(tool, scope, outcome, raw_args, trace):
                return ToolResult(
                    status=ToolStatus.ERROR, trace_id=trace, error="audit unavailable"
                )
            return result

        if not authorize(self._principal.role, scope):
            return finish(
                ToolResult(
                    status=ToolStatus.DENIED, trace_id=trace, error=f"role lacks {scope.value}"
                ),
                "denied",
            )
        if not self._limiter.allow(self._principal.actor):
            return finish(
                ToolResult(status=ToolStatus.RATE_LIMITED, trace_id=trace, error="rate limited"),
                "rate_limited",
            )
        try:
            req = model.model_validate(dict(raw_args))
        except ValidationError as exc:
            # Names and types only. Never echo the offending value: it may be PHI.
            fields = ", ".join(f"{'.'.join(map(str, e['loc']))}:{e['type']}" for e in exc.errors())
            return finish(
                ToolResult(status=ToolStatus.INVALID, trace_id=trace, error=f"invalid: {fields}"),
                "invalid",
            )
        try:
            data, review, status = handler(req)
        except PayerUnavailableError:
            return finish(
                ToolResult(
                    status=ToolStatus.RETRYABLE, trace_id=trace, error="payer unavailable, retry"
                ),
                "retryable_error",
            )
        except Exception as exc:  # boundary: must not leak internals or PHI
            log.error("tool=%s failed type=%s", tool, type(exc).__name__)
            return finish(
                ToolResult(status=ToolStatus.ERROR, trace_id=trace, error="internal error"),
                "error",
            )
        return finish(
            ToolResult(status=status, trace_id=trace, data=data, requires_human_review=review),
            status.value,
        )
