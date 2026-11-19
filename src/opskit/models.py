"""Typed contracts for tool inputs and outputs.

Design rules (see docs/adr/0001-opaque-references.md):

* Tools accept **opaque references** (``pt_...``, ``clm_...``), never names, DOBs or member IDs.
  The reference-to-identity mapping lives behind the service boundary, so the model never
  holds PHI it does not need (HIPAA minimum necessary, 45 CFR 164.502(b)).
* Models forbid unknown fields: an agent cannot smuggle extra identifiers into a call.
* Validation errors are reported by field name and error type only, never by echoing input.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PatientRef = Annotated[str, StringConstraints(pattern=r"^pt_[a-z0-9]{6,32}$")]
ClaimRef = Annotated[str, StringConstraints(pattern=r"^clm_[a-z0-9]{6,32}$")]
PayerId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{1,31}$")]
CptCode = Annotated[str, StringConstraints(pattern=r"^(\d{5}|[A-Z]\d{4})$")]
# Claim Adjustment Reason Code with group prefix, e.g. CO-197 (X12 835 CAS segment)
CarcCode = Annotated[str, StringConstraints(pattern=r"^(CO|PR|OA|PI|CR)-\d{1,3}$")]


class ServiceLine(StrEnum):
    ABA_THERAPY = "ABA_THERAPY"
    SPEECH = "SPEECH"
    OCCUPATIONAL = "OCCUPATIONAL"
    PHYSICAL = "PHYSICAL"
    PSYCHIATRY = "PSYCHIATRY"


class PaDecision(StrEnum):
    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class ToolStatus(StrEnum):
    OK = "ok"
    DENIED = "denied"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    RETRYABLE = "retryable_error"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EligibilityRequest(_Strict):
    patient_ref: PatientRef
    payer_id: PayerId
    service_line: ServiceLine
    date_of_service: date


class PriorAuthRequest(_Strict):
    patient_ref: PatientRef
    payer_id: PayerId
    cpt_code: CptCode
    units: Annotated[int, Field(ge=1, le=1000)]


class AppealRequest(_Strict):
    claim_ref: ClaimRef
    carc_code: CarcCode
    cpt_code: CptCode
    clinical_rationale: Annotated[str, Field(max_length=2000)] = ""


class ToolResult(BaseModel):
    """Uniform envelope. ``requires_human_review`` is the human-in-the-loop signal."""

    model_config = ConfigDict(frozen=True)

    status: ToolStatus
    trace_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    requires_human_review: bool = False
