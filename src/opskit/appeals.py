"""Appeal draft templates keyed by CARC code.

Drafts are *never sent*. They are a starting point for a billing specialist, always flagged
for human review. Provider free text is redacted and quoted as unverified so that it cannot
act as an instruction to downstream systems or readers.
"""

from __future__ import annotations

from dataclasses import dataclass

from opskit.phi import redact

_TEMPLATES: dict[str, tuple[str, str]] = {
    "197": (
        "carc_197",
        "Precertification/authorization absent. Request reconsideration: authorization "
        "reference should be attached by the billing specialist before submission.",
    ),
    "50": (
        "carc_50",
        "Denied as not medically necessary. Request reconsideration citing the treatment "
        "plan and supporting clinical documentation, to be attached by the clinician.",
    ),
    "16": (
        "carc_16",
        "Claim lacks information needed for adjudication. Resubmit with the missing data "
        "elements identified in the remittance remark codes.",
    ),
    "29": (
        "carc_29",
        "Time limit for filing has expired. Include proof of timely filing if available.",
    ),
}


@dataclass(frozen=True)
class AppealDraft:
    template: str
    body: str
    redactions_applied: int


def draft(claim_ref: str, carc_code: str, cpt_code: str, rationale: str) -> AppealDraft:
    number = carc_code.split("-", 1)[1]
    template, text = _TEMPLATES.get(
        number,
        (
            "generic",
            "Reason code has no dedicated template. A specialist must write the appeal.",
        ),
    )
    clean = redact(rationale)
    lines = [
        "DRAFT - NOT SENT - REQUIRES HUMAN REVIEW",
        f"Claim reference: {claim_ref}",
        f"Denial code: {carc_code}  Service code: {cpt_code}",
        "",
        text,
    ]
    if clean.text.strip():
        lines += ["", "Provider statement (unverified, quoted):", f'"{clean.text.strip()}"']
    return AppealDraft(template=template, body="\n".join(lines), redactions_applied=clean.count)
