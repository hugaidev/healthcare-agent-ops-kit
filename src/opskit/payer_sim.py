"""Deterministic synthetic payer. All data here is fictional; no real people or plans.

Stands in for an X12 270/271 (eligibility) and 278 (prior auth) clearinghouse connection.
Swap it for a real adapter by implementing the ``Payer`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from opskit.models import PaDecision


class PayerUnavailableError(RuntimeError):
    """Transient upstream failure; callers may retry with backoff."""


@dataclass(frozen=True)
class MemberRecord:
    payer_id: str
    plan_name: str
    plan_type: str
    coverage_start: date
    coverage_end: date
    deductible_remaining_cents: int
    copay_cents: int
    coinsurance_pct: int
    visit_limit: int | None
    visits_used: int


@dataclass(frozen=True)
class PaRule:
    rule_id: str
    units_threshold: int  # auth required when units > threshold (0 = always required)


@dataclass(frozen=True)
class PaOutcome:
    decision: PaDecision
    rule_id: str
    reason: str
    policy_version: str


class Payer(Protocol):
    def lookup_member(self, patient_ref: str) -> MemberRecord | None: ...

    def prior_auth_rule(self, payer_id: str, cpt_code: str) -> PaRule | None: ...


_POLICY_VERSION = "2026-01-synthetic"

_MEMBERS: dict[str, MemberRecord] = {
    "pt_demo000001": MemberRecord(
        "acme_health",
        "Acme PPO Gold (synthetic)",
        "PPO",
        date(2026, 1, 1),
        date(2026, 12, 31),
        25000,
        3000,
        20,
        None,
        0,
    ),
    "pt_demo000002": MemberRecord(
        "acme_health",
        "Acme PPO Gold (synthetic)",
        "PPO",
        date(2025, 1, 1),
        date(2026, 3, 31),
        0,
        3000,
        20,
        None,
        12,
    ),
    "pt_demo000003": MemberRecord(
        "northwind_plan",
        "Northwind HMO Select (synthetic)",
        "HMO",
        date(2026, 1, 1),
        date(2026, 12, 31),
        0,
        2500,
        0,
        60,
        58,
    ),
}

# CPT codes are ABA codes (97151 assessment, 97153 direct tx, 97155 protocol modification,
# 97156 family guidance). Thresholds are illustrative, not any real payer's policy.
_PA_RULES: dict[tuple[str, str], PaRule] = {
    ("acme_health", "97151"): PaRule("ACME-ABA-001", 0),
    ("acme_health", "97153"): PaRule("ACME-ABA-002", 0),
    ("acme_health", "97155"): PaRule("ACME-ABA-003", 8),
    ("acme_health", "97156"): PaRule("ACME-ABA-004", 10_000),
    ("northwind_plan", "97151"): PaRule("NW-ABA-001", 0),
    ("northwind_plan", "97153"): PaRule("NW-ABA-002", 40),
}


class SyntheticPayer:
    def lookup_member(self, patient_ref: str) -> MemberRecord | None:
        if patient_ref == "pt_timeout0001":
            raise PayerUnavailableError("simulated upstream timeout")
        return _MEMBERS.get(patient_ref)

    def prior_auth_rule(self, payer_id: str, cpt_code: str) -> PaRule | None:
        return _PA_RULES.get((payer_id, cpt_code))


def evaluate_prior_auth(rule: PaRule | None, units: int) -> PaOutcome:
    if rule is None:
        return PaOutcome(
            PaDecision.NEEDS_HUMAN_REVIEW,
            "NO_RULE",
            "No policy rule on file for this payer and code; do not assume.",
            _POLICY_VERSION,
        )
    required = units > rule.units_threshold
    return PaOutcome(
        PaDecision.REQUIRED if required else PaDecision.NOT_REQUIRED,
        rule.rule_id,
        f"Requested units {units} vs threshold {rule.units_threshold}.",
        _POLICY_VERSION,
    )
