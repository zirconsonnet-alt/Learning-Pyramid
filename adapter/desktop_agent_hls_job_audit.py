from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.models.desktop_agent_hls_job_audit import DesktopAgentHlsJobAudit
from backend.system.auth_store import AuthStore
from backend.system.desktop_media_hls import serialize_hls_profile


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def persist_runtime_hls_job_audit(
    auth_store: AuthStore,
    job: Any,
    *,
    observed_at: str | None = None,
) -> DesktopAgentHlsJobAudit:
    current = auth_store.get_desktop_agent_hls_job_audit(str(job.job_id))
    next_updated_at = str(observed_at or getattr(job, "updated_at", None) or _utc_now_text())
    raw_profile = getattr(job, "profile", {})
    serialized_profile = serialize_hls_profile(raw_profile if isinstance(raw_profile, dict) else {})
    next_started_at = None if not str(getattr(job, "started_at", "") or "").strip() else str(job.started_at)
    if next_started_at is None and str(getattr(job, "state", "")).strip().upper() != "OPENING":
        next_started_at = next_updated_at
    next_finished_at = None if not str(getattr(job, "finished_at", "") or "").strip() else str(job.finished_at)
    if str(getattr(job, "state", "")).strip().upper() in {"COMPLETED", "FAILED", "CANCELLED"} and next_finished_at is None:
        next_finished_at = next_updated_at
    item = DesktopAgentHlsJobAudit(
        job_id=str(job.job_id),
        cache_key=str(job.cache_key),
        project_id=str(job.project_id),
        instance_id=str(job.instance_id),
        agent_id=str(job.agent_id),
        relative_path=str(job.relative_path),
        profile=serialized_profile,
        state=str(job.state),
        artifact_count=int(getattr(job, "artifact_count", 0)),
        artifact_bytes=int(getattr(job, "artifact_bytes", 0)),
        created_at=str(getattr(job, "created_at", None) or next_updated_at),
        updated_at=next_updated_at,
        expires_at=str(getattr(job, "expires_at", None) or next_updated_at),
        started_at=next_started_at if next_started_at is not None else (None if current is None else current.started_at),
        finished_at=next_finished_at if next_finished_at is not None else (None if current is None else current.finished_at),
        last_artifact_at=(
            None
            if not str(getattr(job, "last_artifact_at", "") or "").strip()
            else str(job.last_artifact_at)
        )
        or (None if current is None else current.last_artifact_at),
        message=None if getattr(job, "message", None) is None else str(job.message),
    )
    return auth_store.upsert_desktop_agent_hls_job_audit(item)
