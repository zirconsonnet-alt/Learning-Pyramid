from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from backend.models.desktop_agent import DesktopAgent
from backend.models.enums import DesktopAgentStatus


def _coerce_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _env_positive_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except Exception:
        return float(default)
    return float(default) if value <= 0 else float(value)


def desktop_agent_offline_grace_seconds() -> float:
    return _env_positive_float("PLM_DESKTOP_AGENT_OFFLINE_GRACE_SECONDS", 90.0)


def desktop_agent_is_within_offline_grace(
    agent: DesktopAgent,
    *,
    now: datetime | None = None,
    grace_seconds: float | None = None,
) -> bool:
    if agent.status != DesktopAgentStatus.ONLINE:
        return False
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    deadline = _coerce_utc_datetime(agent.last_seen_at) + timedelta(
        seconds=desktop_agent_offline_grace_seconds() if grace_seconds is None else max(0.0, float(grace_seconds))
    )
    return deadline > effective_now


def effective_desktop_agent_status(
    agent: DesktopAgent,
    *,
    connected: bool = False,
    now: datetime | None = None,
    grace_seconds: float | None = None,
) -> DesktopAgentStatus:
    if connected:
        return DesktopAgentStatus.ONLINE
    if desktop_agent_is_within_offline_grace(agent, now=now, grace_seconds=grace_seconds):
        return DesktopAgentStatus.ONLINE
    return DesktopAgentStatus.OFFLINE


def desktop_agent_connection_state(
    agent: DesktopAgent,
    *,
    connected: bool = False,
    now: datetime | None = None,
    grace_seconds: float | None = None,
) -> str:
    if connected:
        return "CONNECTED"
    if desktop_agent_is_within_offline_grace(agent, now=now, grace_seconds=grace_seconds):
        return "RECONNECTING"
    return "OFFLINE"


def desktop_agent_offline_cutoff(
    *,
    now: datetime | None = None,
    grace_seconds: float | None = None,
) -> str:
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    return (
        effective_now
        - timedelta(seconds=desktop_agent_offline_grace_seconds() if grace_seconds is None else max(0.0, float(grace_seconds)))
    ).isoformat()
