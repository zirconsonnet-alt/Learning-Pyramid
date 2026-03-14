from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from adapter.desktop_agent_alert_webhooks import (
    dispatch_desktop_agent_alert_webhook,
    snapshot_desktop_agent_alert_webhook,
)
from adapter.desktop_agent_hls_job_audit import persist_runtime_hls_job_audit
from adapter.desktop_agent_metric_samples import (
    current_desktop_agent_metric_sampling_config,
    persist_desktop_agent_metric_samples,
)
from backend.models.errors import NotFound
from backend.system.auth_store import AuthStore
from backend.system.desktop_agent_presence import desktop_agent_offline_cutoff
from backend.system.desktop_agent_runtime import DesktopAgentRuntime
from backend.system.desktop_media_hls import prune_hls_cache


def _diagnostic_event_retention_days() -> int:
    raw = (os.getenv("PLM_AGENT_DIAGNOSTIC_RETENTION_DAYS") or "30").strip()
    try:
        value = int(raw)
    except Exception:
        return 30
    return max(1, value)


def _finalize_expired_stream_sessions(auth_store: AuthStore, stream_ids: tuple[str, ...]) -> int:
    finalized_count = 0
    for stream_id in stream_ids:
        try:
            auth_store.finalize_media_stream_session(
                stream_id,
                status="FAILED",
                failure_reason="desktop agent stream session expired",
            )
        except NotFound:
            continue
        finalized_count += 1
    return finalized_count


def _sync_hls_job_audits(auth_store: AuthStore, runtime: DesktopAgentRuntime, job_ids: tuple[str, ...]) -> int:
    synced_count = 0
    for job_id in job_ids:
        try:
            job = runtime.get_hls_job(job_id)
        except Exception:
            continue
        persist_runtime_hls_job_audit(auth_store, job)
        synced_count += 1
    return synced_count


def collect_desktop_agent_relay_status(
    *,
    runtime: DesktopAgentRuntime,
    auth_store: AuthStore | None = None,
    now: datetime | None = None,
    run_maintenance: bool = True,
    dispatch_alert_webhooks: bool = False,
    include_runtime_details: bool = False,
    max_recent_hls_jobs: int = 20,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "expiredStreamIds": (),
        "expiredProbeIds": (),
        "expiredHlsJobIds": (),
        "alertWebhook": snapshot_desktop_agent_alert_webhook(),
    }
    if run_maintenance:
        payload.update(runtime.reap_expired(now=now))

    if auth_store is not None:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        else:
            observed_at = observed_at.astimezone(timezone.utc)
        observed_at = observed_at.replace(microsecond=0)
        expired_stream_ids = tuple(str(item) for item in payload.get("expiredStreamIds", ()))
        payload["persistedExpiredStreamCount"] = (
            _finalize_expired_stream_sessions(auth_store, expired_stream_ids) if run_maintenance else 0
        )
        expired_hls_job_ids = tuple(str(item) for item in payload.get("expiredHlsJobIds", ()))
        payload["persistedExpiredHlsJobCount"] = (
            _sync_hls_job_audits(auth_store, runtime, expired_hls_job_ids) if run_maintenance else 0
        )
        payload["staleAgentOfflineCount"] = (
            auth_store.mark_stale_desktop_agents_offline(
                offline_before=desktop_agent_offline_cutoff(now=observed_at)
            )
            if run_maintenance
            else 0
        )
        pruned_hls_entries = prune_hls_cache(auth_store, now=now) if run_maintenance else ()
        payload["prunedDiagnosticEventCount"] = (
            auth_store.delete_desktop_agent_diagnostic_events_before(
                (observed_at - timedelta(days=_diagnostic_event_retention_days())).isoformat()
            )
            if run_maintenance
            else 0
        )
        if run_maintenance:
            payload.update(persist_desktop_agent_metric_samples(auth_store, now=now))
        else:
            sampling_config = current_desktop_agent_metric_sampling_config()
            payload.update(
                {
                    "metricSampleBucketSeconds": int(sampling_config.bucket_seconds),
                    "metricSampleRetentionDays": int(sampling_config.retention_days),
                    "metricSampleCapturedAt": None,
                    "metricSampleBucketStart": None,
                    "sampledMetricProjectCount": 0,
                    "prunedMetricSampleCount": 0,
                }
            )
        hls_cache_entries = auth_store.list_all_hls_cache_entries()
        hls_job_audits = auth_store.list_all_desktop_agent_hls_job_audits()
        metric_samples = auth_store.list_all_desktop_agent_metric_samples()
        diagnostic_events = auth_store.list_all_desktop_agent_diagnostic_events()
        payload["hlsCacheEntryCount"] = len(hls_cache_entries)
        payload["hlsCacheBytes"] = sum(int(item.size_bytes) for item in hls_cache_entries)
        payload["hlsCachePrunedCount"] = len(pruned_hls_entries)
        payload["persistedHlsJobAuditCount"] = len(hls_job_audits)
        payload["persistedMetricSampleCount"] = len(metric_samples)
        payload["persistedDiagnosticEventCount"] = len(diagnostic_events)
        if run_maintenance and dispatch_alert_webhooks:
            payload["alertWebhook"] = dispatch_desktop_agent_alert_webhook(auth_store, now=observed_at)

    payload.update(
        runtime.snapshot_state(
            include_details=include_runtime_details,
            max_recent_hls_jobs=max_recent_hls_jobs,
        )
    )
    return payload
