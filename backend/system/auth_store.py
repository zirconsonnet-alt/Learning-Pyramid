from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PUBLIC_UID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
USER_STATUSES = {"active", "suspended", "deleted"}
GLOBAL_ROLES = {"super_admin", "admin"}
FRIEND_REQUEST_STATUSES = {"pending", "accepted", "rejected", "cancelled"}
USER_SERVICE_KINDS = {"llm", "asr"}
CLOUD_ACCOUNT_PROVIDERS = {"baidu_netdisk"}
STUDY_DATE_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REVIEW_CHAIN_TEMPLATE_KINDS = {"CONVERGENCE", "REVIEW_TASK"}
LEARNING_PLAN_TARGET_KINDS = {"PROJECT", "LEARNING_OBJECT_NODES"}
DEFAULT_USER_THEME = "mist"
DEFAULT_POMODORO_ENABLED = False
DEFAULT_POMODORO_TRANSITION_SOUND_ENABLED = False
DEFAULT_POMODORO_FOCUS_MINUTES = 25
DEFAULT_POMODORO_BREAK_MINUTES = 5
DEFAULT_POMODORO_COUNT = 4
DEFAULT_POMODORO_START_TIME = "19:00"
DEFAULT_POMODORO_MICRO_BREAKS = {
    "enabled": False,
    "minIntervalSeconds": 180,
    "maxIntervalSeconds": 300,
    "durationSeconds": 10,
}
MAX_POMODORO_PLANS_PER_DAY = 24
MAX_POMODORO_PROMPT_LENGTH = 200
POMODORO_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
USER_COLUMNS_SQL = """
    u.user_id,
    u.email,
    u.created_at,
    p.public_uid,
    p.nickname,
    p.bio,
    p.avatar_key,
    p.status,
    p.updated_at
"""
SESSION_TOKEN_HASH_PREFIX = "sha256:"
SESSION_TOKEN_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

from backend.models.cloud_account_binding import CloudAccountBinding
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.global_settings import normalize_llm_prompt_assembly_mode
from backend.models.project_config import LocalServiceConfig
from backend.system.app_paths import resolve_auth_db_path
from backend.system.postgres_runtime import get_postgres_pool, redact_postgres_dsn
from backend.system.postgres_schema import (
    apply_postgres_migrations,
    expected_postgres_migration_status,
    postgres_migration_status,
    validate_postgres_migration_plan,
)
from backend.system.sql_backend import current_sql_runtime_config

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None
    dict_row = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_email(email: str) -> str:
    value = str(email).strip().lower()
    if not value:
        raise PreconditionFailure("email must be non-empty")
    return value


def _configured_bootstrap_super_admin_emails() -> tuple[str, ...]:
    raw_values = (
        os.getenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS"),
        os.getenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAIL"),
    )
    items: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if raw is None:
            continue
        for part in str(raw).split(","):
            if not str(part).strip():
                continue
            normalized = _normalize_email(part)
            if normalized in seen:
                continue
            seen.add(normalized)
            items.append(normalized)
    return tuple(items)


def email_is_bootstrap_super_admin(email: str) -> bool:
    return _normalize_email(email) in set(_configured_bootstrap_super_admin_emails())


def _is_hashed_session_token(value: Any) -> bool:
    return SESSION_TOKEN_HASH_RE.fullmatch(str(value or "").strip()) is not None


def _hash_session_token(session_token: str) -> str:
    token = str(session_token).strip()
    if not token:
        raise PreconditionFailure("session token must be non-empty")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{SESSION_TOKEN_HASH_PREFIX}{digest}"


def _stored_session_token_value(session_token: Any) -> str:
    token = str(session_token or "").strip()
    if not token:
        raise PreconditionFailure("session token must be non-empty")
    if _is_hashed_session_token(token):
        return token
    return _hash_session_token(token)


def _session_token_lookup_candidates(session_token: Any) -> tuple[str, ...]:
    token = str(session_token or "").strip()
    if not token:
        return ()
    stored_value = _stored_session_token_value(token)
    if stored_value == token:
        return (stored_value,)
    return (stored_value, token)


def _session_ttl_days() -> int:
    raw = (os.getenv("PLM_SESSION_TTL_DAYS") or "30").strip()
    try:
        value = int(raw)
    except Exception as exc:
        raise PreconditionFailure("PLM_SESSION_TTL_DAYS must be an integer") from exc
    return max(1, value)


def _password_reset_token_ttl_minutes() -> int:
    raw = (os.getenv("PLM_PASSWORD_RESET_TOKEN_TTL_MINUTES") or "30").strip()
    try:
        value = int(raw)
    except Exception as exc:
        raise PreconditionFailure("PLM_PASSWORD_RESET_TOKEN_TTL_MINUTES must be an integer") from exc
    return max(5, value)


def _email_verification_token_ttl_minutes() -> int:
    raw = (os.getenv("PLM_EMAIL_VERIFICATION_TOKEN_TTL_MINUTES") or "1440").strip()
    try:
        value = int(raw)
    except Exception as exc:
        raise PreconditionFailure("PLM_EMAIL_VERIFICATION_TOKEN_TTL_MINUTES must be an integer") from exc
    return max(10, value)


def _require_psycopg() -> Any:
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg[binary] is required for the PostgreSQL auth backend")
    return psycopg


def _is_missing_optional_auth_table_error(exc: Exception) -> bool:
    return bool(psycopg is not None and isinstance(exc, psycopg.errors.UndefinedTable))


