"""Tamper-evident audit log.

Each event embeds the SHA-256 of the previous event, forming a hash chain: editing or
deleting any line breaks verification from that point on (HIPAA 164.312(b) audit controls,
164.312(c)(1) integrity). Events never contain request payloads, only an HMAC digest of the
arguments, so the log itself is not a PHI store and can be shipped to a SIEM.

For production, also write to an append-only sink (e.g. S3 Object Lock / CloudWatch with
retention of at least six years per 164.316(b)(2)) and anchor the chain head externally.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _canonical(obj: Mapping[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    events: int
    broken_at: int | None = None


class AuditLog:
    def __init__(
        self,
        path: Path,
        hmac_key: bytes | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._path = path
        self._clock = clock
        # Ephemeral key if none supplied: fine for dev, set AUDIT_HMAC_KEY from a secrets
        # manager in real deployments so digests are comparable across restarts.
        self._key = hmac_key or secrets.token_bytes(32)
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._seq, self._prev = self._load_tail()

    @property
    def path(self) -> Path:
        return self._path

    def _load_tail(self) -> tuple[int, str]:
        if not self._path.exists():
            return 0, GENESIS
        last: dict[str, Any] | None = None
        with self._path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = json.loads(line)
        if last is None:
            return 0, GENESIS
        return int(last["seq"]), str(last["hash"])

    def args_digest(self, args: Mapping[str, Any]) -> str:
        return hmac.new(self._key, _canonical(args).encode(), hashlib.sha256).hexdigest()

    def record(
        self,
        *,
        actor: str,
        role: str,
        tool: str,
        scope: str,
        outcome: str,
        args: Mapping[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            event: dict[str, Any] = {
                "seq": self._seq + 1,
                "ts": self._clock().isoformat(),
                "actor": actor,
                "role": role,
                "tool": tool,
                "scope": scope,
                "outcome": outcome,
                "args_hmac": self.args_digest(args),
                "trace_id": trace_id,
                "prev_hash": self._prev,
            }
            event["hash"] = hashlib.sha256(_canonical(event).encode()).hexdigest()
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._seq, self._prev = event["seq"], event["hash"]
            return event


def verify_chain(path: Path) -> VerifyResult:
    prev = GENESIS
    count = 0
    if not path.exists():
        return VerifyResult(ok=True, events=0)
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                claimed = event.pop("hash")
                expected = hashlib.sha256(_canonical(event).encode()).hexdigest()
                ok = (
                    event["prev_hash"] == prev and claimed == expected and event["seq"] == count + 1
                )
            except (ValueError, KeyError):
                ok = False
            if not ok:
                return VerifyResult(ok=False, events=count, broken_at=count + 1)
            prev = claimed
            count += 1
    return VerifyResult(ok=True, events=count)


def verify_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the audit log hash chain.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    result = verify_chain(args.path)
    print(json.dumps({"ok": result.ok, "events": result.events, "broken_at": result.broken_at}))
    return 0 if result.ok else 1
