from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from backend.models.desktop_agent_diagnostic_event import (
    DESKTOP_AGENT_DIAGNOSTIC_LEVELS,
    DesktopAgentDiagnosticEvent,
)
from backend.system.auth_store import AuthStore


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def record_desktop_agent_diagnostic_event(
    auth_store: AuthStore,
    *,
    agent_id: str,
    user_id: str,
    level: str,
    category: str,
    event_type: str,
    message: str,
    details: dict[str, object] | None = None,
    project_id: str | None = None,
    instance_id: str | None = None,
    relative_path: str | None = None,
    created_at: str | None = None,
) -> DesktopAgentDiagnosticEvent:
    normalized_level = str(level or "").strip().upper()
    if normalized_level not in DESKTOP_AGENT_DIAGNOSTIC_LEVELS:
        raise HTTPException(status_code=400, detail="Desktop agent diagnostic level is invalid")
    payload = DesktopAgentDiagnosticEvent(
        event_id=f"diag_{uuid.uuid4().hex}",
        agent_id=str(agent_id),
        user_id=str(user_id),
        project_id=None if project_id is None else str(project_id),
        instance_id=None if instance_id is None else str(instance_id),
        relative_path=None if relative_path is None else str(relative_path),
        level=normalized_level,
        category=str(category).strip(),
        event_type=str(event_type).strip(),
        message=str(message).strip(),
        details=json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        created_at=str(created_at or utc_now_text()),
    )
    return auth_store.create_desktop_agent_diagnostic_event(payload)