def _postgres_table_exists(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM pg_tables
        WHERE schemaname = current_schema() AND tablename = %s
        LIMIT 1
        """,
        (str(table_name),),
    ).fetchone()
    return row is not None


def _random_public_uid() -> str:
    return "LP" + "".join(secrets.choice(PUBLIC_UID_ALPHABET) for _ in range(8))


def _seeded_public_uid(seed: str) -> str:
    digest = hashlib.sha1(str(seed).encode("utf-8")).hexdigest().upper()
    return "LP" + digest[:8]


def _default_nickname_for_email(email: str) -> str:
    local = str(email).split("@", 1)[0].strip()
    return (local or "user")[:40]


def _normalize_nickname(nickname: str) -> str:
    value = str(nickname).strip()
    if not value:
        raise PreconditionFailure("nickname must be non-empty")
    if len(value) > 40:
        raise PreconditionFailure("nickname must be at most 40 characters")
    return value


def _normalize_bio(bio: str | None) -> str:
    value = str(bio or "").strip()
    if len(value) > 500:
        raise PreconditionFailure("bio must be at most 500 characters")
    return value


def _normalize_avatar_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_project_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PreconditionFailure("project_id must be non-empty")
    if len(text) > 200:
        raise PreconditionFailure("project_id must be at most 200 characters")
    return text


def _normalize_learning_plan_text(value: Any, *, maximum: int) -> str:
    text = str(value or "").strip()
    return text[:maximum]


def _normalize_learning_plan_int(value: Any, *, default: int, minimum: int = 0, maximum: int = 9_999_999_999_999) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _normalize_learning_plan_ratio(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = 0.0
    return max(0.0, min(1.0, parsed))


def _default_learning_plans_payload() -> dict[str, Any]:
    return {"plans": [], "progressSnapshots": []}


def _normalize_learning_plans_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _default_learning_plans_payload()
    plans: list[dict[str, Any]] = []
    raw_plans = value.get("plans")
    if isinstance(raw_plans, list):
        for item in raw_plans[:500]:
            if not isinstance(item, dict):
                continue
            plan_id = _normalize_learning_plan_text(item.get("planId"), maximum=240)
            project_id = _normalize_learning_plan_text(item.get("projectId"), maximum=200)
            if not plan_id or not project_id:
                continue
            target_kind = str(item.get("targetKind") or "PROJECT").strip()
            if target_kind not in LEARNING_PLAN_TARGET_KINDS:
                target_kind = "PROJECT"
            node_ids = item.get("learningObjectNodeIds")
            if not isinstance(node_ids, list):
                node_ids = []
            normalized_node_ids = []
            seen_node_ids: set[str] = set()
            for node_id_item in node_ids[:500]:
                node_id = _normalize_learning_plan_text(node_id_item, maximum=240)
                if not node_id or node_id in seen_node_ids:
                    continue
                seen_node_ids.add(node_id)
                normalized_node_ids.append(node_id)
            archived_at = item.get("archivedAt")
            plans.append(
                {
                    "planId": plan_id,
                    "projectId": project_id,
                    "title": _normalize_learning_plan_text(item.get("title"), maximum=120) or "学习计划",
                    "targetKind": target_kind,
                    "learningObjectNodeIds": normalized_node_ids,
                    "targetDays": _normalize_learning_plan_int(item.get("targetDays"), default=1, minimum=1, maximum=3650),
                    "createdDateKey": _normalize_learning_plan_text(item.get("createdDateKey"), maximum=10),
                    "dueDateKey": _normalize_learning_plan_text(item.get("dueDateKey"), maximum=10),
                    "archivedAt": None
                    if archived_at is None
                    else _normalize_learning_plan_int(archived_at, default=0, minimum=0),
                    "updatedAt": _normalize_learning_plan_int(item.get("updatedAt"), default=0, minimum=0),
                }
            )
    snapshots: list[dict[str, Any]] = []
    raw_snapshots = value.get("progressSnapshots")
    if isinstance(raw_snapshots, list):
        for item in raw_snapshots[:5000]:
            if not isinstance(item, dict):
                continue
            plan_id = _normalize_learning_plan_text(item.get("planId"), maximum=240)
            date_key = _normalize_learning_plan_text(item.get("dateKey"), maximum=10)
            if not plan_id or not date_key:
                continue
            snapshots.append(
                {
                    "planId": plan_id,
                    "dateKey": date_key,
                    "progressRatio": _normalize_learning_plan_ratio(item.get("progressRatio")),
                    "updatedAt": _normalize_learning_plan_int(item.get("updatedAt"), default=0, minimum=0),
                }
            )
    return {"plans": plans, "progressSnapshots": snapshots}


def _normalize_user_status(status: str) -> str:
    value = str(status).strip().lower()
    if value not in USER_STATUSES:
        raise PreconditionFailure("status must be one of active, suspended, deleted")
    return value


def _normalize_global_role(role: str) -> str:
    value = str(role).strip().lower()
    if value not in GLOBAL_ROLES:
        raise PreconditionFailure("role must be one of super_admin, admin")
    return value


def _normalize_user_role_filter(role: str | None) -> str | None:
    value = str(role or "").strip().lower()
    if not value:
        return None
    if value == "none":
        return value
    return _normalize_global_role(value)


def _normalize_admin_action_field(value: str, *, field_name: str, maximum: int) -> str:
    text = str(value).strip()
    if not text:
        raise PreconditionFailure(f"{field_name} must be non-empty")
    if len(text) > maximum:
        raise PreconditionFailure(f"{field_name} must be at most {maximum} characters")
    return text


def _normalize_friend_request_message(message: str | None) -> str:
    value = str(message or "").strip()
    if len(value) > 200:
        raise PreconditionFailure("friend request message must be at most 200 characters")
    return value


def _normalize_friend_request_status(status: str) -> str:
    value = str(status).strip().lower()
    if value not in FRIEND_REQUEST_STATUSES:
        raise PreconditionFailure("friend request status must be one of pending, accepted, rejected, cancelled")
    return value


def _friend_pair(user_a_id: str, user_b_id: str) -> tuple[str, str]:
    left = str(user_a_id).strip()
    right = str(user_b_id).strip()
    if not left or not right:
        raise PreconditionFailure("friend user ids must be non-empty")
    return (left, right) if left <= right else (right, left)


def _normalize_limit(limit: int, *, default: int = 100, maximum: int = 200) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, maximum))


def _normalize_service_kind(service_kind: str) -> str:
    value = str(service_kind).strip().lower()
    if value not in USER_SERVICE_KINDS:
        raise PreconditionFailure("service kind must be one of llm, asr")
    return value


def _normalize_service_base_url(base_url: str) -> str:
    cfg = LocalServiceConfig(base_url=str(base_url).strip())
    cfg.validate_write_time()
    return cfg.base_url


def _normalize_service_model_name(model_name: str | None) -> str:
    value = str(model_name or "").strip()
    if len(value) > 200:
        raise PreconditionFailure("model name must be at most 200 characters")
    return value


def _normalize_service_api_key(api_key: str | None) -> str | None:
    value = str(api_key or "").strip()
    if len(value) > 500:
        raise PreconditionFailure("api key must be at most 500 characters")
    return value or None


def _normalize_service_prompt_assembly_mode(prompt_assembly_mode: str | None) -> str:
    return normalize_llm_prompt_assembly_mode(prompt_assembly_mode)


def _normalize_cloud_account_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in CLOUD_ACCOUNT_PROVIDERS:
        raise PreconditionFailure("cloud account provider must be one of baidu_netdisk")
    return value


def _normalize_cloud_account_text(value: str | None, *, field_name: str, maximum: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise PreconditionFailure(f"{field_name} must be non-empty")
    if len(text) > maximum:
        raise PreconditionFailure(f"{field_name} must be at most {maximum} characters")
    return text


def _normalize_cloud_account_optional_text(value: str | None, *, maximum: int = 2000) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > maximum:
        raise PreconditionFailure(f"cloud account field must be at most {maximum} characters")
    return text


def _normalize_study_date_key(value: str) -> str:
    text = str(value or "").strip()
    if not STUDY_DATE_KEY_RE.fullmatch(text):
        raise PreconditionFailure("study date key must use YYYY-MM-DD")
    return text


def _normalize_study_duration_ms(value: int | float | str | None, *, field_name: str) -> int:
    try:
        number = int(value or 0)
    except Exception as exc:
        raise PreconditionFailure(f"{field_name} must be an integer") from exc
    if number < 0:
        raise PreconditionFailure(f"{field_name} must be non-negative")
    return number


def _normalize_study_ranges(ranges: Iterable[tuple[int, int] | list[int]]) -> tuple[tuple[int, int], ...]:
    normalized: list[tuple[int, int]] = []
    for item in ranges:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            raise PreconditionFailure("study ranges must be [start_ms, end_ms] pairs")
        start_ms = _normalize_study_duration_ms(item[0], field_name="study range start_ms")
        end_ms = _normalize_study_duration_ms(item[1], field_name="study range end_ms")
        if end_ms <= start_ms:
            raise PreconditionFailure("study range end_ms must be greater than start_ms")
        normalized.append((start_ms, end_ms))

    if len(normalized) <= 1:
        return tuple(normalized)

    normalized.sort(key=lambda item: item[0])
    merged: list[tuple[int, int]] = [normalized[0]]
    for start_ms, end_ms in normalized[1:]:
        last_start_ms, last_end_ms = merged[-1]
        if start_ms <= last_end_ms:
            merged[-1] = (last_start_ms, max(last_end_ms, end_ms))
            continue
        merged.append((start_ms, end_ms))
    return tuple(merged)


def _sum_study_ranges(ranges: Iterable[tuple[int, int]]) -> int:
    return sum(max(0, int(end_ms) - int(start_ms)) for start_ms, end_ms in ranges)


def _merge_study_metric_value(existing_ms: int, incoming_ms: int, merged_ranges: tuple[tuple[int, int], ...]) -> int:
    return max(int(existing_ms), int(incoming_ms), _sum_study_ranges(merged_ranges))


def _clamp_int(value: int | float | str | None, *, minimum: int, maximum: int, field_name: str) -> int:
    try:
        number = int(value)
    except Exception as exc:
        raise PreconditionFailure(f"{field_name} must be an integer") from exc
    return max(minimum, min(maximum, number))


def _normalize_user_theme(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_USER_THEME
    if len(text) > 40:
        raise PreconditionFailure("theme must be at most 40 characters")
    return text


def _normalize_pomodoro_start_time(value: str | None) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", text)
    if not match:
        return DEFAULT_POMODORO_START_TIME
    hours = _clamp_int(match.group(1), minimum=0, maximum=23, field_name="pomodoro start hour")
    minutes = _clamp_int(match.group(2), minimum=0, maximum=59, field_name="pomodoro start minute")
    return f"{hours:02d}:{minutes:02d}"


def _read_pomodoro_start_minutes(start_time: str) -> int:
    hours_text, minutes_text = _normalize_pomodoro_start_time(start_time).split(":")
    return int(hours_text) * 60 + int(minutes_text)


def _normalize_pomodoro_plan_id(value: Any, *, day_key: str, index: int) -> str:
    text = re.sub(r"\s+", "-", str(value or "").strip())
    return text[:80] if text else f"{day_key}-{index + 1}"


def _normalize_pomodoro_prompt_text(value: str | None) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) > MAX_POMODORO_PROMPT_LENGTH:
        raise PreconditionFailure(f"pomodoro prompt must be at most {MAX_POMODORO_PROMPT_LENGTH} characters")
    return text


def _normalize_pomodoro_micro_break_settings(value: Any) -> PomodoroMicroBreakSettings:
    payload = value if isinstance(value, dict) else {}
    min_interval_seconds = _clamp_int(
        payload.get("minIntervalSeconds", DEFAULT_POMODORO_MICRO_BREAKS["minIntervalSeconds"]),
        minimum=30,
        maximum=3600,
        field_name="pomodoro micro break min interval seconds",
    )
    max_interval_seconds = _clamp_int(
        payload.get("maxIntervalSeconds", DEFAULT_POMODORO_MICRO_BREAKS["maxIntervalSeconds"]),
        minimum=30,
        maximum=3600,
        field_name="pomodoro micro break max interval seconds",
    )
    return PomodoroMicroBreakSettings(
        enabled=bool(payload.get("enabled", DEFAULT_POMODORO_MICRO_BREAKS["enabled"])),
        min_interval_seconds=min_interval_seconds,
        max_interval_seconds=max(min_interval_seconds, max_interval_seconds),
        duration_seconds=_clamp_int(
            payload.get("durationSeconds", DEFAULT_POMODORO_MICRO_BREAKS["durationSeconds"]),
            minimum=5,
            maximum=300,
            field_name="pomodoro micro break duration seconds",
        ),
    )


def _pomodoro_micro_break_settings_to_json(item: PomodoroMicroBreakSettings) -> dict[str, Any]:
    normalized = _normalize_pomodoro_micro_break_settings(
        {
            "enabled": item.enabled,
            "minIntervalSeconds": item.min_interval_seconds,
            "maxIntervalSeconds": item.max_interval_seconds,
            "durationSeconds": item.duration_seconds,
        }
    )
    return {
        "enabled": normalized.enabled,
        "minIntervalSeconds": normalized.min_interval_seconds,
        "maxIntervalSeconds": normalized.max_interval_seconds,
        "durationSeconds": normalized.duration_seconds,
    }


def _create_pomodoro_schedule_day(
    day_key: str,
    *,
    plan_id: str = "",
    plan_index: int = 0,
    enabled: bool = False,
    start_time: str = DEFAULT_POMODORO_START_TIME,
    focus_minutes: int = DEFAULT_POMODORO_FOCUS_MINUTES,
    break_minutes: int = DEFAULT_POMODORO_BREAK_MINUTES,
    pomodoro_count: int = DEFAULT_POMODORO_COUNT,
    project_ids: Iterable[str | None] | None = None,
    break_prompt: str | None = None,
    focus_prompts: Iterable[str | None] | None = None,
) -> PomodoroScheduleDay:
    normalized_day_key = str(day_key or "").strip().lower()
    if normalized_day_key not in POMODORO_WEEKDAY_KEYS:
        raise PreconditionFailure("pomodoro weekday must be one of mon, tue, wed, thu, fri, sat, sun")
    normalized_pomodoro_count = _clamp_int(
        pomodoro_count,
        minimum=1,
        maximum=12,
        field_name="pomodoro count",
    )
    return PomodoroScheduleDay(
        day_key=normalized_day_key,
        plan_id=_normalize_pomodoro_plan_id(plan_id, day_key=normalized_day_key, index=plan_index),
        enabled=bool(enabled),
        start_time=_normalize_pomodoro_start_time(start_time),
        focus_minutes=_clamp_int(
            focus_minutes,
            minimum=1,
            maximum=180,
            field_name="pomodoro focus minutes",
        ),
        break_minutes=_clamp_int(
            break_minutes,
            minimum=1,
            maximum=60,
            field_name="pomodoro break minutes",
        ),
        pomodoro_count=normalized_pomodoro_count,
        project_ids=_normalize_pomodoro_project_ids(project_ids, pomodoro_count=normalized_pomodoro_count),
        break_prompt=_normalize_pomodoro_prompt_text(break_prompt),
        focus_prompts=_normalize_pomodoro_focus_prompts(focus_prompts, pomodoro_count=normalized_pomodoro_count),
    )


def _pomodoro_plan_duration_minutes(item: PomodoroScheduleDay) -> int:
    return int(item.focus_minutes) * int(item.pomodoro_count) + int(item.break_minutes) * max(
        0,
        int(item.pomodoro_count) - 1,
    )


def _validate_pomodoro_day_plan_conflicts(day_key: str, items: Iterable[PomodoroScheduleDay]) -> None:
    enabled_ranges: list[tuple[int, int, PomodoroScheduleDay]] = []
    for item in items:
        if not item.enabled:
            continue
        start_minutes = _read_pomodoro_start_minutes(item.start_time)
        end_minutes = start_minutes + _pomodoro_plan_duration_minutes(item)
        if end_minutes > 24 * 60:
            raise PreconditionFailure("pomodoro plan must end before midnight")
        enabled_ranges.append((start_minutes, end_minutes, item))

    enabled_ranges.sort(key=lambda value: (value[0], value[2].plan_id))
    previous: tuple[int, int, PomodoroScheduleDay] | None = None
    for current in enabled_ranges:
        if previous is not None and current[0] < previous[1]:
            raise PreconditionFailure(f"pomodoro plans for {day_key} overlap")
        previous = current


def _normalize_pomodoro_project_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_pomodoro_project_ids(
    raw_project_ids: Iterable[str | None] | None,
    *,
    pomodoro_count: int,
) -> tuple[str | None, ...]:
    normalized_count = _clamp_int(
        pomodoro_count,
        minimum=1,
        maximum=12,
        field_name="pomodoro count",
    )
    raw_items = list(raw_project_ids or [])
    normalized: list[str | None] = []
    for index in range(normalized_count):
        normalized.append(_normalize_pomodoro_project_id(raw_items[index] if index < len(raw_items) else None))
    return tuple(normalized)


def _normalize_pomodoro_focus_prompts(
    raw_focus_prompts: Iterable[str | None] | None,
    *,
    pomodoro_count: int,
) -> tuple[str, ...]:
    normalized_count = _clamp_int(
        pomodoro_count,
        minimum=1,
        maximum=12,
        field_name="pomodoro count",
    )
    raw_items = list(raw_focus_prompts or [])
    normalized: list[str] = []
    for index in range(normalized_count):
        normalized.append(_normalize_pomodoro_prompt_text(raw_items[index] if index < len(raw_items) else None))
    return tuple(normalized)


def _normalize_pomodoro_weekly_schedule(
    raw_schedule: Any,
    *,
    legacy_focus_minutes: int | float | str | None = DEFAULT_POMODORO_FOCUS_MINUTES,
    legacy_break_minutes: int | float | str | None = DEFAULT_POMODORO_BREAK_MINUTES,
    legacy_pomodoro_count: int | float | str | None = DEFAULT_POMODORO_COUNT,
) -> tuple[PomodoroScheduleDay, ...]:
    payload = raw_schedule if isinstance(raw_schedule, dict) else {}
    normalized_focus_minutes = _clamp_int(
        legacy_focus_minutes,
        minimum=1,
        maximum=180,
        field_name="pomodoro focus minutes",
    )
    normalized_break_minutes = _clamp_int(
        legacy_break_minutes,
        minimum=1,
        maximum=60,
        field_name="pomodoro break minutes",
    )
    normalized_pomodoro_count = _clamp_int(
        legacy_pomodoro_count,
        minimum=1,
        maximum=12,
        field_name="pomodoro count",
    )
    items: list[PomodoroScheduleDay] = []
    for day_key in POMODORO_WEEKDAY_KEYS:
        day_payload = payload.get(day_key)
        if not isinstance(day_payload, dict):
            day_payload = {}
        raw_plans = day_payload.get("plans")
        is_plan_list = isinstance(raw_plans, list)
        plan_payloads = raw_plans if is_plan_list else ([day_payload] if bool(day_payload.get("enabled", False)) else [])
        if len(plan_payloads) > MAX_POMODORO_PLANS_PER_DAY:
            raise PreconditionFailure(f"pomodoro plans for {day_key} must be at most {MAX_POMODORO_PLANS_PER_DAY}")

        day_items: list[PomodoroScheduleDay] = []
        for plan_index, raw_plan in enumerate(plan_payloads):
            plan_payload = raw_plan if isinstance(raw_plan, dict) else {}
            day_items.append(
                _create_pomodoro_schedule_day(
                    day_key,
                    plan_id=plan_payload.get("id"),
                    plan_index=plan_index,
                    enabled=bool(plan_payload.get("enabled", True if is_plan_list else False)),
                    start_time=str(plan_payload.get("startTime", DEFAULT_POMODORO_START_TIME)),
                    focus_minutes=plan_payload.get("focusMinutes", normalized_focus_minutes),
                    break_minutes=plan_payload.get("breakMinutes", normalized_break_minutes),
                    pomodoro_count=plan_payload.get("pomodoroCount", normalized_pomodoro_count),
                    project_ids=plan_payload.get("projectIds"),
                    break_prompt=plan_payload.get("breakPrompt"),
                    focus_prompts=plan_payload.get("focusPrompts"),
                )
            )
        _validate_pomodoro_day_plan_conflicts(day_key, day_items)
        items.extend(sorted(day_items, key=lambda item: (_read_pomodoro_start_minutes(item.start_time), item.plan_id)))
    return tuple(items)


def _pomodoro_weekly_schedule_to_json(items: Iterable[PomodoroScheduleDay]) -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {day_key: {"plans": []} for day_key in POMODORO_WEEKDAY_KEYS}
    for item in items:
        if item.day_key not in payload:
            continue
        payload[item.day_key]["plans"].append({
            "id": _normalize_pomodoro_plan_id(item.plan_id, day_key=item.day_key, index=len(payload[item.day_key]["plans"])),
            "enabled": bool(item.enabled),
            "startTime": _normalize_pomodoro_start_time(item.start_time),
            "focusMinutes": _clamp_int(
                item.focus_minutes,
                minimum=1,
                maximum=180,
                field_name="pomodoro focus minutes",
            ),
            "breakMinutes": _clamp_int(
                item.break_minutes,
                minimum=1,
                maximum=60,
                field_name="pomodoro break minutes",
            ),
            "pomodoroCount": _clamp_int(
                item.pomodoro_count,
                minimum=1,
                maximum=12,
                field_name="pomodoro count",
            ),
            "projectIds": list(
                _normalize_pomodoro_project_ids(item.project_ids, pomodoro_count=item.pomodoro_count)
            ),
            "breakPrompt": _normalize_pomodoro_prompt_text(item.break_prompt),
            "focusPrompts": list(
                _normalize_pomodoro_focus_prompts(item.focus_prompts, pomodoro_count=item.pomodoro_count)
            ),
        })
    return payload


def _normalize_review_chain_template_item(kind: str | None, count: int | float | str | None = None) -> tuple[str, int | None]:
    normalized_kind = str(kind or "").strip().upper()
    if normalized_kind not in REVIEW_CHAIN_TEMPLATE_KINDS:
        raise PreconditionFailure("review chain template kind must be CONVERGENCE or REVIEW_TASK")
    if normalized_kind == "CONVERGENCE":
        return ("CONVERGENCE", None)
    normalized_count = _clamp_int(count or 1, minimum=1, maximum=999, field_name="review chain template count")
    return ("REVIEW_TASK", normalized_count)


def _normalize_review_chain_template(
    items: Iterable[dict[str, Any] | tuple[str, int | None] | list[Any]],
) -> tuple[tuple[str, int | None], ...]:
    normalized: list[tuple[str, int | None]] = []
    has_convergence = False
    for item in items:
        if isinstance(item, dict):
            kind, count = _normalize_review_chain_template_item(item.get("kind"), item.get("count"))
        elif isinstance(item, (tuple, list)) and len(item) >= 1:
            raw_count = item[1] if len(item) > 1 else None
            kind, count = _normalize_review_chain_template_item(item[0], raw_count)
        else:
            continue
        normalized.append((kind, count))
        if kind == "CONVERGENCE":
            has_convergence = True
    if not normalized:
        return (("CONVERGENCE", None),)
    if not has_convergence:
        normalized.insert(0, ("CONVERGENCE", None))
    return tuple(normalized)


def _review_chain_template_to_json(items: Iterable[tuple[str, int | None]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for kind, count in items:
        if kind == "REVIEW_TASK" and int(count or 1) > 1:
            payload.append({"kind": "REVIEW_TASK", "count": int(count or 1)})
        else:
            payload.append({"kind": kind})
    return payload


def _normalize_cloud_account_scope(scope: str | None) -> str:
    value = str(scope or "").strip()
    if len(value) > 1000:
        raise PreconditionFailure("cloud account scope must be at most 1000 characters")
    return value


def _normalize_cloud_account_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    normalized = {} if meta is None else dict(meta)
    try:
        json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except Exception as exc:
        raise PreconditionFailure("cloud account meta must be JSON-serializable") from exc
    return normalized


def _token_encryption_key() -> bytes:
    raw = str(os.getenv("PLM_TOKEN_ENCRYPTION_KEY") or "").strip()
    if not raw:
        raise PreconditionFailure("PLM_TOKEN_ENCRYPTION_KEY must be configured")
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_secret_value(plain_text: str) -> str:
    text = str(plain_text or "")
    if not text:
        raise PreconditionFailure("secret value must be non-empty")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_token_encryption_key()).encrypt(nonce, text.encode("utf-8"), b"plm:secret:v1")
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"aesgcm:v1:{payload}"


def decrypt_secret_value(ciphertext: str) -> str:
    raw = str(ciphertext or "").strip()
    if not raw:
        raise PreconditionFailure("secret ciphertext must be non-empty")
    if not raw.startswith("aesgcm:v1:"):
        raise PreconditionFailure("secret ciphertext format is unsupported")
    payload = raw.split(":", 2)[2]
    try:
        blob = base64.urlsafe_b64decode(payload.encode("ascii"))
    except Exception as exc:
        raise PreconditionFailure("secret ciphertext is invalid") from exc
    if len(blob) <= 12:
        raise PreconditionFailure("secret ciphertext is truncated")
    nonce = blob[:12]
    encrypted = blob[12:]
    try:
        plain = AESGCM(_token_encryption_key()).decrypt(nonce, encrypted, b"plm:secret:v1")
    except Exception as exc:
        raise PreconditionFailure("secret ciphertext cannot be decrypted") from exc
    return plain.decode("utf-8")


@dataclass(frozen=True, slots=True)
class AuthUser:
    user_id: str
    email: str
    created_at: str
    public_uid: str
    nickname: str
    bio: str
    avatar_key: str | None
    status: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class UserServiceConfig:
    user_id: str
    service_kind: str
    base_url: str
    model_name: str
    api_key: str | None
    prompt_assembly_mode: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ReviewChainTemplateStep:
    kind: str
    count: int | None = None


@dataclass(frozen=True, slots=True)
class PomodoroScheduleDay:
    day_key: str
    plan_id: str
    enabled: bool
    start_time: str
    focus_minutes: int
    break_minutes: int
    pomodoro_count: int
    project_ids: tuple[str | None, ...] = ()
    break_prompt: str = ""
    focus_prompts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PomodoroMicroBreakSettings:
    enabled: bool
    min_interval_seconds: int
    max_interval_seconds: int
    duration_seconds: int


@dataclass(frozen=True, slots=True)
class UserGlobalSettings:
    user_id: str
    theme: str
    pomodoro_enabled: bool
    pomodoro_transition_sound_enabled: bool
    pomodoro_default_focus_prompt: str
    pomodoro_default_break_prompt: str
    pomodoro_micro_breaks: PomodoroMicroBreakSettings
    pomodoro_weekly_schedule: tuple[PomodoroScheduleDay, ...]
    default_project_review_template: tuple[ReviewChainTemplateStep, ...]
    learning_plans: dict[str, Any]
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class AdminUser:
    user_id: str
    email: str
    created_at: str
    public_uid: str
    nickname: str
    bio: str
    avatar_key: str | None
    status: str
    updated_at: str
    roles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdminActionLog:
    log_id: str
    actor_user_id: str
    actor_public_uid: str
    actor_nickname: str
    actor_avatar_key: str | None
    action_type: str
    target_kind: str
    target_id: str
    summary: str
    created_at: str


@dataclass(frozen=True, slots=True)
class FriendListItem:
    user_id: str
    public_uid: str
    nickname: str
    bio: str
    avatar_key: str | None
    friended_at: str


@dataclass(frozen=True, slots=True)
class FriendRequest:
    request_id: str
    requester_user_id: str
    requester_public_uid: str
    requester_nickname: str
    requester_bio: str
    requester_avatar_key: str | None
    receiver_user_id: str
    receiver_public_uid: str
    receiver_nickname: str
    receiver_bio: str
    receiver_avatar_key: str | None
    message: str
    status: str
    created_at: str
    handled_at: str | None
    handled_by_user_id: str | None


@dataclass(frozen=True, slots=True)
class Friendship:
    user_low_id: str
    user_high_id: str
    created_at: str
    source_request_id: str | None


@dataclass(frozen=True, slots=True)
class UserProjectDailyStudyStatInput:
    project_id: str
    date_key: str
    schema_version: int
    web_presence_ms: int
    video_ms: int
    recall_entry_ms: int
    ai_qa_ms: int
    distraction_ms: int
    presence_ranges: tuple[tuple[int, int], ...]
    video_ranges: tuple[tuple[int, int], ...]
    recall_entry_ranges: tuple[tuple[int, int], ...]
    ai_qa_ranges: tuple[tuple[int, int], ...]
    is_partition_complete: bool
    effective_ms: int
    watch_ms: int
    compose_ms: int
    review_ms: int
    qa_ms: int
    effective_ranges: tuple[tuple[int, int], ...]
    watch_ranges: tuple[tuple[int, int], ...]
    compose_ranges: tuple[tuple[int, int], ...]
    review_ranges: tuple[tuple[int, int], ...]
    qa_ranges: tuple[tuple[int, int], ...]

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        date_key: str,
        schema_version: int | float | str | None = 1,
        web_presence_ms: int | float | str | None = 0,
        video_ms: int | float | str | None = 0,
        recall_entry_ms: int | float | str | None = 0,
        ai_qa_ms: int | float | str | None = 0,
        distraction_ms: int | float | str | None = 0,
        presence_ranges: Iterable[tuple[int, int] | list[int]] = (),
        video_ranges: Iterable[tuple[int, int] | list[int]] = (),
        recall_entry_ranges: Iterable[tuple[int, int] | list[int]] = (),
        ai_qa_ranges: Iterable[tuple[int, int] | list[int]] = (),
        is_partition_complete: bool = False,
        effective_ms: int | float | str | None = 0,
        watch_ms: int | float | str | None = 0,
        compose_ms: int | float | str | None = 0,
        review_ms: int | float | str | None = 0,
        qa_ms: int | float | str | None = 0,
        effective_ranges: Iterable[tuple[int, int] | list[int]] = (),
        watch_ranges: Iterable[tuple[int, int] | list[int]] = (),
        compose_ranges: Iterable[tuple[int, int] | list[int]] = (),
        review_ranges: Iterable[tuple[int, int] | list[int]] = (),
        qa_ranges: Iterable[tuple[int, int] | list[int]] = (),
    ) -> "UserProjectDailyStudyStatInput":
        normalized_presence_ranges = _normalize_study_ranges(presence_ranges)
        normalized_video_ranges = _normalize_study_ranges(video_ranges)
        normalized_recall_entry_ranges = _normalize_study_ranges(recall_entry_ranges)
        normalized_ai_qa_ranges = _normalize_study_ranges(ai_qa_ranges)
        normalized_effective_ranges = _normalize_study_ranges(effective_ranges)
        normalized_watch_ranges = _normalize_study_ranges(watch_ranges)
        normalized_compose_ranges = _normalize_study_ranges(compose_ranges)
        normalized_review_ranges = _normalize_study_ranges(review_ranges)
        normalized_qa_ranges = _normalize_study_ranges(qa_ranges)
        normalized_schema_version = max(1, _normalize_study_duration_ms(schema_version, field_name="schema_version"))
        normalized_video_ms = max(
            _normalize_study_duration_ms(video_ms, field_name="video_ms"),
            _sum_study_ranges(normalized_video_ranges),
        )
        normalized_recall_entry_ms = max(
            _normalize_study_duration_ms(recall_entry_ms, field_name="recall_entry_ms"),
            _sum_study_ranges(normalized_recall_entry_ranges),
        )
        normalized_ai_qa_ms = max(
            _normalize_study_duration_ms(ai_qa_ms, field_name="ai_qa_ms"),
            _sum_study_ranges(normalized_ai_qa_ranges),
        )
        return cls(
            project_id=_normalize_project_id(project_id),
            date_key=_normalize_study_date_key(date_key),
            schema_version=normalized_schema_version,
            web_presence_ms=max(
                _normalize_study_duration_ms(web_presence_ms, field_name="web_presence_ms"),
                _sum_study_ranges(normalized_presence_ranges),
            ),
            video_ms=normalized_video_ms,
            recall_entry_ms=normalized_recall_entry_ms,
            ai_qa_ms=normalized_ai_qa_ms,
            distraction_ms=_normalize_study_duration_ms(distraction_ms, field_name="distraction_ms"),
            presence_ranges=normalized_presence_ranges,
            video_ranges=normalized_video_ranges,
            recall_entry_ranges=normalized_recall_entry_ranges,
            ai_qa_ranges=normalized_ai_qa_ranges,
            is_partition_complete=bool(is_partition_complete),
            effective_ms=max(
                _normalize_study_duration_ms(effective_ms, field_name="effective_ms"),
                _sum_study_ranges(normalized_effective_ranges),
            ),
            watch_ms=max(
                _normalize_study_duration_ms(watch_ms, field_name="watch_ms"),
                normalized_video_ms,
                _sum_study_ranges(normalized_watch_ranges),
            ),
            compose_ms=max(
                _normalize_study_duration_ms(compose_ms, field_name="compose_ms"),
                normalized_recall_entry_ms,
                _sum_study_ranges(normalized_compose_ranges),
            ),
            review_ms=max(
                _normalize_study_duration_ms(review_ms, field_name="review_ms"),
                _sum_study_ranges(normalized_review_ranges),
            ),
            qa_ms=max(
                _normalize_study_duration_ms(qa_ms, field_name="qa_ms"),
                normalized_ai_qa_ms,
                _sum_study_ranges(normalized_qa_ranges),
            ),
            effective_ranges=normalized_effective_ranges,
            watch_ranges=normalized_watch_ranges,
            compose_ranges=normalized_compose_ranges,
            review_ranges=normalized_review_ranges,
            qa_ranges=normalized_qa_ranges,
        )


@dataclass(frozen=True, slots=True)
class UserProjectDailyStudyStat:
    user_id: str
    project_id: str
    date_key: str
    schema_version: int
    web_presence_ms: int
    video_ms: int
    recall_entry_ms: int
    ai_qa_ms: int
    distraction_ms: int
    presence_ranges: tuple[tuple[int, int], ...]
    video_ranges: tuple[tuple[int, int], ...]
    recall_entry_ranges: tuple[tuple[int, int], ...]
    ai_qa_ranges: tuple[tuple[int, int], ...]
    is_partition_complete: bool
    effective_ms: int
    watch_ms: int
    compose_ms: int
    review_ms: int
    qa_ms: int
    effective_ranges: tuple[tuple[int, int], ...]
    watch_ranges: tuple[tuple[int, int], ...]
    compose_ranges: tuple[tuple[int, int], ...]
    review_ranges: tuple[tuple[int, int], ...]
    qa_ranges: tuple[tuple[int, int], ...]
    updated_at: str


class _AuthStoreImpl:
    @staticmethod
    def _hash_password(password: str) -> str:
        text = str(password)
        if len(text) < 8:
            raise PreconditionFailure("password must be at least 8 characters")
        salt = os.urandom(16)
        rounds = 390_000
        digest = hashlib.pbkdf2_hmac("sha256", text.encode("utf-8"), salt, rounds)
        return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, rounds_text, salt_hex, digest_hex = str(encoded).split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            rounds = int(rounds_text)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except Exception:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _row_to_user(row: Any) -> AuthUser:
        return AuthUser(
            user_id=str(row["user_id"]),
            email=str(row["email"]),
            created_at=str(row["created_at"]),
            public_uid=str(row["public_uid"]),
            nickname=str(row["nickname"]),
            bio=str(row["bio"]),
            avatar_key=_normalize_avatar_key(row["avatar_key"]),
            status=str(row["status"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_user_service_config(row: Any) -> UserServiceConfig:
        prompt_assembly_mode = None
        try:
            prompt_assembly_mode = row["prompt_assembly_mode"]
        except Exception:
            prompt_assembly_mode = None
        return UserServiceConfig(
            user_id=str(row["user_id"]),
            service_kind=_normalize_service_kind(str(row["service_kind"])),
            base_url=str(row["base_url"]),
            model_name=str(row["model_name"]),
            api_key=_normalize_service_api_key(row["api_key"]),
            prompt_assembly_mode=_normalize_service_prompt_assembly_mode(prompt_assembly_mode),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _default_user_global_settings(user_id: str) -> UserGlobalSettings:
        return UserGlobalSettings(
            user_id=str(user_id),
            theme=DEFAULT_USER_THEME,
            pomodoro_enabled=DEFAULT_POMODORO_ENABLED,
            pomodoro_transition_sound_enabled=DEFAULT_POMODORO_TRANSITION_SOUND_ENABLED,
            pomodoro_default_focus_prompt="",
            pomodoro_default_break_prompt="",
            pomodoro_micro_breaks=_normalize_pomodoro_micro_break_settings({}),
            pomodoro_weekly_schedule=_normalize_pomodoro_weekly_schedule({}),
            default_project_review_template=(ReviewChainTemplateStep(kind="CONVERGENCE"),),
            learning_plans=_default_learning_plans_payload(),
            updated_at=None,
        )

    @staticmethod
    def _row_to_user_global_settings(row: Any) -> UserGlobalSettings:
        raw_payload = row["payload_json"]
        try:
            payload = json.loads(str(raw_payload)) if raw_payload not in (None, "") else {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        normalized_template = _normalize_review_chain_template(payload.get("defaultProjectReviewTemplate", ()))
        pomodoro_payload = payload.get("pomodoro")
        legacy_focus_minutes = (
            pomodoro_payload.get("focusMinutes", DEFAULT_POMODORO_FOCUS_MINUTES)
            if isinstance(pomodoro_payload, dict)
            else DEFAULT_POMODORO_FOCUS_MINUTES
        )
        legacy_break_minutes = (
            pomodoro_payload.get("breakMinutes", DEFAULT_POMODORO_BREAK_MINUTES)
            if isinstance(pomodoro_payload, dict)
            else DEFAULT_POMODORO_BREAK_MINUTES
        )
        legacy_pomodoro_count = (
            pomodoro_payload.get("pomodoroCount", DEFAULT_POMODORO_COUNT)
            if isinstance(pomodoro_payload, dict)
            else DEFAULT_POMODORO_COUNT
        )
        return UserGlobalSettings(
            user_id=str(row["user_id"]),
            theme=_normalize_user_theme(payload.get("theme")),
            pomodoro_enabled=bool(pomodoro_payload.get("enabled", DEFAULT_POMODORO_ENABLED))
            if isinstance(pomodoro_payload, dict)
            else DEFAULT_POMODORO_ENABLED,
            pomodoro_transition_sound_enabled=bool(
                pomodoro_payload.get("transitionSoundEnabled", DEFAULT_POMODORO_TRANSITION_SOUND_ENABLED)
            )
            if isinstance(pomodoro_payload, dict)
            else DEFAULT_POMODORO_TRANSITION_SOUND_ENABLED,
            pomodoro_default_focus_prompt=_normalize_pomodoro_prompt_text(
                pomodoro_payload.get("defaultFocusPrompt") if isinstance(pomodoro_payload, dict) else ""
            ),
            pomodoro_default_break_prompt=_normalize_pomodoro_prompt_text(
                pomodoro_payload.get("defaultBreakPrompt") if isinstance(pomodoro_payload, dict) else ""
            ),
            pomodoro_micro_breaks=_normalize_pomodoro_micro_break_settings(
                pomodoro_payload.get("microBreaks") if isinstance(pomodoro_payload, dict) else {}
            ),
            pomodoro_weekly_schedule=_normalize_pomodoro_weekly_schedule(
                pomodoro_payload.get("weeklySchedule") if isinstance(pomodoro_payload, dict) else {},
                legacy_focus_minutes=legacy_focus_minutes,
                legacy_break_minutes=legacy_break_minutes,
                legacy_pomodoro_count=legacy_pomodoro_count,
            ),
            default_project_review_template=tuple(
                ReviewChainTemplateStep(kind=kind, count=count) for kind, count in normalized_template
            ),
            learning_plans=_normalize_learning_plans_payload(payload.get("learningPlans")),
            updated_at=None if row["updated_at"] is None else str(row["updated_at"]),
        )

    def user_email_verified(self, user_id: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def _row_to_admin_action_log(row: Any) -> AdminActionLog:
        return AdminActionLog(
            log_id=str(row["log_id"]),
            actor_user_id=str(row["actor_user_id"]),
            actor_public_uid=str(row["actor_public_uid"]),
            actor_nickname=str(row["actor_nickname"]),
            actor_avatar_key=_normalize_avatar_key(row["actor_avatar_key"]),
            action_type=str(row["action_type"]),
            target_kind=str(row["target_kind"]),
            target_id=str(row["target_id"]),
            summary=str(row["summary"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _row_to_friend_list_item(row: Any) -> FriendListItem:
        return FriendListItem(
            user_id=str(row["user_id"]),
            public_uid=str(row["public_uid"]),
            nickname=str(row["nickname"]),
            bio=str(row["bio"]),
            avatar_key=_normalize_avatar_key(row["avatar_key"]),
            friended_at=str(row["friended_at"]),
        )

    @staticmethod
    def _row_to_friend_request(row: Any) -> FriendRequest:
        return FriendRequest(
            request_id=str(row["request_id"]),
            requester_user_id=str(row["requester_user_id"]),
            requester_public_uid=str(row["requester_public_uid"]),
            requester_nickname=str(row["requester_nickname"]),
            requester_bio=str(row["requester_bio"]),
            requester_avatar_key=_normalize_avatar_key(row["requester_avatar_key"]),
            receiver_user_id=str(row["receiver_user_id"]),
            receiver_public_uid=str(row["receiver_public_uid"]),
            receiver_nickname=str(row["receiver_nickname"]),
            receiver_bio=str(row["receiver_bio"]),
            receiver_avatar_key=_normalize_avatar_key(row["receiver_avatar_key"]),
            message=str(row["message"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            handled_at=None if row["handled_at"] is None else str(row["handled_at"]),
            handled_by_user_id=None if row["handled_by_user_id"] is None else str(row["handled_by_user_id"]),
        )

    @staticmethod
    def _row_to_friendship(row: Any) -> Friendship:
        return Friendship(
            user_low_id=str(row["user_low_id"]),
            user_high_id=str(row["user_high_id"]),
            created_at=str(row["created_at"]),
            source_request_id=None if row["source_request_id"] is None else str(row["source_request_id"]),
        )

    @staticmethod
    def _row_to_cloud_account_binding(row: Any) -> CloudAccountBinding:
        raw_meta = row["meta_json"]
        meta = json.loads(str(raw_meta)) if raw_meta not in (None, "") else {}
        if not isinstance(meta, dict):
            meta = {}
        return CloudAccountBinding.create(
            account_id=str(row["account_id"]),
            user_id=str(row["user_id"]),
            provider=_normalize_cloud_account_provider(str(row["provider"])),
            provider_user_id=str(row["provider_user_id"]),
            display_name=str(row["display_name"]),
            avatar_url=_normalize_cloud_account_optional_text(row["avatar_url"]),
            access_token_ciphertext=str(row["access_token_ciphertext"]),
            refresh_token_ciphertext=str(row["refresh_token_ciphertext"]),
            expires_at=_normalize_cloud_account_optional_text(row["expires_at"]),
            scope=_normalize_cloud_account_scope(row["scope"]),
            meta=meta,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            disabled_at=_normalize_cloud_account_optional_text(row["disabled_at"]),
        )

    @staticmethod
    def _row_to_user_project_daily_study_stat(row: Any) -> UserProjectDailyStudyStat:
        def parse_ranges(key: str) -> tuple[tuple[int, int], ...]:
            try:
                raw = row[key]
            except Exception:
                raw = None
            payload = json.loads(str(raw)) if raw not in (None, "") else []
            if not isinstance(payload, list):
                payload = []
            parsed: list[tuple[int, int] | list[int]] = []
            for item in payload:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    parsed.append((item[0], item[1]))
            return _normalize_study_ranges(parsed)

        def read_optional(key: str, default: Any = 0) -> Any:
            try:
                value = row[key]
            except Exception:
                return default
            return default if value is None else value

        return UserProjectDailyStudyStat(
            user_id=str(row["user_id"]),
            project_id=_normalize_project_id(row["project_id"]),
            date_key=_normalize_study_date_key(row["date_key"]),
            schema_version=max(1, _normalize_study_duration_ms(read_optional("schema_version", 1), field_name="schema_version")),
            web_presence_ms=_normalize_study_duration_ms(read_optional("web_presence_ms", 0), field_name="web_presence_ms"),
            video_ms=_normalize_study_duration_ms(read_optional("video_ms", 0), field_name="video_ms"),
            recall_entry_ms=_normalize_study_duration_ms(read_optional("recall_entry_ms", 0), field_name="recall_entry_ms"),
            ai_qa_ms=_normalize_study_duration_ms(read_optional("ai_qa_ms", 0), field_name="ai_qa_ms"),
            distraction_ms=_normalize_study_duration_ms(read_optional("distraction_ms", 0), field_name="distraction_ms"),
            presence_ranges=parse_ranges("presence_ranges_json"),
            video_ranges=parse_ranges("video_ranges_json"),
            recall_entry_ranges=parse_ranges("recall_entry_ranges_json"),
            ai_qa_ranges=parse_ranges("ai_qa_ranges_json"),
            is_partition_complete=bool(read_optional("is_partition_complete", 0)),
            effective_ms=_normalize_study_duration_ms(row["effective_ms"], field_name="effective_ms"),
            watch_ms=_normalize_study_duration_ms(row["watch_ms"], field_name="watch_ms"),
            compose_ms=_normalize_study_duration_ms(row["compose_ms"], field_name="compose_ms"),
            review_ms=_normalize_study_duration_ms(row["review_ms"], field_name="review_ms"),
            qa_ms=_normalize_study_duration_ms(row["qa_ms"], field_name="qa_ms"),
            effective_ranges=parse_ranges("effective_ranges_json"),
            watch_ranges=parse_ranges("watch_ranges_json"),
            compose_ranges=parse_ranges("compose_ranges_json"),
            review_ranges=parse_ranges("review_ranges_json"),
            qa_ranges=parse_ranges("qa_ranges_json"),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _snapshot_payload(
        *,
        users: list[dict[str, str]],
        sessions: list[dict[str, str]],
        memberships: list[dict[str, str]],
        profiles: list[dict[str, str | None]],
        user_service_configs: list[dict[str, str | None]],
        user_global_settings: list[dict[str, Any]],
        roles: list[dict[str, str]],
        cloud_accounts: list[dict[str, Any]],
        friend_requests: list[dict[str, str | None]],
        friendships: list[dict[str, str | None]],
        admin_action_logs: list[dict[str, str | None]],
    ) -> dict[str, Any]:
        return {
            "users": users,
            "sessions": sessions,
            "projectMemberships": memberships,
            "userProfiles": profiles,
            "userServiceConfigs": user_service_configs,
            "userGlobalSettings": user_global_settings,
            "userGlobalRoles": roles,
            "userCloudAccounts": cloud_accounts,
            "friendRequests": friend_requests,
            "friendships": friendships,
            "adminActionLogs": admin_action_logs,
        }


class SQLiteAuthStore(_AuthStoreImpl):
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = (db_path or resolve_auth_db_path()).expanduser().resolve()
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_unique_public_uid(self, conn: sqlite3.Connection, seed: str | None = None) -> str:
        candidate = _seeded_public_uid(seed) if seed else _random_public_uid()
        while True:
            row = conn.execute("SELECT 1 FROM user_profiles WHERE public_uid = ? LIMIT 1", (candidate,)).fetchone()
            if row is None:
                return candidate
            candidate = _random_public_uid()

    def _backfill_user_profiles(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT u.user_id, u.email, u.created_at
            FROM users u
            LEFT JOIN user_profiles p ON p.user_id = u.user_id
            WHERE p.user_id IS NULL
            ORDER BY u.created_at ASC, u.user_id ASC
            """
        ).fetchall()
        for row in rows:
            email = str(row["email"])
            created_at = str(row["created_at"])
            conn.execute(
                """
                INSERT INTO user_profiles (
                    user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                )
                VALUES (?, ?, ?, '', NULL, 'active', ?, ?)
                """,
                (
                    str(row["user_id"]),
                    self._ensure_unique_public_uid(conn, str(row["user_id"])),
                    _default_nickname_for_email(email),
                    created_at,
                    created_at,
                ),
            )

    def _bootstrap_configured_super_admins_sqlite(self, conn: sqlite3.Connection) -> None:
        configured_emails = _configured_bootstrap_super_admin_emails()
        if not configured_emails:
            return
        placeholders = ", ".join("?" for _ in configured_emails)
        rows = conn.execute(
            f"""
            SELECT user_id, created_at
            FROM users
            WHERE email IN ({placeholders})
            ORDER BY created_at ASC, user_id ASC
            """,
            configured_emails,
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                VALUES (?, 'super_admin', ?, ?)
                """,
                (str(row["user_id"]), str(row["user_id"]), str(row["created_at"])),
            )

    def _roles_by_user_id(self, conn: sqlite3.Connection, user_ids: Iterable[str]) -> dict[str, tuple[str, ...]]:
        ids = tuple(str(user_id) for user_id in user_ids)
        if not ids:
            return {}
        placeholders = ", ".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT user_id, role FROM user_global_roles WHERE user_id IN ({placeholders}) ORDER BY user_id ASC, role ASC",
            ids,
        ).fetchall()
        payload: dict[str, list[str]] = {}
        for row in rows:
            payload.setdefault(str(row["user_id"]), []).append(str(row["role"]))
        return {key: tuple(value) for key, value in payload.items()}

    @staticmethod
    def _ensure_user_service_prompt_assembly_mode_column(conn: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(user_service_configs)").fetchall()
        }
        if "prompt_assembly_mode" in columns:
            return
        conn.execute(
            """
            ALTER TABLE user_service_configs
            ADD COLUMN prompt_assembly_mode TEXT NOT NULL DEFAULT 'system'
            """
        )

    @staticmethod
    def _ensure_users_email_verified_column(conn: sqlite3.Connection) -> bool:
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email_verified_at" in columns:
            return False
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN email_verified_at TEXT
            """
        )
        return True

    @staticmethod
    def _ensure_user_project_daily_study_stats_metric_columns(conn: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(user_project_daily_study_stats)").fetchall()
        }
        definitions = {
            "schema_version": "INTEGER NOT NULL DEFAULT 1",
            "web_presence_ms": "INTEGER NOT NULL DEFAULT 0",
            "video_ms": "INTEGER NOT NULL DEFAULT 0",
            "recall_entry_ms": "INTEGER NOT NULL DEFAULT 0",
            "ai_qa_ms": "INTEGER NOT NULL DEFAULT 0",
            "distraction_ms": "INTEGER NOT NULL DEFAULT 0",
            "presence_ranges_json": "TEXT NOT NULL DEFAULT '[]'",
            "video_ranges_json": "TEXT NOT NULL DEFAULT '[]'",
            "recall_entry_ranges_json": "TEXT NOT NULL DEFAULT '[]'",
            "ai_qa_ranges_json": "TEXT NOT NULL DEFAULT '[]'",
            "is_partition_complete": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, definition in definitions.items():
            if column_name in columns:
                continue
            conn.execute(f"ALTER TABLE user_project_daily_study_stats ADD COLUMN {column_name} {definition}")

    @staticmethod
    def _ensure_email_verification_tokens_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user_expires
            ON email_verification_tokens (user_id, expires_at DESC)
            """
        )

    @staticmethod
    def _backfill_hashed_session_tokens_sqlite(conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT session_token
            FROM sessions
            WHERE session_token IS NOT NULL
              AND session_token <> ''
              AND session_token NOT LIKE 'sha256:%'
            ORDER BY created_at ASC, session_token ASC
            """
        ).fetchall()
        for row in rows:
            legacy_token = str(row["session_token"])
            conn.execute(
                "UPDATE sessions SET session_token = ? WHERE session_token = ?",
                (_hash_session_token(legacy_token), legacy_token),
            )

    @staticmethod
    def _backfill_existing_users_as_verified_sqlite(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE users
            SET email_verified_at = created_at
            WHERE email_verified_at IS NULL OR TRIM(email_verified_at) = ''
            """
        )

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        email_verified_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        session_token TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        token_hash TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS email_verification_tokens (
                        token_hash TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS project_memberships (
                        project_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY(project_id, user_id),
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id TEXT PRIMARY KEY,
                        public_uid TEXT NOT NULL UNIQUE,
                        nickname TEXT NOT NULL,
                        bio TEXT NOT NULL DEFAULT '',
                        avatar_key TEXT,
                        status TEXT NOT NULL DEFAULT 'active',
                        updated_at TEXT NOT NULL,
                        password_changed_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS user_service_configs (
                        user_id TEXT NOT NULL,
                        service_kind TEXT NOT NULL,
                        base_url TEXT NOT NULL,
                        model_name TEXT NOT NULL DEFAULT '',
                        api_key TEXT,
                        prompt_assembly_mode TEXT NOT NULL DEFAULT 'system',
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, service_kind),
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS user_global_settings (
                        user_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL DEFAULT '{}',
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS user_cloud_accounts (
                        account_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        provider_user_id TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        avatar_url TEXT,
                        access_token_ciphertext TEXT NOT NULL,
                        refresh_token_ciphertext TEXT NOT NULL,
                        expires_at TEXT,
                        scope TEXT NOT NULL DEFAULT '',
                        meta_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        disabled_at TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        UNIQUE(user_id, provider, provider_user_id)
                    );

                    CREATE TABLE IF NOT EXISTS user_global_roles (
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        granted_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, role),
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY(granted_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS friend_requests (
                        request_id TEXT PRIMARY KEY,
                        requester_user_id TEXT NOT NULL,
                        receiver_user_id TEXT NOT NULL,
                        message TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        handled_at TEXT,
                        handled_by_user_id TEXT,
                        FOREIGN KEY(requester_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY(receiver_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY(handled_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
                    );

                    CREATE TABLE IF NOT EXISTS friendships (
                        user_low_id TEXT NOT NULL,
                        user_high_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        source_request_id TEXT,
                        PRIMARY KEY(user_low_id, user_high_id),
                        FOREIGN KEY(user_low_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY(user_high_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS admin_action_logs (
                        log_id TEXT PRIMARY KEY,
                        actor_user_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        target_kind TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(actor_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS user_project_daily_study_stats (
                        user_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        date_key TEXT NOT NULL,
                        schema_version INTEGER NOT NULL DEFAULT 1,
                        web_presence_ms INTEGER NOT NULL DEFAULT 0,
                        video_ms INTEGER NOT NULL DEFAULT 0,
                        recall_entry_ms INTEGER NOT NULL DEFAULT 0,
                        ai_qa_ms INTEGER NOT NULL DEFAULT 0,
                        distraction_ms INTEGER NOT NULL DEFAULT 0,
                        presence_ranges_json TEXT NOT NULL DEFAULT '[]',
                        video_ranges_json TEXT NOT NULL DEFAULT '[]',
                        recall_entry_ranges_json TEXT NOT NULL DEFAULT '[]',
                        ai_qa_ranges_json TEXT NOT NULL DEFAULT '[]',
                        is_partition_complete INTEGER NOT NULL DEFAULT 0,
                        effective_ms INTEGER NOT NULL DEFAULT 0,
                        watch_ms INTEGER NOT NULL DEFAULT 0,
                        compose_ms INTEGER NOT NULL DEFAULT 0,
                        review_ms INTEGER NOT NULL DEFAULT 0,
                        qa_ms INTEGER NOT NULL DEFAULT 0,
                        effective_ranges_json TEXT NOT NULL DEFAULT '[]',
                        watch_ranges_json TEXT NOT NULL DEFAULT '[]',
                        compose_ranges_json TEXT NOT NULL DEFAULT '[]',
                        review_ranges_json TEXT NOT NULL DEFAULT '[]',
                        qa_ranges_json TEXT NOT NULL DEFAULT '[]',
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, project_id, date_key),
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_user_profiles_public_uid ON user_profiles (public_uid);
                    CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_expires
                    ON password_reset_tokens (user_id, expires_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user_expires
                    ON email_verification_tokens (user_id, expires_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_user_service_configs_kind ON user_service_configs (service_kind, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_user_global_settings_updated_at ON user_global_settings (updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_user_cloud_accounts_user_provider
                    ON user_cloud_accounts (user_id, provider, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_user_global_roles_role ON user_global_roles (role, user_id);
                    CREATE INDEX IF NOT EXISTS idx_friend_requests_receiver_status
                    ON friend_requests (receiver_user_id, status, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_friend_requests_requester_status
                    ON friend_requests (requester_user_id, status, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_friend_requests_pair_status
                    ON friend_requests (requester_user_id, receiver_user_id, status, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_friendships_user_low_created
                    ON friendships (user_low_id, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_friendships_user_high_created
                    ON friendships (user_high_id, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_admin_action_logs_created_at ON admin_action_logs (created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_user_project_daily_study_stats_user_project_date
                    ON user_project_daily_study_stats (user_id, project_id, date_key DESC);
                    CREATE INDEX IF NOT EXISTS idx_user_project_daily_study_stats_user_date
                    ON user_project_daily_study_stats (user_id, date_key DESC);
                    """
                )
                conn.executescript(
                    """
                    DROP TABLE IF EXISTS study_group_post_comments;
                    DROP TABLE IF EXISTS study_group_join_requests;
                    DROP TABLE IF EXISTS study_group_posts;
                    DROP TABLE IF EXISTS study_group_members;
                    DROP TABLE IF EXISTS study_groups;
                    """
                )
                # Older hosted auth databases may still carry the deprecated study-group tables.
                # Drop them eagerly so upgraded installs converge on the friend-only schema.
                self._ensure_user_service_prompt_assembly_mode_column(conn)
                self._ensure_user_project_daily_study_stats_metric_columns(conn)
                added_email_verified_column = self._ensure_users_email_verified_column(conn)
                self._ensure_email_verification_tokens_table(conn)
                if added_email_verified_column:
                    self._backfill_existing_users_as_verified_sqlite(conn)
                self._backfill_user_profiles(conn)
                self._backfill_hashed_session_tokens_sqlite(conn)
                self._bootstrap_configured_super_admins_sqlite(conn)
                conn.commit()
            finally:
                conn.close()

    def create_user(self, email: str, password: str, *, email_verified: bool = True) -> AuthUser:
        normalized_email = _normalize_email(email)
        now_text = _utc_now().isoformat()
        user_id = f"user_{uuid.uuid4().hex}"
        password_hash = self._hash_password(password)
        email_verified_at = now_text if email_verified else None
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, created_at, email_verified_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, normalized_email, password_hash, now_text, email_verified_at),
                )
                conn.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                    )
                    VALUES (?, ?, ?, '', NULL, 'active', ?, ?)
                    """,
                    (user_id, self._ensure_unique_public_uid(conn), _default_nickname_for_email(normalized_email), now_text, now_text),
                )
                if email_is_bootstrap_super_admin(normalized_email):
                    conn.execute(
                        """
                        INSERT INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        VALUES (?, 'super_admin', ?, ?)
                        """,
                        (user_id, user_id, now_text),
                    )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise PreconditionFailure("email already exists") from exc
            finally:
                conn.close()
        return self.get_user_by_id(user_id)

    def authenticate_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        conn = self._connect()
        try:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}, u.password_hash, u.email_verified_at
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE u.email = ?
                """,
                (normalized_email,),
            ).fetchone()
        finally:
            conn.close()
        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise PreconditionFailure("invalid email or password")
        if str(row["email_verified_at"] or "").strip() == "":
            raise PreconditionFailure("email verification is required before login")
        if str(row["status"]) != "active":
            raise PreconditionFailure("account is not active")
        return self._row_to_user(row)

    def create_session(self, user_id: str) -> str:
        now = _utc_now()
        token = secrets.token_urlsafe(32)
        stored_token = _hash_session_token(token)
        expires_at = (now + timedelta(days=_session_ttl_days())).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO sessions (session_token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (stored_token, str(user_id), now.isoformat(), expires_at),
                )
                conn.commit()
                return token
            finally:
                conn.close()

    def get_user_by_session(self, session_token: str) -> AuthUser:
        candidates = _session_token_lookup_candidates(session_token)
        if not candidates:
            raise NotFound("session")
        now_text = _utc_now().isoformat()
        placeholders = ", ".join("?" for _ in candidates)
        conn = self._connect()
        try:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE s.session_token IN ({placeholders}) AND s.expires_at > ? AND p.status = 'active'
                """,
                (*candidates, now_text),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("session")
        return self._row_to_user(row)

    def delete_session(self, session_token: str) -> None:
        candidates = _session_token_lookup_candidates(session_token)
        if not candidates:
            return
        placeholders = ", ".join("?" for _ in candidates)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"DELETE FROM sessions WHERE session_token IN ({placeholders})", candidates)
                conn.commit()
            finally:
                conn.close()

    def delete_other_sessions_for_user(self, user_id: str, *, except_session_token: str | None = None) -> None:
        with self._lock:
            conn = self._connect()
            try:
                if except_session_token:
                    candidates = _session_token_lookup_candidates(except_session_token)
                    if candidates:
                        placeholders = ", ".join("?" for _ in candidates)
                        conn.execute(
                            f"DELETE FROM sessions WHERE user_id = ? AND session_token NOT IN ({placeholders})",
                            (str(user_id), *candidates),
                        )
                    else:
                        conn.execute("DELETE FROM sessions WHERE user_id = ?", (str(user_id),))
                else:
                    conn.execute("DELETE FROM sessions WHERE user_id = ?", (str(user_id),))
                conn.commit()
            finally:
                conn.close()

    def get_user_by_id(self, user_id: str) -> AuthUser:
        conn = self._connect()
        try:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE u.user_id = ?
                """,
                (str(user_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("user")
        return self._row_to_user(row)

    def user_email_verified(self, user_id: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT email_verified_at
                FROM users
                WHERE user_id = ?
                """,
                (str(user_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("user")
        return bool(str(row["email_verified_at"] or "").strip())

    def get_user_by_public_uid(self, public_uid: str) -> AuthUser:
        normalized_uid = str(public_uid).strip().upper()
        if not normalized_uid:
            raise NotFound("user")
        conn = self._connect()
        try:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE p.public_uid = ?
                """,
                (normalized_uid,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("user")
        return self._row_to_user(row)

    def _get_friend_request(self, conn: sqlite3.Connection, request_id: str) -> FriendRequest:
        row = conn.execute(
            """
            SELECT
                r.request_id,
                r.requester_user_id,
                requester.public_uid AS requester_public_uid,
                requester.nickname AS requester_nickname,
                requester.bio AS requester_bio,
                requester.avatar_key AS requester_avatar_key,
                r.receiver_user_id,
                receiver.public_uid AS receiver_public_uid,
                receiver.nickname AS receiver_nickname,
                receiver.bio AS receiver_bio,
                receiver.avatar_key AS receiver_avatar_key,
                r.message,
                r.status,
                r.created_at,
                r.handled_at,
                r.handled_by_user_id
            FROM friend_requests r
            JOIN user_profiles requester ON requester.user_id = r.requester_user_id
            JOIN user_profiles receiver ON receiver.user_id = r.receiver_user_id
            WHERE r.request_id = ?
            """,
            (str(request_id),),
        ).fetchone()
        if row is None:
            raise NotFound("friend request")
        return self._row_to_friend_request(row)

    def create_friend_request(
        self,
        *,
        requester_user_id: str,
        receiver_user_id: str,
        message: str | None,
    ) -> FriendRequest:
        requester_id = str(requester_user_id)
        receiver_id = str(receiver_user_id)
        if requester_id == receiver_id:
            raise PreconditionFailure("cannot send a friend request to yourself")
        normalized_message = _normalize_friend_request_message(message)
        now_text = _utc_now().isoformat()
        user_low_id, user_high_id = _friend_pair(requester_id, receiver_id)
        with self._lock:
            conn = self._connect()
            try:
                requester = conn.execute(
                    "SELECT status FROM user_profiles WHERE user_id = ?",
                    (requester_id,),
                ).fetchone()
                if requester is None:
                    raise NotFound("user")
                if str(requester["status"]) != "active":
                    raise PreconditionFailure("only active users can send friend requests")

                receiver = conn.execute(
                    "SELECT status FROM user_profiles WHERE user_id = ?",
                    (receiver_id,),
                ).fetchone()
                if receiver is None:
                    raise NotFound("user")
                if str(receiver["status"]) != "active":
                    raise PreconditionFailure("only active users can receive friend requests")

                existing_friendship = conn.execute(
                    "SELECT 1 FROM friendships WHERE user_low_id = ? AND user_high_id = ? LIMIT 1",
                    (user_low_id, user_high_id),
                ).fetchone()
                if existing_friendship is not None:
                    raise PreconditionFailure("users are already friends")

                reverse_request = conn.execute(
                    """
                    SELECT request_id
                    FROM friend_requests
                    WHERE requester_user_id = ? AND receiver_user_id = ? AND status = 'pending'
                    ORDER BY created_at DESC, request_id DESC
                    LIMIT 1
                    """,
                    (receiver_id, requester_id),
                ).fetchone()
                if reverse_request is not None:
                    request_id = str(reverse_request["request_id"])
                    conn.execute(
                        """
                        UPDATE friend_requests
                        SET status = 'accepted', handled_at = ?, handled_by_user_id = ?
                        WHERE request_id = ?
                        """,
                        (now_text, requester_id, request_id),
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_low_id, user_high_id, now_text, request_id),
                    )
                    conn.commit()
                    return self._get_friend_request(conn, request_id)

                duplicate_request = conn.execute(
                    """
                    SELECT 1
                    FROM friend_requests
                    WHERE requester_user_id = ? AND receiver_user_id = ? AND status = 'pending'
                    LIMIT 1
                    """,
                    (requester_id, receiver_id),
                ).fetchone()
                if duplicate_request is not None:
                    raise PreconditionFailure("friend request already pending")

                request_id = f"friend_req_{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO friend_requests (
                        request_id, requester_user_id, receiver_user_id, message, status, created_at, handled_at, handled_by_user_id
                    )
                    VALUES (?, ?, ?, ?, 'pending', ?, NULL, NULL)
                    """,
                    (request_id, requester_id, receiver_id, normalized_message, now_text),
                )
                conn.commit()
                return self._get_friend_request(conn, request_id)
            finally:
                conn.close()

    def list_incoming_friend_requests(self, user_id: str, *, limit: int = 100) -> tuple[FriendRequest, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    r.request_id,
                    r.requester_user_id,
                    requester.public_uid AS requester_public_uid,
                    requester.nickname AS requester_nickname,
                    requester.bio AS requester_bio,
                    requester.avatar_key AS requester_avatar_key,
                    r.receiver_user_id,
                    receiver.public_uid AS receiver_public_uid,
                    receiver.nickname AS receiver_nickname,
                    receiver.bio AS receiver_bio,
                    receiver.avatar_key AS receiver_avatar_key,
                    r.message,
                    r.status,
                    r.created_at,
                    r.handled_at,
                    r.handled_by_user_id
                FROM friend_requests r
                JOIN user_profiles requester ON requester.user_id = r.requester_user_id
                JOIN user_profiles receiver ON receiver.user_id = r.receiver_user_id
                WHERE r.receiver_user_id = ?
                ORDER BY CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END, r.created_at DESC, r.request_id DESC
                LIMIT ?
                """,
                (str(user_id), _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_friend_request(row) for row in rows)

    def list_outgoing_friend_requests(self, user_id: str, *, limit: int = 100) -> tuple[FriendRequest, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    r.request_id,
                    r.requester_user_id,
                    requester.public_uid AS requester_public_uid,
                    requester.nickname AS requester_nickname,
                    requester.bio AS requester_bio,
                    requester.avatar_key AS requester_avatar_key,
                    r.receiver_user_id,
                    receiver.public_uid AS receiver_public_uid,
                    receiver.nickname AS receiver_nickname,
                    receiver.bio AS receiver_bio,
                    receiver.avatar_key AS receiver_avatar_key,
                    r.message,
                    r.status,
                    r.created_at,
                    r.handled_at,
                    r.handled_by_user_id
                FROM friend_requests r
                JOIN user_profiles requester ON requester.user_id = r.requester_user_id
                JOIN user_profiles receiver ON receiver.user_id = r.receiver_user_id
                WHERE r.requester_user_id = ?
                ORDER BY CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END, r.created_at DESC, r.request_id DESC
                LIMIT ?
                """,
                (str(user_id), _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_friend_request(row) for row in rows)

    def accept_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT requester_user_id, receiver_user_id, status
                    FROM friend_requests
                    WHERE request_id = ?
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("friend request")
                if str(row["receiver_user_id"]) != str(actor_user_id):
                    raise PreconditionFailure("only the receiver can accept this friend request")
                if _normalize_friend_request_status(str(row["status"])) != "pending":
                    raise PreconditionFailure("friend request is not pending")

                user_low_id, user_high_id = _friend_pair(str(row["requester_user_id"]), str(row["receiver_user_id"]))
                conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'accepted', handled_at = ?, handled_by_user_id = ?
                    WHERE request_id = ?
                    """,
                    (now_text, str(actor_user_id), str(request_id)),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_low_id, user_high_id, now_text, str(request_id)),
                )
                conn.commit()
                return self._get_friend_request(conn, str(request_id))
            finally:
                conn.close()

    def reject_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT receiver_user_id, status
                    FROM friend_requests
                    WHERE request_id = ?
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("friend request")
                if str(row["receiver_user_id"]) != str(actor_user_id):
                    raise PreconditionFailure("only the receiver can reject this friend request")
                if _normalize_friend_request_status(str(row["status"])) != "pending":
                    raise PreconditionFailure("friend request is not pending")

                conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'rejected', handled_at = ?, handled_by_user_id = ?
                    WHERE request_id = ?
                    """,
                    (now_text, str(actor_user_id), str(request_id)),
                )
                conn.commit()
                return self._get_friend_request(conn, str(request_id))
            finally:
                conn.close()

    def cancel_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT requester_user_id, status
                    FROM friend_requests
                    WHERE request_id = ?
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("friend request")
                if str(row["requester_user_id"]) != str(actor_user_id):
                    raise PreconditionFailure("only the requester can cancel this friend request")
                if _normalize_friend_request_status(str(row["status"])) != "pending":
                    raise PreconditionFailure("friend request is not pending")

                conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'cancelled', handled_at = ?, handled_by_user_id = ?
                    WHERE request_id = ?
                    """,
                    (now_text, str(actor_user_id), str(request_id)),
                )
                conn.commit()
                return self._get_friend_request(conn, str(request_id))
            finally:
                conn.close()

    def list_friends_for_user(self, user_id: str, *, limit: int = 100) -> tuple[FriendListItem, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    counterpart.user_id AS user_id,
                    counterpart.public_uid AS public_uid,
                    counterpart.nickname AS nickname,
                    counterpart.bio AS bio,
                    counterpart.avatar_key AS avatar_key,
                    f.created_at AS friended_at
                FROM friendships f
                JOIN user_profiles counterpart
                    ON counterpart.user_id = CASE
                        WHEN f.user_low_id = ? THEN f.user_high_id
                        ELSE f.user_low_id
                    END
                WHERE f.user_low_id = ? OR f.user_high_id = ?
                ORDER BY f.created_at DESC, counterpart.public_uid ASC
                LIMIT ?
                """,
                (str(user_id), str(user_id), str(user_id), _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_friend_list_item(row) for row in rows)

    def delete_friendship(self, friend_user_id: str, *, actor_user_id: str) -> None:
        actor_id = str(actor_user_id)
        friend_id = str(friend_user_id)
        if actor_id == friend_id:
            raise PreconditionFailure("cannot delete yourself from friends")
        user_low_id, user_high_id = _friend_pair(actor_id, friend_id)
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT 1 FROM friendships WHERE user_low_id = ? AND user_high_id = ? LIMIT 1",
                    (user_low_id, user_high_id),
                ).fetchone()
                if existing is None:
                    raise NotFound("friendship")
                conn.execute(
                    "DELETE FROM friendships WHERE user_low_id = ? AND user_high_id = ?",
                    (user_low_id, user_high_id),
                )
                conn.commit()
            finally:
                conn.close()

    def create_friendship(self, user_a_id: str, user_b_id: str) -> Friendship:
        left = str(user_a_id).strip()
        right = str(user_b_id).strip()
        user_low_id, user_high_id = _friend_pair(left, right)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_low_id, user_high_id, now_text, None),
                )
                row = conn.execute(
                    "SELECT * FROM friendships WHERE user_low_id = ? AND user_high_id = ? LIMIT 1",
                    (user_low_id, user_high_id),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("friendship")
                return self._row_to_friendship(row)
            finally:
                conn.close()

    def users_are_friends(self, user_a_id: str, user_b_id: str) -> bool:
        left = str(user_a_id).strip()
        right = str(user_b_id).strip()
        if not left or not right or left == right:
            return False
        user_low_id, user_high_id = _friend_pair(left, right)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM friendships WHERE user_low_id = ? AND user_high_id = ? LIMIT 1",
                (user_low_id, user_high_id),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def update_user_profile(self, user_id: str, *, nickname: str, bio: str | None) -> AuthUser:
        normalized_nickname = _normalize_nickname(nickname)
        normalized_bio = _normalize_bio(bio)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "UPDATE user_profiles SET nickname = ?, bio = ?, updated_at = ? WHERE user_id = ? RETURNING user_id",
                    (normalized_nickname, normalized_bio, now_text, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("user")
                conn.commit()
            finally:
                conn.close()
        return self.get_user_by_id(user_id)

    def update_user_avatar(self, user_id: str, *, avatar_key: str | None) -> AuthUser:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "UPDATE user_profiles SET avatar_key = ?, updated_at = ? WHERE user_id = ? RETURNING user_id",
                    (_normalize_avatar_key(avatar_key), now_text, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("user")
                conn.commit()
            finally:
                conn.close()
        return self.get_user_by_id(user_id)

    def get_user_service_config(self, user_id: str, *, service_kind: str) -> UserServiceConfig | None:
        normalized_kind = _normalize_service_kind(service_kind)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                FROM user_service_configs
                WHERE user_id = ? AND service_kind = ?
                """,
                (str(user_id), normalized_kind),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_user_service_config(row)

    def upsert_user_service_config(
        self,
        user_id: str,
        *,
        service_kind: str,
        base_url: str,
        model_name: str | None,
        api_key: str | None = None,
        prompt_assembly_mode: str | None = None,
        clear_api_key: bool = False,
    ) -> UserServiceConfig:
        normalized_kind = _normalize_service_kind(service_kind)
        normalized_base_url = _normalize_service_base_url(base_url)
        normalized_model_name = _normalize_service_model_name(model_name)
        normalized_api_key = _normalize_service_api_key(api_key)
        normalized_prompt_assembly_mode = _normalize_service_prompt_assembly_mode(prompt_assembly_mode)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                current = conn.execute(
                    "SELECT api_key FROM user_service_configs WHERE user_id = ? AND service_kind = ?",
                    (str(user_id), normalized_kind),
                ).fetchone()
                if clear_api_key:
                    resolved_api_key: str | None = None
                elif normalized_api_key is not None:
                    resolved_api_key = normalized_api_key
                elif current is not None:
                    resolved_api_key = _normalize_service_api_key(current["api_key"])
                else:
                    resolved_api_key = None
                conn.execute(
                    """
                    INSERT INTO user_service_configs (
                        user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, service_kind) DO UPDATE SET
                        base_url = excluded.base_url,
                        model_name = excluded.model_name,
                        api_key = excluded.api_key,
                        prompt_assembly_mode = excluded.prompt_assembly_mode,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(user_id),
                        normalized_kind,
                        normalized_base_url,
                        normalized_model_name,
                        resolved_api_key,
                        normalized_prompt_assembly_mode,
                        now_text,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        saved = self.get_user_service_config(user_id, service_kind=normalized_kind)
        if saved is None:
            raise NotFound("user_service_config")
        return saved

    def get_user_global_settings(self, user_id: str) -> UserGlobalSettings:
        conn = self._connect()
        try:
            user_row = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (str(user_id),)).fetchone()
            if user_row is None:
                raise NotFound("user")
            row = conn.execute(
                """
                SELECT user_id, payload_json, updated_at
                FROM user_global_settings
                WHERE user_id = ?
                """,
                (str(user_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return self._default_user_global_settings(str(user_id))
        return self._row_to_user_global_settings(row)

    def upsert_user_global_settings(
        self,
        user_id: str,
        *,
        theme: str | None,
        pomodoro_enabled: bool,
        pomodoro_transition_sound_enabled: bool,
        pomodoro_default_focus_prompt: str | None,
        pomodoro_default_break_prompt: str | None,
        pomodoro_micro_breaks: dict[str, Any] | None,
        pomodoro_weekly_schedule: dict[str, Any],
        default_project_review_template: Iterable[dict[str, Any] | tuple[str, int | None] | list[Any]],
        learning_plans: dict[str, Any] | None = None,
    ) -> UserGlobalSettings:
        current = self.get_user_global_settings(user_id)
        normalized_theme = _normalize_user_theme(theme)
        normalized_default_focus_prompt = _normalize_pomodoro_prompt_text(pomodoro_default_focus_prompt)
        normalized_default_break_prompt = _normalize_pomodoro_prompt_text(pomodoro_default_break_prompt)
        normalized_micro_breaks = _normalize_pomodoro_micro_break_settings(pomodoro_micro_breaks)
        normalized_template = _normalize_review_chain_template(default_project_review_template)
        normalized_weekly_schedule = _normalize_pomodoro_weekly_schedule(pomodoro_weekly_schedule)
        normalized_learning_plans = (
            current.learning_plans if learning_plans is None else _normalize_learning_plans_payload(learning_plans)
        )
        payload_json = json.dumps(
            {
                "theme": normalized_theme,
                "pomodoro": {
                    "enabled": bool(pomodoro_enabled),
                    "transitionSoundEnabled": bool(pomodoro_transition_sound_enabled),
                    "defaultFocusPrompt": normalized_default_focus_prompt,
                    "defaultBreakPrompt": normalized_default_break_prompt,
                    "microBreaks": _pomodoro_micro_break_settings_to_json(normalized_micro_breaks),
                    "weeklySchedule": _pomodoro_weekly_schedule_to_json(normalized_weekly_schedule),
                },
                "defaultProjectReviewTemplate": _review_chain_template_to_json(normalized_template),
                "learningPlans": normalized_learning_plans,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                conn.execute(
                    """
                    INSERT INTO user_global_settings (user_id, payload_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (str(user_id), payload_json, now_text),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_user_global_settings(user_id)

    def list_user_cloud_accounts(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> tuple[CloudAccountBinding, ...]:
        normalized_provider = None if provider is None else _normalize_cloud_account_provider(provider)
        conn = self._connect()
        try:
            sql = """
                SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                       access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                       meta_json, created_at, updated_at, disabled_at
                FROM user_cloud_accounts
                WHERE user_id = ?
            """
            params: list[Any] = [str(user_id)]
            if normalized_provider is not None:
                sql += " AND provider = ?"
                params.append(normalized_provider)
            if not include_disabled:
                sql += " AND disabled_at IS NULL"
            sql += " ORDER BY updated_at DESC, account_id ASC"
            rows = conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_cloud_account_binding(row) for row in rows)

    def get_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> CloudAccountBinding:
        normalized_provider = None if provider is None else _normalize_cloud_account_provider(provider)
        conn = self._connect()
        try:
            sql = """
                SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                       access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                       meta_json, created_at, updated_at, disabled_at
                FROM user_cloud_accounts
                WHERE user_id = ? AND account_id = ?
            """
            params: list[Any] = [str(user_id), str(account_id)]
            if normalized_provider is not None:
                sql += " AND provider = ?"
                params.append(normalized_provider)
            if not include_disabled:
                sql += " AND disabled_at IS NULL"
            row = conn.execute(sql, tuple(params)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("cloud account")
        return self._row_to_cloud_account_binding(row)

    def get_cloud_account_by_id(self, account_id: str, *, include_disabled: bool = False) -> CloudAccountBinding:
        conn = self._connect()
        try:
            sql = """
                SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                       access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                       meta_json, created_at, updated_at, disabled_at
                FROM user_cloud_accounts
                WHERE account_id = ?
            """
            params: list[Any] = [str(account_id)]
            if not include_disabled:
                sql += " AND disabled_at IS NULL"
            row = conn.execute(sql, tuple(params)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("cloud account")
        return self._row_to_cloud_account_binding(row)

    def upsert_user_cloud_account(
        self,
        *,
        user_id: str,
        provider: str,
        provider_user_id: str,
        display_name: str,
        avatar_url: str | None,
        access_token_ciphertext: str,
        refresh_token_ciphertext: str,
        expires_at: str | None,
        scope: str = "",
        meta: dict[str, Any] | None = None,
    ) -> CloudAccountBinding:
        normalized_provider = _normalize_cloud_account_provider(provider)
        normalized_provider_user_id = _normalize_cloud_account_text(
            provider_user_id,
            field_name="provider_user_id",
            maximum=200,
        )
        normalized_display_name = _normalize_cloud_account_text(display_name, field_name="display_name", maximum=200)
        normalized_avatar_url = _normalize_cloud_account_optional_text(avatar_url, maximum=2000)
        normalized_scope = _normalize_cloud_account_scope(scope)
        normalized_meta = _normalize_cloud_account_meta(meta)
        encrypted_access_token = _normalize_cloud_account_text(
            access_token_ciphertext,
            field_name="access_token_ciphertext",
            maximum=8192,
        )
        encrypted_refresh_token = _normalize_cloud_account_text(
            refresh_token_ciphertext,
            field_name="refresh_token_ciphertext",
            maximum=8192,
        )
        normalized_expires_at = _normalize_cloud_account_optional_text(expires_at)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                existing = conn.execute(
                    """
                    SELECT account_id, created_at
                    FROM user_cloud_accounts
                    WHERE user_id = ? AND provider = ? AND provider_user_id = ?
                    """,
                    (str(user_id), normalized_provider, normalized_provider_user_id),
                ).fetchone()
                account_id = str(existing["account_id"]) if existing is not None else f"account_{uuid.uuid4().hex}"
                created_at = str(existing["created_at"]) if existing is not None else now_text
                conn.execute(
                    """
                    INSERT INTO user_cloud_accounts (
                        account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                        access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                        meta_json, created_at, updated_at, disabled_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    ON CONFLICT(account_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        avatar_url = excluded.avatar_url,
                        access_token_ciphertext = excluded.access_token_ciphertext,
                        refresh_token_ciphertext = excluded.refresh_token_ciphertext,
                        expires_at = excluded.expires_at,
                        scope = excluded.scope,
                        meta_json = excluded.meta_json,
                        updated_at = excluded.updated_at,
                        disabled_at = NULL
                    """,
                    (
                        account_id,
                        str(user_id),
                        normalized_provider,
                        normalized_provider_user_id,
                        normalized_display_name,
                        normalized_avatar_url,
                        encrypted_access_token,
                        encrypted_refresh_token,
                        normalized_expires_at,
                        normalized_scope,
                        json.dumps(normalized_meta, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                        created_at,
                        now_text,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_user_cloud_account(
            str(user_id),
            account_id=account_id,
            provider=normalized_provider,
            include_disabled=True,
        )

    def disable_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
    ) -> None:
        normalized_provider = None if provider is None else _normalize_cloud_account_provider(provider)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                sql = "UPDATE user_cloud_accounts SET disabled_at = ?, updated_at = ? WHERE user_id = ? AND account_id = ?"
                params: list[Any] = [now_text, now_text, str(user_id), str(account_id)]
                if normalized_provider is not None:
                    sql += " AND provider = ?"
                    params.append(normalized_provider)
                row = conn.execute(sql + " RETURNING account_id", tuple(params)).fetchone()
                if row is None:
                    raise NotFound("cloud account")
                conn.commit()
            finally:
                conn.close()

    def create_password_reset_token(self, email: str) -> str | None:
        normalized_email = _normalize_email(email)
        now = _utc_now()
        now_text = now.isoformat()
        expires_at = (now + timedelta(minutes=_password_reset_token_ttl_minutes())).isoformat()
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_session_token(raw_token)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ?", (now_text,))
                row = conn.execute(
                    f"""
                    SELECT {USER_COLUMNS_SQL}
                    FROM users u
                    JOIN user_profiles p ON p.user_id = u.user_id
                    WHERE u.email = ? AND p.status = 'active' AND u.email_verified_at IS NOT NULL AND TRIM(u.email_verified_at) <> ''
                    """,
                    (normalized_email,),
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None
                conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (str(row["user_id"]),))
                conn.execute(
                    """
                    INSERT INTO password_reset_tokens (token_hash, user_id, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (token_hash, str(row["user_id"]), now_text, expires_at),
                )
                conn.commit()
                return raw_token
            finally:
                conn.close()

    def create_email_verification_token(self, email: str) -> str | None:
        normalized_email = _normalize_email(email)
        now = _utc_now()
        now_text = now.isoformat()
        expires_at = (now + timedelta(minutes=_email_verification_token_ttl_minutes())).isoformat()
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_session_token(raw_token)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM email_verification_tokens WHERE expires_at <= ?", (now_text,))
                row = conn.execute(
                    """
                    SELECT u.user_id
                    FROM users u
                    JOIN user_profiles p ON p.user_id = u.user_id
                    WHERE u.email = ?
                      AND p.status = 'active'
                      AND (u.email_verified_at IS NULL OR TRIM(u.email_verified_at) = '')
                    """,
                    (normalized_email,),
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None
                user_id = str(row["user_id"])
                conn.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
                conn.execute(
                    """
                    INSERT INTO email_verification_tokens (token_hash, user_id, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (token_hash, user_id, now_text, expires_at),
                )
                conn.commit()
                return raw_token
            finally:
                conn.close()

    def verify_email_with_token(self, token: str) -> AuthUser:
        token_hash = _hash_session_token(token)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM email_verification_tokens WHERE expires_at <= ?", (now_text,))
                row = conn.execute(
                    """
                    SELECT evt.user_id
                    FROM email_verification_tokens evt
                    JOIN user_profiles p ON p.user_id = evt.user_id
                    WHERE evt.token_hash = ? AND evt.expires_at > ? AND p.status = 'active'
                    """,
                    (token_hash, now_text),
                ).fetchone()
                if row is None:
                    raise PreconditionFailure("email verification token is invalid or expired")
                user_id = str(row["user_id"])
                conn.execute(
                    "UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE user_id = ?",
                    (now_text, user_id),
                )
                conn.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
                conn.commit()
            finally:
                conn.close()
        return self.get_user_by_id(user_id)

    def reset_password_with_token(self, token: str, *, new_password: str) -> None:
        token_hash = _hash_session_token(token)
        new_hash = self._hash_password(new_password)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ?", (now_text,))
                row = conn.execute(
                    """
                    SELECT pr.user_id
                    FROM password_reset_tokens pr
                    JOIN user_profiles p ON p.user_id = pr.user_id
                    WHERE pr.token_hash = ? AND pr.expires_at > ? AND p.status = 'active'
                    """,
                    (token_hash, now_text),
                ).fetchone()
                if row is None:
                    raise PreconditionFailure("password reset token is invalid or expired")
                user_id = str(row["user_id"])
                conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
                conn.execute(
                    "UPDATE user_profiles SET password_changed_at = ?, updated_at = ? WHERE user_id = ?",
                    (now_text, now_text, user_id),
                )
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
                conn.commit()
            finally:
                conn.close()

    def change_password(self, user_id: str, *, current_password: str, new_password: str) -> None:
        new_hash = self._hash_password(new_password)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
                if row is None:
                    raise NotFound("user")
                if not self._verify_password(current_password, str(row["password_hash"])):
                    raise PreconditionFailure("current password is incorrect")
                conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, str(user_id)))
                conn.execute(
                    "UPDATE user_profiles SET password_changed_at = ?, updated_at = ? WHERE user_id = ?",
                    (now_text, now_text, str(user_id)),
                )
                conn.commit()
            finally:
                conn.close()

    def list_project_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT project_id FROM project_memberships WHERE user_id = ? ORDER BY project_id ASC",
                (str(user_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(str(row["project_id"]) for row in rows)

    def add_project_owner(self, project_id: str, user_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO project_memberships (project_id, user_id, role, created_at)
                    VALUES (?, ?, 'owner', ?)
                    """,
                    (str(project_id), str(user_id), _utc_now().isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

    def remove_project_memberships(self, project_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM project_memberships WHERE project_id = ?", (str(project_id),))
                conn.commit()
            finally:
                conn.close()

    def user_has_project_access(self, user_id: str, project_id: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM project_memberships WHERE project_id = ? AND user_id = ? LIMIT 1",
                (str(project_id), str(user_id)),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def upsert_user_project_daily_study_stats(
        self,
        user_id: str,
        *,
        entries: Iterable[UserProjectDailyStudyStatInput],
    ) -> tuple[UserProjectDailyStudyStat, ...]:
        normalized_entries = tuple(entries)
        if not normalized_entries:
            return tuple()
        now_text = _utc_now().isoformat()
        saved: list[UserProjectDailyStudyStat] = []
        with self._lock:
            conn = self._connect()
            try:
                for entry in normalized_entries:
                    current_row = conn.execute(
                        """
                        SELECT
                            user_id,
                            project_id,
                            date_key,
                            schema_version,
                            web_presence_ms,
                            video_ms,
                            recall_entry_ms,
                            ai_qa_ms,
                            distraction_ms,
                            presence_ranges_json,
                            video_ranges_json,
                            recall_entry_ranges_json,
                            ai_qa_ranges_json,
                            is_partition_complete,
                            effective_ms,
                            watch_ms,
                            compose_ms,
                            review_ms,
                            qa_ms,
                            effective_ranges_json,
                            watch_ranges_json,
                            compose_ranges_json,
                            review_ranges_json,
                            qa_ranges_json,
                            updated_at
                        FROM user_project_daily_study_stats
                        WHERE user_id = ? AND project_id = ? AND date_key = ?
                        """,
                        (str(user_id), entry.project_id, entry.date_key),
                    ).fetchone()
                    current = None if current_row is None else self._row_to_user_project_daily_study_stat(current_row)
                    presence_ranges = _normalize_study_ranges([*(current.presence_ranges if current else ()), *entry.presence_ranges])
                    video_ranges = _normalize_study_ranges([*(current.video_ranges if current else ()), *entry.video_ranges])
                    recall_entry_ranges = _normalize_study_ranges(
                        [*(current.recall_entry_ranges if current else ()), *entry.recall_entry_ranges]
                    )
                    ai_qa_ranges = _normalize_study_ranges([*(current.ai_qa_ranges if current else ()), *entry.ai_qa_ranges])
                    effective_ranges = _normalize_study_ranges(
                        [*(current.effective_ranges if current else ()), *entry.effective_ranges]
                    )
                    watch_ranges = _normalize_study_ranges([*(current.watch_ranges if current else ()), *entry.watch_ranges])
                    compose_ranges = _normalize_study_ranges([*(current.compose_ranges if current else ()), *entry.compose_ranges])
                    review_ranges = _normalize_study_ranges([*(current.review_ranges if current else ()), *entry.review_ranges])
                    qa_ranges = _normalize_study_ranges([*(current.qa_ranges if current else ()), *entry.qa_ranges])
                    merged = UserProjectDailyStudyStat(
                        user_id=str(user_id),
                        project_id=entry.project_id,
                        date_key=entry.date_key,
                        schema_version=max(current.schema_version if current else 1, entry.schema_version),
                        web_presence_ms=_merge_study_metric_value(
                            current.web_presence_ms if current else 0,
                            entry.web_presence_ms,
                            presence_ranges,
                        ),
                        video_ms=_merge_study_metric_value(current.video_ms if current else 0, entry.video_ms, video_ranges),
                        recall_entry_ms=_merge_study_metric_value(
                            current.recall_entry_ms if current else 0,
                            entry.recall_entry_ms,
                            recall_entry_ranges,
                        ),
                        ai_qa_ms=_merge_study_metric_value(current.ai_qa_ms if current else 0, entry.ai_qa_ms, ai_qa_ranges),
                        distraction_ms=max(current.distraction_ms if current else 0, entry.distraction_ms),
                        presence_ranges=presence_ranges,
                        video_ranges=video_ranges,
                        recall_entry_ranges=recall_entry_ranges,
                        ai_qa_ranges=ai_qa_ranges,
                        is_partition_complete=bool(
                            entry.is_partition_complete or (current.is_partition_complete if current else False)
                        ),
                        effective_ms=_merge_study_metric_value(current.effective_ms if current else 0, entry.effective_ms, effective_ranges),
                        watch_ms=max(
                            _merge_study_metric_value(current.watch_ms if current else 0, entry.watch_ms, watch_ranges),
                            _merge_study_metric_value(current.video_ms if current else 0, entry.video_ms, video_ranges),
                        ),
                        compose_ms=max(
                            _merge_study_metric_value(current.compose_ms if current else 0, entry.compose_ms, compose_ranges),
                            _merge_study_metric_value(current.recall_entry_ms if current else 0, entry.recall_entry_ms, recall_entry_ranges),
                        ),
                        review_ms=_merge_study_metric_value(current.review_ms if current else 0, entry.review_ms, review_ranges),
                        qa_ms=max(
                            _merge_study_metric_value(current.qa_ms if current else 0, entry.qa_ms, qa_ranges),
                            _merge_study_metric_value(current.ai_qa_ms if current else 0, entry.ai_qa_ms, ai_qa_ranges),
                        ),
                        effective_ranges=effective_ranges,
                        watch_ranges=watch_ranges,
                        compose_ranges=compose_ranges,
                        review_ranges=review_ranges,
                        qa_ranges=qa_ranges,
                        updated_at=now_text,
                    )
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO user_project_daily_study_stats (
                            user_id,
                            project_id,
                            date_key,
                            schema_version,
                            web_presence_ms,
                            video_ms,
                            recall_entry_ms,
                            ai_qa_ms,
                            distraction_ms,
                            presence_ranges_json,
                            video_ranges_json,
                            recall_entry_ranges_json,
                            ai_qa_ranges_json,
                            is_partition_complete,
                            effective_ms,
                            watch_ms,
                            compose_ms,
                            review_ms,
                            qa_ms,
                            effective_ranges_json,
                            watch_ranges_json,
                            compose_ranges_json,
                            review_ranges_json,
                            qa_ranges_json,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            merged.user_id,
                            merged.project_id,
                            merged.date_key,
                            merged.schema_version,
                            merged.web_presence_ms,
                            merged.video_ms,
                            merged.recall_entry_ms,
                            merged.ai_qa_ms,
                            merged.distraction_ms,
                            json.dumps(merged.presence_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.video_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.recall_entry_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.ai_qa_ranges, ensure_ascii=False, separators=(",", ":")),
                            1 if merged.is_partition_complete else 0,
                            merged.effective_ms,
                            merged.watch_ms,
                            merged.compose_ms,
                            merged.review_ms,
                            merged.qa_ms,
                            json.dumps(merged.effective_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.watch_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.compose_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.review_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.qa_ranges, ensure_ascii=False, separators=(",", ":")),
                            merged.updated_at,
                        ),
                    )
                    saved.append(merged)
                conn.commit()
            finally:
                conn.close()
        return tuple(saved)

    def list_user_project_daily_study_stats(
        self,
        user_id: str,
        *,
        project_ids: Iterable[str],
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[UserProjectDailyStudyStat, ...]:
        normalized_project_ids = tuple(dict.fromkeys(_normalize_project_id(project_id) for project_id in project_ids))
        if not normalized_project_ids:
            return tuple()
        normalized_date_from = None if date_from is None else _normalize_study_date_key(date_from)
        normalized_date_to = None if date_to is None else _normalize_study_date_key(date_to)
        if normalized_date_from and normalized_date_to and normalized_date_from > normalized_date_to:
            raise PreconditionFailure("date_from must be less than or equal to date_to")
        placeholders = ", ".join("?" for _ in normalized_project_ids)
        sql = f"""
            SELECT
                user_id,
                project_id,
                date_key,
                schema_version,
                web_presence_ms,
                video_ms,
                recall_entry_ms,
                ai_qa_ms,
                distraction_ms,
                presence_ranges_json,
                video_ranges_json,
                recall_entry_ranges_json,
                ai_qa_ranges_json,
                is_partition_complete,
                effective_ms,
                watch_ms,
                compose_ms,
                review_ms,
                qa_ms,
                effective_ranges_json,
                watch_ranges_json,
                compose_ranges_json,
                review_ranges_json,
                qa_ranges_json,
                updated_at
            FROM user_project_daily_study_stats
            WHERE user_id = ? AND project_id IN ({placeholders})
        """
        params: list[Any] = [str(user_id), *normalized_project_ids]
        if normalized_date_from is not None:
            sql += " AND date_key >= ?"
            params.append(normalized_date_from)
        if normalized_date_to is not None:
            sql += " AND date_key <= ?"
            params.append(normalized_date_to)
        sql += " ORDER BY date_key ASC, project_id ASC"
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_user_project_daily_study_stat(row) for row in rows)

    def list_user_roles(self, user_id: str) -> tuple[str, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT role FROM user_global_roles WHERE user_id = ? ORDER BY role ASC",
                (str(user_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(str(row["role"]) for row in rows)

    def user_has_global_role(self, user_id: str, roles: Iterable[str]) -> bool:
        normalized_roles = tuple(_normalize_global_role(role) for role in roles)
        if not normalized_roles:
            return False
        placeholders = ", ".join("?" for _ in normalized_roles)
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT 1 FROM user_global_roles WHERE user_id = ? AND role IN ({placeholders}) LIMIT 1",
                (str(user_id), *normalized_roles),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def set_user_global_role(self, user_id: str, *, role: str, enabled: bool, granted_by_user_id: str) -> tuple[str, ...]:
        normalized_role = _normalize_global_role(role)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                if enabled:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (str(user_id), normalized_role, str(granted_by_user_id), now_text),
                    )
                else:
                    if normalized_role == "super_admin":
                        existing = conn.execute(
                            "SELECT 1 FROM user_global_roles WHERE user_id = ? AND role = 'super_admin' LIMIT 1",
                            (str(user_id),),
                        ).fetchone()
                        if existing is not None:
                            count = int(
                                conn.execute(
                                    "SELECT COUNT(*) AS count FROM user_global_roles WHERE role = 'super_admin'"
                                ).fetchone()["count"]
                            )
                            if count <= 1:
                                raise PreconditionFailure("cannot remove the last super_admin")
                    conn.execute(
                        "DELETE FROM user_global_roles WHERE user_id = ? AND role = ?",
                        (str(user_id), normalized_role),
                    )
                conn.commit()
            finally:
                conn.close()
        return self.list_user_roles(user_id)

    def list_users(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        limit: int = 100,
    ) -> tuple[AdminUser, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(u.email LIKE ? OR p.nickname LIKE ? OR p.public_uid LIKE ?)")
            params.extend((needle, needle, needle.upper()))
        if status and str(status).strip():
            clauses.append("p.status = ?")
            params.append(_normalize_user_status(status))
        normalized_role = _normalize_user_role_filter(role)
        if normalized_role == "none":
            clauses.append("NOT EXISTS (SELECT 1 FROM user_global_roles ugr WHERE ugr.user_id = u.user_id)")
        elif normalized_role:
            clauses.append("EXISTS (SELECT 1 FROM user_global_roles ugr WHERE ugr.user_id = u.user_id AND ugr.role = ?)")
            params.append(normalized_role)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE {' AND '.join(clauses)}
                ORDER BY u.created_at DESC, u.user_id ASC
                LIMIT ?
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
            roles_by_user_id = self._roles_by_user_id(conn, (str(row["user_id"]) for row in rows))
        finally:
            conn.close()
        payload: list[AdminUser] = []
        for row in rows:
            user = self._row_to_user(row)
            payload.append(
                AdminUser(
                    user_id=user.user_id,
                    email=user.email,
                    created_at=user.created_at,
                    public_uid=user.public_uid,
                    nickname=user.nickname,
                    bio=user.bio,
                    avatar_key=user.avatar_key,
                    status=user.status,
                    updated_at=user.updated_at,
                    roles=roles_by_user_id.get(user.user_id, ()),
                )
            )
        return tuple(payload)

    def set_user_status(self, user_id: str, *, status: str) -> AuthUser:
        normalized_status = _normalize_user_status(status)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "UPDATE user_profiles SET status = ?, updated_at = ? WHERE user_id = ? RETURNING user_id",
                    (normalized_status, now_text, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("user")
                if normalized_status != "active":
                    conn.execute("DELETE FROM sessions WHERE user_id = ?", (str(user_id),))
                conn.commit()
            finally:
                conn.close()
        return self.get_user_by_id(user_id)

    def get_admin_overview(self) -> dict[str, int]:
        conn = self._connect()
        try:
            users = int(conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"])
            active_users = int(conn.execute("SELECT COUNT(*) AS count FROM user_profiles WHERE status = 'active'").fetchone()["count"])
            study_users = int(
                conn.execute(
                    "SELECT COUNT(DISTINCT user_id) AS count FROM user_project_daily_study_stats WHERE effective_ms > 0"
                ).fetchone()["count"]
            )
            study_users_7d = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) AS count
                    FROM user_project_daily_study_stats
                    WHERE effective_ms > 0 AND updated_at >= ?
                    """,
                    ((_utc_now() - timedelta(days=7)).isoformat(),),
                ).fetchone()["count"]
            )
            study_totals_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(effective_ms), 0) AS effective_ms,
                    COALESCE(SUM(watch_ms), 0) AS watch_ms,
                    COALESCE(SUM(compose_ms), 0) AS compose_ms,
                    COALESCE(SUM(review_ms), 0) AS review_ms,
                    COALESCE(SUM(qa_ms), 0) AS qa_ms
                FROM user_project_daily_study_stats
                """
            ).fetchone()
        finally:
            conn.close()
        return {
            "users": users,
            "activeUsers": active_users,
            "studyUsers": study_users,
            "studyUsers7d": study_users_7d,
            "effectiveStudyMs": int(study_totals_row["effective_ms"]) if study_totals_row is not None else 0,
            "watchMs": int(study_totals_row["watch_ms"]) if study_totals_row is not None else 0,
            "composeMs": int(study_totals_row["compose_ms"]) if study_totals_row is not None else 0,
            "reviewMs": int(study_totals_row["review_ms"]) if study_totals_row is not None else 0,
            "qaMs": int(study_totals_row["qa_ms"]) if study_totals_row is not None else 0,
        }

    def record_admin_action(
        self,
        *,
        actor_user_id: str,
        action_type: str,
        target_kind: str,
        target_id: str,
        summary: str,
    ) -> AdminActionLog:
        normalized_action_type = _normalize_admin_action_field(action_type, field_name="action type", maximum=80)
        normalized_target_kind = _normalize_admin_action_field(target_kind, field_name="target kind", maximum=80)
        normalized_target_id = _normalize_admin_action_field(target_id, field_name="target id", maximum=120)
        normalized_summary = _normalize_admin_action_field(summary, field_name="summary", maximum=500)
        log_id = f"adminlog_{uuid.uuid4().hex}"
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO admin_action_logs (
                        log_id, actor_user_id, action_type, target_kind, target_id, summary, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log_id,
                        str(actor_user_id),
                        normalized_action_type,
                        normalized_target_kind,
                        normalized_target_id,
                        normalized_summary,
                        now_text,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        logs = self.list_admin_action_logs(limit=50)
        for item in logs:
            if item.log_id == log_id:
                return item
        raise NotFound("admin_action_log")

    def list_admin_action_logs(self, *, limit: int = 100) -> tuple[AdminActionLog, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    l.log_id,
                    l.actor_user_id,
                    p.public_uid AS actor_public_uid,
                    p.nickname AS actor_nickname,
                    p.avatar_key AS actor_avatar_key,
                    l.action_type,
                    l.target_kind,
                    l.target_id,
                    l.summary,
                    l.created_at
                FROM admin_action_logs l
                JOIN user_profiles p ON p.user_id = l.actor_user_id
                ORDER BY l.created_at DESC, l.log_id DESC
                LIMIT ?
                """,
                (_normalize_limit(limit),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_admin_action_log(row) for row in rows)


    def export_snapshot(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            users = [
                {
                    "userId": str(row["user_id"]),
                    "email": str(row["email"]),
                    "passwordHash": str(row["password_hash"]),
                    "createdAt": str(row["created_at"]),
                    "emailVerifiedAt": None if row["email_verified_at"] is None else str(row["email_verified_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, email, password_hash, created_at, email_verified_at
                    FROM users
                    ORDER BY created_at ASC, user_id ASC
                    """
                ).fetchall()
            ]
            sessions = [
                {
                    "sessionToken": str(row["session_token"]),
                    "userId": str(row["user_id"]),
                    "createdAt": str(row["created_at"]),
                    "expiresAt": str(row["expires_at"]),
                }
                for row in conn.execute(
                    "SELECT session_token, user_id, created_at, expires_at FROM sessions ORDER BY session_token ASC"
                ).fetchall()
            ]
            memberships = [
                {
                    "projectId": str(row["project_id"]),
                    "userId": str(row["user_id"]),
                    "role": str(row["role"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT project_id, user_id, role, created_at
                    FROM project_memberships
                    ORDER BY project_id ASC, user_id ASC
                    """
                ).fetchall()
            ]
            profiles = [
                {
                    "userId": str(row["user_id"]),
                    "publicUid": str(row["public_uid"]),
                    "nickname": str(row["nickname"]),
                    "bio": str(row["bio"]),
                    "avatarKey": None if row["avatar_key"] is None else str(row["avatar_key"]),
                    "status": str(row["status"]),
                    "updatedAt": str(row["updated_at"]),
                    "passwordChangedAt": str(row["password_changed_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                    FROM user_profiles
                    ORDER BY user_id ASC
                    """
                ).fetchall()
            ]
            user_service_configs = [
                {
                    "userId": str(row["user_id"]),
                    "serviceKind": str(row["service_kind"]),
                    "baseUrl": str(row["base_url"]),
                    "modelName": str(row["model_name"]),
                    "apiKey": None if row["api_key"] is None else str(row["api_key"]),
                    "promptAssemblyMode": _normalize_service_prompt_assembly_mode(row["prompt_assembly_mode"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                    FROM user_service_configs
                    ORDER BY user_id ASC, service_kind ASC
                    """
                ).fetchall()
            ]
            cloud_accounts = [
                {
                    "accountId": str(row["account_id"]),
                    "userId": str(row["user_id"]),
                    "provider": str(row["provider"]),
                    "providerUserId": str(row["provider_user_id"]),
                    "displayName": str(row["display_name"]),
                    "avatarUrl": None if row["avatar_url"] is None else str(row["avatar_url"]),
                    "accessTokenCiphertext": str(row["access_token_ciphertext"]),
                    "refreshTokenCiphertext": str(row["refresh_token_ciphertext"]),
                    "expiresAt": None if row["expires_at"] is None else str(row["expires_at"]),
                    "scope": str(row["scope"]),
                    "meta": json.loads(str(row["meta_json"]) if row["meta_json"] is not None else "{}"),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                    "disabledAt": None if row["disabled_at"] is None else str(row["disabled_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                           access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                           meta_json, created_at, updated_at, disabled_at
                    FROM user_cloud_accounts
                    ORDER BY user_id ASC, provider ASC, updated_at DESC, account_id ASC
                    """
                ).fetchall()
            ]
            user_global_settings = [
                {
                    "userId": str(row["user_id"]),
                    "payloadJson": str(row["payload_json"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, payload_json, updated_at
                    FROM user_global_settings
                    ORDER BY user_id ASC
                    """
                ).fetchall()
            ]
            roles = [
                {
                    "userId": str(row["user_id"]),
                    "role": str(row["role"]),
                    "grantedByUserId": str(row["granted_by_user_id"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    "SELECT user_id, role, granted_by_user_id, created_at FROM user_global_roles ORDER BY user_id ASC, role ASC"
                ).fetchall()
            ]
            friend_requests = [
                {
                    "requestId": str(row["request_id"]),
                    "requesterUserId": str(row["requester_user_id"]),
                    "receiverUserId": str(row["receiver_user_id"]),
                    "message": str(row["message"]),
                    "status": str(row["status"]),
                    "createdAt": str(row["created_at"]),
                    "handledAt": None if row["handled_at"] is None else str(row["handled_at"]),
                    "handledByUserId": None if row["handled_by_user_id"] is None else str(row["handled_by_user_id"]),
                }
                for row in conn.execute(
                    """
                    SELECT request_id, requester_user_id, receiver_user_id, message, status, created_at, handled_at, handled_by_user_id
                    FROM friend_requests
                    ORDER BY created_at ASC, request_id ASC
                    """
                ).fetchall()
            ]
            friendships = [
                {
                    "userLowId": str(row["user_low_id"]),
                    "userHighId": str(row["user_high_id"]),
                    "createdAt": str(row["created_at"]),
                    "sourceRequestId": None if row["source_request_id"] is None else str(row["source_request_id"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_low_id, user_high_id, created_at, source_request_id
                    FROM friendships
                    ORDER BY created_at ASC, user_low_id ASC, user_high_id ASC
                    """
                ).fetchall()
            ]
            admin_action_logs = [
                {
                    "logId": str(row["log_id"]),
                    "actorUserId": str(row["actor_user_id"]),
                    "actionType": str(row["action_type"]),
                    "targetKind": str(row["target_kind"]),
                    "targetId": str(row["target_id"]),
                    "summary": str(row["summary"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT log_id, actor_user_id, action_type, target_kind, target_id, summary, created_at
                    FROM admin_action_logs
                    ORDER BY created_at ASC, log_id ASC
                    """
                ).fetchall()
            ]
            return self._snapshot_payload(
                users=users,
                sessions=sessions,
                memberships=memberships,
                profiles=profiles,
                user_service_configs=user_service_configs,
                user_global_settings=user_global_settings,
                roles=roles,
                cloud_accounts=cloud_accounts,
                friend_requests=friend_requests,
                friendships=friendships,
                admin_action_logs=admin_action_logs,
            )
        finally:
            conn.close()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        profiles = list(snapshot.get("userProfiles", []))
        user_service_configs = list(snapshot.get("userServiceConfigs", []))
        user_global_settings = list(snapshot.get("userGlobalSettings", []))
        roles = list(snapshot.get("userGlobalRoles", []))
        cloud_accounts = list(snapshot.get("userCloudAccounts", []))
        friend_requests = list(snapshot.get("friendRequests", []))
        friendships = list(snapshot.get("friendships", []))
        admin_action_logs = list(snapshot.get("adminActionLogs", []))
        with self._lock:
            conn = self._connect()
            try:
                if replace:
                    conn.execute("DELETE FROM admin_action_logs")
                    conn.execute("DELETE FROM friendships")
                    conn.execute("DELETE FROM friend_requests")
                    conn.execute("DELETE FROM user_global_roles")
                    conn.execute("DELETE FROM user_cloud_accounts")
                    conn.execute("DELETE FROM user_global_settings")
                    conn.execute("DELETE FROM user_service_configs")
                    conn.execute("DELETE FROM project_memberships")
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM user_profiles")
                    conn.execute("DELETE FROM users")
                for item in users:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO users (user_id, email, password_hash, created_at, email_verified_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("email", "")),
                            str(row.get("passwordHash", "")),
                            str(row.get("createdAt", "")),
                            row.get("emailVerifiedAt", row.get("createdAt")),
                        ),
                    )
                for item in profiles:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_profiles (
                            user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("publicUid", "")),
                            str(row.get("nickname", "")) or "user",
                            str(row.get("bio", "")),
                            _normalize_avatar_key(row.get("avatarKey")),
                            str(row.get("status", "active") or "active"),
                            str(row.get("updatedAt", row.get("passwordChangedAt", ""))),
                            str(row.get("passwordChangedAt", row.get("updatedAt", ""))),
                        ),
                    )
                if not profiles:
                    self._backfill_user_profiles(conn)
                for item in user_service_configs:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_service_configs (
                            user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("userId", "")),
                            _normalize_service_kind(str(row.get("serviceKind", ""))),
                            _normalize_service_base_url(str(row.get("baseUrl", ""))),
                            _normalize_service_model_name(row.get("modelName")),
                            _normalize_service_api_key(row.get("apiKey")),
                            _normalize_service_prompt_assembly_mode(row.get("promptAssemblyMode")),
                            str(row.get("updatedAt", "")),
                        ),
                    )
                for item in user_global_settings:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO user_global_settings (user_id, payload_json, updated_at)
                        VALUES (?, ?, ?)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("payloadJson", "{}") or "{}"),
                            str(row.get("updatedAt", "")),
                        ),
                    )
                for item in cloud_accounts:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_cloud_accounts (
                            account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                            access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                            meta_json, created_at, updated_at, disabled_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("accountId", "")),
                            str(row.get("userId", "")),
                            _normalize_cloud_account_provider(str(row.get("provider", ""))),
                            _normalize_cloud_account_text(row.get("providerUserId"), field_name="provider_user_id", maximum=200),
                            _normalize_cloud_account_text(row.get("displayName"), field_name="display_name", maximum=200),
                            _normalize_cloud_account_optional_text(row.get("avatarUrl"), maximum=2000),
                            _normalize_cloud_account_text(
                                row.get("accessTokenCiphertext"),
                                field_name="access_token_ciphertext",
                                maximum=8192,
                            ),
                            _normalize_cloud_account_text(
                                row.get("refreshTokenCiphertext"),
                                field_name="refresh_token_ciphertext",
                                maximum=8192,
                            ),
                            _normalize_cloud_account_optional_text(row.get("expiresAt")),
                            _normalize_cloud_account_scope(row.get("scope")),
                            json.dumps(
                                _normalize_cloud_account_meta(
                                    row.get("meta") if isinstance(row.get("meta"), dict) else None
                                ),
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", "")),
                            _normalize_cloud_account_optional_text(row.get("disabledAt")),
                        ),
                    )
                for item in roles:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("role", "admin")),
                            str(row.get("grantedByUserId", row.get("userId", ""))),
                            str(row.get("createdAt", "")),
                        ),
                    )
                if not roles:
                    self._bootstrap_configured_super_admins_sqlite(conn)
                for item in sessions:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO sessions (session_token, user_id, created_at, expires_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            _stored_session_token_value(row.get("sessionToken", "")),
                            str(row.get("userId", "")),
                            str(row.get("createdAt", "")),
                            str(row.get("expiresAt", "")),
                        ),
                    )
                for item in memberships:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO project_memberships (project_id, user_id, role, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("userId", "")),
                            str(row.get("role", "owner") or "owner"),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in friend_requests:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO friend_requests (
                            request_id, requester_user_id, receiver_user_id, message, status, created_at, handled_at, handled_by_user_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("requestId", "")),
                            str(row.get("requesterUserId", "")),
                            str(row.get("receiverUserId", "")),
                            str(row.get("message", "")),
                            str(row.get("status", "pending")),
                            str(row.get("createdAt", "")),
                            row.get("handledAt"),
                            row.get("handledByUserId"),
                        ),
                    )
                for item in friendships:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(row.get("userLowId", "")),
                            str(row.get("userHighId", "")),
                            str(row.get("createdAt", "")),
                            row.get("sourceRequestId"),
                        ),
                    )
                for item in admin_action_logs:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO admin_action_logs (
                            log_id, actor_user_id, action_type, target_kind, target_id, summary, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("logId", "")),
                            str(row.get("actorUserId", "")),
                            str(row.get("actionType", "")),
                            str(row.get("targetKind", "")),
                            str(row.get("targetId", "")),
                            str(row.get("summary", "")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    def healthcheck(self) -> dict[str, object]:
        try:
            conn = self._connect()
            try:
                row = conn.execute("SELECT 1 AS ok").fetchone()
            finally:
                conn.close()
            return {
                "ok": bool(row is not None and int(row["ok"]) == 1),
                "backend": "sqlite",
                "location": self.db_path.as_posix(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "backend": "sqlite",
                "location": self.db_path.as_posix(),
                "error": str(exc),
            }


class PostgresAuthStore(_AuthStoreImpl):
    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn).strip()
        if not self._dsn:
            raise ValueError("PostgreSQL DSN must be non-empty")
        self._lock = threading.Lock()
        self._pool = get_postgres_pool(self._dsn)
        self._init_db()

    def _connect(self):
        return self._pool.connection()

    def _ensure_unique_public_uid(self, conn, seed: str | None = None) -> str:
        candidate = _seeded_public_uid(seed) if seed else _random_public_uid()
        while True:
            row = conn.execute("SELECT 1 FROM user_profiles WHERE public_uid = %s LIMIT 1", (candidate,)).fetchone()
            if row is None:
                return candidate
            candidate = _random_public_uid()

    def _bootstrap_configured_super_admins_postgres(self, conn) -> None:
        configured_emails = _configured_bootstrap_super_admin_emails()
        if not configured_emails:
            return
        rows = conn.execute(
            """
            SELECT user_id, created_at
            FROM users
            WHERE email = ANY(%s)
            ORDER BY created_at ASC, user_id ASC
            """,
            (list(configured_emails),),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                VALUES (%s, 'super_admin', %s, %s)
                ON CONFLICT(user_id, role) DO NOTHING
                """,
                (str(row["user_id"]), str(row["user_id"]), str(row["created_at"])),
            )

    @staticmethod
    def _backfill_hashed_session_tokens_postgres(conn) -> None:
        rows = conn.execute(
            """
            SELECT session_token
            FROM sessions
            WHERE session_token IS NOT NULL
              AND session_token <> ''
              AND session_token NOT LIKE 'sha256:%'
            ORDER BY created_at ASC, session_token ASC
            """
        ).fetchall()
        for row in rows:
            legacy_token = str(row["session_token"])
            conn.execute(
                "UPDATE sessions SET session_token = %s WHERE session_token = %s",
                (_hash_session_token(legacy_token), legacy_token),
            )

    def _roles_by_user_id(self, conn, user_ids: Iterable[str]) -> dict[str, tuple[str, ...]]:
        ids = tuple(str(user_id) for user_id in user_ids)
        if not ids:
            return {}
        rows = conn.execute(
            "SELECT user_id, role FROM user_global_roles WHERE user_id = ANY(%s) ORDER BY user_id ASC, role ASC",
            (list(ids),),
        ).fetchall()
        payload: dict[str, list[str]] = {}
        for row in rows:
            payload.setdefault(str(row["user_id"]), []).append(str(row["role"]))
        return {key: tuple(value) for key, value in payload.items()}

    def _init_db(self) -> None:
        with self._lock:
            validate_postgres_migration_plan()
            conn = self._pool.acquire()
            try:
                apply_postgres_migrations(conn, target="auth")
                self._backfill_hashed_session_tokens_postgres(conn)
                conn.commit()
            finally:
                self._pool.release(conn)

    @staticmethod
    def _migration_health_error(status: dict[str, object]) -> str | None:
        conflicts = list(status.get("conflicts", []))
        if conflicts:
            item = conflicts[0]
            if isinstance(item, dict):
                return (
                    "Conflicting PostgreSQL auth migrations detected for "
                    f"{item.get('scope')}:{item.get('version')}"
                )
            return "Conflicting PostgreSQL auth migrations detected"
        pending = list(status.get("pending", []))
        if pending:
            item = pending[0]
            if isinstance(item, dict):
                return f"Pending PostgreSQL auth migration {item.get('scope')}:{item.get('version')}"
            return "Pending PostgreSQL auth migrations detected"
        return None

    def create_user(self, email: str, password: str, *, email_verified: bool = True) -> AuthUser:
        normalized_email = _normalize_email(email)
        now_text = _utc_now().isoformat()
        user_id = f"user_{uuid.uuid4().hex}"
        password_hash = self._hash_password(password)
        email_verified_at = now_text if email_verified else None
        with self._lock:
            conn = self._pool.acquire()
            try:
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, created_at, email_verified_at) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, normalized_email, password_hash, now_text, email_verified_at),
                )
                conn.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                    )
                    VALUES (%s, %s, %s, '', NULL, 'active', %s, %s)
                    """,
                    (user_id, self._ensure_unique_public_uid(conn), _default_nickname_for_email(normalized_email), now_text, now_text),
                )
                if email_is_bootstrap_super_admin(normalized_email):
                    conn.execute(
                        """
                        INSERT INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        VALUES (%s, 'super_admin', %s, %s)
                        """,
                        (user_id, user_id, now_text),
                    )
                conn.commit()
            except _require_psycopg().IntegrityError as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise PreconditionFailure("email already exists") from exc
            finally:
                self._pool.release(conn)
        return self.get_user_by_id(user_id)

    def authenticate_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}, u.password_hash, u.email_verified_at
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE u.email = %s
                """,
                (normalized_email,),
            ).fetchone()
        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise PreconditionFailure("invalid email or password")
        if str(row["email_verified_at"] or "").strip() == "":
            raise PreconditionFailure("email verification is required before login")
        if str(row["status"]) != "active":
            raise PreconditionFailure("account is not active")
        return self._row_to_user(row)

    def create_session(self, user_id: str) -> str:
        now = _utc_now()
        token = secrets.token_urlsafe(32)
        stored_token = _hash_session_token(token)
        expires_at = (now + timedelta(days=_session_ttl_days())).isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO sessions (session_token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                    (stored_token, str(user_id), now.isoformat(), expires_at),
                )
                conn.commit()
                return token

    def get_user_by_session(self, session_token: str) -> AuthUser:
        candidates = _session_token_lookup_candidates(session_token)
        if not candidates:
            raise NotFound("session")
        now_text = _utc_now().isoformat()
        placeholders = ", ".join("%s" for _ in candidates)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE s.session_token IN ({placeholders}) AND s.expires_at > %s AND p.status = 'active'
                """,
                (*candidates, now_text),
            ).fetchone()
        if row is None:
            raise NotFound("session")
        return self._row_to_user(row)

    def delete_session(self, session_token: str) -> None:
        candidates = _session_token_lookup_candidates(session_token)
        if not candidates:
            return
        placeholders = ", ".join("%s" for _ in candidates)
        with self._lock:
            with self._connect() as conn:
                conn.execute(f"DELETE FROM sessions WHERE session_token IN ({placeholders})", candidates)
                conn.commit()

    def delete_other_sessions_for_user(self, user_id: str, *, except_session_token: str | None = None) -> None:
        with self._lock:
            with self._connect() as conn:
                if except_session_token:
                    candidates = _session_token_lookup_candidates(except_session_token)
                    if candidates:
                        placeholders = ", ".join("%s" for _ in candidates)
                        conn.execute(
                            f"DELETE FROM sessions WHERE user_id = %s AND session_token NOT IN ({placeholders})",
                            (str(user_id), *candidates),
                        )
                    else:
                        conn.execute("DELETE FROM sessions WHERE user_id = %s", (str(user_id),))
                else:
                    conn.execute("DELETE FROM sessions WHERE user_id = %s", (str(user_id),))
                conn.commit()

    def get_user_by_id(self, user_id: str) -> AuthUser:
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE u.user_id = %s
                """,
                (str(user_id),),
            ).fetchone()
        if row is None:
            raise NotFound("user")
        return self._row_to_user(row)

    def user_email_verified(self, user_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT email_verified_at
                FROM users
                WHERE user_id = %s
                """,
                (str(user_id),),
            ).fetchone()
        if row is None:
            raise NotFound("user")
        return bool(str(row["email_verified_at"] or "").strip())

    def get_user_by_public_uid(self, public_uid: str) -> AuthUser:
        normalized_uid = str(public_uid).strip().upper()
        if not normalized_uid:
            raise NotFound("user")
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE p.public_uid = %s
                """,
                (normalized_uid,),
            ).fetchone()
        if row is None:
            raise NotFound("user")
        return self._row_to_user(row)

    def _get_friend_request(self, conn, request_id: str) -> FriendRequest:
        row = conn.execute(
            """
            SELECT
                r.request_id,
                r.requester_user_id,
                requester.public_uid AS requester_public_uid,
                requester.nickname AS requester_nickname,
                requester.bio AS requester_bio,
                requester.avatar_key AS requester_avatar_key,
                r.receiver_user_id,
                receiver.public_uid AS receiver_public_uid,
                receiver.nickname AS receiver_nickname,
                receiver.bio AS receiver_bio,
                receiver.avatar_key AS receiver_avatar_key,
                r.message,
                r.status,
                r.created_at,
                r.handled_at,
                r.handled_by_user_id
            FROM friend_requests r
            JOIN user_profiles requester ON requester.user_id = r.requester_user_id
            JOIN user_profiles receiver ON receiver.user_id = r.receiver_user_id
            WHERE r.request_id = %s
            """,
            (str(request_id),),
        ).fetchone()
        if row is None:
            raise NotFound("friend request")
        return self._row_to_friend_request(row)

    def create_friend_request(
        self,
        *,
        requester_user_id: str,
        receiver_user_id: str,
        message: str | None,
    ) -> FriendRequest:
        requester_id = str(requester_user_id)
        receiver_id = str(receiver_user_id)
        if requester_id == receiver_id:
            raise PreconditionFailure("cannot send a friend request to yourself")
        normalized_message = _normalize_friend_request_message(message)
        now_text = _utc_now().isoformat()
        user_low_id, user_high_id = _friend_pair(requester_id, receiver_id)
        with self._lock:
            with self._connect() as conn:
                requester = conn.execute(
                    "SELECT status FROM user_profiles WHERE user_id = %s",
                    (requester_id,),
                ).fetchone()
                if requester is None:
                    raise NotFound("user")
                if str(requester["status"]) != "active":
                    raise PreconditionFailure("only active users can send friend requests")

                receiver = conn.execute(
                    "SELECT status FROM user_profiles WHERE user_id = %s",
                    (receiver_id,),
                ).fetchone()
                if receiver is None:
                    raise NotFound("user")
                if str(receiver["status"]) != "active":
                    raise PreconditionFailure("only active users can receive friend requests")

                existing_friendship = conn.execute(
                    "SELECT 1 FROM friendships WHERE user_low_id = %s AND user_high_id = %s LIMIT 1",
                    (user_low_id, user_high_id),
                ).fetchone()
                if existing_friendship is not None:
                    raise PreconditionFailure("users are already friends")

                reverse_request = conn.execute(
                    """
                    SELECT request_id
                    FROM friend_requests
                    WHERE requester_user_id = %s AND receiver_user_id = %s AND status = 'pending'
                    ORDER BY created_at DESC, request_id DESC
                    LIMIT 1
                    """,
                    (receiver_id, requester_id),
                ).fetchone()
                if reverse_request is not None:
                    request_id = str(reverse_request["request_id"])
                    conn.execute(
                        """
                        UPDATE friend_requests
                        SET status = 'accepted', handled_at = %s, handled_by_user_id = %s
                        WHERE request_id = %s
                        """,
                        (now_text, requester_id, request_id),
                    )
                    conn.execute(
                        """
                        INSERT INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(user_low_id, user_high_id) DO NOTHING
                        """,
                        (user_low_id, user_high_id, now_text, request_id),
                    )
                    conn.commit()
                    return self._get_friend_request(conn, request_id)

                duplicate_request = conn.execute(
                    """
                    SELECT 1
                    FROM friend_requests
                    WHERE requester_user_id = %s AND receiver_user_id = %s AND status = 'pending'
                    LIMIT 1
                    """,
                    (requester_id, receiver_id),
                ).fetchone()
                if duplicate_request is not None:
                    raise PreconditionFailure("friend request already pending")

                request_id = f"friend_req_{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO friend_requests (
                        request_id, requester_user_id, receiver_user_id, message, status, created_at, handled_at, handled_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, 'pending', %s, NULL, NULL)
                    """,
                    (request_id, requester_id, receiver_id, normalized_message, now_text),
                )
                conn.commit()
                return self._get_friend_request(conn, request_id)

    def list_incoming_friend_requests(self, user_id: str, *, limit: int = 100) -> tuple[FriendRequest, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    r.request_id,
                    r.requester_user_id,
                    requester.public_uid AS requester_public_uid,
                    requester.nickname AS requester_nickname,
                    requester.bio AS requester_bio,
                    requester.avatar_key AS requester_avatar_key,
                    r.receiver_user_id,
                    receiver.public_uid AS receiver_public_uid,
                    receiver.nickname AS receiver_nickname,
                    receiver.bio AS receiver_bio,
                    receiver.avatar_key AS receiver_avatar_key,
                    r.message,
                    r.status,
                    r.created_at,
                    r.handled_at,
                    r.handled_by_user_id
                FROM friend_requests r
                JOIN user_profiles requester ON requester.user_id = r.requester_user_id
                JOIN user_profiles receiver ON receiver.user_id = r.receiver_user_id
                WHERE r.receiver_user_id = %s
                ORDER BY CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END, r.created_at DESC, r.request_id DESC
                LIMIT %s
                """,
                (str(user_id), _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_friend_request(row) for row in rows)

    def list_outgoing_friend_requests(self, user_id: str, *, limit: int = 100) -> tuple[FriendRequest, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    r.request_id,
                    r.requester_user_id,
                    requester.public_uid AS requester_public_uid,
                    requester.nickname AS requester_nickname,
                    requester.bio AS requester_bio,
                    requester.avatar_key AS requester_avatar_key,
                    r.receiver_user_id,
                    receiver.public_uid AS receiver_public_uid,
                    receiver.nickname AS receiver_nickname,
                    receiver.bio AS receiver_bio,
                    receiver.avatar_key AS receiver_avatar_key,
                    r.message,
                    r.status,
                    r.created_at,
                    r.handled_at,
                    r.handled_by_user_id
                FROM friend_requests r
                JOIN user_profiles requester ON requester.user_id = r.requester_user_id
                JOIN user_profiles receiver ON receiver.user_id = r.receiver_user_id
                WHERE r.requester_user_id = %s
                ORDER BY CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END, r.created_at DESC, r.request_id DESC
                LIMIT %s
                """,
                (str(user_id), _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_friend_request(row) for row in rows)

    def accept_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT requester_user_id, receiver_user_id, status
                    FROM friend_requests
                    WHERE request_id = %s
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("friend request")
                if str(row["receiver_user_id"]) != str(actor_user_id):
                    raise PreconditionFailure("only the receiver can accept this friend request")
                if _normalize_friend_request_status(str(row["status"])) != "pending":
                    raise PreconditionFailure("friend request is not pending")

                user_low_id, user_high_id = _friend_pair(str(row["requester_user_id"]), str(row["receiver_user_id"]))
                conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'accepted', handled_at = %s, handled_by_user_id = %s
                    WHERE request_id = %s
                    """,
                    (now_text, str(actor_user_id), str(request_id)),
                )
                conn.execute(
                    """
                    INSERT INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(user_low_id, user_high_id) DO NOTHING
                    """,
                    (user_low_id, user_high_id, now_text, str(request_id)),
                )
                conn.commit()
                return self._get_friend_request(conn, str(request_id))

    def reject_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT receiver_user_id, status
                    FROM friend_requests
                    WHERE request_id = %s
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("friend request")
                if str(row["receiver_user_id"]) != str(actor_user_id):
                    raise PreconditionFailure("only the receiver can reject this friend request")
                if _normalize_friend_request_status(str(row["status"])) != "pending":
                    raise PreconditionFailure("friend request is not pending")

                conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'rejected', handled_at = %s, handled_by_user_id = %s
                    WHERE request_id = %s
                    """,
                    (now_text, str(actor_user_id), str(request_id)),
                )
                conn.commit()
                return self._get_friend_request(conn, str(request_id))

    def cancel_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT requester_user_id, status
                    FROM friend_requests
                    WHERE request_id = %s
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("friend request")
                if str(row["requester_user_id"]) != str(actor_user_id):
                    raise PreconditionFailure("only the requester can cancel this friend request")
                if _normalize_friend_request_status(str(row["status"])) != "pending":
                    raise PreconditionFailure("friend request is not pending")

                conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'cancelled', handled_at = %s, handled_by_user_id = %s
                    WHERE request_id = %s
                    """,
                    (now_text, str(actor_user_id), str(request_id)),
                )
                conn.commit()
                return self._get_friend_request(conn, str(request_id))

    def list_friends_for_user(self, user_id: str, *, limit: int = 100) -> tuple[FriendListItem, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    counterpart.user_id AS user_id,
                    counterpart.public_uid AS public_uid,
                    counterpart.nickname AS nickname,
                    counterpart.bio AS bio,
                    counterpart.avatar_key AS avatar_key,
                    f.created_at AS friended_at
                FROM friendships f
                JOIN user_profiles counterpart
                    ON counterpart.user_id = CASE
                        WHEN f.user_low_id = %s THEN f.user_high_id
                        ELSE f.user_low_id
                    END
                WHERE f.user_low_id = %s OR f.user_high_id = %s
                ORDER BY f.created_at DESC, counterpart.public_uid ASC
                LIMIT %s
                """,
                (str(user_id), str(user_id), str(user_id), _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_friend_list_item(row) for row in rows)

    def delete_friendship(self, friend_user_id: str, *, actor_user_id: str) -> None:
        actor_id = str(actor_user_id)
        friend_id = str(friend_user_id)
        if actor_id == friend_id:
            raise PreconditionFailure("cannot delete yourself from friends")
        user_low_id, user_high_id = _friend_pair(actor_id, friend_id)
        with self._lock:
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT 1 FROM friendships WHERE user_low_id = %s AND user_high_id = %s LIMIT 1",
                    (user_low_id, user_high_id),
                ).fetchone()
                if existing is None:
                    raise NotFound("friendship")
                conn.execute(
                    "DELETE FROM friendships WHERE user_low_id = %s AND user_high_id = %s",
                    (user_low_id, user_high_id),
                )
                conn.commit()

    def create_friendship(self, user_a_id: str, user_b_id: str) -> Friendship:
        left = str(user_a_id).strip()
        right = str(user_b_id).strip()
        user_low_id, user_high_id = _friend_pair(left, right)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    INSERT INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(user_low_id, user_high_id) DO UPDATE
                    SET user_low_id = EXCLUDED.user_low_id
                    RETURNING *
                    """,
                    (user_low_id, user_high_id, now_text, None),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("friendship")
                return self._row_to_friendship(row)

    def users_are_friends(self, user_a_id: str, user_b_id: str) -> bool:
        left = str(user_a_id).strip()
        right = str(user_b_id).strip()
        if not left or not right or left == right:
            return False
        user_low_id, user_high_id = _friend_pair(left, right)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM friendships WHERE user_low_id = %s AND user_high_id = %s LIMIT 1",
                (user_low_id, user_high_id),
            ).fetchone()
        return row is not None

    def update_user_profile(self, user_id: str, *, nickname: str, bio: str | None) -> AuthUser:
        normalized_nickname = _normalize_nickname(nickname)
        normalized_bio = _normalize_bio(bio)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "UPDATE user_profiles SET nickname = %s, bio = %s, updated_at = %s WHERE user_id = %s RETURNING user_id",
                    (normalized_nickname, normalized_bio, now_text, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("user")
                conn.commit()
        return self.get_user_by_id(user_id)

    def update_user_avatar(self, user_id: str, *, avatar_key: str | None) -> AuthUser:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "UPDATE user_profiles SET avatar_key = %s, updated_at = %s WHERE user_id = %s RETURNING user_id",
                    (_normalize_avatar_key(avatar_key), now_text, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("user")
                conn.commit()
        return self.get_user_by_id(user_id)

    def get_user_service_config(self, user_id: str, *, service_kind: str) -> UserServiceConfig | None:
        normalized_kind = _normalize_service_kind(service_kind)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                FROM user_service_configs
                WHERE user_id = %s AND service_kind = %s
                """,
                (str(user_id), normalized_kind),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user_service_config(row)

    def upsert_user_service_config(
        self,
        user_id: str,
        *,
        service_kind: str,
        base_url: str,
        model_name: str | None,
        api_key: str | None = None,
        prompt_assembly_mode: str | None = None,
        clear_api_key: bool = False,
    ) -> UserServiceConfig:
        normalized_kind = _normalize_service_kind(service_kind)
        normalized_base_url = _normalize_service_base_url(base_url)
        normalized_model_name = _normalize_service_model_name(model_name)
        normalized_api_key = _normalize_service_api_key(api_key)
        normalized_prompt_assembly_mode = _normalize_service_prompt_assembly_mode(prompt_assembly_mode)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = %s LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                current = conn.execute(
                    "SELECT api_key FROM user_service_configs WHERE user_id = %s AND service_kind = %s",
                    (str(user_id), normalized_kind),
                ).fetchone()
                if clear_api_key:
                    resolved_api_key: str | None = None
                elif normalized_api_key is not None:
                    resolved_api_key = normalized_api_key
                elif current is not None:
                    resolved_api_key = _normalize_service_api_key(current["api_key"])
                else:
                    resolved_api_key = None
                conn.execute(
                    """
                    INSERT INTO user_service_configs (
                        user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(user_id, service_kind) DO UPDATE SET
                        base_url = EXCLUDED.base_url,
                        model_name = EXCLUDED.model_name,
                        api_key = EXCLUDED.api_key,
                        prompt_assembly_mode = EXCLUDED.prompt_assembly_mode,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        str(user_id),
                        normalized_kind,
                        normalized_base_url,
                        normalized_model_name,
                        resolved_api_key,
                        normalized_prompt_assembly_mode,
                        now_text,
                    ),
                )
                conn.commit()
        saved = self.get_user_service_config(user_id, service_kind=normalized_kind)
        if saved is None:
            raise NotFound("user_service_config")
        return saved

    def get_user_global_settings(self, user_id: str) -> UserGlobalSettings:
        with self._connect() as conn:
            user_row = conn.execute("SELECT 1 FROM users WHERE user_id = %s LIMIT 1", (str(user_id),)).fetchone()
            if user_row is None:
                raise NotFound("user")
            row = conn.execute(
                """
                SELECT user_id, payload_json, updated_at
                FROM user_global_settings
                WHERE user_id = %s
                """,
                (str(user_id),),
            ).fetchone()
        if row is None:
            return self._default_user_global_settings(str(user_id))
        return self._row_to_user_global_settings(row)

    def upsert_user_global_settings(
        self,
        user_id: str,
        *,
        theme: str | None,
        pomodoro_enabled: bool,
        pomodoro_transition_sound_enabled: bool,
        pomodoro_default_focus_prompt: str | None,
        pomodoro_default_break_prompt: str | None,
        pomodoro_micro_breaks: dict[str, Any] | None,
        pomodoro_weekly_schedule: dict[str, Any],
        default_project_review_template: Iterable[dict[str, Any] | tuple[str, int | None] | list[Any]],
        learning_plans: dict[str, Any] | None = None,
    ) -> UserGlobalSettings:
        current = self.get_user_global_settings(user_id)
        normalized_theme = _normalize_user_theme(theme)
        normalized_default_focus_prompt = _normalize_pomodoro_prompt_text(pomodoro_default_focus_prompt)
        normalized_default_break_prompt = _normalize_pomodoro_prompt_text(pomodoro_default_break_prompt)
        normalized_micro_breaks = _normalize_pomodoro_micro_break_settings(pomodoro_micro_breaks)
        normalized_template = _normalize_review_chain_template(default_project_review_template)
        normalized_weekly_schedule = _normalize_pomodoro_weekly_schedule(pomodoro_weekly_schedule)
        normalized_learning_plans = (
            current.learning_plans if learning_plans is None else _normalize_learning_plans_payload(learning_plans)
        )
        payload_json = json.dumps(
            {
                "theme": normalized_theme,
                "pomodoro": {
                    "enabled": bool(pomodoro_enabled),
                    "transitionSoundEnabled": bool(pomodoro_transition_sound_enabled),
                    "defaultFocusPrompt": normalized_default_focus_prompt,
                    "defaultBreakPrompt": normalized_default_break_prompt,
                    "microBreaks": _pomodoro_micro_break_settings_to_json(normalized_micro_breaks),
                    "weeklySchedule": _pomodoro_weekly_schedule_to_json(normalized_weekly_schedule),
                },
                "defaultProjectReviewTemplate": _review_chain_template_to_json(normalized_template),
                "learningPlans": normalized_learning_plans,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = %s LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                conn.execute(
                    """
                    INSERT INTO user_global_settings (user_id, payload_json, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(user_id) DO UPDATE SET
                        payload_json = EXCLUDED.payload_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (str(user_id), payload_json, now_text),
                )
                conn.commit()
        return self.get_user_global_settings(user_id)

    def list_user_cloud_accounts(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> tuple[CloudAccountBinding, ...]:
        normalized_provider = None if provider is None else _normalize_cloud_account_provider(provider)
        sql = """
            SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                   access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                   meta_json, created_at, updated_at, disabled_at
            FROM user_cloud_accounts
            WHERE user_id = %s
        """
        params: list[Any] = [str(user_id)]
        if normalized_provider is not None:
            sql += " AND provider = %s"
            params.append(normalized_provider)
        if not include_disabled:
            sql += " AND disabled_at IS NULL"
        sql += " ORDER BY updated_at DESC, account_id ASC"
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, tuple(params)).fetchall()
        except Exception as exc:
            if _is_missing_optional_auth_table_error(exc):
                return tuple()
            raise
        return tuple(self._row_to_cloud_account_binding(row) for row in rows)

    def get_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> CloudAccountBinding:
        normalized_provider = None if provider is None else _normalize_cloud_account_provider(provider)
        sql = """
            SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                   access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                   meta_json, created_at, updated_at, disabled_at
            FROM user_cloud_accounts
            WHERE user_id = %s AND account_id = %s
        """
        params: list[Any] = [str(user_id), str(account_id)]
        if normalized_provider is not None:
            sql += " AND provider = %s"
            params.append(normalized_provider)
        if not include_disabled:
            sql += " AND disabled_at IS NULL"
        try:
            with self._connect() as conn:
                row = conn.execute(sql, tuple(params)).fetchone()
        except Exception as exc:
            if _is_missing_optional_auth_table_error(exc):
                raise NotFound("cloud account") from exc
            raise
        if row is None:
            raise NotFound("cloud account")
        return self._row_to_cloud_account_binding(row)

    def get_cloud_account_by_id(self, account_id: str, *, include_disabled: bool = False) -> CloudAccountBinding:
        sql = """
            SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                   access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                   meta_json, created_at, updated_at, disabled_at
            FROM user_cloud_accounts
            WHERE account_id = %s
        """
        params: list[Any] = [str(account_id)]
        if not include_disabled:
            sql += " AND disabled_at IS NULL"
        try:
            with self._connect() as conn:
                row = conn.execute(sql, tuple(params)).fetchone()
        except Exception as exc:
            if _is_missing_optional_auth_table_error(exc):
                raise NotFound("cloud account") from exc
            raise
        if row is None:
            raise NotFound("cloud account")
        return self._row_to_cloud_account_binding(row)

    def upsert_user_cloud_account(
        self,
        *,
        user_id: str,
        provider: str,
        provider_user_id: str,
        display_name: str,
        avatar_url: str | None,
        access_token_ciphertext: str,
        refresh_token_ciphertext: str,
        expires_at: str | None,
        scope: str = "",
        meta: dict[str, Any] | None = None,
    ) -> CloudAccountBinding:
        normalized_provider = _normalize_cloud_account_provider(provider)
        normalized_provider_user_id = _normalize_cloud_account_text(
            provider_user_id,
            field_name="provider_user_id",
            maximum=200,
        )
        normalized_display_name = _normalize_cloud_account_text(display_name, field_name="display_name", maximum=200)
        normalized_avatar_url = _normalize_cloud_account_optional_text(avatar_url, maximum=2000)
        normalized_scope = _normalize_cloud_account_scope(scope)
        normalized_meta = _normalize_cloud_account_meta(meta)
        encrypted_access_token = _normalize_cloud_account_text(
            access_token_ciphertext,
            field_name="access_token_ciphertext",
            maximum=8192,
        )
        encrypted_refresh_token = _normalize_cloud_account_text(
            refresh_token_ciphertext,
            field_name="refresh_token_ciphertext",
            maximum=8192,
        )
        normalized_expires_at = _normalize_cloud_account_optional_text(expires_at)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = %s LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                existing = conn.execute(
                    """
                    SELECT account_id, created_at
                    FROM user_cloud_accounts
                    WHERE user_id = %s AND provider = %s AND provider_user_id = %s
                    """,
                    (str(user_id), normalized_provider, normalized_provider_user_id),
                ).fetchone()
                account_id = str(existing["account_id"]) if existing is not None else f"account_{uuid.uuid4().hex}"
                created_at = str(existing["created_at"]) if existing is not None else now_text
                conn.execute(
                    """
                    INSERT INTO user_cloud_accounts (
                        account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                        access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                        meta_json, created_at, updated_at, disabled_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                    ON CONFLICT(account_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        avatar_url = EXCLUDED.avatar_url,
                        access_token_ciphertext = EXCLUDED.access_token_ciphertext,
                        refresh_token_ciphertext = EXCLUDED.refresh_token_ciphertext,
                        expires_at = EXCLUDED.expires_at,
                        scope = EXCLUDED.scope,
                        meta_json = EXCLUDED.meta_json,
                        updated_at = EXCLUDED.updated_at,
                        disabled_at = NULL
                    """,
                    (
                        account_id,
                        str(user_id),
                        normalized_provider,
                        normalized_provider_user_id,
                        normalized_display_name,
                        normalized_avatar_url,
                        encrypted_access_token,
                        encrypted_refresh_token,
                        normalized_expires_at,
                        normalized_scope,
                        json.dumps(normalized_meta, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                        created_at,
                        now_text,
                    ),
                )
                conn.commit()
        return self.get_user_cloud_account(
            str(user_id),
            account_id=account_id,
            provider=normalized_provider,
            include_disabled=True,
        )

    def disable_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
    ) -> None:
        normalized_provider = None if provider is None else _normalize_cloud_account_provider(provider)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                sql = "UPDATE user_cloud_accounts SET disabled_at = %s, updated_at = %s WHERE user_id = %s AND account_id = %s"
                params: list[Any] = [now_text, now_text, str(user_id), str(account_id)]
                if normalized_provider is not None:
                    sql += " AND provider = %s"
                    params.append(normalized_provider)
                sql += " RETURNING account_id"
                row = conn.execute(sql, tuple(params)).fetchone()
                if row is None:
                    raise NotFound("cloud account")
                conn.commit()

    def create_password_reset_token(self, email: str) -> str | None:
        normalized_email = _normalize_email(email)
        now = _utc_now()
        now_text = now.isoformat()
        expires_at = (now + timedelta(minutes=_password_reset_token_ttl_minutes())).isoformat()
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_session_token(raw_token)
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= %s", (now_text,))
                row = conn.execute(
                    f"""
                    SELECT {USER_COLUMNS_SQL}
                    FROM users u
                    JOIN user_profiles p ON p.user_id = u.user_id
                    WHERE u.email = %s AND p.status = 'active' AND u.email_verified_at IS NOT NULL AND BTRIM(u.email_verified_at) <> ''
                    """,
                    (normalized_email,),
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None
                conn.execute("DELETE FROM password_reset_tokens WHERE user_id = %s", (str(row["user_id"]),))
                conn.execute(
                    """
                    INSERT INTO password_reset_tokens (token_hash, user_id, created_at, expires_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (token_hash, str(row["user_id"]), now_text, expires_at),
                )
                conn.commit()
                return raw_token

    def create_email_verification_token(self, email: str) -> str | None:
        normalized_email = _normalize_email(email)
        now = _utc_now()
        now_text = now.isoformat()
        expires_at = (now + timedelta(minutes=_email_verification_token_ttl_minutes())).isoformat()
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_session_token(raw_token)
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM email_verification_tokens WHERE expires_at <= %s", (now_text,))
                row = conn.execute(
                    """
                    SELECT u.user_id
                    FROM users u
                    JOIN user_profiles p ON p.user_id = u.user_id
                    WHERE u.email = %s
                      AND p.status = 'active'
                      AND (u.email_verified_at IS NULL OR BTRIM(u.email_verified_at) = '')
                    """,
                    (normalized_email,),
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None
                user_id = str(row["user_id"])
                conn.execute("DELETE FROM email_verification_tokens WHERE user_id = %s", (user_id,))
                conn.execute(
                    """
                    INSERT INTO email_verification_tokens (token_hash, user_id, created_at, expires_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (token_hash, user_id, now_text, expires_at),
                )
                conn.commit()
                return raw_token

    def verify_email_with_token(self, token: str) -> AuthUser:
        token_hash = _hash_session_token(token)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM email_verification_tokens WHERE expires_at <= %s", (now_text,))
                row = conn.execute(
                    """
                    SELECT evt.user_id
                    FROM email_verification_tokens evt
                    JOIN user_profiles p ON p.user_id = evt.user_id
                    WHERE evt.token_hash = %s AND evt.expires_at > %s AND p.status = 'active'
                    """,
                    (token_hash, now_text),
                ).fetchone()
                if row is None:
                    raise PreconditionFailure("email verification token is invalid or expired")
                user_id = str(row["user_id"])
                conn.execute(
                    "UPDATE users SET email_verified_at = COALESCE(email_verified_at, %s) WHERE user_id = %s",
                    (now_text, user_id),
                )
                conn.execute("DELETE FROM email_verification_tokens WHERE user_id = %s", (user_id,))
                conn.commit()
        return self.get_user_by_id(user_id)

    def reset_password_with_token(self, token: str, *, new_password: str) -> None:
        token_hash = _hash_session_token(token)
        new_hash = self._hash_password(new_password)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= %s", (now_text,))
                row = conn.execute(
                    """
                    SELECT pr.user_id
                    FROM password_reset_tokens pr
                    JOIN user_profiles p ON p.user_id = pr.user_id
                    WHERE pr.token_hash = %s AND pr.expires_at > %s AND p.status = 'active'
                    """,
                    (token_hash, now_text),
                ).fetchone()
                if row is None:
                    raise PreconditionFailure("password reset token is invalid or expired")
                user_id = str(row["user_id"])
                conn.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (new_hash, user_id))
                conn.execute(
                    "UPDATE user_profiles SET password_changed_at = %s, updated_at = %s WHERE user_id = %s",
                    (now_text, now_text, user_id),
                )
                conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
                conn.execute("DELETE FROM password_reset_tokens WHERE user_id = %s", (user_id,))
                conn.commit()

    def change_password(self, user_id: str, *, current_password: str, new_password: str) -> None:
        new_hash = self._hash_password(new_password)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT password_hash FROM users WHERE user_id = %s", (str(user_id),)).fetchone()
                if row is None:
                    raise NotFound("user")
                if not self._verify_password(current_password, str(row["password_hash"])):
                    raise PreconditionFailure("current password is incorrect")
                conn.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (new_hash, str(user_id)))
                conn.execute(
                    "UPDATE user_profiles SET password_changed_at = %s, updated_at = %s WHERE user_id = %s",
                    (now_text, now_text, str(user_id)),
                )
                conn.commit()

    def list_project_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT project_id FROM project_memberships WHERE user_id = %s ORDER BY project_id ASC",
                (str(user_id),),
            ).fetchall()
        return tuple(str(row["project_id"]) for row in rows)

    def add_project_owner(self, project_id: str, user_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO project_memberships (project_id, user_id, role, created_at)
                    VALUES (%s, %s, 'owner', %s)
                    ON CONFLICT(project_id, user_id) DO UPDATE SET
                        role = EXCLUDED.role,
                        created_at = EXCLUDED.created_at
                    """,
                    (str(project_id), str(user_id), _utc_now().isoformat()),
                )
                conn.commit()

    def remove_project_memberships(self, project_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM project_memberships WHERE project_id = %s", (str(project_id),))
                conn.commit()

    def user_has_project_access(self, user_id: str, project_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM project_memberships WHERE project_id = %s AND user_id = %s LIMIT 1",
                (str(project_id), str(user_id)),
            ).fetchone()
        return row is not None

    def upsert_user_project_daily_study_stats(
        self,
        user_id: str,
        *,
        entries: Iterable[UserProjectDailyStudyStatInput],
    ) -> tuple[UserProjectDailyStudyStat, ...]:
        normalized_entries = tuple(entries)
        if not normalized_entries:
            return tuple()
        now_text = _utc_now().isoformat()
        saved: list[UserProjectDailyStudyStat] = []
        with self._lock:
            with self._connect() as conn:
                for entry in normalized_entries:
                    current_row = conn.execute(
                        """
                        SELECT
                            user_id,
                            project_id,
                            date_key,
                            schema_version,
                            web_presence_ms,
                            video_ms,
                            recall_entry_ms,
                            ai_qa_ms,
                            distraction_ms,
                            presence_ranges_json,
                            video_ranges_json,
                            recall_entry_ranges_json,
                            ai_qa_ranges_json,
                            is_partition_complete,
                            effective_ms,
                            watch_ms,
                            compose_ms,
                            review_ms,
                            qa_ms,
                            effective_ranges_json,
                            watch_ranges_json,
                            compose_ranges_json,
                            review_ranges_json,
                            qa_ranges_json,
                            updated_at
                        FROM user_project_daily_study_stats
                        WHERE user_id = %s AND project_id = %s AND date_key = %s
                        """,
                        (str(user_id), entry.project_id, entry.date_key),
                    ).fetchone()
                    current = None if current_row is None else self._row_to_user_project_daily_study_stat(current_row)
                    presence_ranges = _normalize_study_ranges([*(current.presence_ranges if current else ()), *entry.presence_ranges])
                    video_ranges = _normalize_study_ranges([*(current.video_ranges if current else ()), *entry.video_ranges])
                    recall_entry_ranges = _normalize_study_ranges(
                        [*(current.recall_entry_ranges if current else ()), *entry.recall_entry_ranges]
                    )
                    ai_qa_ranges = _normalize_study_ranges([*(current.ai_qa_ranges if current else ()), *entry.ai_qa_ranges])
                    effective_ranges = _normalize_study_ranges(
                        [*(current.effective_ranges if current else ()), *entry.effective_ranges]
                    )
                    watch_ranges = _normalize_study_ranges([*(current.watch_ranges if current else ()), *entry.watch_ranges])
                    compose_ranges = _normalize_study_ranges([*(current.compose_ranges if current else ()), *entry.compose_ranges])
                    review_ranges = _normalize_study_ranges([*(current.review_ranges if current else ()), *entry.review_ranges])
                    qa_ranges = _normalize_study_ranges([*(current.qa_ranges if current else ()), *entry.qa_ranges])
                    merged = UserProjectDailyStudyStat(
                        user_id=str(user_id),
                        project_id=entry.project_id,
                        date_key=entry.date_key,
                        schema_version=max(current.schema_version if current else 1, entry.schema_version),
                        web_presence_ms=_merge_study_metric_value(
                            current.web_presence_ms if current else 0,
                            entry.web_presence_ms,
                            presence_ranges,
                        ),
                        video_ms=_merge_study_metric_value(current.video_ms if current else 0, entry.video_ms, video_ranges),
                        recall_entry_ms=_merge_study_metric_value(
                            current.recall_entry_ms if current else 0,
                            entry.recall_entry_ms,
                            recall_entry_ranges,
                        ),
                        ai_qa_ms=_merge_study_metric_value(current.ai_qa_ms if current else 0, entry.ai_qa_ms, ai_qa_ranges),
                        distraction_ms=max(current.distraction_ms if current else 0, entry.distraction_ms),
                        presence_ranges=presence_ranges,
                        video_ranges=video_ranges,
                        recall_entry_ranges=recall_entry_ranges,
                        ai_qa_ranges=ai_qa_ranges,
                        is_partition_complete=bool(
                            entry.is_partition_complete or (current.is_partition_complete if current else False)
                        ),
                        effective_ms=_merge_study_metric_value(current.effective_ms if current else 0, entry.effective_ms, effective_ranges),
                        watch_ms=max(
                            _merge_study_metric_value(current.watch_ms if current else 0, entry.watch_ms, watch_ranges),
                            _merge_study_metric_value(current.video_ms if current else 0, entry.video_ms, video_ranges),
                        ),
                        compose_ms=max(
                            _merge_study_metric_value(current.compose_ms if current else 0, entry.compose_ms, compose_ranges),
                            _merge_study_metric_value(current.recall_entry_ms if current else 0, entry.recall_entry_ms, recall_entry_ranges),
                        ),
                        review_ms=_merge_study_metric_value(current.review_ms if current else 0, entry.review_ms, review_ranges),
                        qa_ms=max(
                            _merge_study_metric_value(current.qa_ms if current else 0, entry.qa_ms, qa_ranges),
                            _merge_study_metric_value(current.ai_qa_ms if current else 0, entry.ai_qa_ms, ai_qa_ranges),
                        ),
                        effective_ranges=effective_ranges,
                        watch_ranges=watch_ranges,
                        compose_ranges=compose_ranges,
                        review_ranges=review_ranges,
                        qa_ranges=qa_ranges,
                        updated_at=now_text,
                    )
                    conn.execute(
                        """
                        INSERT INTO user_project_daily_study_stats (
                            user_id,
                            project_id,
                            date_key,
                            schema_version,
                            web_presence_ms,
                            video_ms,
                            recall_entry_ms,
                            ai_qa_ms,
                            distraction_ms,
                            presence_ranges_json,
                            video_ranges_json,
                            recall_entry_ranges_json,
                            ai_qa_ranges_json,
                            is_partition_complete,
                            effective_ms,
                            watch_ms,
                            compose_ms,
                            review_ms,
                            qa_ms,
                            effective_ranges_json,
                            watch_ranges_json,
                            compose_ranges_json,
                            review_ranges_json,
                            qa_ranges_json,
                            updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(user_id, project_id, date_key) DO UPDATE SET
                            schema_version = EXCLUDED.schema_version,
                            web_presence_ms = EXCLUDED.web_presence_ms,
                            video_ms = EXCLUDED.video_ms,
                            recall_entry_ms = EXCLUDED.recall_entry_ms,
                            ai_qa_ms = EXCLUDED.ai_qa_ms,
                            distraction_ms = EXCLUDED.distraction_ms,
                            presence_ranges_json = EXCLUDED.presence_ranges_json,
                            video_ranges_json = EXCLUDED.video_ranges_json,
                            recall_entry_ranges_json = EXCLUDED.recall_entry_ranges_json,
                            ai_qa_ranges_json = EXCLUDED.ai_qa_ranges_json,
                            is_partition_complete = EXCLUDED.is_partition_complete,
                            effective_ms = EXCLUDED.effective_ms,
                            watch_ms = EXCLUDED.watch_ms,
                            compose_ms = EXCLUDED.compose_ms,
                            review_ms = EXCLUDED.review_ms,
                            qa_ms = EXCLUDED.qa_ms,
                            effective_ranges_json = EXCLUDED.effective_ranges_json,
                            watch_ranges_json = EXCLUDED.watch_ranges_json,
                            compose_ranges_json = EXCLUDED.compose_ranges_json,
                            review_ranges_json = EXCLUDED.review_ranges_json,
                            qa_ranges_json = EXCLUDED.qa_ranges_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            merged.user_id,
                            merged.project_id,
                            merged.date_key,
                            merged.schema_version,
                            merged.web_presence_ms,
                            merged.video_ms,
                            merged.recall_entry_ms,
                            merged.ai_qa_ms,
                            merged.distraction_ms,
                            json.dumps(merged.presence_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.video_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.recall_entry_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.ai_qa_ranges, ensure_ascii=False, separators=(",", ":")),
                            merged.is_partition_complete,
                            merged.effective_ms,
                            merged.watch_ms,
                            merged.compose_ms,
                            merged.review_ms,
                            merged.qa_ms,
                            json.dumps(merged.effective_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.watch_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.compose_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.review_ranges, ensure_ascii=False, separators=(",", ":")),
                            json.dumps(merged.qa_ranges, ensure_ascii=False, separators=(",", ":")),
                            merged.updated_at,
                        ),
                    )
                    saved.append(merged)
                conn.commit()
        return tuple(saved)

    def list_user_project_daily_study_stats(
        self,
        user_id: str,
        *,
        project_ids: Iterable[str],
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[UserProjectDailyStudyStat, ...]:
        normalized_project_ids = tuple(dict.fromkeys(_normalize_project_id(project_id) for project_id in project_ids))
        if not normalized_project_ids:
            return tuple()
        normalized_date_from = None if date_from is None else _normalize_study_date_key(date_from)
        normalized_date_to = None if date_to is None else _normalize_study_date_key(date_to)
        if normalized_date_from and normalized_date_to and normalized_date_from > normalized_date_to:
            raise PreconditionFailure("date_from must be less than or equal to date_to")
        sql = """
            SELECT
                user_id,
                project_id,
                date_key,
                schema_version,
                web_presence_ms,
                video_ms,
                recall_entry_ms,
                ai_qa_ms,
                distraction_ms,
                presence_ranges_json,
                video_ranges_json,
                recall_entry_ranges_json,
                ai_qa_ranges_json,
                is_partition_complete,
                effective_ms,
                watch_ms,
                compose_ms,
                review_ms,
                qa_ms,
                effective_ranges_json,
                watch_ranges_json,
                compose_ranges_json,
                review_ranges_json,
                qa_ranges_json,
                updated_at
            FROM user_project_daily_study_stats
            WHERE user_id = %s AND project_id = ANY(%s)
        """
        params: list[Any] = [str(user_id), list(normalized_project_ids)]
        if normalized_date_from is not None:
            sql += " AND date_key >= %s"
            params.append(normalized_date_from)
        if normalized_date_to is not None:
            sql += " AND date_key <= %s"
            params.append(normalized_date_to)
        sql += " ORDER BY date_key ASC, project_id ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return tuple(self._row_to_user_project_daily_study_stat(row) for row in rows)

    def list_user_roles(self, user_id: str) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role FROM user_global_roles WHERE user_id = %s ORDER BY role ASC",
                (str(user_id),),
            ).fetchall()
        return tuple(str(row["role"]) for row in rows)

    def user_has_global_role(self, user_id: str, roles: Iterable[str]) -> bool:
        normalized_roles = tuple(_normalize_global_role(role) for role in roles)
        if not normalized_roles:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM user_global_roles WHERE user_id = %s AND role = ANY(%s) LIMIT 1",
                (str(user_id), list(normalized_roles)),
            ).fetchone()
        return row is not None

    def set_user_global_role(self, user_id: str, *, role: str, enabled: bool, granted_by_user_id: str) -> tuple[str, ...]:
        normalized_role = _normalize_global_role(role)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                user_row = conn.execute("SELECT 1 FROM users WHERE user_id = %s LIMIT 1", (str(user_id),)).fetchone()
                if user_row is None:
                    raise NotFound("user")
                if enabled:
                    conn.execute(
                        """
                        INSERT INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(user_id, role) DO UPDATE SET
                            granted_by_user_id = EXCLUDED.granted_by_user_id,
                            created_at = EXCLUDED.created_at
                        """,
                        (str(user_id), normalized_role, str(granted_by_user_id), now_text),
                    )
                else:
                    if normalized_role == "super_admin":
                        existing = conn.execute(
                            "SELECT 1 FROM user_global_roles WHERE user_id = %s AND role = 'super_admin' LIMIT 1",
                            (str(user_id),),
                        ).fetchone()
                        if existing is not None:
                            count = int(
                                conn.execute(
                                    "SELECT COUNT(*) AS count FROM user_global_roles WHERE role = 'super_admin'"
                                ).fetchone()["count"]
                            )
                            if count <= 1:
                                raise PreconditionFailure("cannot remove the last super_admin")
                    conn.execute(
                        "DELETE FROM user_global_roles WHERE user_id = %s AND role = %s",
                        (str(user_id), normalized_role),
                    )
                conn.commit()
        return self.list_user_roles(user_id)

    def list_users(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        limit: int = 100,
    ) -> tuple[AdminUser, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(u.email ILIKE %s OR p.nickname ILIKE %s OR p.public_uid ILIKE %s)")
            params.extend((needle, needle, needle.upper()))
        if status and str(status).strip():
            clauses.append("p.status = %s")
            params.append(_normalize_user_status(status))
        normalized_role = _normalize_user_role_filter(role)
        if normalized_role == "none":
            clauses.append("NOT EXISTS (SELECT 1 FROM user_global_roles ugr WHERE ugr.user_id = u.user_id)")
        elif normalized_role:
            clauses.append("EXISTS (SELECT 1 FROM user_global_roles ugr WHERE ugr.user_id = u.user_id AND ugr.role = %s)")
            params.append(normalized_role)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE {' AND '.join(clauses)}
                ORDER BY u.created_at DESC, u.user_id ASC
                LIMIT %s
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
            roles_by_user_id = self._roles_by_user_id(conn, (str(row["user_id"]) for row in rows))
        payload: list[AdminUser] = []
        for row in rows:
            user = self._row_to_user(row)
            payload.append(
                AdminUser(
                    user_id=user.user_id,
                    email=user.email,
                    created_at=user.created_at,
                    public_uid=user.public_uid,
                    nickname=user.nickname,
                    bio=user.bio,
                    avatar_key=user.avatar_key,
                    status=user.status,
                    updated_at=user.updated_at,
                    roles=roles_by_user_id.get(user.user_id, ()),
                )
            )
        return tuple(payload)

    def set_user_status(self, user_id: str, *, status: str) -> AuthUser:
        normalized_status = _normalize_user_status(status)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "UPDATE user_profiles SET status = %s, updated_at = %s WHERE user_id = %s RETURNING user_id",
                    (normalized_status, now_text, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("user")
                if normalized_status != "active":
                    conn.execute("DELETE FROM sessions WHERE user_id = %s", (str(user_id),))
                conn.commit()
        return self.get_user_by_id(user_id)

    def get_admin_overview(self) -> dict[str, int]:
        with self._connect() as conn:
            users = int(conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"])
            active_users = int(conn.execute("SELECT COUNT(*) AS count FROM user_profiles WHERE status = 'active'").fetchone()["count"])
            study_users = int(
                conn.execute(
                    "SELECT COUNT(DISTINCT user_id) AS count FROM user_project_daily_study_stats WHERE effective_ms > 0"
                ).fetchone()["count"]
            )
            study_users_7d = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) AS count
                    FROM user_project_daily_study_stats
                    WHERE effective_ms > 0 AND updated_at >= %s
                    """,
                    ((_utc_now() - timedelta(days=7)).isoformat(),),
                ).fetchone()["count"]
            )
            study_totals_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(effective_ms), 0) AS effective_ms,
                    COALESCE(SUM(watch_ms), 0) AS watch_ms,
                    COALESCE(SUM(compose_ms), 0) AS compose_ms,
                    COALESCE(SUM(review_ms), 0) AS review_ms,
                    COALESCE(SUM(qa_ms), 0) AS qa_ms
                FROM user_project_daily_study_stats
                """
            ).fetchone()
        return {
            "users": users,
            "activeUsers": active_users,
            "studyUsers": study_users,
            "studyUsers7d": study_users_7d,
            "effectiveStudyMs": int(study_totals_row["effective_ms"]) if study_totals_row is not None else 0,
            "watchMs": int(study_totals_row["watch_ms"]) if study_totals_row is not None else 0,
            "composeMs": int(study_totals_row["compose_ms"]) if study_totals_row is not None else 0,
            "reviewMs": int(study_totals_row["review_ms"]) if study_totals_row is not None else 0,
            "qaMs": int(study_totals_row["qa_ms"]) if study_totals_row is not None else 0,
        }

    def record_admin_action(
        self,
        *,
        actor_user_id: str,
        action_type: str,
        target_kind: str,
        target_id: str,
        summary: str,
    ) -> AdminActionLog:
        normalized_action_type = _normalize_admin_action_field(action_type, field_name="action type", maximum=80)
        normalized_target_kind = _normalize_admin_action_field(target_kind, field_name="target kind", maximum=80)
        normalized_target_id = _normalize_admin_action_field(target_id, field_name="target id", maximum=120)
        normalized_summary = _normalize_admin_action_field(summary, field_name="summary", maximum=500)
        log_id = f"adminlog_{uuid.uuid4().hex}"
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO admin_action_logs (
                        log_id, actor_user_id, action_type, target_kind, target_id, summary, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        log_id,
                        str(actor_user_id),
                        normalized_action_type,
                        normalized_target_kind,
                        normalized_target_id,
                        normalized_summary,
                        now_text,
                    ),
                )
                conn.commit()
        logs = self.list_admin_action_logs(limit=50)
        for item in logs:
            if item.log_id == log_id:
                return item
        raise NotFound("admin_action_log")

    def list_admin_action_logs(self, *, limit: int = 100) -> tuple[AdminActionLog, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    l.log_id,
                    l.actor_user_id,
                    p.public_uid AS actor_public_uid,
                    p.nickname AS actor_nickname,
                    p.avatar_key AS actor_avatar_key,
                    l.action_type,
                    l.target_kind,
                    l.target_id,
                    l.summary,
                    l.created_at
                FROM admin_action_logs l
                JOIN user_profiles p ON p.user_id = l.actor_user_id
                ORDER BY l.created_at DESC, l.log_id DESC
                LIMIT %s
                """,
                (_normalize_limit(limit),),
            ).fetchall()
        return tuple(self._row_to_admin_action_log(row) for row in rows)


    def export_snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            users = [
                {
                    "userId": str(row["user_id"]),
                    "email": str(row["email"]),
                    "passwordHash": str(row["password_hash"]),
                    "createdAt": str(row["created_at"]),
                    "emailVerifiedAt": None if row["email_verified_at"] is None else str(row["email_verified_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, email, password_hash, created_at, email_verified_at
                    FROM users
                    ORDER BY created_at ASC, user_id ASC
                    """
                ).fetchall()
            ]
            sessions = [
                {
                    "sessionToken": str(row["session_token"]),
                    "userId": str(row["user_id"]),
                    "createdAt": str(row["created_at"]),
                    "expiresAt": str(row["expires_at"]),
                }
                for row in conn.execute(
                    "SELECT session_token, user_id, created_at, expires_at FROM sessions ORDER BY session_token ASC"
                ).fetchall()
            ]
            memberships = [
                {
                    "projectId": str(row["project_id"]),
                    "userId": str(row["user_id"]),
                    "role": str(row["role"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT project_id, user_id, role, created_at
                    FROM project_memberships
                    ORDER BY project_id ASC, user_id ASC
                    """
                ).fetchall()
            ]
            profiles = [
                {
                    "userId": str(row["user_id"]),
                    "publicUid": str(row["public_uid"]),
                    "nickname": str(row["nickname"]),
                    "bio": str(row["bio"]),
                    "avatarKey": None if row["avatar_key"] is None else str(row["avatar_key"]),
                    "status": str(row["status"]),
                    "updatedAt": str(row["updated_at"]),
                    "passwordChangedAt": str(row["password_changed_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                    FROM user_profiles
                    ORDER BY user_id ASC
                    """
                ).fetchall()
            ]
            user_service_configs = [
                {
                    "userId": str(row["user_id"]),
                    "serviceKind": str(row["service_kind"]),
                    "baseUrl": str(row["base_url"]),
                    "modelName": str(row["model_name"]),
                    "apiKey": None if row["api_key"] is None else str(row["api_key"]),
                    "promptAssemblyMode": _normalize_service_prompt_assembly_mode(row["prompt_assembly_mode"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                    FROM user_service_configs
                    ORDER BY user_id ASC, service_kind ASC
                    """
                ).fetchall()
            ]
            user_global_settings = [
                {
                    "userId": str(row["user_id"]),
                    "payloadJson": str(row["payload_json"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_id, payload_json, updated_at
                    FROM user_global_settings
                    ORDER BY user_id ASC
                    """
                ).fetchall()
            ]
            cloud_accounts = [
                {
                    "accountId": str(row["account_id"]),
                    "userId": str(row["user_id"]),
                    "provider": str(row["provider"]),
                    "providerUserId": str(row["provider_user_id"]),
                    "displayName": str(row["display_name"]),
                    "avatarUrl": None if row["avatar_url"] is None else str(row["avatar_url"]),
                    "accessTokenCiphertext": str(row["access_token_ciphertext"]),
                    "refreshTokenCiphertext": str(row["refresh_token_ciphertext"]),
                    "expiresAt": None if row["expires_at"] is None else str(row["expires_at"]),
                    "scope": str(row["scope"]),
                    "meta": json.loads(str(row["meta_json"]) if row["meta_json"] is not None else "{}"),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                    "disabledAt": None if row["disabled_at"] is None else str(row["disabled_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                           access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                           meta_json, created_at, updated_at, disabled_at
                    FROM user_cloud_accounts
                    ORDER BY user_id ASC, provider ASC, updated_at DESC, account_id ASC
                    """
                ).fetchall()
            ]
            roles = [
                {
                    "userId": str(row["user_id"]),
                    "role": str(row["role"]),
                    "grantedByUserId": str(row["granted_by_user_id"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    "SELECT user_id, role, granted_by_user_id, created_at FROM user_global_roles ORDER BY user_id ASC, role ASC"
                ).fetchall()
            ]
            friend_requests = [
                {
                    "requestId": str(row["request_id"]),
                    "requesterUserId": str(row["requester_user_id"]),
                    "receiverUserId": str(row["receiver_user_id"]),
                    "message": str(row["message"]),
                    "status": str(row["status"]),
                    "createdAt": str(row["created_at"]),
                    "handledAt": None if row["handled_at"] is None else str(row["handled_at"]),
                    "handledByUserId": None if row["handled_by_user_id"] is None else str(row["handled_by_user_id"]),
                }
                for row in conn.execute(
                    """
                    SELECT request_id, requester_user_id, receiver_user_id, message, status, created_at, handled_at, handled_by_user_id
                    FROM friend_requests
                    ORDER BY created_at ASC, request_id ASC
                    """
                ).fetchall()
            ]
            friendships = [
                {
                    "userLowId": str(row["user_low_id"]),
                    "userHighId": str(row["user_high_id"]),
                    "createdAt": str(row["created_at"]),
                    "sourceRequestId": None if row["source_request_id"] is None else str(row["source_request_id"]),
                }
                for row in conn.execute(
                    """
                    SELECT user_low_id, user_high_id, created_at, source_request_id
                    FROM friendships
                    ORDER BY created_at ASC, user_low_id ASC, user_high_id ASC
                    """
                ).fetchall()
            ]
            admin_action_logs = [
                {
                    "logId": str(row["log_id"]),
                    "actorUserId": str(row["actor_user_id"]),
                    "actionType": str(row["action_type"]),
                    "targetKind": str(row["target_kind"]),
                    "targetId": str(row["target_id"]),
                    "summary": str(row["summary"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT log_id, actor_user_id, action_type, target_kind, target_id, summary, created_at
                    FROM admin_action_logs
                    ORDER BY created_at ASC, log_id ASC
                    """
                ).fetchall()
            ]
        return self._snapshot_payload(
            users=users,
            sessions=sessions,
            memberships=memberships,
            profiles=profiles,
            user_service_configs=user_service_configs,
            user_global_settings=user_global_settings,
            roles=roles,
            cloud_accounts=cloud_accounts,
            friend_requests=friend_requests,
            friendships=friendships,
            admin_action_logs=admin_action_logs,
        )

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        profiles = list(snapshot.get("userProfiles", []))
        user_service_configs = list(snapshot.get("userServiceConfigs", []))
        user_global_settings = list(snapshot.get("userGlobalSettings", []))
        roles = list(snapshot.get("userGlobalRoles", []))
        cloud_accounts = list(snapshot.get("userCloudAccounts", []))
        friend_requests = list(snapshot.get("friendRequests", []))
        friendships = list(snapshot.get("friendships", []))
        admin_action_logs = list(snapshot.get("adminActionLogs", []))
        with self._lock:
            with self._connect() as conn:
                if replace:
                    conn.execute("DELETE FROM admin_action_logs")
                    conn.execute("DELETE FROM friendships")
                    conn.execute("DELETE FROM friend_requests")
                    conn.execute("DELETE FROM user_global_roles")
                    conn.execute("DELETE FROM user_cloud_accounts")
                    conn.execute("DELETE FROM user_global_settings")
                    conn.execute("DELETE FROM user_service_configs")
                    conn.execute("DELETE FROM project_memberships")
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM user_profiles")
                    conn.execute("DELETE FROM users")
                for item in users:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO users (user_id, email, password_hash, created_at, email_verified_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("email", "")),
                            str(row.get("passwordHash", "")),
                            str(row.get("createdAt", "")),
                            row.get("emailVerifiedAt", row.get("createdAt")),
                        ),
                    )
                for item in profiles:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_profiles (
                            user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("publicUid", "")),
                            str(row.get("nickname", "")) or "user",
                            str(row.get("bio", "")),
                            _normalize_avatar_key(row.get("avatarKey")),
                            str(row.get("status", "active") or "active"),
                            str(row.get("updatedAt", row.get("passwordChangedAt", ""))),
                            str(row.get("passwordChangedAt", row.get("updatedAt", ""))),
                        ),
                    )
                if not profiles:
                    conn.execute(
                        """
                        INSERT INTO user_profiles (user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at)
                        SELECT
                            u.user_id,
                            CONCAT('LP', UPPER(SUBSTRING(MD5(u.user_id || ':' || u.email) FROM 1 FOR 8))),
                            SPLIT_PART(u.email, '@', 1),
                            '',
                            NULL,
                            'active',
                            u.created_at,
                            u.created_at
                        FROM users u
                        ON CONFLICT (user_id) DO NOTHING
                        """
                    )
                for item in user_service_configs:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_service_configs (
                            user_id, service_kind, base_url, model_name, api_key, prompt_assembly_mode, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(user_id, service_kind) DO UPDATE SET
                            base_url = EXCLUDED.base_url,
                            model_name = EXCLUDED.model_name,
                            api_key = EXCLUDED.api_key,
                            prompt_assembly_mode = EXCLUDED.prompt_assembly_mode,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(row.get("userId", "")),
                            _normalize_service_kind(str(row.get("serviceKind", ""))),
                            _normalize_service_base_url(str(row.get("baseUrl", ""))),
                            _normalize_service_model_name(row.get("modelName")),
                            _normalize_service_api_key(row.get("apiKey")),
                            _normalize_service_prompt_assembly_mode(row.get("promptAssemblyMode")),
                            str(row.get("updatedAt", "")),
                        ),
                    )
                for item in user_global_settings:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_global_settings (user_id, payload_json, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT(user_id) DO UPDATE SET
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("payloadJson", "{}") or "{}"),
                            str(row.get("updatedAt", "")),
                        ),
                    )
                for item in cloud_accounts:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_cloud_accounts (
                            account_id, user_id, provider, provider_user_id, display_name, avatar_url,
                            access_token_ciphertext, refresh_token_ciphertext, expires_at, scope,
                            meta_json, created_at, updated_at, disabled_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("accountId", "")),
                            str(row.get("userId", "")),
                            _normalize_cloud_account_provider(str(row.get("provider", ""))),
                            _normalize_cloud_account_text(row.get("providerUserId"), field_name="provider_user_id", maximum=200),
                            _normalize_cloud_account_text(row.get("displayName"), field_name="display_name", maximum=200),
                            _normalize_cloud_account_optional_text(row.get("avatarUrl"), maximum=2000),
                            _normalize_cloud_account_text(
                                row.get("accessTokenCiphertext"),
                                field_name="access_token_ciphertext",
                                maximum=8192,
                            ),
                            _normalize_cloud_account_text(
                                row.get("refreshTokenCiphertext"),
                                field_name="refresh_token_ciphertext",
                                maximum=8192,
                            ),
                            _normalize_cloud_account_optional_text(row.get("expiresAt")),
                            _normalize_cloud_account_scope(row.get("scope")),
                            json.dumps(
                                _normalize_cloud_account_meta(
                                    row.get("meta") if isinstance(row.get("meta"), dict) else None
                                ),
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", "")),
                            _normalize_cloud_account_optional_text(row.get("disabledAt")),
                        ),
                    )
                for item in roles:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(user_id, role) DO UPDATE SET
                            granted_by_user_id = EXCLUDED.granted_by_user_id,
                            created_at = EXCLUDED.created_at
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("role", "admin")),
                            str(row.get("grantedByUserId", row.get("userId", ""))),
                            str(row.get("createdAt", "")),
                        ),
                    )
                if not roles:
                    self._bootstrap_configured_super_admins_postgres(conn)
                for item in sessions:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO sessions (session_token, user_id, created_at, expires_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            _stored_session_token_value(row.get("sessionToken", "")),
                            str(row.get("userId", "")),
                            str(row.get("createdAt", "")),
                            str(row.get("expiresAt", "")),
                        ),
                    )
                for item in memberships:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO project_memberships (project_id, user_id, role, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(project_id, user_id) DO UPDATE SET
                            role = EXCLUDED.role,
                            created_at = EXCLUDED.created_at
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("userId", "")),
                            str(row.get("role", "owner") or "owner"),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in friend_requests:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO friend_requests (
                            request_id, requester_user_id, receiver_user_id, message, status, created_at, handled_at, handled_by_user_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("requestId", "")),
                            str(row.get("requesterUserId", "")),
                            str(row.get("receiverUserId", "")),
                            str(row.get("message", "")),
                            str(row.get("status", "pending")),
                            str(row.get("createdAt", "")),
                            row.get("handledAt"),
                            row.get("handledByUserId"),
                        ),
                    )
                for item in friendships:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO friendships (user_low_id, user_high_id, created_at, source_request_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(user_low_id, user_high_id) DO UPDATE SET
                            created_at = EXCLUDED.created_at,
                            source_request_id = EXCLUDED.source_request_id
                        """,
                        (
                            str(row.get("userLowId", "")),
                            str(row.get("userHighId", "")),
                            str(row.get("createdAt", "")),
                            row.get("sourceRequestId"),
                        ),
                    )
                for item in admin_action_logs:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO admin_action_logs (
                            log_id, actor_user_id, action_type, target_kind, target_id, summary, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(log_id) DO UPDATE SET
                            actor_user_id = EXCLUDED.actor_user_id,
                            action_type = EXCLUDED.action_type,
                            target_kind = EXCLUDED.target_kind,
                            target_id = EXCLUDED.target_id,
                            summary = EXCLUDED.summary,
                            created_at = EXCLUDED.created_at
                        """,
                        (
                            str(row.get("logId", "")),
                            str(row.get("actorUserId", "")),
                            str(row.get("actionType", "")),
                            str(row.get("targetKind", "")),
                            str(row.get("targetId", "")),
                            str(row.get("summary", "")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                conn.commit()

    def healthcheck(self) -> dict[str, object]:
        health = self._pool.healthcheck()
        health["backend"] = "postgres"
        health["dsn"] = redact_postgres_dsn(self._dsn)
        health["expectedMigrations"] = expected_postgres_migration_status(target="auth")
        if bool(health.get("ok", False)):
            conn = self._pool.acquire()
            try:
                status = postgres_migration_status(conn, target="auth")
                health["migrations"] = status
                migration_error = self._migration_health_error(status)
                if migration_error:
                    health["ok"] = False
                    health["error"] = migration_error
                else:
                    required_targets = [
                        "users",
                        "user_profiles",
                        "sessions",
                        "user_global_roles",
                    ]
                    optional_targets = [
                        "user_service_configs",
                        "user_global_settings",
                        "user_cloud_accounts",
                        "friend_requests",
                        "friendships",
                    ]
                    for table_name in required_targets:
                        conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone()
                    probed_targets = list(required_targets)
                    skipped_optional_targets: list[str] = []
                    for table_name in optional_targets:
                        if not _postgres_table_exists(conn, table_name):
                            skipped_optional_targets.append(table_name)
                            continue
                        conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone()
                        probed_targets.append(table_name)
                    health["probe"] = {"ok": True, "targets": probed_targets}
                    if skipped_optional_targets:
                        health["probe"]["skippedOptionalTargets"] = skipped_optional_targets
            except Exception as exc:
                health["ok"] = False
                health["error"] = str(exc)
                health["probe"] = {"ok": False, "error": str(exc)}
            finally:
                self._pool.release(conn)
        return health


class AuthStore:
    def __init__(self, db_path: Path | None = None, *, postgres_dsn: str | None = None) -> None:
        cfg = current_sql_runtime_config()
        if postgres_dsn is not None:
            self._impl = PostgresAuthStore(postgres_dsn)
            return
        if db_path is not None:
            self._impl = SQLiteAuthStore(db_path)
            return
        if cfg.backend == "postgres":
            if cfg.auth_postgres_dsn is None:
                raise RuntimeError("PostgreSQL auth backend selected without a DSN")
            self._impl = PostgresAuthStore(cfg.auth_postgres_dsn)
            return
        self._impl = SQLiteAuthStore(cfg.auth_db_path)

    def create_user(self, email: str, password: str, *, email_verified: bool = True) -> AuthUser:
        return self._impl.create_user(email, password, email_verified=email_verified)

    def authenticate_user(self, email: str, password: str) -> AuthUser:
        return self._impl.authenticate_user(email, password)

    def create_session(self, user_id: str) -> str:
        return self._impl.create_session(user_id)

    def get_user_by_session(self, session_token: str) -> AuthUser:
        return self._impl.get_user_by_session(session_token)

    def delete_session(self, session_token: str) -> None:
        self._impl.delete_session(session_token)

    def delete_other_sessions_for_user(self, user_id: str, *, except_session_token: str | None = None) -> None:
        self._impl.delete_other_sessions_for_user(user_id, except_session_token=except_session_token)

    def list_project_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        return self._impl.list_project_ids_for_user(user_id)

    def add_project_owner(self, project_id: str, user_id: str) -> None:
        self._impl.add_project_owner(project_id, user_id)

    def remove_project_memberships(self, project_id: str) -> None:
        self._impl.remove_project_memberships(project_id)

    def user_has_project_access(self, user_id: str, project_id: str) -> bool:
        return self._impl.user_has_project_access(user_id, project_id)

    def upsert_user_project_daily_study_stats(
        self,
        user_id: str,
        *,
        entries: Iterable[UserProjectDailyStudyStatInput],
    ) -> tuple[UserProjectDailyStudyStat, ...]:
        return self._impl.upsert_user_project_daily_study_stats(user_id, entries=entries)

    def list_user_project_daily_study_stats(
        self,
        user_id: str,
        *,
        project_ids: Iterable[str],
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[UserProjectDailyStudyStat, ...]:
        return self._impl.list_user_project_daily_study_stats(
            user_id,
            project_ids=project_ids,
            date_from=date_from,
            date_to=date_to,
        )

    def get_user_by_id(self, user_id: str) -> AuthUser:
        return self._impl.get_user_by_id(user_id)

    def user_email_verified(self, user_id: str) -> bool:
        return self._impl.user_email_verified(user_id)

    def get_user_by_public_uid(self, public_uid: str) -> AuthUser:
        return self._impl.get_user_by_public_uid(public_uid)

    def create_friend_request(
        self,
        *,
        requester_user_id: str,
        receiver_user_id: str,
        message: str | None,
    ) -> FriendRequest:
        return self._impl.create_friend_request(
            requester_user_id=requester_user_id,
            receiver_user_id=receiver_user_id,
            message=message,
        )

    def list_incoming_friend_requests(self, user_id: str, *, limit: int = 100) -> tuple[FriendRequest, ...]:
        return self._impl.list_incoming_friend_requests(user_id, limit=limit)

    def list_outgoing_friend_requests(self, user_id: str, *, limit: int = 100) -> tuple[FriendRequest, ...]:
        return self._impl.list_outgoing_friend_requests(user_id, limit=limit)

    def accept_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        return self._impl.accept_friend_request(request_id, actor_user_id=actor_user_id)

    def reject_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        return self._impl.reject_friend_request(request_id, actor_user_id=actor_user_id)

    def cancel_friend_request(self, request_id: str, *, actor_user_id: str) -> FriendRequest:
        return self._impl.cancel_friend_request(request_id, actor_user_id=actor_user_id)

    def list_friends_for_user(self, user_id: str, *, limit: int = 100) -> tuple[FriendListItem, ...]:
        return self._impl.list_friends_for_user(user_id, limit=limit)

    def delete_friendship(self, friend_user_id: str, *, actor_user_id: str) -> None:
        self._impl.delete_friendship(friend_user_id, actor_user_id=actor_user_id)

    def create_friendship(self, user_a_id: str, user_b_id: str) -> Friendship:
        return self._impl.create_friendship(user_a_id, user_b_id)

    def users_are_friends(self, user_a_id: str, user_b_id: str) -> bool:
        return self._impl.users_are_friends(user_a_id, user_b_id)

    def update_user_profile(self, user_id: str, *, nickname: str, bio: str | None) -> AuthUser:
        return self._impl.update_user_profile(user_id, nickname=nickname, bio=bio)

    def update_user_avatar(self, user_id: str, *, avatar_key: str | None) -> AuthUser:
        return self._impl.update_user_avatar(user_id, avatar_key=avatar_key)

    def get_user_service_config(self, user_id: str, *, service_kind: str) -> UserServiceConfig | None:
        return self._impl.get_user_service_config(user_id, service_kind=service_kind)

    def upsert_user_service_config(
        self,
        user_id: str,
        *,
        service_kind: str,
        base_url: str,
        model_name: str | None,
        api_key: str | None = None,
        prompt_assembly_mode: str | None = None,
        clear_api_key: bool = False,
    ) -> UserServiceConfig:
        return self._impl.upsert_user_service_config(
            user_id,
            service_kind=service_kind,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            prompt_assembly_mode=prompt_assembly_mode,
            clear_api_key=clear_api_key,
        )

    def get_user_global_settings(self, user_id: str) -> UserGlobalSettings:
        return self._impl.get_user_global_settings(user_id)

    def upsert_user_global_settings(
        self,
        user_id: str,
        *,
        theme: str | None,
        pomodoro_enabled: bool,
        pomodoro_transition_sound_enabled: bool,
        pomodoro_default_focus_prompt: str | None,
        pomodoro_default_break_prompt: str | None,
        pomodoro_micro_breaks: dict[str, Any] | None,
        pomodoro_weekly_schedule: dict[str, Any],
        default_project_review_template: Iterable[dict[str, Any] | tuple[str, int | None] | list[Any]],
        learning_plans: dict[str, Any] | None = None,
    ) -> UserGlobalSettings:
        return self._impl.upsert_user_global_settings(
            user_id,
            theme=theme,
            pomodoro_enabled=pomodoro_enabled,
            pomodoro_transition_sound_enabled=pomodoro_transition_sound_enabled,
            pomodoro_default_focus_prompt=pomodoro_default_focus_prompt,
            pomodoro_default_break_prompt=pomodoro_default_break_prompt,
            pomodoro_micro_breaks=pomodoro_micro_breaks,
            pomodoro_weekly_schedule=pomodoro_weekly_schedule,
            default_project_review_template=default_project_review_template,
            learning_plans=learning_plans,
        )

    def get_user_learning_plans(self, user_id: str) -> dict[str, Any]:
        return self.get_user_global_settings(user_id).learning_plans

    def upsert_user_learning_plans(self, user_id: str, *, learning_plans: dict[str, Any]) -> dict[str, Any]:
        current = self.get_user_global_settings(user_id)
        updated = self.upsert_user_global_settings(
            user_id,
            theme=current.theme,
            pomodoro_enabled=current.pomodoro_enabled,
            pomodoro_transition_sound_enabled=current.pomodoro_transition_sound_enabled,
            pomodoro_default_focus_prompt=current.pomodoro_default_focus_prompt,
            pomodoro_default_break_prompt=current.pomodoro_default_break_prompt,
            pomodoro_micro_breaks=_pomodoro_micro_break_settings_to_json(current.pomodoro_micro_breaks),
            pomodoro_weekly_schedule=_pomodoro_weekly_schedule_to_json(current.pomodoro_weekly_schedule),
            default_project_review_template=_review_chain_template_to_json(
                ((step.kind, step.count) for step in current.default_project_review_template)
            ),
            learning_plans=learning_plans,
        )
        return updated.learning_plans

    def list_user_cloud_accounts(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> tuple[CloudAccountBinding, ...]:
        return self._impl.list_user_cloud_accounts(
            user_id,
            provider=provider,
            include_disabled=include_disabled,
        )

    def get_cloud_account_by_id(self, account_id: str, *, include_disabled: bool = False) -> CloudAccountBinding:
        return self._impl.get_cloud_account_by_id(account_id, include_disabled=include_disabled)

    def get_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> CloudAccountBinding:
        return self._impl.get_user_cloud_account(
            user_id,
            account_id=account_id,
            provider=provider,
            include_disabled=include_disabled,
        )

    def upsert_user_cloud_account(
        self,
        *,
        user_id: str,
        provider: str,
        provider_user_id: str,
        display_name: str,
        avatar_url: str | None,
        access_token_ciphertext: str,
        refresh_token_ciphertext: str,
        expires_at: str | None,
        scope: str = "",
        meta: dict[str, Any] | None = None,
    ) -> CloudAccountBinding:
        return self._impl.upsert_user_cloud_account(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            display_name=display_name,
            avatar_url=avatar_url,
            access_token_ciphertext=access_token_ciphertext,
            refresh_token_ciphertext=refresh_token_ciphertext,
            expires_at=expires_at,
            scope=scope,
            meta=meta,
        )

    def disable_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
    ) -> None:
        self._impl.disable_user_cloud_account(
            user_id,
            account_id=account_id,
            provider=provider,
        )

    def change_password(self, user_id: str, *, current_password: str, new_password: str) -> None:
        self._impl.change_password(user_id, current_password=current_password, new_password=new_password)

    def create_password_reset_token(self, email: str) -> str | None:
        return self._impl.create_password_reset_token(email)

    def create_email_verification_token(self, email: str) -> str | None:
        return self._impl.create_email_verification_token(email)

    def verify_email_with_token(self, token: str) -> AuthUser:
        return self._impl.verify_email_with_token(token)

    def reset_password_with_token(self, token: str, *, new_password: str) -> None:
        self._impl.reset_password_with_token(token, new_password=new_password)

    def list_user_roles(self, user_id: str) -> tuple[str, ...]:
        return self._impl.list_user_roles(user_id)

    def user_has_global_role(self, user_id: str, roles: Iterable[str]) -> bool:
        return self._impl.user_has_global_role(user_id, roles)

    def set_user_global_role(self, user_id: str, *, role: str, enabled: bool, granted_by_user_id: str) -> tuple[str, ...]:
        return self._impl.set_user_global_role(user_id, role=role, enabled=enabled, granted_by_user_id=granted_by_user_id)

    def list_users(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        limit: int = 100,
    ) -> tuple[AdminUser, ...]:
        return self._impl.list_users(search=search, status=status, role=role, limit=limit)

    def set_user_status(self, user_id: str, *, status: str) -> AuthUser:
        return self._impl.set_user_status(user_id, status=status)

    def get_admin_overview(self) -> dict[str, int]:
        return self._impl.get_admin_overview()

    def record_admin_action(
        self,
        *,
        actor_user_id: str,
        action_type: str,
        target_kind: str,
        target_id: str,
        summary: str,
    ) -> AdminActionLog:
        return self._impl.record_admin_action(
            actor_user_id=actor_user_id,
            action_type=action_type,
            target_kind=target_kind,
            target_id=target_id,
            summary=summary,
        )

    def list_admin_action_logs(self, *, limit: int = 100) -> tuple[AdminActionLog, ...]:
        return self._impl.list_admin_action_logs(limit=limit)


    def export_snapshot(self) -> dict[str, Any]:
        return self._impl.export_snapshot()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        self._impl.import_snapshot(snapshot, replace=replace)

    def healthcheck(self) -> dict[str, object]:
        return self._impl.healthcheck()
