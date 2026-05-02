from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.system.data_safety_audit import validate_emergency_override


def test_validate_emergency_override_requires_reason_and_expiry() -> None:
    result = validate_emergency_override({"actor": "operator"})

    assert result["valid"] is False
    assert "reason" in result["errors"]
    assert "expiresAt" in result["errors"]


def test_validate_emergency_override_rejects_expired_override() -> None:
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    result = validate_emergency_override({"actor": "operator", "reason": "incident", "expiresAt": expired, "acknowledgedRisks": ["risk"]})

    assert result["valid"] is False
    assert "expired" in result["errors"]


def test_validate_emergency_override_accepts_time_limited_override() -> None:
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    result = validate_emergency_override({"actor": "operator", "reason": "incident", "expiresAt": expires, "acknowledgedRisks": ["risk"]})

    assert result == {"valid": True, "errors": []}
