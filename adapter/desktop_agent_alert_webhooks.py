from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from backend.models.desktop_agent_diagnostic_event import DesktopAgentDiagnosticEvent
from backend.system.auth_store import AuthStore


_LOGGER = logging.getLogger(__name__)


def _coerce_utc_datetime(value: str | None) -> datetime:
    if not str(value or "").strip():
        return datetime.fromtimestamp(0, tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _env_positive_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return max(minimum, int(value))


def _env_positive_float(name: str, default: float, *, minimum: float = 0.1) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except Exception:
        return float(default)
    return max(minimum, float(value))


def _alert_webhook_url() -> str | None:
    value = (os.getenv("PLM_AGENT_ALERT_WEBHOOK_URL") or "").strip()
    return value or None


def _alert_webhook_targets_raw() -> str:
    return (os.getenv("PLM_AGENT_ALERT_WEBHOOK_TARGETS") or "").strip()


def _alert_webhook_window_hours() -> int:
    return _env_positive_int("PLM_AGENT_ALERT_WEBHOOK_WINDOW_HOURS", 1)


def _alert_webhook_cooldown_seconds() -> int:
    return _env_positive_int("PLM_AGENT_ALERT_WEBHOOK_COOLDOWN_SECONDS", 900, minimum=0)


def _alert_webhook_timeout_seconds() -> float:
    return _env_positive_float("PLM_AGENT_ALERT_WEBHOOK_TIMEOUT_SECONDS", 5.0)


def _alert_webhook_max_alerts() -> int:
    return _env_positive_int("PLM_AGENT_ALERT_WEBHOOK_MAX_ALERTS", 8)


def _alert_webhook_retry_backoff_seconds() -> int:
    return _env_positive_int("PLM_AGENT_ALERT_WEBHOOK_RETRY_BACKOFF_SECONDS", 60, minimum=1)


def _alert_webhook_retry_max_backoff_seconds() -> int:
    return _env_positive_int("PLM_AGENT_ALERT_WEBHOOK_RETRY_MAX_BACKOFF_SECONDS", 900, minimum=1)


def _latest_iso_text(values: list[str | None]) -> str | None:
    non_empty = [value for value in values if str(value or "").strip()]
    if not non_empty:
        return None
    return max(non_empty, key=lambda item: _coerce_utc_datetime(item).timestamp())


def _default_target_name(url: str, *, index: int) -> str:
    parsed = urlparse(str(url))
    host = str(parsed.netloc or parsed.path or "").strip()
    if host:
        return host
    return f"webhook-{index}"


def _is_builtin_log_target(url: str) -> bool:
    parsed = urlparse(str(url))
    if str(parsed.scheme).strip().lower() == "log":
        return True
    if str(parsed.scheme).strip().lower() != "builtin":
        return False
    target = f"{parsed.netloc}{parsed.path}".strip("/").lower()
    return target == "log"


@dataclass(frozen=True, slots=True)
class _AlertWebhookTarget:
    name: str
    url: str


@dataclass(slots=True)
class _AlertWebhookChannelState:
    name: str
    url: str
    last_sent_signature: str | None = None
    pending_signature: str | None = None
    last_sent_at: datetime | None = None
    next_retry_at: datetime | None = None
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    sent_count: int = 0
    suppressed_count: int = 0
    failed_count: int = 0
    last_alert_count: int = 0
    consecutive_failure_count: int = 0

    def snapshot(self) -> dict[str, Any]:
        retry_pending = bool(self.pending_signature and self.next_retry_at is not None)
        if retry_pending:
            status = "RETRYING"
        elif self.last_error:
            status = "FAILED"
        elif self.last_success_at:
            status = "HEALTHY"
        else:
            status = "IDLE"
        return {
            "name": str(self.name),
            "url": str(self.url),
            "status": status,
            "lastAttemptAt": self.last_attempt_at,
            "lastSuccessAt": self.last_success_at,
            "lastError": self.last_error,
            "sentCount": int(self.sent_count),
            "suppressedCount": int(self.suppressed_count),
            "failedCount": int(self.failed_count),
            "lastAlertCount": int(self.last_alert_count),
            "nextRetryAt": None if self.next_retry_at is None else self.next_retry_at.isoformat(),
            "retryPending": retry_pending,
            "consecutiveFailureCount": int(self.consecutive_failure_count),
        }


def _parse_alert_webhook_targets() -> tuple[_AlertWebhookTarget, ...]:
    raw = _alert_webhook_targets_raw()
    items: list[Any] = []
    if raw:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            items.extend(parsed)
        elif isinstance(parsed, dict):
            items.extend(parsed.values())
        else:
            for entry in raw.replace(";", "\n").splitlines():
                normalized = entry.strip().rstrip(",")
                if normalized:
                    items.append(normalized)
    if not items:
        fallback_url = _alert_webhook_url()
        if fallback_url:
            items.append({"name": "primary", "url": fallback_url})

    targets: list[_AlertWebhookTarget] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            raw_value = item.strip()
            if not raw_value:
                continue
            if "=" in raw_value and "://" not in raw_value.split("=", 1)[0]:
                name_part, url_part = raw_value.split("=", 1)
                name = str(name_part).strip() or _default_target_name(url_part, index=index)
                url = str(url_part).strip()
            else:
                url = raw_value
                name = _default_target_name(url, index=index)
        elif isinstance(item, dict):
            url = str(item.get("url") or item.get("href") or "").strip()
            if not url:
                continue
            name = str(item.get("name") or item.get("id") or _default_target_name(url, index=index)).strip()
        else:
            continue
        if not url:
            continue
        targets.append(_AlertWebhookTarget(name=name or _default_target_name(url, index=index), url=url))
    return tuple(targets)


def _build_recent_alerts(
    events: tuple[DesktopAgentDiagnosticEvent, ...],
    *,
    now: datetime,
    window_hours: int,
    max_alerts: int,
) -> list[dict[str, Any]]:
    window_cutoff = now - timedelta(hours=max(1, int(window_hours)))
    aggregated: dict[tuple[str, str, str, str, str | None], dict[str, Any]] = {}
    for item in events:
        severity = str(item.level).strip().upper()
        if severity not in {"ERROR", "WARNING"}:
            continue
        observed_at = _coerce_utc_datetime(item.created_at)
        if observed_at < window_cutoff:
            continue
        key = (
            severity,
            str(item.user_id),
            str(item.agent_id),
            str(item.event_type),
            None if item.project_id is None else str(item.project_id),
        )
        current = aggregated.setdefault(
            key,
            {
                "severity": "error" if severity == "ERROR" else "warning",
                "userId": str(item.user_id),
                "agentId": str(item.agent_id),
                "projectId": None if item.project_id is None else str(item.project_id),
                "category": str(item.category),
                "code": str(item.event_type),
                "title": f"{item.category}: {item.event_type}",
                "message": str(item.message),
                "observedAt": str(item.created_at),
                "count": 0,
            },
        )
        current["count"] = int(current.get("count", 0)) + 1
        if observed_at > _coerce_utc_datetime(str(current.get("observedAt"))):
            current["observedAt"] = str(item.created_at)
            current["message"] = str(item.message)
    ordered = sorted(
        aggregated.values(),
        key=lambda item: (
            1 if str(item.get("severity")) == "error" else 0,
            _coerce_utc_datetime(str(item.get("observedAt"))).timestamp(),
        ),
        reverse=True,
    )
    return ordered[: max(1, int(max_alerts))]


def _signature_for_alerts(alerts: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(alerts, sort_keys=True).encode("utf-8")).hexdigest()


class RelayAlertWebhookDispatcher:
    def __init__(self, request_post: Callable[..., Any] | None = None):
        self._request_post = request_post or requests.post
        self._lock = Lock()
        self._channels: dict[str, _AlertWebhookChannelState] = {}

    def _channel_key(self, target: _AlertWebhookTarget) -> str:
        return f"{target.name}|{target.url}"

    def _sync_channels_unlocked(self, targets: tuple[_AlertWebhookTarget, ...]) -> list[_AlertWebhookChannelState]:
        ordered: list[_AlertWebhookChannelState] = []
        next_channels: dict[str, _AlertWebhookChannelState] = {}
        for target in targets:
            key = self._channel_key(target)
            current = self._channels.get(key) or _AlertWebhookChannelState(name=target.name, url=target.url)
            current.name = target.name
            current.url = target.url
            next_channels[key] = current
            ordered.append(current)
        self._channels = next_channels
        return ordered

    def _snapshot_unlocked(self, channels: list[_AlertWebhookChannelState]) -> dict[str, Any]:
        channel_snapshots = [item.snapshot() for item in channels]
        error_channels = [item for item in channel_snapshots if str(item.get("lastError") or "").strip()]
        latest_error_channel = None
        if error_channels:
            latest_error_channel = max(
                error_channels,
                key=lambda item: _coerce_utc_datetime(str(item.get("lastAttemptAt") or item.get("nextRetryAt") or "")).timestamp(),
            )
        healthy_channel_count = sum(1 for item in channel_snapshots if str(item.get("status")) in {"IDLE", "HEALTHY"})
        retrying_channel_count = sum(1 for item in channel_snapshots if str(item.get("status")) == "RETRYING")
        return {
            "configured": bool(channel_snapshots),
            "windowHours": int(_alert_webhook_window_hours()),
            "cooldownSeconds": int(_alert_webhook_cooldown_seconds()),
            "retryBackoffSeconds": int(_alert_webhook_retry_backoff_seconds()),
            "retryMaxBackoffSeconds": int(_alert_webhook_retry_max_backoff_seconds()),
            "channelCount": len(channel_snapshots),
            "healthyChannelCount": healthy_channel_count,
            "retryingChannelCount": retrying_channel_count,
            "failingChannelCount": len(error_channels),
            "lastAttemptAt": _latest_iso_text([item.get("lastAttemptAt") for item in channel_snapshots]),
            "lastSuccessAt": _latest_iso_text([item.get("lastSuccessAt") for item in channel_snapshots]),
            "lastError": None if latest_error_channel is None else str(latest_error_channel.get("lastError")),
            "sentCount": sum(int(item.get("sentCount", 0)) for item in channel_snapshots),
            "suppressedCount": sum(int(item.get("suppressedCount", 0)) for item in channel_snapshots),
            "failedCount": sum(int(item.get("failedCount", 0)) for item in channel_snapshots),
            "lastAlertCount": max((int(item.get("lastAlertCount", 0)) for item in channel_snapshots), default=0),
            "channels": channel_snapshots,
        }

    def _dispatch_channel(self, channel: _AlertWebhookChannelState, body: dict[str, Any], *, timeout_seconds: float) -> None:
        if _is_builtin_log_target(channel.url):
            _LOGGER.warning(
                "desktop_agent_relay_alert channel=%s payload=%s",
                channel.name,
                json.dumps(body, ensure_ascii=False, sort_keys=True),
            )
            return
        response = self._request_post(
            channel.url,
            json=body,
            timeout=timeout_seconds,
        )
        response.raise_for_status()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            channels = self._sync_channels_unlocked(_parse_alert_webhook_targets())
            return self._snapshot_unlocked(channels)

    def dispatch(self, auth_store: AuthStore, *, now: datetime | None = None) -> dict[str, Any]:
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        else:
            observed_at = observed_at.astimezone(timezone.utc)
        observed_at = observed_at.replace(microsecond=0)
        targets = _parse_alert_webhook_targets()
        window_hours = _alert_webhook_window_hours()
        events = auth_store.list_all_desktop_agent_diagnostic_events(
            since=(observed_at - timedelta(hours=window_hours)).isoformat()
        )
        alerts = _build_recent_alerts(
            events,
            now=observed_at,
            window_hours=window_hours,
            max_alerts=_alert_webhook_max_alerts(),
        )
        signature = None if not alerts else _signature_for_alerts(alerts)
        payload = None
        if alerts:
            payload = {
                "source": "desktop-agent-relay",
                "sentAt": observed_at.isoformat(),
                "windowHours": window_hours,
                "alertCount": len(alerts),
                "alerts": alerts,
            }

        actions: list[tuple[_AlertWebhookChannelState, dict[str, Any]]] = []
        with self._lock:
            channels = self._sync_channels_unlocked(targets)
            for channel in channels:
                channel.last_alert_count = len(alerts)
                if not alerts:
                    channel.pending_signature = None
                    channel.next_retry_at = None
                    channel.consecutive_failure_count = 0
                    continue
                assert signature is not None
                cooldown_seconds = _alert_webhook_cooldown_seconds()
                if (
                    channel.last_sent_signature == signature
                    and channel.last_sent_at is not None
                    and cooldown_seconds > 0
                    and (observed_at - channel.last_sent_at).total_seconds() < cooldown_seconds
                ):
                    channel.suppressed_count += 1
                    continue
                if (
                    channel.pending_signature == signature
                    and channel.next_retry_at is not None
                    and observed_at < channel.next_retry_at
                ):
                    continue
                if channel.pending_signature != signature:
                    channel.pending_signature = None
                    channel.next_retry_at = None
                    channel.consecutive_failure_count = 0
                channel.last_attempt_at = observed_at.isoformat()
                actions.append((channel, dict(payload)))

        timeout_seconds = _alert_webhook_timeout_seconds()
        for channel, body in actions:
            try:
                self._dispatch_channel(channel, body, timeout_seconds=timeout_seconds)
            except Exception as exc:
                with self._lock:
                    if channel.pending_signature == signature:
                        channel.consecutive_failure_count += 1
                    else:
                        channel.consecutive_failure_count = 1
                    retry_seconds = min(
                        _alert_webhook_retry_backoff_seconds() * (2 ** max(0, channel.consecutive_failure_count - 1)),
                        _alert_webhook_retry_max_backoff_seconds(),
                    )
                    channel.pending_signature = signature
                    channel.next_retry_at = observed_at + timedelta(seconds=retry_seconds)
                    channel.last_error = str(exc)
                    channel.failed_count += 1
                continue
            with self._lock:
                channel.last_sent_signature = signature
                channel.pending_signature = None
                channel.next_retry_at = None
                channel.last_sent_at = observed_at
                channel.last_success_at = observed_at.isoformat()
                channel.last_error = None
                channel.consecutive_failure_count = 0
                channel.sent_count += 1

        with self._lock:
            channels = self._sync_channels_unlocked(targets)
            return self._snapshot_unlocked(channels)


_relay_alert_webhook_dispatcher = RelayAlertWebhookDispatcher()


def reset_desktop_agent_alert_webhook_dispatcher(request_post: Callable[..., Any] | None = None) -> None:
    global _relay_alert_webhook_dispatcher
    _relay_alert_webhook_dispatcher = RelayAlertWebhookDispatcher(request_post=request_post)


def snapshot_desktop_agent_alert_webhook() -> dict[str, Any]:
    return _relay_alert_webhook_dispatcher.snapshot()


def dispatch_desktop_agent_alert_webhook(auth_store: AuthStore, *, now: datetime | None = None) -> dict[str, Any]:
    return _relay_alert_webhook_dispatcher.dispatch(auth_store, now=now)
