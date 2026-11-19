from __future__ import annotations

import json
from pathlib import Path

from opskit.audit import AuditLog, verify_chain, verify_main


def _record(log: AuditLog, n: int) -> None:
    for i in range(n):
        log.record(
            actor="a",
            role="r",
            tool="t",
            scope="s",
            outcome="ok",
            args={"i": i},
            trace_id=f"trace{i}",
        )


def test_chain_verifies_and_resumes_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _record(AuditLog(path, hmac_key=b"k"), 3)
    _record(AuditLog(path, hmac_key=b"k"), 2)  # new instance continues the chain
    result = verify_chain(path)
    assert result.ok
    assert result.events == 5


def test_tampering_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _record(AuditLog(path, hmac_key=b"k"), 4)
    lines = path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[1])
    event["outcome"] = "denied"  # rewrite history
    lines[1] = json.dumps(event, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = verify_chain(path)
    assert not result.ok
    assert result.broken_at == 2


def test_deleted_event_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _record(AuditLog(path, hmac_key=b"k"), 4)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not verify_chain(path).ok


def test_log_never_contains_raw_arguments(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    log = AuditLog(path, hmac_key=b"k")
    log.record(
        actor="a",
        role="r",
        tool="t",
        scope="s",
        outcome="ok",
        args={"patient_ref": "pt_secretvalue1"},
        trace_id="x",
    )
    assert "pt_secretvalue1" not in path.read_text(encoding="utf-8")


def test_missing_file_is_valid_and_cli_exit_codes(tmp_path: Path) -> None:
    assert verify_chain(tmp_path / "none.jsonl").ok
    path = tmp_path / "a.jsonl"
    _record(AuditLog(path, hmac_key=b"k"), 1)
    assert verify_main([str(path)]) == 0
    path.write_text("not json\n", encoding="utf-8")
    assert verify_main([str(path)]) == 1
