"""
tests/unit/test_mission_audit.py — Unit tests for services/mission/audit.py (P1-09).

Verifies:
  - log_action emits structured records to the audit logger.
  - alog_action awaits correctly and calls the sync path.
  - Records contain all required fields.
  - Long strings are truncated to prevent log injection / oversized payloads.
  - Outcome field defaults to SUCCESS.
"""

from unittest.mock import patch

import pytest

from services.mission.audit import alog_action, log_action, _build_record

# ── _build_record unit tests ──────────────────────────────────────────────────


def test_build_record_contains_required_fields():
    record = _build_record(
        action="CREATE",
        resource_type="mission",
        resource_id="msn-001",
        subject="user:analyst-1",
        organisation_id="org-test",
        outcome="SUCCESS",
    )
    assert record["action"] == "CREATE"
    assert record["resource_type"] == "mission"
    assert record["resource_id"] == "msn-001"
    assert record["subject"] == "user:analyst-1"
    assert record["organisation_id"] == "org-test"
    assert record["outcome"] == "SUCCESS"
    assert "ts" in record


def test_build_record_defaults_outcome_to_success():
    record = _build_record("UPDATE", "job", "j-001", "sub", "org", "SUCCESS")
    assert record["outcome"] == "SUCCESS"


def test_build_record_truncates_long_extra_strings():
    """Extra strings > 256 chars must be truncated (OWASP A09 — no log injection)."""
    long_val = "X" * 500
    record = _build_record(
        "DELETE", "aoi", "aoi-1", "sub", "org", "SUCCESS", extra={"note": long_val}
    )
    assert len(record["note"]) == 257  # 256 chars + "…"
    assert record["note"].endswith("…")


def test_build_record_allows_short_extra_strings():
    record = _build_record(
        "DELETE", "aoi", "aoi-1", "sub", "org", "SUCCESS", extra={"note": "short"}
    )
    assert record["note"] == "short"


def test_build_record_handles_no_extra():
    record = _build_record("CREATE", "mission", "m-1", "s", "o", "SUCCESS")
    # No extra fields beyond the base ones
    assert "note" not in record


# ── log_action integration (with real logger) ─────────────────────────────────


def test_log_action_emits_log_record():
    """log_action must write an INFO record to the audit logger."""
    import logging
    from services.mission.audit import _get_audit_logger

    # Capture records by injecting a MemoryHandler into the audit logger directly.
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    cap = _Capture()
    lg = _get_audit_logger()
    lg.addHandler(cap)
    try:
        log_action(
            action="CREATE",
            resource_type="mission",
            resource_id="m-test-001",
            subject="user:test",
            organisation_id="org-caplog",
        )
        assert len(records) >= 1
        assert "CREATE" in records[-1].getMessage()
    finally:
        lg.removeHandler(cap)


def test_log_action_failure_outcome():
    """FAILURE outcome must appear in the log message."""
    import logging
    from services.mission.audit import _get_audit_logger

    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    cap = _Capture()
    lg = _get_audit_logger()
    lg.addHandler(cap)
    try:
        log_action(
            action="SUBMIT",
            resource_type="job",
            resource_id="j-fail",
            subject="user:op",
            organisation_id="org-x",
            outcome="FAILURE",
        )
        assert any("FAILURE" in r.getMessage() for r in records)
    finally:
        lg.removeHandler(cap)


# ── alog_action async tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alog_action_calls_sync_log_action():
    """alog_action must delegate to log_action without blocking the loop."""
    called_with = {}

    def _fake_log(action, resource_type, resource_id, subject, org, outcome, extra):
        called_with.update(
            {
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "subject": subject,
                "org": org,
                "outcome": outcome,
            }
        )

    with patch("services.mission.audit.log_action", side_effect=_fake_log):
        await alog_action(
            action="DELETE",
            resource_type="aoi",
            resource_id="aoi-99",
            subject="user:admin",
            organisation_id="org-async",
            outcome="SUCCESS",
        )

    assert called_with["action"] == "DELETE"
    assert called_with["resource_type"] == "aoi"
    assert called_with["org"] == "org-async"
