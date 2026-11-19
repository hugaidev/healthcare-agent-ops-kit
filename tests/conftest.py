from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from opskit.audit import AuditLog
from opskit.payer_sim import SyntheticPayer
from opskit.policy import Principal, RateLimiter
from opskit.service import BenefitsService

ServiceFactory = Callable[..., BenefitsService]


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "audit.jsonl", hmac_key=b"test-key")


@pytest.fixture
def make_service(audit: AuditLog) -> ServiceFactory:
    def _make(
        role: str = "billing_specialist", limiter: RateLimiter | None = None
    ) -> BenefitsService:
        return BenefitsService(SyntheticPayer(), audit, Principal("tester", role), limiter)

    return _make
