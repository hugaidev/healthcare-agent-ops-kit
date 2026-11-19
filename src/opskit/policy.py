"""Least-privilege authorization and abuse limits for agent tool calls.

Fail-closed: no role, unknown role, or missing scope means the call is denied.
Maps to HIPAA Security Rule access control (45 CFR 164.312(a)(1)) and the
minimum-necessary standard.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class Scope(StrEnum):
    ELIGIBILITY_READ = "eligibility:read"
    PRIOR_AUTH_READ = "prior_auth:read"
    APPEAL_DRAFT = "appeal:draft"
    AUDIT_READ = "audit:read"


ROLE_SCOPES: Mapping[str, frozenset[Scope]] = {
    "benefits_specialist": frozenset({Scope.ELIGIBILITY_READ, Scope.PRIOR_AUTH_READ}),
    "billing_specialist": frozenset(
        {Scope.ELIGIBILITY_READ, Scope.PRIOR_AUTH_READ, Scope.APPEAL_DRAFT}
    ),
    "compliance_auditor": frozenset({Scope.AUDIT_READ}),
}


class ConfigError(RuntimeError):
    """Raised when the server is started without a valid identity."""


@dataclass(frozen=True)
class Principal:
    actor: str
    role: str


def principal_from_env(env: Mapping[str, str]) -> Principal:
    actor = env.get("OPS_ACTOR", "").strip()
    role = env.get("OPS_ROLE", "").strip()
    if not actor or not role:
        raise ConfigError("OPS_ACTOR and OPS_ROLE must be set (fail-closed: no anonymous access)")
    if role not in ROLE_SCOPES:
        raise ConfigError(f"unknown role {role!r}; allowed: {sorted(ROLE_SCOPES)}")
    return Principal(actor=actor, role=role)


def authorize(role: str, scope: Scope) -> bool:
    return scope in ROLE_SCOPES.get(role, frozenset())


class RateLimiter:
    """Sliding-window limiter. Bounds runaway agent loops and bulk enumeration of members."""

    def __init__(
        self,
        max_calls: int = 60,
        window_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_calls
        self._window = window_s
        self._clock = clock
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        q = self._calls[key]
        while q and now - q[0] >= self._window:
            q.popleft()
        if len(q) >= self._max:
            return False
        q.append(now)
        return True
