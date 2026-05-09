import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class DataSafetyAuditEvent:
    event_id: str
    occurred_at: str
    actor: str
    operation_type: str
    operation_id: str
    inputs_summary: dict[str, object]
    result: str
    protected_classes: tuple[str, ...]
    override_id: str | None = None


def new_data_safety_audit_event(
    *,
    event_id: str,
    actor: str,
    operation_type: str,
    operation_id: str,
    result: str,
    protected_classes: Sequence[str],
    inputs_summary: dict[str, object] | None = None,
    override_id: str | None = None,
) -> DataSafetyAuditEvent:
    return DataSafetyAuditEvent(
        event_id=event_id,
        occurred_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        actor=actor,
        operation_type=operation_type,
        operation_id=operation_id,
        inputs_summary=dict(inputs_summary or {}),
        result=result,
        protected_classes=tuple(str(item) for item in protected_classes),
        override_id=override_id,
    )


def append_data_safety_audit_event(path: Path, event: DataSafetyAuditEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")


def validate_emergency_override(payload: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    actor = str(payload.get("actor") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    expires_at = str(payload.get("expiresAt") or "").strip()
    risks = payload.get("acknowledgedRisks")
    if not actor:
        errors.append("actor")
    if not reason:
        errors.append("reason")
    if not expires_at:
        errors.append("expiresAt")
    if not isinstance(risks, list) or not risks:
        errors.append("acknowledgedRisks")
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_dt <= datetime.now(timezone.utc):
                errors.append("expired")
        except ValueError:
            errors.append("expiresAt")
    return {"valid": not errors, "errors": errors}
