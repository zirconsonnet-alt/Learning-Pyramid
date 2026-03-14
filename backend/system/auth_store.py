from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.models.desktop_agent import DesktopAgent
from backend.models.desktop_agent_diagnostic_event import DesktopAgentDiagnosticEvent
from backend.models.desktop_agent_hls_job_audit import DesktopAgentHlsJobAudit
from backend.models.desktop_agent_metric_sample import DesktopAgentMetricSample
from backend.models.desktop_agent_pairing_code import DesktopAgentPairingCode
from backend.models.desktop_media_probe_cache import DesktopMediaProbeCache
from backend.models.hls_cache_entry import HlsCacheEntry
from backend.models.media_stream_session import (
    MEDIA_STREAM_SESSION_STATUSES,
    MediaStreamSession,
)
from backend.models.enums import DesktopAgentStatus
from backend.models.errors import NotFound, PreconditionFailure
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


def _session_ttl_days() -> int:
    raw = (os.getenv("PLM_SESSION_TTL_DAYS") or "30").strip()
    try:
        value = int(raw)
    except Exception as exc:
        raise PreconditionFailure("PLM_SESSION_TTL_DAYS must be an integer") from exc
    return max(1, value)


def _desktop_agent_pairing_ttl_minutes() -> int:
    raw = (os.getenv("PLM_DESKTOP_AGENT_PAIRING_TTL_MINUTES") or "10").strip()
    try:
        value = int(raw)
    except Exception as exc:
        raise PreconditionFailure("PLM_DESKTOP_AGENT_PAIRING_TTL_MINUTES must be an integer") from exc
    return max(1, value)


def _pairing_code_text() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    left = "".join(secrets.choice(alphabet) for _ in range(4))
    right = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"{left}-{right}"


def _issue_desktop_agent_tokens() -> tuple[str, str]:
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _normalize_device_text(value: str, *, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise PreconditionFailure(f"{field_name} must be non-empty")
    return text


def _normalize_stream_status(status: str) -> str:
    value = str(status).strip().upper()
    if value not in MEDIA_STREAM_SESSION_STATUSES:
        raise PreconditionFailure("media stream session status is invalid")
    return value


def _require_psycopg() -> Any:
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg[binary] is required for the PostgreSQL auth backend")
    return psycopg


@dataclass(frozen=True, slots=True)
class AuthUser:
    user_id: str
    email: str
    created_at: str


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
        )

    @staticmethod
    def _row_to_desktop_agent(row: Any) -> DesktopAgent:
        agent = DesktopAgent(
            agent_id=str(row["agent_id"]),
            user_id=str(row["user_id"]),
            device_name=str(row["device_name"]),
            platform=str(row["platform"]),
            app_version=str(row["app_version"]),
            status=DesktopAgentStatus(str(row["status"])),
            last_seen_at=str(row["last_seen_at"]),
            paired_at=str(row["paired_at"]),
        )
        agent.validate_write_time()
        return agent

    @staticmethod
    def _row_to_pairing_code(row: Any) -> DesktopAgentPairingCode:
        pairing = DesktopAgentPairingCode(
            pairing_code=str(row["pairing_code"]),
            user_id=str(row["user_id"]),
            expires_at=str(row["expires_at"]),
            used_at=None if row["used_at"] is None else str(row["used_at"]),
            created_at=str(row["created_at"]),
        )
        pairing.validate_write_time()
        return pairing

    @staticmethod
    def _row_to_media_stream_session(row: Any) -> MediaStreamSession:
        stream = MediaStreamSession(
            stream_id=str(row["stream_id"]),
            project_id=str(row["project_id"]),
            instance_id=str(row["instance_id"]),
            agent_id=str(row["agent_id"]),
            user_id=str(row["user_id"]),
            mode=str(row["mode"]),
            status=str(row["status"]),
            range_start=None if row["range_start"] is None else int(row["range_start"]),
            range_end=None if row["range_end"] is None else int(row["range_end"]),
            bytes_from_agent=int(row["bytes_from_agent"]),
            bytes_to_viewer=int(row["bytes_to_viewer"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            expires_at=str(row["expires_at"]),
            finished_at=None if row["finished_at"] is None else str(row["finished_at"]),
            failure_reason=None if row["failure_reason"] is None else str(row["failure_reason"]),
        )
        stream.validate_write_time()
        return stream

    @staticmethod
    def _row_to_desktop_media_probe_cache(row: Any) -> DesktopMediaProbeCache:
        item = DesktopMediaProbeCache(
            project_id=str(row["project_id"]),
            instance_id=str(row["instance_id"]),
            agent_id=str(row["agent_id"]),
            container=str(row["container"]),
            video_codec=None if row["video_codec"] is None else str(row["video_codec"]),
            audio_codec=None if row["audio_codec"] is None else str(row["audio_codec"]),
            duration_ms=None if row["duration_ms"] is None else int(row["duration_ms"]),
            bitrate_bps=None if row["bitrate_bps"] is None else int(row["bitrate_bps"]),
            width=None if row["width"] is None else int(row["width"]),
            height=None if row["height"] is None else int(row["height"]),
            fps=None if row["fps"] is None else float(row["fps"]),
            audio_channels=None if row["audio_channels"] is None else int(row["audio_channels"]),
            audio_sample_rate=None if row["audio_sample_rate"] is None else int(row["audio_sample_rate"]),
            video_stream_count=None if row["video_stream_count"] is None else int(row["video_stream_count"]),
            audio_stream_count=None if row["audio_stream_count"] is None else int(row["audio_stream_count"]),
            subtitle_stream_count=None if row["subtitle_stream_count"] is None else int(row["subtitle_stream_count"]),
            size_bytes=None if row["size_bytes"] is None else int(row["size_bytes"]),
            modified_at=None if row["modified_at"] is None else str(row["modified_at"]),
            updated_at=str(row["updated_at"]),
        )
        item.validate_write_time()
        return item

    @staticmethod
    def _row_to_hls_cache_entry(row: Any) -> HlsCacheEntry:
        item = HlsCacheEntry(
            cache_key=str(row["cache_key"]),
            project_id=str(row["project_id"]),
            instance_id=str(row["instance_id"]),
            agent_id=str(row["agent_id"]),
            profile=str(row["profile"]),
            segment_name=str(row["segment_name"]),
            file_path=str(row["file_path"]),
            size_bytes=int(row["size_bytes"]),
            created_at=str(row["created_at"]),
            last_accessed_at=str(row["last_accessed_at"]),
            expires_at=str(row["expires_at"]),
        )
        item.validate_write_time()
        return item

    @staticmethod
    def _row_to_desktop_agent_hls_job_audit(row: Any) -> DesktopAgentHlsJobAudit:
        item = DesktopAgentHlsJobAudit(
            job_id=str(row["job_id"]),
            cache_key=str(row["cache_key"]),
            project_id=str(row["project_id"]),
            instance_id=str(row["instance_id"]),
            agent_id=str(row["agent_id"]),
            relative_path=str(row["relative_path"]),
            profile=str(row["profile"]),
            state=str(row["state"]),
            artifact_count=int(row["artifact_count"]),
            artifact_bytes=int(row["artifact_bytes"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            expires_at=str(row["expires_at"]),
            started_at=None if row["started_at"] is None else str(row["started_at"]),
            finished_at=None if row["finished_at"] is None else str(row["finished_at"]),
            last_artifact_at=None if row["last_artifact_at"] is None else str(row["last_artifact_at"]),
            message=None if row["message"] is None else str(row["message"]),
        )
        item.validate_write_time()
        return item

    @staticmethod
    def _row_to_desktop_agent_metric_sample(row: Any) -> DesktopAgentMetricSample:
        item = DesktopAgentMetricSample(
            project_id=str(row["project_id"]),
            bucket_start=str(row["bucket_start"]),
            bucket_seconds=int(row["bucket_seconds"]),
            captured_at=str(row["captured_at"]),
            session_count=int(row["session_count"]),
            active_stream_count=int(row["active_stream_count"]),
            completed_stream_count=int(row["completed_stream_count"]),
            failed_stream_count=int(row["failed_stream_count"]),
            cancelled_stream_count=int(row["cancelled_stream_count"]),
            bytes_from_agent_total=int(row["bytes_from_agent_total"]),
            bytes_to_viewer_total=int(row["bytes_to_viewer_total"]),
            hls_job_count=int(row["hls_job_count"]),
            active_hls_job_count=int(row["active_hls_job_count"]),
            completed_hls_job_count=int(row["completed_hls_job_count"]),
            failed_hls_job_count=int(row["failed_hls_job_count"]),
            cancelled_hls_job_count=int(row["cancelled_hls_job_count"]),
            hls_artifact_bytes_total=int(row["hls_artifact_bytes_total"]),
            hls_cache_entry_count=int(row["hls_cache_entry_count"]),
            hls_cache_bytes=int(row["hls_cache_bytes"]),
        )
        item.validate_write_time()
        return item

    @staticmethod
    def _row_to_desktop_agent_diagnostic_event(row: Any) -> DesktopAgentDiagnosticEvent:
        item = DesktopAgentDiagnosticEvent(
            event_id=str(row["event_id"]),
            agent_id=str(row["agent_id"]),
            user_id=str(row["user_id"]),
            project_id=None if row["project_id"] is None else str(row["project_id"]),
            instance_id=None if row["instance_id"] is None else str(row["instance_id"]),
            relative_path=None if row["relative_path"] is None else str(row["relative_path"]),
            level=str(row["level"]),
            category=str(row["category"]),
            event_type=str(row["event_type"]),
            message=str(row["message"]),
            details=str(row["details"]),
            created_at=str(row["created_at"]),
        )
        item.validate_write_time()
        return item

    @staticmethod
    def _snapshot_payload(
        *,
        users: list[dict[str, str]],
        sessions: list[dict[str, str]],
        memberships: list[dict[str, str]],
        desktop_agents: list[dict[str, str]],
        desktop_agent_pairing_codes: list[dict[str, str | None]],
        desktop_media_probe_cache: list[dict[str, str | int | float | None]],
        hls_cache_entries: list[dict[str, str | int]],
        desktop_agent_hls_job_audits: list[dict[str, str | int | None]],
        desktop_agent_metric_samples: list[dict[str, str | int]],
        desktop_agent_diagnostic_events: list[dict[str, str | None]],
        media_stream_sessions: list[dict[str, str | int | None]],
    ) -> dict[str, Any]:
        return {
            "users": users,
            "sessions": sessions,
            "projectMemberships": memberships,
            "desktopAgents": desktop_agents,
            "desktopAgentPairingCodes": desktop_agent_pairing_codes,
            "desktopMediaProbeCache": desktop_media_probe_cache,
            "hlsCacheEntries": hls_cache_entries,
            "desktopAgentHlsJobAudits": desktop_agent_hls_job_audits,
            "desktopAgentMetricSamples": desktop_agent_metric_samples,
            "desktopAgentDiagnosticEvents": desktop_agent_diagnostic_events,
            "mediaStreamSessions": media_stream_sessions,
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

    @staticmethod
    def _ensure_sqlite_table_columns(
        conn: sqlite3.Connection,
        table_name: str,
        columns: dict[str, str],
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in rows}
        for column_name, column_sql in columns.items():
            if column_name in existing:
                continue
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

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
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        session_token TEXT PRIMARY KEY,
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

                    CREATE TABLE IF NOT EXISTS desktop_agents (
                        agent_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        app_version TEXT NOT NULL,
                        status TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL,
                        paired_at TEXT NOT NULL,
                        agent_token_hash TEXT NOT NULL,
                        refresh_token_hash TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS desktop_agent_pairing_codes (
                        pairing_code TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        used_at TEXT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS media_stream_sessions (
                        stream_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        status TEXT NOT NULL,
                        range_start INTEGER NULL,
                        range_end INTEGER NULL,
                        bytes_from_agent INTEGER NOT NULL,
                        bytes_to_viewer INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        finished_at TEXT NULL,
                        failure_reason TEXT NULL,
                        FOREIGN KEY(agent_id) REFERENCES desktop_agents(agent_id) ON DELETE CASCADE,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_media_stream_sessions_project
                    ON media_stream_sessions (project_id, created_at, stream_id);

                    CREATE INDEX IF NOT EXISTS idx_media_stream_sessions_agent
                    ON media_stream_sessions (agent_id, created_at, stream_id);

                    CREATE INDEX IF NOT EXISTS idx_media_stream_sessions_user
                    ON media_stream_sessions (user_id, created_at, stream_id);

                    CREATE TABLE IF NOT EXISTS desktop_media_probe_cache (
                        project_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        container TEXT NOT NULL,
                        video_codec TEXT NULL,
                        audio_codec TEXT NULL,
                        duration_ms INTEGER NULL,
                        bitrate_bps INTEGER NULL,
                        width INTEGER NULL,
                        height INTEGER NULL,
                        fps REAL NULL,
                        audio_channels INTEGER NULL,
                        audio_sample_rate INTEGER NULL,
                        video_stream_count INTEGER NULL,
                        audio_stream_count INTEGER NULL,
                        subtitle_stream_count INTEGER NULL,
                        size_bytes INTEGER NULL,
                        modified_at TEXT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(project_id, instance_id, agent_id),
                        FOREIGN KEY(agent_id) REFERENCES desktop_agents(agent_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_desktop_media_probe_cache_project
                    ON desktop_media_probe_cache (project_id, updated_at, instance_id, agent_id);

                    CREATE TABLE IF NOT EXISTS hls_cache_entries (
                        cache_key TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        profile TEXT NOT NULL,
                        segment_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        last_accessed_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        PRIMARY KEY(cache_key, segment_name),
                        FOREIGN KEY(agent_id) REFERENCES desktop_agents(agent_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_hls_cache_entries_project
                    ON hls_cache_entries (project_id, cache_key, segment_name);

                    CREATE INDEX IF NOT EXISTS idx_hls_cache_entries_expires
                    ON hls_cache_entries (expires_at, last_accessed_at, cache_key, segment_name);

                    CREATE TABLE IF NOT EXISTS desktop_agent_hls_job_audits (
                        job_id TEXT PRIMARY KEY,
                        cache_key TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        relative_path TEXT NOT NULL,
                        profile TEXT NOT NULL,
                        state TEXT NOT NULL,
                        artifact_count INTEGER NOT NULL,
                        artifact_bytes INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        started_at TEXT NULL,
                        finished_at TEXT NULL,
                        last_artifact_at TEXT NULL,
                        message TEXT NULL,
                        FOREIGN KEY(agent_id) REFERENCES desktop_agents(agent_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_desktop_agent_hls_job_audits_project
                    ON desktop_agent_hls_job_audits (project_id, updated_at, job_id);

                    CREATE INDEX IF NOT EXISTS idx_desktop_agent_hls_job_audits_agent
                    ON desktop_agent_hls_job_audits (agent_id, updated_at, job_id);

                    CREATE INDEX IF NOT EXISTS idx_desktop_agent_hls_job_audits_cache_key
                    ON desktop_agent_hls_job_audits (cache_key, updated_at, created_at, job_id);

                    CREATE TABLE IF NOT EXISTS desktop_agent_metric_samples (
                        project_id TEXT NOT NULL,
                        bucket_start TEXT NOT NULL,
                        bucket_seconds INTEGER NOT NULL,
                        captured_at TEXT NOT NULL,
                        session_count INTEGER NOT NULL,
                        active_stream_count INTEGER NOT NULL,
                        completed_stream_count INTEGER NOT NULL,
                        failed_stream_count INTEGER NOT NULL,
                        cancelled_stream_count INTEGER NOT NULL,
                        bytes_from_agent_total INTEGER NOT NULL,
                        bytes_to_viewer_total INTEGER NOT NULL,
                        hls_job_count INTEGER NOT NULL,
                        active_hls_job_count INTEGER NOT NULL,
                        completed_hls_job_count INTEGER NOT NULL,
                        failed_hls_job_count INTEGER NOT NULL,
                        cancelled_hls_job_count INTEGER NOT NULL,
                        hls_artifact_bytes_total INTEGER NOT NULL,
                        hls_cache_entry_count INTEGER NOT NULL,
                        hls_cache_bytes INTEGER NOT NULL,
                        PRIMARY KEY(project_id, bucket_start)
                    );

                    CREATE INDEX IF NOT EXISTS idx_desktop_agent_metric_samples_bucket
                    ON desktop_agent_metric_samples (bucket_start, project_id);

                    CREATE TABLE IF NOT EXISTS desktop_agent_diagnostic_events (
                        event_id TEXT PRIMARY KEY,
                        agent_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        project_id TEXT NULL,
                        instance_id TEXT NULL,
                        relative_path TEXT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(agent_id) REFERENCES desktop_agents(agent_id) ON DELETE CASCADE,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_desktop_agent_diagnostic_events_user
                    ON desktop_agent_diagnostic_events (user_id, created_at, event_id);

                    CREATE INDEX IF NOT EXISTS idx_desktop_agent_diagnostic_events_agent
                    ON desktop_agent_diagnostic_events (agent_id, created_at, event_id);
                    """
                )
                self._ensure_sqlite_table_columns(
                    conn,
                    "desktop_media_probe_cache",
                    {
                        "fps": "REAL NULL",
                        "audio_channels": "INTEGER NULL",
                        "audio_sample_rate": "INTEGER NULL",
                        "video_stream_count": "INTEGER NULL",
                        "audio_stream_count": "INTEGER NULL",
                        "subtitle_stream_count": "INTEGER NULL",
                        "size_bytes": "INTEGER NULL",
                        "modified_at": "TEXT NULL",
                    },
                )
                conn.commit()
            finally:
                conn.close()

    def create_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        user = AuthUser(user_id=f"user_{uuid.uuid4().hex}", email=normalized_email, created_at=_utc_now().isoformat())
        password_hash = self._hash_password(password)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (user.user_id, user.email, password_hash, user.created_at),
                )
                conn.commit()
                return user
            except sqlite3.IntegrityError as exc:
                raise PreconditionFailure("email already exists") from exc
            finally:
                conn.close()

    def authenticate_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT user_id, email, password_hash, created_at FROM users WHERE email = ?",
                (normalized_email,),
            ).fetchone()
        finally:
            conn.close()
        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise PreconditionFailure("invalid email or password")
        return self._row_to_user(row)

    def create_session(self, user_id: str) -> str:
        now = _utc_now()
        token = secrets.token_urlsafe(32)
        expires_at = (now + timedelta(days=_session_ttl_days())).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO sessions (session_token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (token, str(user_id), now.isoformat(), expires_at),
                )
                conn.commit()
                return token
            finally:
                conn.close()

    def get_user_by_session(self, session_token: str) -> AuthUser:
        token = str(session_token).strip()
        if not token:
            raise NotFound("session")
        now_text = _utc_now().isoformat()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT u.user_id, u.email, u.created_at
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.session_token = ? AND s.expires_at > ?
                """,
                (token, now_text),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("session")
        return self._row_to_user(row)

    def delete_session(self, session_token: str) -> None:
        token = str(session_token).strip()
        if not token:
            return
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM sessions WHERE session_token = ?", (token,))
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

    def create_desktop_agent_pairing_code(self, user_id: str) -> DesktopAgentPairingCode:
        normalized_user_id = _normalize_device_text(user_id, field_name="user_id")
        created_at = _utc_now()
        expires_at = created_at + timedelta(minutes=_desktop_agent_pairing_ttl_minutes())
        pairing = DesktopAgentPairingCode(
            pairing_code=_pairing_code_text(),
            user_id=normalized_user_id,
            expires_at=expires_at.isoformat(),
            used_at=None,
            created_at=created_at.isoformat(),
        )
        pairing.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_pairing_codes (pairing_code, user_id, expires_at, used_at, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pairing.pairing_code, pairing.user_id, pairing.expires_at, pairing.used_at, pairing.created_at),
                )
                conn.commit()
                return pairing
            finally:
                conn.close()

    def pair_desktop_agent(
        self,
        pairing_code: str,
        *,
        device_name: str,
        platform: str,
        app_version: str,
    ) -> tuple[DesktopAgent, str, str]:
        normalized_pairing_code = _normalize_device_text(pairing_code, field_name="pairing_code").upper()
        normalized_device_name = _normalize_device_text(device_name, field_name="device_name")
        normalized_platform = _normalize_device_text(platform, field_name="platform").lower()
        normalized_app_version = _normalize_device_text(app_version, field_name="app_version")
        now = _utc_now()
        agent_token, refresh_token = _issue_desktop_agent_tokens()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT pairing_code, user_id, expires_at, used_at, created_at
                    FROM desktop_agent_pairing_codes
                    WHERE pairing_code = ?
                    """,
                    (normalized_pairing_code,),
                ).fetchone()
                if row is None:
                    raise NotFound("desktop_agent_pairing_code")
                pairing = self._row_to_pairing_code(row)
                if pairing.used_at is not None:
                    raise PreconditionFailure("pairing code already used")
                if datetime.fromisoformat(pairing.expires_at) <= now:
                    raise PreconditionFailure("pairing code expired")

                paired_agent = DesktopAgent(
                    agent_id="",
                    user_id=pairing.user_id,
                    device_name=normalized_device_name,
                    platform=normalized_platform,
                    app_version=normalized_app_version,
                    status=DesktopAgentStatus.OFFLINE,
                    last_seen_at=now.isoformat(),
                    paired_at=now.isoformat(),
                )
                existing_row = conn.execute(
                    """
                    SELECT agent_id
                    FROM desktop_agents
                    WHERE user_id = ? AND lower(device_name) = lower(?) AND platform = ?
                    ORDER BY paired_at DESC, agent_id DESC
                    LIMIT 1
                    """,
                    (pairing.user_id, normalized_device_name, normalized_platform),
                ).fetchone()
                paired_agent = DesktopAgent(
                    agent_id=(
                        str(existing_row["agent_id"])
                        if existing_row is not None
                        else f"agent_{uuid.uuid4().hex}"
                    ),
                    user_id=paired_agent.user_id,
                    device_name=paired_agent.device_name,
                    platform=paired_agent.platform,
                    app_version=paired_agent.app_version,
                    status=paired_agent.status,
                    last_seen_at=paired_agent.last_seen_at,
                    paired_at=paired_agent.paired_at,
                )
                paired_agent.validate_write_time()
                if existing_row is None:
                    conn.execute(
                        """
                        INSERT INTO desktop_agents (
                            agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at,
                            agent_token_hash, refresh_token_hash
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            paired_agent.agent_id,
                            paired_agent.user_id,
                            paired_agent.device_name,
                            paired_agent.platform,
                            paired_agent.app_version,
                            paired_agent.status.value,
                            paired_agent.last_seen_at,
                            paired_agent.paired_at,
                            _token_hash(agent_token),
                            _token_hash(refresh_token),
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE desktop_agents
                        SET device_name = ?, platform = ?, app_version = ?, status = ?, last_seen_at = ?, paired_at = ?,
                            agent_token_hash = ?, refresh_token_hash = ?
                        WHERE agent_id = ?
                        """,
                        (
                            paired_agent.device_name,
                            paired_agent.platform,
                            paired_agent.app_version,
                            paired_agent.status.value,
                            paired_agent.last_seen_at,
                            paired_agent.paired_at,
                            _token_hash(agent_token),
                            _token_hash(refresh_token),
                            paired_agent.agent_id,
                        ),
                    )
                conn.execute(
                    "UPDATE desktop_agent_pairing_codes SET used_at = ? WHERE pairing_code = ?",
                    (now.isoformat(), normalized_pairing_code),
                )
                conn.commit()
                return paired_agent, agent_token, refresh_token
            finally:
                conn.close()

    def list_desktop_agents_for_user(self, user_id: str) -> tuple[DesktopAgent, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE user_id = ?
                ORDER BY paired_at ASC, agent_id ASC
                """,
                (str(user_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent(row) for row in rows)

    def user_has_desktop_agent(self, user_id: str, agent_id: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM desktop_agents WHERE agent_id = ? AND user_id = ? LIMIT 1",
                (str(agent_id), str(user_id)),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def get_desktop_agent_by_token(self, agent_token: str) -> DesktopAgent:
        token_hash = _token_hash(_normalize_device_text(agent_token, field_name="agent_token"))
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE agent_token_hash = ?
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("desktop_agent")
        return self._row_to_desktop_agent(row)

    def get_desktop_agent_by_refresh_token(self, refresh_token: str) -> DesktopAgent:
        token_hash = _token_hash(_normalize_device_text(refresh_token, field_name="refresh_token"))
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE refresh_token_hash = ?
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("desktop_agent")
        return self._row_to_desktop_agent(row)

    def refresh_desktop_agent_tokens(self, refresh_token: str) -> tuple[DesktopAgent, str, str]:
        current = self.get_desktop_agent_by_refresh_token(refresh_token)
        next_agent_token, next_refresh_token = _issue_desktop_agent_tokens()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE desktop_agents
                    SET agent_token_hash = ?, refresh_token_hash = ?
                    WHERE agent_id = ?
                    """,
                    (_token_hash(next_agent_token), _token_hash(next_refresh_token), current.agent_id),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_desktop_agent(current.agent_id), next_agent_token, next_refresh_token

    def get_desktop_agent(self, agent_id: str) -> DesktopAgent:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE agent_id = ?
                LIMIT 1
                """,
                (str(agent_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("desktop_agent")
        return self._row_to_desktop_agent(row)

    def update_desktop_agent_presence(
        self,
        agent_id: str,
        *,
        status: DesktopAgentStatus,
        last_seen_at: str | None = None,
        device_name: str | None = None,
        app_version: str | None = None,
    ) -> DesktopAgent:
        updated_at = last_seen_at or _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                current = self.get_desktop_agent(agent_id)
                next_device_name = current.device_name if device_name is None else _normalize_device_text(device_name, field_name="device_name")
                next_app_version = current.app_version if app_version is None else _normalize_device_text(app_version, field_name="app_version")
                conn.execute(
                    """
                    UPDATE desktop_agents
                    SET status = ?, last_seen_at = ?, device_name = ?, app_version = ?
                    WHERE agent_id = ?
                    """,
                    (status.value, updated_at, next_device_name, next_app_version, str(agent_id)),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_desktop_agent(agent_id)

    def mark_stale_desktop_agents_offline(self, *, offline_before: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    UPDATE desktop_agents
                    SET status = ?
                    WHERE status = ? AND last_seen_at < ?
                    """,
                    (DesktopAgentStatus.OFFLINE.value, DesktopAgentStatus.ONLINE.value, str(offline_before)),
                )
                conn.commit()
                return int(cursor.rowcount or 0)
            finally:
                conn.close()

    def create_media_stream_session(self, stream: MediaStreamSession) -> MediaStreamSession:
        stream.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO media_stream_sessions (
                        stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                        bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stream.stream_id,
                        stream.project_id,
                        stream.instance_id,
                        stream.agent_id,
                        stream.user_id,
                        stream.mode,
                        stream.status,
                        None if stream.range_start is None else int(stream.range_start),
                        None if stream.range_end is None else int(stream.range_end),
                        int(stream.bytes_from_agent),
                        int(stream.bytes_to_viewer),
                        stream.created_at,
                        stream.updated_at,
                        stream.expires_at,
                        stream.finished_at,
                        stream.failure_reason,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_media_stream_session(stream.stream_id)

    def get_media_stream_session(self, stream_id: str) -> MediaStreamSession:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                       bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                FROM media_stream_sessions
                WHERE stream_id = ?
                LIMIT 1
                """,
                (str(stream_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("media_stream_session")
        return self._row_to_media_stream_session(row)

    def list_media_stream_sessions_for_project(self, project_id: str) -> tuple[MediaStreamSession, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                       bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                FROM media_stream_sessions
                WHERE project_id = ?
                ORDER BY created_at ASC, stream_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_media_stream_session(row) for row in rows)

    def list_all_media_stream_sessions(self) -> tuple[MediaStreamSession, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                       bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                FROM media_stream_sessions
                ORDER BY updated_at DESC, created_at DESC, stream_id DESC
                """
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_media_stream_session(row) for row in rows)

    def mark_media_stream_session_streaming(self, stream_id: str) -> MediaStreamSession:
        current = self.get_media_stream_session(stream_id)
        if current.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return current
        updated_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET status = ?, updated_at = ?, failure_reason = NULL
                    WHERE stream_id = ?
                    """,
                    ("STREAMING", updated_at, str(stream_id)),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_media_stream_session(stream_id)

    def add_media_stream_session_agent_bytes(self, stream_id: str, delta: int) -> MediaStreamSession:
        delta_int = int(delta)
        if delta_int < 0:
            raise PreconditionFailure("media stream session delta must be >= 0")
        current = self.get_media_stream_session(stream_id)
        if current.status in {"FAILED", "CANCELLED"}:
            return current
        updated_at = _utc_now().isoformat()
        next_status = "STREAMING" if current.status == "OPENING" else current.status
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET bytes_from_agent = bytes_from_agent + ?, status = ?, updated_at = ?
                    WHERE stream_id = ?
                    """,
                    (delta_int, next_status, updated_at, str(stream_id)),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_media_stream_session(stream_id)

    def add_media_stream_session_viewer_bytes(self, stream_id: str, delta: int) -> MediaStreamSession:
        delta_int = int(delta)
        if delta_int < 0:
            raise PreconditionFailure("media stream session delta must be >= 0")
        current = self.get_media_stream_session(stream_id)
        if current.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return current
        updated_at = _utc_now().isoformat()
        next_status = "STREAMING" if current.status == "OPENING" else current.status
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET bytes_to_viewer = bytes_to_viewer + ?, status = ?, updated_at = ?
                    WHERE stream_id = ?
                    """,
                    (delta_int, next_status, updated_at, str(stream_id)),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_media_stream_session(stream_id)

    def finalize_media_stream_session(
        self,
        stream_id: str,
        *,
        status: str,
        failure_reason: str | None = None,
    ) -> MediaStreamSession:
        next_status = _normalize_stream_status(status)
        if next_status not in {"COMPLETED", "FAILED", "CANCELLED"}:
            raise PreconditionFailure("media stream session final status must be terminal")
        current = self.get_media_stream_session(stream_id)
        if current.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return current
        finished_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET status = ?, updated_at = ?, finished_at = ?, failure_reason = ?
                    WHERE stream_id = ?
                    """,
                    (next_status, finished_at, finished_at, None if failure_reason is None else str(failure_reason), str(stream_id)),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_media_stream_session(stream_id)

    def upsert_desktop_media_probe_cache(self, item: DesktopMediaProbeCache) -> DesktopMediaProbeCache:
        item.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO desktop_media_probe_cache (
                        project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                        bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                        audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, instance_id, agent_id) DO UPDATE SET
                        container = excluded.container,
                        video_codec = excluded.video_codec,
                        audio_codec = excluded.audio_codec,
                        duration_ms = excluded.duration_ms,
                        bitrate_bps = excluded.bitrate_bps,
                        width = excluded.width,
                        height = excluded.height,
                        fps = excluded.fps,
                        audio_channels = excluded.audio_channels,
                        audio_sample_rate = excluded.audio_sample_rate,
                        video_stream_count = excluded.video_stream_count,
                        audio_stream_count = excluded.audio_stream_count,
                        subtitle_stream_count = excluded.subtitle_stream_count,
                        size_bytes = excluded.size_bytes,
                        modified_at = excluded.modified_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        item.project_id,
                        item.instance_id,
                        item.agent_id,
                        item.container,
                        item.video_codec,
                        item.audio_codec,
                        None if item.duration_ms is None else int(item.duration_ms),
                        None if item.bitrate_bps is None else int(item.bitrate_bps),
                        None if item.width is None else int(item.width),
                        None if item.height is None else int(item.height),
                        None if item.fps is None else float(item.fps),
                        None if item.audio_channels is None else int(item.audio_channels),
                        None if item.audio_sample_rate is None else int(item.audio_sample_rate),
                        None if item.video_stream_count is None else int(item.video_stream_count),
                        None if item.audio_stream_count is None else int(item.audio_stream_count),
                        None if item.subtitle_stream_count is None else int(item.subtitle_stream_count),
                        None if item.size_bytes is None else int(item.size_bytes),
                        item.modified_at,
                        item.updated_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return self.get_desktop_media_probe_cache(item.project_id, item.instance_id, item.agent_id)

    def get_desktop_media_probe_cache(
        self,
        project_id: str,
        instance_id: str,
        agent_id: str,
    ) -> DesktopMediaProbeCache | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                       bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                       audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                FROM desktop_media_probe_cache
                WHERE project_id = ? AND instance_id = ? AND agent_id = ?
                LIMIT 1
                """,
                (str(project_id), str(instance_id), str(agent_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_desktop_media_probe_cache(row)

    def delete_desktop_media_probe_cache(self, project_id: str, instance_id: str, agent_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    DELETE FROM desktop_media_probe_cache
                    WHERE project_id = ? AND instance_id = ? AND agent_id = ?
                    """,
                    (str(project_id), str(instance_id), str(agent_id)),
                )
                conn.commit()
            finally:
                conn.close()

    def upsert_hls_cache_entry(self, item: HlsCacheEntry) -> HlsCacheEntry:
        item.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO hls_cache_entries (
                        cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                        created_at, last_accessed_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key, segment_name) DO UPDATE SET
                        project_id = excluded.project_id,
                        instance_id = excluded.instance_id,
                        agent_id = excluded.agent_id,
                        profile = excluded.profile,
                        file_path = excluded.file_path,
                        size_bytes = excluded.size_bytes,
                        last_accessed_at = excluded.last_accessed_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        item.cache_key,
                        item.project_id,
                        item.instance_id,
                        item.agent_id,
                        item.profile,
                        item.segment_name,
                        item.file_path,
                        int(item.size_bytes),
                        item.created_at,
                        item.last_accessed_at,
                        item.expires_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        entry = self.get_hls_cache_entry(item.cache_key, item.segment_name)
        if entry is None:
            raise NotFound("hls_cache_entry")
        return entry

    def get_hls_cache_entry(self, cache_key: str, segment_name: str) -> HlsCacheEntry | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                       created_at, last_accessed_at, expires_at
                FROM hls_cache_entries
                WHERE cache_key = ? AND segment_name = ?
                LIMIT 1
                """,
                (str(cache_key), str(segment_name)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_hls_cache_entry(row)

    def list_hls_cache_entries(self, cache_key: str) -> tuple[HlsCacheEntry, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                       created_at, last_accessed_at, expires_at
                FROM hls_cache_entries
                WHERE cache_key = ?
                ORDER BY segment_name ASC
                """,
                (str(cache_key),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_hls_cache_entry(row) for row in rows)

    def list_all_hls_cache_entries(self) -> tuple[HlsCacheEntry, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                       created_at, last_accessed_at, expires_at
                FROM hls_cache_entries
                ORDER BY last_accessed_at ASC, created_at ASC, cache_key ASC, segment_name ASC
                """
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_hls_cache_entry(row) for row in rows)

    def touch_hls_cache_entry_access(
        self,
        cache_key: str,
        segment_name: str,
        *,
        last_accessed_at: str | None = None,
    ) -> HlsCacheEntry:
        current = self.get_hls_cache_entry(cache_key, segment_name)
        if current is None:
            raise NotFound("hls_cache_entry")
        next_accessed_at = str(last_accessed_at or _utc_now().isoformat())
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE hls_cache_entries
                    SET last_accessed_at = ?
                    WHERE cache_key = ? AND segment_name = ?
                    """,
                    (next_accessed_at, str(cache_key), str(segment_name)),
                )
                conn.commit()
            finally:
                conn.close()
        updated = self.get_hls_cache_entry(cache_key, segment_name)
        if updated is None:
            raise NotFound("hls_cache_entry")
        return updated

    def delete_hls_cache_entry(self, cache_key: str, segment_name: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    DELETE FROM hls_cache_entries
                    WHERE cache_key = ? AND segment_name = ?
                    """,
                    (str(cache_key), str(segment_name)),
                )
                conn.commit()
            finally:
                conn.close()

    def upsert_desktop_agent_hls_job_audit(self, item: DesktopAgentHlsJobAudit) -> DesktopAgentHlsJobAudit:
        item.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_hls_job_audits (
                        job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                        artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                        last_artifact_at, message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        cache_key = excluded.cache_key,
                        project_id = excluded.project_id,
                        instance_id = excluded.instance_id,
                        agent_id = excluded.agent_id,
                        relative_path = excluded.relative_path,
                        profile = excluded.profile,
                        state = excluded.state,
                        artifact_count = excluded.artifact_count,
                        artifact_bytes = excluded.artifact_bytes,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at,
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at,
                        last_artifact_at = excluded.last_artifact_at,
                        message = excluded.message
                    """,
                    (
                        item.job_id,
                        item.cache_key,
                        item.project_id,
                        item.instance_id,
                        item.agent_id,
                        item.relative_path,
                        item.profile,
                        item.state,
                        int(item.artifact_count),
                        int(item.artifact_bytes),
                        item.created_at,
                        item.updated_at,
                        item.expires_at,
                        item.started_at,
                        item.finished_at,
                        item.last_artifact_at,
                        item.message,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        audit = self.get_desktop_agent_hls_job_audit(item.job_id)
        if audit is None:
            raise NotFound("desktop_agent_hls_job_audit")
        return audit

    def get_desktop_agent_hls_job_audit(self, job_id: str) -> DesktopAgentHlsJobAudit | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                WHERE job_id = ?
                LIMIT 1
                """,
                (str(job_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_desktop_agent_hls_job_audit(row)

    def get_latest_desktop_agent_hls_job_audit_by_cache_key(self, cache_key: str) -> DesktopAgentHlsJobAudit | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                WHERE cache_key = ?
                ORDER BY updated_at DESC, created_at DESC, job_id DESC
                LIMIT 1
                """,
                (str(cache_key),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_desktop_agent_hls_job_audit(row)

    def list_desktop_agent_hls_job_audits_for_project(self, project_id: str) -> tuple[DesktopAgentHlsJobAudit, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                WHERE project_id = ?
                ORDER BY updated_at DESC, created_at DESC, job_id DESC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent_hls_job_audit(row) for row in rows)

    def list_all_desktop_agent_hls_job_audits(self) -> tuple[DesktopAgentHlsJobAudit, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                ORDER BY updated_at DESC, created_at DESC, job_id DESC
                """
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent_hls_job_audit(row) for row in rows)

    def upsert_desktop_agent_metric_sample(self, item: DesktopAgentMetricSample) -> DesktopAgentMetricSample:
        item.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_metric_samples (
                        project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                        completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                        bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                        failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                        hls_cache_entry_count, hls_cache_bytes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, bucket_start) DO UPDATE SET
                        bucket_seconds = excluded.bucket_seconds,
                        captured_at = excluded.captured_at,
                        session_count = excluded.session_count,
                        active_stream_count = excluded.active_stream_count,
                        completed_stream_count = excluded.completed_stream_count,
                        failed_stream_count = excluded.failed_stream_count,
                        cancelled_stream_count = excluded.cancelled_stream_count,
                        bytes_from_agent_total = excluded.bytes_from_agent_total,
                        bytes_to_viewer_total = excluded.bytes_to_viewer_total,
                        hls_job_count = excluded.hls_job_count,
                        active_hls_job_count = excluded.active_hls_job_count,
                        completed_hls_job_count = excluded.completed_hls_job_count,
                        failed_hls_job_count = excluded.failed_hls_job_count,
                        cancelled_hls_job_count = excluded.cancelled_hls_job_count,
                        hls_artifact_bytes_total = excluded.hls_artifact_bytes_total,
                        hls_cache_entry_count = excluded.hls_cache_entry_count,
                        hls_cache_bytes = excluded.hls_cache_bytes
                    """,
                    (
                        item.project_id,
                        item.bucket_start,
                        int(item.bucket_seconds),
                        item.captured_at,
                        int(item.session_count),
                        int(item.active_stream_count),
                        int(item.completed_stream_count),
                        int(item.failed_stream_count),
                        int(item.cancelled_stream_count),
                        int(item.bytes_from_agent_total),
                        int(item.bytes_to_viewer_total),
                        int(item.hls_job_count),
                        int(item.active_hls_job_count),
                        int(item.completed_hls_job_count),
                        int(item.failed_hls_job_count),
                        int(item.cancelled_hls_job_count),
                        int(item.hls_artifact_bytes_total),
                        int(item.hls_cache_entry_count),
                        int(item.hls_cache_bytes),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        sample = self.get_desktop_agent_metric_sample(item.project_id, item.bucket_start)
        if sample is None:
            raise NotFound("desktop_agent_metric_sample")
        return sample

    def get_desktop_agent_metric_sample(self, project_id: str, bucket_start: str) -> DesktopAgentMetricSample | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                       completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                       bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                       failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                       hls_cache_entry_count, hls_cache_bytes
                FROM desktop_agent_metric_samples
                WHERE project_id = ? AND bucket_start = ?
                LIMIT 1
                """,
                (str(project_id), str(bucket_start)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_desktop_agent_metric_sample(row)

    def list_desktop_agent_metric_samples_for_project(
        self,
        project_id: str,
        *,
        since: str | None = None,
    ) -> tuple[DesktopAgentMetricSample, ...]:
        conn = self._connect()
        try:
            if since is None:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    WHERE project_id = ?
                    ORDER BY bucket_start ASC, project_id ASC
                    """,
                    (str(project_id),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    WHERE project_id = ? AND bucket_start >= ?
                    ORDER BY bucket_start ASC, project_id ASC
                    """,
                    (str(project_id), str(since)),
                ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent_metric_sample(row) for row in rows)

    def list_all_desktop_agent_metric_samples(
        self,
        *,
        since: str | None = None,
    ) -> tuple[DesktopAgentMetricSample, ...]:
        conn = self._connect()
        try:
            if since is None:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    ORDER BY bucket_start ASC, project_id ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    WHERE bucket_start >= ?
                    ORDER BY bucket_start ASC, project_id ASC
                    """,
                    (str(since),),
                ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent_metric_sample(row) for row in rows)

    def delete_desktop_agent_metric_samples_before(self, before: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    DELETE FROM desktop_agent_metric_samples
                    WHERE bucket_start < ?
                    """,
                    (str(before),),
                )
                conn.commit()
                return int(cursor.rowcount or 0)
            finally:
                conn.close()

    def create_desktop_agent_diagnostic_event(self, item: DesktopAgentDiagnosticEvent) -> DesktopAgentDiagnosticEvent:
        item.validate_write_time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_diagnostic_events (
                        event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                        event_type, message, details, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.event_id,
                        item.agent_id,
                        item.user_id,
                        item.project_id,
                        item.instance_id,
                        item.relative_path,
                        item.level,
                        item.category,
                        item.event_type,
                        item.message,
                        item.details,
                        item.created_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                       event_type, message, details, created_at
                FROM desktop_agent_diagnostic_events
                WHERE event_id = ?
                LIMIT 1
                """,
                (item.event_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("desktop_agent_diagnostic_event")
        return self._row_to_desktop_agent_diagnostic_event(row)

    def list_desktop_agent_diagnostic_events_for_user(
        self,
        user_id: str,
        *,
        since: str | None = None,
        limit: int | None = None,
    ) -> tuple[DesktopAgentDiagnosticEvent, ...]:
        limit_value = None if limit is None else max(1, int(limit))
        conn = self._connect()
        try:
            if since is None and limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = ?
                    ORDER BY created_at DESC, event_id DESC
                    """,
                    (str(user_id),),
                ).fetchall()
            elif since is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = ?
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT ?
                    """,
                    (str(user_id), limit_value),
                ).fetchall()
            elif limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = ? AND created_at >= ?
                    ORDER BY created_at DESC, event_id DESC
                    """,
                    (str(user_id), str(since)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = ? AND created_at >= ?
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT ?
                    """,
                    (str(user_id), str(since), limit_value),
                ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent_diagnostic_event(row) for row in rows)

    def list_all_desktop_agent_diagnostic_events(
        self,
        *,
        since: str | None = None,
        limit: int | None = None,
    ) -> tuple[DesktopAgentDiagnosticEvent, ...]:
        limit_value = None if limit is None else max(1, int(limit))
        conn = self._connect()
        try:
            if since is None and limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    ORDER BY created_at DESC, event_id DESC
                    """
                ).fetchall()
            elif since is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT ?
                    """,
                    (limit_value,),
                ).fetchall()
            elif limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE created_at >= ?
                    ORDER BY created_at DESC, event_id DESC
                    """,
                    (str(since),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE created_at >= ?
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT ?
                    """,
                    (str(since), limit_value),
                ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_desktop_agent_diagnostic_event(row) for row in rows)

    def delete_desktop_agent_diagnostic_events_before(self, before: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    DELETE FROM desktop_agent_diagnostic_events
                    WHERE created_at < ?
                    """,
                    (str(before),),
                )
                conn.commit()
                return int(cursor.rowcount or 0)
            finally:
                conn.close()

    def export_snapshot(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            users = [
                {
                    "userId": str(row["user_id"]),
                    "email": str(row["email"]),
                    "passwordHash": str(row["password_hash"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    "SELECT user_id, email, password_hash, created_at FROM users ORDER BY user_id ASC"
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
            desktop_agents = [
                {
                    "agentId": str(row["agent_id"]),
                    "userId": str(row["user_id"]),
                    "deviceName": str(row["device_name"]),
                    "platform": str(row["platform"]),
                    "appVersion": str(row["app_version"]),
                    "status": str(row["status"]),
                    "lastSeenAt": str(row["last_seen_at"]),
                    "pairedAt": str(row["paired_at"]),
                    "agentTokenHash": str(row["agent_token_hash"]),
                    "refreshTokenHash": str(row["refresh_token_hash"]),
                }
                for row in conn.execute(
                    """
                    SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at,
                           agent_token_hash, refresh_token_hash
                    FROM desktop_agents
                    ORDER BY paired_at ASC, agent_id ASC
                    """
                ).fetchall()
            ]
            desktop_agent_pairing_codes = [
                {
                    "pairingCode": str(row["pairing_code"]),
                    "userId": str(row["user_id"]),
                    "expiresAt": str(row["expires_at"]),
                    "usedAt": None if row["used_at"] is None else str(row["used_at"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT pairing_code, user_id, expires_at, used_at, created_at
                    FROM desktop_agent_pairing_codes
                    ORDER BY created_at ASC, pairing_code ASC
                    """
                ).fetchall()
            ]
            desktop_media_probe_cache = [
                {
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "container": str(row["container"]),
                    "videoCodec": None if row["video_codec"] is None else str(row["video_codec"]),
                    "audioCodec": None if row["audio_codec"] is None else str(row["audio_codec"]),
                    "durationMs": None if row["duration_ms"] is None else int(row["duration_ms"]),
                    "bitrateBps": None if row["bitrate_bps"] is None else int(row["bitrate_bps"]),
                    "width": None if row["width"] is None else int(row["width"]),
                    "height": None if row["height"] is None else int(row["height"]),
                    "fps": None if row["fps"] is None else float(row["fps"]),
                    "audioChannels": None if row["audio_channels"] is None else int(row["audio_channels"]),
                    "audioSampleRate": None if row["audio_sample_rate"] is None else int(row["audio_sample_rate"]),
                    "videoStreamCount": None if row["video_stream_count"] is None else int(row["video_stream_count"]),
                    "audioStreamCount": None if row["audio_stream_count"] is None else int(row["audio_stream_count"]),
                    "subtitleStreamCount": None if row["subtitle_stream_count"] is None else int(row["subtitle_stream_count"]),
                    "sizeBytes": None if row["size_bytes"] is None else int(row["size_bytes"]),
                    "modifiedAt": None if row["modified_at"] is None else str(row["modified_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                           bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                           audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                    FROM desktop_media_probe_cache
                    ORDER BY project_id ASC, instance_id ASC, agent_id ASC
                    """
                ).fetchall()
            ]
            hls_cache_entries = [
                {
                    "cacheKey": str(row["cache_key"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "profile": str(row["profile"]),
                    "segmentName": str(row["segment_name"]),
                    "filePath": str(row["file_path"]),
                    "sizeBytes": int(row["size_bytes"]),
                    "createdAt": str(row["created_at"]),
                    "lastAccessedAt": str(row["last_accessed_at"]),
                    "expiresAt": str(row["expires_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                           created_at, last_accessed_at, expires_at
                    FROM hls_cache_entries
                    ORDER BY cache_key ASC, segment_name ASC
                    """
                ).fetchall()
            ]
            hls_cache_entries = [
                {
                    "cacheKey": str(row["cache_key"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "profile": str(row["profile"]),
                    "segmentName": str(row["segment_name"]),
                    "filePath": str(row["file_path"]),
                    "sizeBytes": int(row["size_bytes"]),
                    "createdAt": str(row["created_at"]),
                    "lastAccessedAt": str(row["last_accessed_at"]),
                    "expiresAt": str(row["expires_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                           created_at, last_accessed_at, expires_at
                    FROM hls_cache_entries
                    ORDER BY cache_key ASC, segment_name ASC
                    """
                ).fetchall()
            ]
            desktop_agent_hls_job_audits = [
                {
                    "jobId": str(row["job_id"]),
                    "cacheKey": str(row["cache_key"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "relativePath": str(row["relative_path"]),
                    "profile": str(row["profile"]),
                    "state": str(row["state"]),
                    "artifactCount": int(row["artifact_count"]),
                    "artifactBytes": int(row["artifact_bytes"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                    "expiresAt": str(row["expires_at"]),
                    "startedAt": None if row["started_at"] is None else str(row["started_at"]),
                    "finishedAt": None if row["finished_at"] is None else str(row["finished_at"]),
                    "lastArtifactAt": None if row["last_artifact_at"] is None else str(row["last_artifact_at"]),
                    "message": None if row["message"] is None else str(row["message"]),
                }
                for row in conn.execute(
                    """
                    SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                           artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                           last_artifact_at, message
                    FROM desktop_agent_hls_job_audits
                    ORDER BY updated_at DESC, created_at DESC, job_id DESC
                    """
                ).fetchall()
            ]
            desktop_agent_metric_samples = [
                {
                    "projectId": str(row["project_id"]),
                    "bucketStart": str(row["bucket_start"]),
                    "bucketSeconds": int(row["bucket_seconds"]),
                    "capturedAt": str(row["captured_at"]),
                    "sessionCount": int(row["session_count"]),
                    "activeStreamCount": int(row["active_stream_count"]),
                    "completedStreamCount": int(row["completed_stream_count"]),
                    "failedStreamCount": int(row["failed_stream_count"]),
                    "cancelledStreamCount": int(row["cancelled_stream_count"]),
                    "bytesFromAgentTotal": int(row["bytes_from_agent_total"]),
                    "bytesToViewerTotal": int(row["bytes_to_viewer_total"]),
                    "hlsJobCount": int(row["hls_job_count"]),
                    "activeHlsJobCount": int(row["active_hls_job_count"]),
                    "completedHlsJobCount": int(row["completed_hls_job_count"]),
                    "failedHlsJobCount": int(row["failed_hls_job_count"]),
                    "cancelledHlsJobCount": int(row["cancelled_hls_job_count"]),
                    "hlsArtifactBytesTotal": int(row["hls_artifact_bytes_total"]),
                    "hlsCacheEntryCount": int(row["hls_cache_entry_count"]),
                    "hlsCacheBytes": int(row["hls_cache_bytes"]),
                }
                for row in conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    ORDER BY bucket_start ASC, project_id ASC
                    """
                ).fetchall()
            ]
            desktop_agent_diagnostic_events = [
                {
                    "eventId": str(row["event_id"]),
                    "agentId": str(row["agent_id"]),
                    "userId": str(row["user_id"]),
                    "projectId": None if row["project_id"] is None else str(row["project_id"]),
                    "instanceId": None if row["instance_id"] is None else str(row["instance_id"]),
                    "relativePath": None if row["relative_path"] is None else str(row["relative_path"]),
                    "level": str(row["level"]),
                    "category": str(row["category"]),
                    "eventType": str(row["event_type"]),
                    "message": str(row["message"]),
                    "details": str(row["details"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    ORDER BY created_at DESC, event_id DESC
                    """
                ).fetchall()
            ]
            desktop_agent_diagnostic_events = [
                {
                    "eventId": str(row["event_id"]),
                    "agentId": str(row["agent_id"]),
                    "userId": str(row["user_id"]),
                    "projectId": None if row["project_id"] is None else str(row["project_id"]),
                    "instanceId": None if row["instance_id"] is None else str(row["instance_id"]),
                    "relativePath": None if row["relative_path"] is None else str(row["relative_path"]),
                    "level": str(row["level"]),
                    "category": str(row["category"]),
                    "eventType": str(row["event_type"]),
                    "message": str(row["message"]),
                    "details": str(row["details"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    ORDER BY created_at DESC, event_id DESC
                    """
                ).fetchall()
            ]
            media_stream_sessions = [
                {
                    "streamId": str(row["stream_id"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "userId": str(row["user_id"]),
                    "mode": str(row["mode"]),
                    "status": str(row["status"]),
                    "rangeStart": None if row["range_start"] is None else int(row["range_start"]),
                    "rangeEnd": None if row["range_end"] is None else int(row["range_end"]),
                    "bytesFromAgent": int(row["bytes_from_agent"]),
                    "bytesToViewer": int(row["bytes_to_viewer"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                    "expiresAt": str(row["expires_at"]),
                    "finishedAt": None if row["finished_at"] is None else str(row["finished_at"]),
                    "failureReason": None if row["failure_reason"] is None else str(row["failure_reason"]),
                }
                for row in conn.execute(
                    """
                    SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                           bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                    FROM media_stream_sessions
                    ORDER BY created_at ASC, stream_id ASC
                    """
                ).fetchall()
            ]
            return self._snapshot_payload(
                users=users,
                sessions=sessions,
                memberships=memberships,
                desktop_agents=desktop_agents,
                desktop_agent_pairing_codes=desktop_agent_pairing_codes,
                desktop_media_probe_cache=desktop_media_probe_cache,
                hls_cache_entries=hls_cache_entries,
                desktop_agent_hls_job_audits=desktop_agent_hls_job_audits,
                desktop_agent_metric_samples=desktop_agent_metric_samples,
                desktop_agent_diagnostic_events=desktop_agent_diagnostic_events,
                media_stream_sessions=media_stream_sessions,
            )
        finally:
            conn.close()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        desktop_agents = list(snapshot.get("desktopAgents", []))
        desktop_agent_pairing_codes = list(snapshot.get("desktopAgentPairingCodes", []))
        desktop_media_probe_cache = list(snapshot.get("desktopMediaProbeCache", []))
        hls_cache_entries = list(snapshot.get("hlsCacheEntries", []))
        desktop_agent_hls_job_audits = list(snapshot.get("desktopAgentHlsJobAudits", []))
        desktop_agent_metric_samples = list(snapshot.get("desktopAgentMetricSamples", []))
        desktop_agent_diagnostic_events = list(snapshot.get("desktopAgentDiagnosticEvents", []))
        media_stream_sessions = list(snapshot.get("mediaStreamSessions", []))
        with self._lock:
            conn = self._connect()
            try:
                if replace:
                    conn.execute("DELETE FROM desktop_agent_diagnostic_events")
                    conn.execute("DELETE FROM desktop_agent_metric_samples")
                    conn.execute("DELETE FROM desktop_agent_hls_job_audits")
                    conn.execute("DELETE FROM hls_cache_entries")
                    conn.execute("DELETE FROM desktop_media_probe_cache")
                    conn.execute("DELETE FROM media_stream_sessions")
                    conn.execute("DELETE FROM desktop_agent_pairing_codes")
                    conn.execute("DELETE FROM desktop_agents")
                    conn.execute("DELETE FROM project_memberships")
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM users")
                for item in users:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO users (user_id, email, password_hash, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("email", "")),
                            str(row.get("passwordHash", "")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in sessions:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO sessions (session_token, user_id, created_at, expires_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(row.get("sessionToken", "")),
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
                            str(row.get("role", "owner")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in desktop_agents:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agents (
                            agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at,
                            agent_token_hash, refresh_token_hash
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("agentId", "")),
                            str(row.get("userId", "")),
                            str(row.get("deviceName", "")),
                            str(row.get("platform", "")),
                            str(row.get("appVersion", "")),
                            str(row.get("status", "")),
                            str(row.get("lastSeenAt", "")),
                            str(row.get("pairedAt", "")),
                            str(row.get("agentTokenHash", "")),
                            str(row.get("refreshTokenHash", "")),
                        ),
                    )
                for item in desktop_agent_pairing_codes:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_pairing_codes (pairing_code, user_id, expires_at, used_at, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("pairingCode", "")),
                            str(row.get("userId", "")),
                            str(row.get("expiresAt", "")),
                            None if row.get("usedAt") is None else str(row.get("usedAt", "")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in desktop_media_probe_cache:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_media_probe_cache (
                            project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                            bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                            audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("container", "")),
                            None if row.get("videoCodec") is None else str(row.get("videoCodec", "")),
                            None if row.get("audioCodec") is None else str(row.get("audioCodec", "")),
                            None if row.get("durationMs") is None else int(row.get("durationMs", 0)),
                            None if row.get("bitrateBps") is None else int(row.get("bitrateBps", 0)),
                            None if row.get("width") is None else int(row.get("width", 0)),
                            None if row.get("height") is None else int(row.get("height", 0)),
                            None if row.get("fps") is None else float(row.get("fps", 0)),
                            None if row.get("audioChannels") is None else int(row.get("audioChannels", 0)),
                            None if row.get("audioSampleRate") is None else int(row.get("audioSampleRate", 0)),
                            None if row.get("videoStreamCount") is None else int(row.get("videoStreamCount", 0)),
                            None if row.get("audioStreamCount") is None else int(row.get("audioStreamCount", 0)),
                            None if row.get("subtitleStreamCount") is None else int(row.get("subtitleStreamCount", 0)),
                            None if row.get("sizeBytes") is None else int(row.get("sizeBytes", 0)),
                            None if row.get("modifiedAt") is None else str(row.get("modifiedAt", "")),
                            str(row.get("updatedAt", "")),
                        ),
                    )
                for item in hls_cache_entries:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO hls_cache_entries (
                            cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                            created_at, last_accessed_at, expires_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("cacheKey", "")),
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("profile", "")),
                            str(row.get("segmentName", "")),
                            str(row.get("filePath", "")),
                            int(row.get("sizeBytes", 0)),
                            str(row.get("createdAt", "")),
                            str(row.get("lastAccessedAt", "")),
                            str(row.get("expiresAt", "")),
                        ),
                    )
                for item in desktop_agent_hls_job_audits:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_hls_job_audits (
                            job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                            artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                            last_artifact_at, message
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("jobId", "")),
                            str(row.get("cacheKey", "")),
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("relativePath", "")),
                            str(row.get("profile", "")),
                            str(row.get("state", "")),
                            int(row.get("artifactCount", 0)),
                            int(row.get("artifactBytes", 0)),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", "")),
                            str(row.get("expiresAt", "")),
                            None if row.get("startedAt") is None else str(row.get("startedAt", "")),
                            None if row.get("finishedAt") is None else str(row.get("finishedAt", "")),
                            None if row.get("lastArtifactAt") is None else str(row.get("lastArtifactAt", "")),
                            None if row.get("message") is None else str(row.get("message", "")),
                        ),
                    )
                for item in desktop_agent_metric_samples:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_metric_samples (
                            project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                            completed_stream_count, failed_stream_count, cancelled_stream_count,
                            bytes_from_agent_total, bytes_to_viewer_total, hls_job_count, active_hls_job_count,
                            completed_hls_job_count, failed_hls_job_count, cancelled_hls_job_count,
                            hls_artifact_bytes_total, hls_cache_entry_count, hls_cache_bytes
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("bucketStart", "")),
                            int(row.get("bucketSeconds", 0)),
                            str(row.get("capturedAt", "")),
                            int(row.get("sessionCount", 0)),
                            int(row.get("activeStreamCount", 0)),
                            int(row.get("completedStreamCount", 0)),
                            int(row.get("failedStreamCount", 0)),
                            int(row.get("cancelledStreamCount", 0)),
                            int(row.get("bytesFromAgentTotal", 0)),
                            int(row.get("bytesToViewerTotal", 0)),
                            int(row.get("hlsJobCount", 0)),
                            int(row.get("activeHlsJobCount", 0)),
                            int(row.get("completedHlsJobCount", 0)),
                            int(row.get("failedHlsJobCount", 0)),
                            int(row.get("cancelledHlsJobCount", 0)),
                            int(row.get("hlsArtifactBytesTotal", 0)),
                            int(row.get("hlsCacheEntryCount", 0)),
                            int(row.get("hlsCacheBytes", 0)),
                        ),
                    )
                for item in desktop_agent_diagnostic_events:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_diagnostic_events (
                            event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                            event_type, message, details, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("eventId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("userId", "")),
                            None if row.get("projectId") is None else str(row.get("projectId", "")),
                            None if row.get("instanceId") is None else str(row.get("instanceId", "")),
                            None if row.get("relativePath") is None else str(row.get("relativePath", "")),
                            str(row.get("level", "")),
                            str(row.get("category", "")),
                            str(row.get("eventType", "")),
                            str(row.get("message", "")),
                            str(row.get("details", "{}")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in media_stream_sessions:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO media_stream_sessions (
                            stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                            bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("streamId", "")),
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("userId", "")),
                            str(row.get("mode", "")),
                            str(row.get("status", "")),
                            None if row.get("rangeStart") is None else int(row.get("rangeStart", 0)),
                            None if row.get("rangeEnd") is None else int(row.get("rangeEnd", 0)),
                            int(row.get("bytesFromAgent", 0)),
                            int(row.get("bytesToViewer", 0)),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", "")),
                            str(row.get("expiresAt", "")),
                            None if row.get("finishedAt") is None else str(row.get("finishedAt", "")),
                            None if row.get("failureReason") is None else str(row.get("failureReason", "")),
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

    def _init_db(self) -> None:
        with self._lock:
            validate_postgres_migration_plan()
            conn = self._pool.acquire()
            try:
                apply_postgres_migrations(conn, target="auth")
            finally:
                self._pool.release(conn)

    def create_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        user = AuthUser(user_id=f"user_{uuid.uuid4().hex}", email=normalized_email, created_at=_utc_now().isoformat())
        password_hash = self._hash_password(password)
        with self._lock:
            conn = self._pool.acquire()
            try:
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, created_at) VALUES (%s, %s, %s, %s)",
                    (user.user_id, user.email, password_hash, user.created_at),
                )
                conn.commit()
                return user
            except _require_psycopg().IntegrityError as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise PreconditionFailure("email already exists") from exc
            finally:
                self._pool.release(conn)

    def authenticate_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, email, password_hash, created_at FROM users WHERE email = %s",
                (normalized_email,),
            ).fetchone()
        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise PreconditionFailure("invalid email or password")
        return self._row_to_user(row)

    def create_session(self, user_id: str) -> str:
        now = _utc_now()
        token = secrets.token_urlsafe(32)
        expires_at = (now + timedelta(days=_session_ttl_days())).isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO sessions (session_token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                    (token, str(user_id), now.isoformat(), expires_at),
                )
                conn.commit()
                return token

    def get_user_by_session(self, session_token: str) -> AuthUser:
        token = str(session_token).strip()
        if not token:
            raise NotFound("session")
        now_text = _utc_now().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.user_id, u.email, u.created_at
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.session_token = %s AND s.expires_at > %s
                """,
                (token, now_text),
            ).fetchone()
        if row is None:
            raise NotFound("session")
        return self._row_to_user(row)

    def delete_session(self, session_token: str) -> None:
        token = str(session_token).strip()
        if not token:
            return
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE session_token = %s", (token,))
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

    def create_desktop_agent_pairing_code(self, user_id: str) -> DesktopAgentPairingCode:
        normalized_user_id = _normalize_device_text(user_id, field_name="user_id")
        created_at = _utc_now()
        expires_at = created_at + timedelta(minutes=_desktop_agent_pairing_ttl_minutes())
        pairing = DesktopAgentPairingCode(
            pairing_code=_pairing_code_text(),
            user_id=normalized_user_id,
            expires_at=expires_at.isoformat(),
            used_at=None,
            created_at=created_at.isoformat(),
        )
        pairing.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_pairing_codes (pairing_code, user_id, expires_at, used_at, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (pairing.pairing_code, pairing.user_id, pairing.expires_at, pairing.used_at, pairing.created_at),
                )
                conn.commit()
        return pairing

    def pair_desktop_agent(
        self,
        pairing_code: str,
        *,
        device_name: str,
        platform: str,
        app_version: str,
    ) -> tuple[DesktopAgent, str, str]:
        normalized_pairing_code = _normalize_device_text(pairing_code, field_name="pairing_code").upper()
        normalized_device_name = _normalize_device_text(device_name, field_name="device_name")
        normalized_platform = _normalize_device_text(platform, field_name="platform").lower()
        normalized_app_version = _normalize_device_text(app_version, field_name="app_version")
        now = _utc_now()
        agent_token, refresh_token = _issue_desktop_agent_tokens()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT pairing_code, user_id, expires_at, used_at, created_at
                    FROM desktop_agent_pairing_codes
                    WHERE pairing_code = %s
                    """,
                    (normalized_pairing_code,),
                ).fetchone()
                if row is None:
                    raise NotFound("desktop_agent_pairing_code")
                pairing = self._row_to_pairing_code(row)
                if pairing.used_at is not None:
                    raise PreconditionFailure("pairing code already used")
                if datetime.fromisoformat(pairing.expires_at) <= now:
                    raise PreconditionFailure("pairing code expired")

                agent = DesktopAgent(
                    agent_id="",
                    user_id=pairing.user_id,
                    device_name=normalized_device_name,
                    platform=normalized_platform,
                    app_version=normalized_app_version,
                    status=DesktopAgentStatus.OFFLINE,
                    last_seen_at=now.isoformat(),
                    paired_at=now.isoformat(),
                )
                existing_row = conn.execute(
                    """
                    SELECT agent_id
                    FROM desktop_agents
                    WHERE user_id = %s AND lower(device_name) = lower(%s) AND platform = %s
                    ORDER BY paired_at DESC, agent_id DESC
                    LIMIT 1
                    """,
                    (pairing.user_id, normalized_device_name, normalized_platform),
                ).fetchone()
                agent = DesktopAgent(
                    agent_id=(
                        str(existing_row["agent_id"])
                        if existing_row is not None
                        else f"agent_{uuid.uuid4().hex}"
                    ),
                    user_id=agent.user_id,
                    device_name=agent.device_name,
                    platform=agent.platform,
                    app_version=agent.app_version,
                    status=agent.status,
                    last_seen_at=agent.last_seen_at,
                    paired_at=agent.paired_at,
                )
                agent.validate_write_time()
                if existing_row is None:
                    conn.execute(
                        """
                        INSERT INTO desktop_agents (
                            agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at,
                            agent_token_hash, refresh_token_hash
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            agent.agent_id,
                            agent.user_id,
                            agent.device_name,
                            agent.platform,
                            agent.app_version,
                            agent.status.value,
                            agent.last_seen_at,
                            agent.paired_at,
                            _token_hash(agent_token),
                            _token_hash(refresh_token),
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE desktop_agents
                        SET device_name = %s, platform = %s, app_version = %s, status = %s, last_seen_at = %s, paired_at = %s,
                            agent_token_hash = %s, refresh_token_hash = %s
                        WHERE agent_id = %s
                        """,
                        (
                            agent.device_name,
                            agent.platform,
                            agent.app_version,
                            agent.status.value,
                            agent.last_seen_at,
                            agent.paired_at,
                            _token_hash(agent_token),
                            _token_hash(refresh_token),
                            agent.agent_id,
                        ),
                    )
                conn.execute(
                    "UPDATE desktop_agent_pairing_codes SET used_at = %s WHERE pairing_code = %s",
                    (now.isoformat(), normalized_pairing_code),
                )
                conn.commit()
                return agent, agent_token, refresh_token

    def list_desktop_agents_for_user(self, user_id: str) -> tuple[DesktopAgent, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE user_id = %s
                ORDER BY paired_at ASC, agent_id ASC
                """,
                (str(user_id),),
            ).fetchall()
        return tuple(self._row_to_desktop_agent(row) for row in rows)

    def user_has_desktop_agent(self, user_id: str, agent_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM desktop_agents WHERE agent_id = %s AND user_id = %s LIMIT 1",
                (str(agent_id), str(user_id)),
            ).fetchone()
        return row is not None

    def get_desktop_agent_by_token(self, agent_token: str) -> DesktopAgent:
        token_hash = _token_hash(_normalize_device_text(agent_token, field_name="agent_token"))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE agent_token_hash = %s
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            raise NotFound("desktop_agent")
        return self._row_to_desktop_agent(row)

    def get_desktop_agent_by_refresh_token(self, refresh_token: str) -> DesktopAgent:
        token_hash = _token_hash(_normalize_device_text(refresh_token, field_name="refresh_token"))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE refresh_token_hash = %s
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            raise NotFound("desktop_agent")
        return self._row_to_desktop_agent(row)

    def refresh_desktop_agent_tokens(self, refresh_token: str) -> tuple[DesktopAgent, str, str]:
        current = self.get_desktop_agent_by_refresh_token(refresh_token)
        next_agent_token, next_refresh_token = _issue_desktop_agent_tokens()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE desktop_agents
                    SET agent_token_hash = %s, refresh_token_hash = %s
                    WHERE agent_id = %s
                    """,
                    (_token_hash(next_agent_token), _token_hash(next_refresh_token), current.agent_id),
                )
                conn.commit()
        return self.get_desktop_agent(current.agent_id), next_agent_token, next_refresh_token

    def get_desktop_agent(self, agent_id: str) -> DesktopAgent:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at
                FROM desktop_agents
                WHERE agent_id = %s
                LIMIT 1
                """,
                (str(agent_id),),
            ).fetchone()
        if row is None:
            raise NotFound("desktop_agent")
        return self._row_to_desktop_agent(row)

    def update_desktop_agent_presence(
        self,
        agent_id: str,
        *,
        status: DesktopAgentStatus,
        last_seen_at: str | None = None,
        device_name: str | None = None,
        app_version: str | None = None,
    ) -> DesktopAgent:
        updated_at = last_seen_at or _utc_now().isoformat()
        with self._lock:
            current = self.get_desktop_agent(agent_id)
            next_device_name = current.device_name if device_name is None else _normalize_device_text(device_name, field_name="device_name")
            next_app_version = current.app_version if app_version is None else _normalize_device_text(app_version, field_name="app_version")
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE desktop_agents
                    SET status = %s, last_seen_at = %s, device_name = %s, app_version = %s
                    WHERE agent_id = %s
                    """,
                    (status.value, updated_at, next_device_name, next_app_version, str(agent_id)),
                )
                conn.commit()
        return self.get_desktop_agent(agent_id)

    def mark_stale_desktop_agents_offline(self, *, offline_before: str) -> int:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE desktop_agents
                    SET status = %s
                    WHERE status = %s AND last_seen_at < %s
                    """,
                    (DesktopAgentStatus.OFFLINE.value, DesktopAgentStatus.ONLINE.value, str(offline_before)),
                )
                conn.commit()
                return int(cursor.rowcount or 0)

    def create_media_stream_session(self, stream: MediaStreamSession) -> MediaStreamSession:
        stream.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO media_stream_sessions (
                        stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                        bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        stream.stream_id,
                        stream.project_id,
                        stream.instance_id,
                        stream.agent_id,
                        stream.user_id,
                        stream.mode,
                        stream.status,
                        None if stream.range_start is None else int(stream.range_start),
                        None if stream.range_end is None else int(stream.range_end),
                        int(stream.bytes_from_agent),
                        int(stream.bytes_to_viewer),
                        stream.created_at,
                        stream.updated_at,
                        stream.expires_at,
                        stream.finished_at,
                        stream.failure_reason,
                    ),
                )
                conn.commit()
        return self.get_media_stream_session(stream.stream_id)

    def get_media_stream_session(self, stream_id: str) -> MediaStreamSession:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                       bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                FROM media_stream_sessions
                WHERE stream_id = %s
                LIMIT 1
                """,
                (str(stream_id),),
            ).fetchone()
        if row is None:
            raise NotFound("media_stream_session")
        return self._row_to_media_stream_session(row)

    def list_media_stream_sessions_for_project(self, project_id: str) -> tuple[MediaStreamSession, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                       bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                FROM media_stream_sessions
                WHERE project_id = %s
                ORDER BY created_at ASC, stream_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        return tuple(self._row_to_media_stream_session(row) for row in rows)

    def list_all_media_stream_sessions(self) -> tuple[MediaStreamSession, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                       bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                FROM media_stream_sessions
                ORDER BY updated_at DESC, created_at DESC, stream_id DESC
                """
            ).fetchall()
        return tuple(self._row_to_media_stream_session(row) for row in rows)

    def mark_media_stream_session_streaming(self, stream_id: str) -> MediaStreamSession:
        current = self.get_media_stream_session(stream_id)
        if current.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return current
        updated_at = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET status = %s, updated_at = %s, failure_reason = NULL
                    WHERE stream_id = %s
                    """,
                    ("STREAMING", updated_at, str(stream_id)),
                )
                conn.commit()
        return self.get_media_stream_session(stream_id)

    def upsert_desktop_media_probe_cache(self, item: DesktopMediaProbeCache) -> DesktopMediaProbeCache:
        item.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO desktop_media_probe_cache (
                        project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                        bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                        audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(project_id, instance_id, agent_id) DO UPDATE SET
                        container = EXCLUDED.container,
                        video_codec = EXCLUDED.video_codec,
                        audio_codec = EXCLUDED.audio_codec,
                        duration_ms = EXCLUDED.duration_ms,
                        bitrate_bps = EXCLUDED.bitrate_bps,
                        width = EXCLUDED.width,
                        height = EXCLUDED.height,
                        fps = EXCLUDED.fps,
                        audio_channels = EXCLUDED.audio_channels,
                        audio_sample_rate = EXCLUDED.audio_sample_rate,
                        video_stream_count = EXCLUDED.video_stream_count,
                        audio_stream_count = EXCLUDED.audio_stream_count,
                        subtitle_stream_count = EXCLUDED.subtitle_stream_count,
                        size_bytes = EXCLUDED.size_bytes,
                        modified_at = EXCLUDED.modified_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        item.project_id,
                        item.instance_id,
                        item.agent_id,
                        item.container,
                        item.video_codec,
                        item.audio_codec,
                        None if item.duration_ms is None else int(item.duration_ms),
                        None if item.bitrate_bps is None else int(item.bitrate_bps),
                        None if item.width is None else int(item.width),
                        None if item.height is None else int(item.height),
                        None if item.fps is None else float(item.fps),
                        None if item.audio_channels is None else int(item.audio_channels),
                        None if item.audio_sample_rate is None else int(item.audio_sample_rate),
                        None if item.video_stream_count is None else int(item.video_stream_count),
                        None if item.audio_stream_count is None else int(item.audio_stream_count),
                        None if item.subtitle_stream_count is None else int(item.subtitle_stream_count),
                        None if item.size_bytes is None else int(item.size_bytes),
                        item.modified_at,
                        item.updated_at,
                    ),
                )
                conn.commit()
        return self.get_desktop_media_probe_cache(item.project_id, item.instance_id, item.agent_id)

    def get_desktop_media_probe_cache(
        self,
        project_id: str,
        instance_id: str,
        agent_id: str,
    ) -> DesktopMediaProbeCache | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                       bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                       audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                FROM desktop_media_probe_cache
                WHERE project_id = %s AND instance_id = %s AND agent_id = %s
                LIMIT 1
                """,
                (str(project_id), str(instance_id), str(agent_id)),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_desktop_media_probe_cache(row)

    def delete_desktop_media_probe_cache(self, project_id: str, instance_id: str, agent_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    DELETE FROM desktop_media_probe_cache
                    WHERE project_id = %s AND instance_id = %s AND agent_id = %s
                    """,
                    (str(project_id), str(instance_id), str(agent_id)),
                )
                conn.commit()

    def upsert_hls_cache_entry(self, item: HlsCacheEntry) -> HlsCacheEntry:
        item.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO hls_cache_entries (
                        cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                        created_at, last_accessed_at, expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(cache_key, segment_name) DO UPDATE SET
                        project_id = EXCLUDED.project_id,
                        instance_id = EXCLUDED.instance_id,
                        agent_id = EXCLUDED.agent_id,
                        profile = EXCLUDED.profile,
                        file_path = EXCLUDED.file_path,
                        size_bytes = EXCLUDED.size_bytes,
                        last_accessed_at = EXCLUDED.last_accessed_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (
                        item.cache_key,
                        item.project_id,
                        item.instance_id,
                        item.agent_id,
                        item.profile,
                        item.segment_name,
                        item.file_path,
                        int(item.size_bytes),
                        item.created_at,
                        item.last_accessed_at,
                        item.expires_at,
                    ),
                )
                conn.commit()
        entry = self.get_hls_cache_entry(item.cache_key, item.segment_name)
        if entry is None:
            raise NotFound("hls_cache_entry")
        return entry

    def get_hls_cache_entry(self, cache_key: str, segment_name: str) -> HlsCacheEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                       created_at, last_accessed_at, expires_at
                FROM hls_cache_entries
                WHERE cache_key = %s AND segment_name = %s
                LIMIT 1
                """,
                (str(cache_key), str(segment_name)),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_hls_cache_entry(row)

    def list_hls_cache_entries(self, cache_key: str) -> tuple[HlsCacheEntry, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                       created_at, last_accessed_at, expires_at
                FROM hls_cache_entries
                WHERE cache_key = %s
                ORDER BY segment_name ASC
                """,
                (str(cache_key),),
            ).fetchall()
        return tuple(self._row_to_hls_cache_entry(row) for row in rows)

    def list_all_hls_cache_entries(self) -> tuple[HlsCacheEntry, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                       created_at, last_accessed_at, expires_at
                FROM hls_cache_entries
                ORDER BY last_accessed_at ASC, created_at ASC, cache_key ASC, segment_name ASC
                """
            ).fetchall()
        return tuple(self._row_to_hls_cache_entry(row) for row in rows)

    def touch_hls_cache_entry_access(
        self,
        cache_key: str,
        segment_name: str,
        *,
        last_accessed_at: str | None = None,
    ) -> HlsCacheEntry:
        current = self.get_hls_cache_entry(cache_key, segment_name)
        if current is None:
            raise NotFound("hls_cache_entry")
        next_accessed_at = str(last_accessed_at or _utc_now().isoformat())
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE hls_cache_entries
                    SET last_accessed_at = %s
                    WHERE cache_key = %s AND segment_name = %s
                    """,
                    (next_accessed_at, str(cache_key), str(segment_name)),
                )
                conn.commit()
        updated = self.get_hls_cache_entry(cache_key, segment_name)
        if updated is None:
            raise NotFound("hls_cache_entry")
        return updated

    def delete_hls_cache_entry(self, cache_key: str, segment_name: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    DELETE FROM hls_cache_entries
                    WHERE cache_key = %s AND segment_name = %s
                    """,
                    (str(cache_key), str(segment_name)),
                )
                conn.commit()

    def upsert_desktop_agent_hls_job_audit(self, item: DesktopAgentHlsJobAudit) -> DesktopAgentHlsJobAudit:
        item.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_hls_job_audits (
                        job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                        artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                        last_artifact_at, message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(job_id) DO UPDATE SET
                        cache_key = EXCLUDED.cache_key,
                        project_id = EXCLUDED.project_id,
                        instance_id = EXCLUDED.instance_id,
                        agent_id = EXCLUDED.agent_id,
                        relative_path = EXCLUDED.relative_path,
                        profile = EXCLUDED.profile,
                        state = EXCLUDED.state,
                        artifact_count = EXCLUDED.artifact_count,
                        artifact_bytes = EXCLUDED.artifact_bytes,
                        updated_at = EXCLUDED.updated_at,
                        expires_at = EXCLUDED.expires_at,
                        started_at = EXCLUDED.started_at,
                        finished_at = EXCLUDED.finished_at,
                        last_artifact_at = EXCLUDED.last_artifact_at,
                        message = EXCLUDED.message
                    """,
                    (
                        item.job_id,
                        item.cache_key,
                        item.project_id,
                        item.instance_id,
                        item.agent_id,
                        item.relative_path,
                        item.profile,
                        item.state,
                        int(item.artifact_count),
                        int(item.artifact_bytes),
                        item.created_at,
                        item.updated_at,
                        item.expires_at,
                        item.started_at,
                        item.finished_at,
                        item.last_artifact_at,
                        item.message,
                    ),
                )
                conn.commit()
        audit = self.get_desktop_agent_hls_job_audit(item.job_id)
        if audit is None:
            raise NotFound("desktop_agent_hls_job_audit")
        return audit

    def get_desktop_agent_hls_job_audit(self, job_id: str) -> DesktopAgentHlsJobAudit | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                WHERE job_id = %s
                LIMIT 1
                """,
                (str(job_id),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_desktop_agent_hls_job_audit(row)

    def get_latest_desktop_agent_hls_job_audit_by_cache_key(self, cache_key: str) -> DesktopAgentHlsJobAudit | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                WHERE cache_key = %s
                ORDER BY updated_at DESC, created_at DESC, job_id DESC
                LIMIT 1
                """,
                (str(cache_key),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_desktop_agent_hls_job_audit(row)

    def list_desktop_agent_hls_job_audits_for_project(self, project_id: str) -> tuple[DesktopAgentHlsJobAudit, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                WHERE project_id = %s
                ORDER BY updated_at DESC, created_at DESC, job_id DESC
                """,
                (str(project_id),),
            ).fetchall()
        return tuple(self._row_to_desktop_agent_hls_job_audit(row) for row in rows)

    def list_all_desktop_agent_hls_job_audits(self) -> tuple[DesktopAgentHlsJobAudit, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                       artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                       last_artifact_at, message
                FROM desktop_agent_hls_job_audits
                ORDER BY updated_at DESC, created_at DESC, job_id DESC
                """
            ).fetchall()
        return tuple(self._row_to_desktop_agent_hls_job_audit(row) for row in rows)

    def upsert_desktop_agent_metric_sample(self, item: DesktopAgentMetricSample) -> DesktopAgentMetricSample:
        item.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_metric_samples (
                        project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                        completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                        bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                        failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                        hls_cache_entry_count, hls_cache_bytes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(project_id, bucket_start) DO UPDATE SET
                        bucket_seconds = EXCLUDED.bucket_seconds,
                        captured_at = EXCLUDED.captured_at,
                        session_count = EXCLUDED.session_count,
                        active_stream_count = EXCLUDED.active_stream_count,
                        completed_stream_count = EXCLUDED.completed_stream_count,
                        failed_stream_count = EXCLUDED.failed_stream_count,
                        cancelled_stream_count = EXCLUDED.cancelled_stream_count,
                        bytes_from_agent_total = EXCLUDED.bytes_from_agent_total,
                        bytes_to_viewer_total = EXCLUDED.bytes_to_viewer_total,
                        hls_job_count = EXCLUDED.hls_job_count,
                        active_hls_job_count = EXCLUDED.active_hls_job_count,
                        completed_hls_job_count = EXCLUDED.completed_hls_job_count,
                        failed_hls_job_count = EXCLUDED.failed_hls_job_count,
                        cancelled_hls_job_count = EXCLUDED.cancelled_hls_job_count,
                        hls_artifact_bytes_total = EXCLUDED.hls_artifact_bytes_total,
                        hls_cache_entry_count = EXCLUDED.hls_cache_entry_count,
                        hls_cache_bytes = EXCLUDED.hls_cache_bytes
                    """,
                    (
                        item.project_id,
                        item.bucket_start,
                        int(item.bucket_seconds),
                        item.captured_at,
                        int(item.session_count),
                        int(item.active_stream_count),
                        int(item.completed_stream_count),
                        int(item.failed_stream_count),
                        int(item.cancelled_stream_count),
                        int(item.bytes_from_agent_total),
                        int(item.bytes_to_viewer_total),
                        int(item.hls_job_count),
                        int(item.active_hls_job_count),
                        int(item.completed_hls_job_count),
                        int(item.failed_hls_job_count),
                        int(item.cancelled_hls_job_count),
                        int(item.hls_artifact_bytes_total),
                        int(item.hls_cache_entry_count),
                        int(item.hls_cache_bytes),
                    ),
                )
                conn.commit()
        sample = self.get_desktop_agent_metric_sample(item.project_id, item.bucket_start)
        if sample is None:
            raise NotFound("desktop_agent_metric_sample")
        return sample

    def get_desktop_agent_metric_sample(self, project_id: str, bucket_start: str) -> DesktopAgentMetricSample | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                       completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                       bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                       failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                       hls_cache_entry_count, hls_cache_bytes
                FROM desktop_agent_metric_samples
                WHERE project_id = %s AND bucket_start = %s
                LIMIT 1
                """,
                (str(project_id), str(bucket_start)),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_desktop_agent_metric_sample(row)

    def list_desktop_agent_metric_samples_for_project(
        self,
        project_id: str,
        *,
        since: str | None = None,
    ) -> tuple[DesktopAgentMetricSample, ...]:
        with self._connect() as conn:
            if since is None:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    WHERE project_id = %s
                    ORDER BY bucket_start ASC, project_id ASC
                    """,
                    (str(project_id),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    WHERE project_id = %s AND bucket_start >= %s
                    ORDER BY bucket_start ASC, project_id ASC
                    """,
                    (str(project_id), str(since)),
                ).fetchall()
        return tuple(self._row_to_desktop_agent_metric_sample(row) for row in rows)

    def list_all_desktop_agent_metric_samples(
        self,
        *,
        since: str | None = None,
    ) -> tuple[DesktopAgentMetricSample, ...]:
        with self._connect() as conn:
            if since is None:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    ORDER BY bucket_start ASC, project_id ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                           completed_stream_count, failed_stream_count, cancelled_stream_count, bytes_from_agent_total,
                           bytes_to_viewer_total, hls_job_count, active_hls_job_count, completed_hls_job_count,
                           failed_hls_job_count, cancelled_hls_job_count, hls_artifact_bytes_total,
                           hls_cache_entry_count, hls_cache_bytes
                    FROM desktop_agent_metric_samples
                    WHERE bucket_start >= %s
                    ORDER BY bucket_start ASC, project_id ASC
                    """,
                    (str(since),),
                ).fetchall()
        return tuple(self._row_to_desktop_agent_metric_sample(row) for row in rows)

    def delete_desktop_agent_metric_samples_before(self, before: str) -> int:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM desktop_agent_metric_samples
                    WHERE bucket_start < %s
                    """,
                    (str(before),),
                )
                conn.commit()
                return int(cursor.rowcount or 0)

    def create_desktop_agent_diagnostic_event(self, item: DesktopAgentDiagnosticEvent) -> DesktopAgentDiagnosticEvent:
        item.validate_write_time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO desktop_agent_diagnostic_events (
                        event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                        event_type, message, details, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item.event_id,
                        item.agent_id,
                        item.user_id,
                        item.project_id,
                        item.instance_id,
                        item.relative_path,
                        item.level,
                        item.category,
                        item.event_type,
                        item.message,
                        item.details,
                        item.created_at,
                    ),
                )
                conn.commit()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                       event_type, message, details, created_at
                FROM desktop_agent_diagnostic_events
                WHERE event_id = %s
                LIMIT 1
                """,
                (item.event_id,),
            ).fetchone()
        if row is None:
            raise NotFound("desktop_agent_diagnostic_event")
        return self._row_to_desktop_agent_diagnostic_event(row)

    def list_desktop_agent_diagnostic_events_for_user(
        self,
        user_id: str,
        *,
        since: str | None = None,
        limit: int | None = None,
    ) -> tuple[DesktopAgentDiagnosticEvent, ...]:
        limit_value = None if limit is None else max(1, int(limit))
        with self._connect() as conn:
            if since is None and limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = %s
                    ORDER BY created_at DESC, event_id DESC
                    """,
                    (str(user_id),),
                ).fetchall()
            elif since is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = %s
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT %s
                    """,
                    (str(user_id), limit_value),
                ).fetchall()
            elif limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = %s AND created_at >= %s
                    ORDER BY created_at DESC, event_id DESC
                    """,
                    (str(user_id), str(since)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE user_id = %s AND created_at >= %s
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT %s
                    """,
                    (str(user_id), str(since), limit_value),
                ).fetchall()
        return tuple(self._row_to_desktop_agent_diagnostic_event(row) for row in rows)

    def list_all_desktop_agent_diagnostic_events(
        self,
        *,
        since: str | None = None,
        limit: int | None = None,
    ) -> tuple[DesktopAgentDiagnosticEvent, ...]:
        limit_value = None if limit is None else max(1, int(limit))
        with self._connect() as conn:
            if since is None and limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    ORDER BY created_at DESC, event_id DESC
                    """
                ).fetchall()
            elif since is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT %s
                    """,
                    (limit_value,),
                ).fetchall()
            elif limit_value is None:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE created_at >= %s
                    ORDER BY created_at DESC, event_id DESC
                    """,
                    (str(since),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                           event_type, message, details, created_at
                    FROM desktop_agent_diagnostic_events
                    WHERE created_at >= %s
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT %s
                    """,
                    (str(since), limit_value),
                ).fetchall()
        return tuple(self._row_to_desktop_agent_diagnostic_event(row) for row in rows)

    def delete_desktop_agent_diagnostic_events_before(self, before: str) -> int:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM desktop_agent_diagnostic_events
                    WHERE created_at < %s
                    """,
                    (str(before),),
                )
                conn.commit()
                return int(cursor.rowcount or 0)

    def add_media_stream_session_agent_bytes(self, stream_id: str, delta: int) -> MediaStreamSession:
        delta_int = int(delta)
        if delta_int < 0:
            raise PreconditionFailure("media stream session delta must be >= 0")
        current = self.get_media_stream_session(stream_id)
        if current.status in {"FAILED", "CANCELLED"}:
            return current
        updated_at = _utc_now().isoformat()
        next_status = "STREAMING" if current.status == "OPENING" else current.status
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET bytes_from_agent = bytes_from_agent + %s, status = %s, updated_at = %s
                    WHERE stream_id = %s
                    """,
                    (delta_int, next_status, updated_at, str(stream_id)),
                )
                conn.commit()
        return self.get_media_stream_session(stream_id)

    def add_media_stream_session_viewer_bytes(self, stream_id: str, delta: int) -> MediaStreamSession:
        delta_int = int(delta)
        if delta_int < 0:
            raise PreconditionFailure("media stream session delta must be >= 0")
        current = self.get_media_stream_session(stream_id)
        if current.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return current
        updated_at = _utc_now().isoformat()
        next_status = "STREAMING" if current.status == "OPENING" else current.status
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET bytes_to_viewer = bytes_to_viewer + %s, status = %s, updated_at = %s
                    WHERE stream_id = %s
                    """,
                    (delta_int, next_status, updated_at, str(stream_id)),
                )
                conn.commit()
        return self.get_media_stream_session(stream_id)

    def finalize_media_stream_session(
        self,
        stream_id: str,
        *,
        status: str,
        failure_reason: str | None = None,
    ) -> MediaStreamSession:
        next_status = _normalize_stream_status(status)
        if next_status not in {"COMPLETED", "FAILED", "CANCELLED"}:
            raise PreconditionFailure("media stream session final status must be terminal")
        current = self.get_media_stream_session(stream_id)
        if current.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return current
        finished_at = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE media_stream_sessions
                    SET status = %s, updated_at = %s, finished_at = %s, failure_reason = %s
                    WHERE stream_id = %s
                    """,
                    (next_status, finished_at, finished_at, None if failure_reason is None else str(failure_reason), str(stream_id)),
                )
                conn.commit()
        return self.get_media_stream_session(stream_id)

    def export_snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            users = [
                {
                    "userId": str(row["user_id"]),
                    "email": str(row["email"]),
                    "passwordHash": str(row["password_hash"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    "SELECT user_id, email, password_hash, created_at FROM users ORDER BY user_id ASC"
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
            desktop_agents = [
                {
                    "agentId": str(row["agent_id"]),
                    "userId": str(row["user_id"]),
                    "deviceName": str(row["device_name"]),
                    "platform": str(row["platform"]),
                    "appVersion": str(row["app_version"]),
                    "status": str(row["status"]),
                    "lastSeenAt": str(row["last_seen_at"]),
                    "pairedAt": str(row["paired_at"]),
                    "agentTokenHash": str(row["agent_token_hash"]),
                    "refreshTokenHash": str(row["refresh_token_hash"]),
                }
                for row in conn.execute(
                    """
                    SELECT agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at,
                           agent_token_hash, refresh_token_hash
                    FROM desktop_agents
                    ORDER BY paired_at ASC, agent_id ASC
                    """
                ).fetchall()
            ]
            desktop_agent_pairing_codes = [
                {
                    "pairingCode": str(row["pairing_code"]),
                    "userId": str(row["user_id"]),
                    "expiresAt": str(row["expires_at"]),
                    "usedAt": None if row["used_at"] is None else str(row["used_at"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT pairing_code, user_id, expires_at, used_at, created_at
                    FROM desktop_agent_pairing_codes
                    ORDER BY created_at ASC, pairing_code ASC
                    """
                ).fetchall()
            ]
            desktop_media_probe_cache = [
                {
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "container": str(row["container"]),
                    "videoCodec": None if row["video_codec"] is None else str(row["video_codec"]),
                    "audioCodec": None if row["audio_codec"] is None else str(row["audio_codec"]),
                    "durationMs": None if row["duration_ms"] is None else int(row["duration_ms"]),
                    "bitrateBps": None if row["bitrate_bps"] is None else int(row["bitrate_bps"]),
                    "width": None if row["width"] is None else int(row["width"]),
                    "height": None if row["height"] is None else int(row["height"]),
                    "fps": None if row["fps"] is None else float(row["fps"]),
                    "audioChannels": None if row["audio_channels"] is None else int(row["audio_channels"]),
                    "audioSampleRate": None if row["audio_sample_rate"] is None else int(row["audio_sample_rate"]),
                    "videoStreamCount": None if row["video_stream_count"] is None else int(row["video_stream_count"]),
                    "audioStreamCount": None if row["audio_stream_count"] is None else int(row["audio_stream_count"]),
                    "subtitleStreamCount": None if row["subtitle_stream_count"] is None else int(row["subtitle_stream_count"]),
                    "sizeBytes": None if row["size_bytes"] is None else int(row["size_bytes"]),
                    "modifiedAt": None if row["modified_at"] is None else str(row["modified_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                           bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                           audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                    FROM desktop_media_probe_cache
                    ORDER BY project_id ASC, instance_id ASC, agent_id ASC
                    """
                ).fetchall()
            ]
            hls_cache_entries = [
                {
                    "cacheKey": str(row["cache_key"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "profile": str(row["profile"]),
                    "segmentName": str(row["segment_name"]),
                    "filePath": str(row["file_path"]),
                    "sizeBytes": int(row["size_bytes"]),
                    "createdAt": str(row["created_at"]),
                    "lastAccessedAt": str(row["last_accessed_at"]),
                    "expiresAt": str(row["expires_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                           created_at, last_accessed_at, expires_at
                    FROM hls_cache_entries
                    ORDER BY cache_key ASC, segment_name ASC
                    """
                ).fetchall()
            ]
            desktop_agent_hls_job_audits = [
                {
                    "jobId": str(row["job_id"]),
                    "cacheKey": str(row["cache_key"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "relativePath": str(row["relative_path"]),
                    "profile": str(row["profile"]),
                    "state": str(row["state"]),
                    "artifactCount": int(row["artifact_count"]),
                    "artifactBytes": int(row["artifact_bytes"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                    "expiresAt": str(row["expires_at"]),
                    "startedAt": None if row["started_at"] is None else str(row["started_at"]),
                    "finishedAt": None if row["finished_at"] is None else str(row["finished_at"]),
                    "lastArtifactAt": None if row["last_artifact_at"] is None else str(row["last_artifact_at"]),
                    "message": None if row["message"] is None else str(row["message"]),
                }
                for row in conn.execute(
                    """
                    SELECT job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                           artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                           last_artifact_at, message
                    FROM desktop_agent_hls_job_audits
                    ORDER BY updated_at DESC, created_at DESC, job_id DESC
                    """
                ).fetchall()
            ]
            media_stream_sessions = [
                {
                    "streamId": str(row["stream_id"]),
                    "projectId": str(row["project_id"]),
                    "instanceId": str(row["instance_id"]),
                    "agentId": str(row["agent_id"]),
                    "userId": str(row["user_id"]),
                    "mode": str(row["mode"]),
                    "status": str(row["status"]),
                    "rangeStart": None if row["range_start"] is None else int(row["range_start"]),
                    "rangeEnd": None if row["range_end"] is None else int(row["range_end"]),
                    "bytesFromAgent": int(row["bytes_from_agent"]),
                    "bytesToViewer": int(row["bytes_to_viewer"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                    "expiresAt": str(row["expires_at"]),
                    "finishedAt": None if row["finished_at"] is None else str(row["finished_at"]),
                    "failureReason": None if row["failure_reason"] is None else str(row["failure_reason"]),
                }
                for row in conn.execute(
                    """
                    SELECT stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                           bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                    FROM media_stream_sessions
                    ORDER BY created_at ASC, stream_id ASC
                    """
                ).fetchall()
            ]
        return self._snapshot_payload(
            users=users,
            sessions=sessions,
            memberships=memberships,
            desktop_agents=desktop_agents,
            desktop_agent_pairing_codes=desktop_agent_pairing_codes,
            desktop_media_probe_cache=desktop_media_probe_cache,
            hls_cache_entries=hls_cache_entries,
            desktop_agent_hls_job_audits=desktop_agent_hls_job_audits,
            desktop_agent_metric_samples=desktop_agent_metric_samples,
            desktop_agent_diagnostic_events=desktop_agent_diagnostic_events,
            media_stream_sessions=media_stream_sessions,
        )

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        desktop_agents = list(snapshot.get("desktopAgents", []))
        desktop_agent_pairing_codes = list(snapshot.get("desktopAgentPairingCodes", []))
        desktop_media_probe_cache = list(snapshot.get("desktopMediaProbeCache", []))
        hls_cache_entries = list(snapshot.get("hlsCacheEntries", []))
        desktop_agent_hls_job_audits = list(snapshot.get("desktopAgentHlsJobAudits", []))
        desktop_agent_metric_samples = list(snapshot.get("desktopAgentMetricSamples", []))
        desktop_agent_diagnostic_events = list(snapshot.get("desktopAgentDiagnosticEvents", []))
        media_stream_sessions = list(snapshot.get("mediaStreamSessions", []))
        with self._lock:
            with self._connect() as conn:
                if replace:
                    conn.execute("DELETE FROM desktop_agent_diagnostic_events")
                    conn.execute("DELETE FROM desktop_agent_metric_samples")
                    conn.execute("DELETE FROM desktop_agent_hls_job_audits")
                    conn.execute("DELETE FROM hls_cache_entries")
                    conn.execute("DELETE FROM desktop_media_probe_cache")
                    conn.execute("DELETE FROM media_stream_sessions")
                    conn.execute("DELETE FROM desktop_agent_pairing_codes")
                    conn.execute("DELETE FROM desktop_agents")
                    conn.execute("DELETE FROM project_memberships")
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM users")
                for item in users:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO users (user_id, email, password_hash, created_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            str(row.get("userId", "")),
                            str(row.get("email", "")),
                            str(row.get("passwordHash", "")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in sessions:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO sessions (session_token, user_id, created_at, expires_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            str(row.get("sessionToken", "")),
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
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("userId", "")),
                            str(row.get("role", "owner")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in desktop_agents:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agents (
                            agent_id, user_id, device_name, platform, app_version, status, last_seen_at, paired_at,
                            agent_token_hash, refresh_token_hash
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("agentId", "")),
                            str(row.get("userId", "")),
                            str(row.get("deviceName", "")),
                            str(row.get("platform", "")),
                            str(row.get("appVersion", "")),
                            str(row.get("status", "")),
                            str(row.get("lastSeenAt", "")),
                            str(row.get("pairedAt", "")),
                            str(row.get("agentTokenHash", "")),
                            str(row.get("refreshTokenHash", "")),
                        ),
                    )
                for item in desktop_agent_pairing_codes:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_pairing_codes (pairing_code, user_id, expires_at, used_at, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("pairingCode", "")),
                            str(row.get("userId", "")),
                            str(row.get("expiresAt", "")),
                            None if row.get("usedAt") is None else str(row.get("usedAt", "")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in desktop_media_probe_cache:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_media_probe_cache (
                            project_id, instance_id, agent_id, container, video_codec, audio_codec, duration_ms,
                            bitrate_bps, width, height, fps, audio_channels, audio_sample_rate, video_stream_count,
                            audio_stream_count, subtitle_stream_count, size_bytes, modified_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("container", "")),
                            None if row.get("videoCodec") is None else str(row.get("videoCodec", "")),
                            None if row.get("audioCodec") is None else str(row.get("audioCodec", "")),
                            None if row.get("durationMs") is None else int(row.get("durationMs", 0)),
                            None if row.get("bitrateBps") is None else int(row.get("bitrateBps", 0)),
                            None if row.get("width") is None else int(row.get("width", 0)),
                            None if row.get("height") is None else int(row.get("height", 0)),
                            None if row.get("fps") is None else float(row.get("fps", 0)),
                            None if row.get("audioChannels") is None else int(row.get("audioChannels", 0)),
                            None if row.get("audioSampleRate") is None else int(row.get("audioSampleRate", 0)),
                            None if row.get("videoStreamCount") is None else int(row.get("videoStreamCount", 0)),
                            None if row.get("audioStreamCount") is None else int(row.get("audioStreamCount", 0)),
                            None if row.get("subtitleStreamCount") is None else int(row.get("subtitleStreamCount", 0)),
                            None if row.get("sizeBytes") is None else int(row.get("sizeBytes", 0)),
                            None if row.get("modifiedAt") is None else str(row.get("modifiedAt", "")),
                            str(row.get("updatedAt", "")),
                        ),
                    )
                for item in hls_cache_entries:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO hls_cache_entries (
                            cache_key, project_id, instance_id, agent_id, profile, segment_name, file_path, size_bytes,
                            created_at, last_accessed_at, expires_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("cacheKey", "")),
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("profile", "")),
                            str(row.get("segmentName", "")),
                            str(row.get("filePath", "")),
                            int(row.get("sizeBytes", 0)),
                            str(row.get("createdAt", "")),
                            str(row.get("lastAccessedAt", "")),
                            str(row.get("expiresAt", "")),
                        ),
                    )
                for item in desktop_agent_hls_job_audits:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_hls_job_audits (
                            job_id, cache_key, project_id, instance_id, agent_id, relative_path, profile, state,
                            artifact_count, artifact_bytes, created_at, updated_at, expires_at, started_at, finished_at,
                            last_artifact_at, message
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("jobId", "")),
                            str(row.get("cacheKey", "")),
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("relativePath", "")),
                            str(row.get("profile", "")),
                            str(row.get("state", "")),
                            int(row.get("artifactCount", 0)),
                            int(row.get("artifactBytes", 0)),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", "")),
                            str(row.get("expiresAt", "")),
                            None if row.get("startedAt") is None else str(row.get("startedAt", "")),
                            None if row.get("finishedAt") is None else str(row.get("finishedAt", "")),
                            None if row.get("lastArtifactAt") is None else str(row.get("lastArtifactAt", "")),
                            None if row.get("message") is None else str(row.get("message", "")),
                        ),
                    )
                for item in desktop_agent_metric_samples:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_metric_samples (
                            project_id, bucket_start, bucket_seconds, captured_at, session_count, active_stream_count,
                            completed_stream_count, failed_stream_count, cancelled_stream_count,
                            bytes_from_agent_total, bytes_to_viewer_total, hls_job_count, active_hls_job_count,
                            completed_hls_job_count, failed_hls_job_count, cancelled_hls_job_count,
                            hls_artifact_bytes_total, hls_cache_entry_count, hls_cache_bytes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("projectId", "")),
                            str(row.get("bucketStart", "")),
                            int(row.get("bucketSeconds", 0)),
                            str(row.get("capturedAt", "")),
                            int(row.get("sessionCount", 0)),
                            int(row.get("activeStreamCount", 0)),
                            int(row.get("completedStreamCount", 0)),
                            int(row.get("failedStreamCount", 0)),
                            int(row.get("cancelledStreamCount", 0)),
                            int(row.get("bytesFromAgentTotal", 0)),
                            int(row.get("bytesToViewerTotal", 0)),
                            int(row.get("hlsJobCount", 0)),
                            int(row.get("activeHlsJobCount", 0)),
                            int(row.get("completedHlsJobCount", 0)),
                            int(row.get("failedHlsJobCount", 0)),
                            int(row.get("cancelledHlsJobCount", 0)),
                            int(row.get("hlsArtifactBytesTotal", 0)),
                            int(row.get("hlsCacheEntryCount", 0)),
                            int(row.get("hlsCacheBytes", 0)),
                        ),
                    )
                for item in desktop_agent_diagnostic_events:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO desktop_agent_diagnostic_events (
                            event_id, agent_id, user_id, project_id, instance_id, relative_path, level, category,
                            event_type, message, details, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("eventId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("userId", "")),
                            None if row.get("projectId") is None else str(row.get("projectId", "")),
                            None if row.get("instanceId") is None else str(row.get("instanceId", "")),
                            None if row.get("relativePath") is None else str(row.get("relativePath", "")),
                            str(row.get("level", "")),
                            str(row.get("category", "")),
                            str(row.get("eventType", "")),
                            str(row.get("message", "")),
                            str(row.get("details", "{}")),
                            str(row.get("createdAt", "")),
                        ),
                    )
                for item in media_stream_sessions:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO media_stream_sessions (
                            stream_id, project_id, instance_id, agent_id, user_id, mode, status, range_start, range_end,
                            bytes_from_agent, bytes_to_viewer, created_at, updated_at, expires_at, finished_at, failure_reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("streamId", "")),
                            str(row.get("projectId", "")),
                            str(row.get("instanceId", "")),
                            str(row.get("agentId", "")),
                            str(row.get("userId", "")),
                            str(row.get("mode", "")),
                            str(row.get("status", "")),
                            None if row.get("rangeStart") is None else int(row.get("rangeStart", 0)),
                            None if row.get("rangeEnd") is None else int(row.get("rangeEnd", 0)),
                            int(row.get("bytesFromAgent", 0)),
                            int(row.get("bytesToViewer", 0)),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", "")),
                            str(row.get("expiresAt", "")),
                            None if row.get("finishedAt") is None else str(row.get("finishedAt", "")),
                            None if row.get("failureReason") is None else str(row.get("failureReason", "")),
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
                health["migrations"] = postgres_migration_status(conn, target="auth")
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
                raise RuntimeError("PostgreSQL backend selected without an auth DSN")
            self._impl = PostgresAuthStore(cfg.auth_postgres_dsn)
            return
        self._impl = SQLiteAuthStore(cfg.auth_db_path or resolve_auth_db_path())

    def create_user(self, email: str, password: str) -> AuthUser:
        return self._impl.create_user(email, password)

    def authenticate_user(self, email: str, password: str) -> AuthUser:
        return self._impl.authenticate_user(email, password)

    def create_session(self, user_id: str) -> str:
        return self._impl.create_session(user_id)

    def get_user_by_session(self, session_token: str) -> AuthUser:
        return self._impl.get_user_by_session(session_token)

    def delete_session(self, session_token: str) -> None:
        self._impl.delete_session(session_token)

    def list_project_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        return self._impl.list_project_ids_for_user(user_id)

    def add_project_owner(self, project_id: str, user_id: str) -> None:
        self._impl.add_project_owner(project_id, user_id)

    def remove_project_memberships(self, project_id: str) -> None:
        self._impl.remove_project_memberships(project_id)

    def user_has_project_access(self, user_id: str, project_id: str) -> bool:
        return self._impl.user_has_project_access(user_id, project_id)

    def create_desktop_agent_pairing_code(self, user_id: str) -> DesktopAgentPairingCode:
        return self._impl.create_desktop_agent_pairing_code(user_id)

    def pair_desktop_agent(
        self,
        pairing_code: str,
        *,
        device_name: str,
        platform: str,
        app_version: str,
    ) -> tuple[DesktopAgent, str, str]:
        return self._impl.pair_desktop_agent(
            pairing_code,
            device_name=device_name,
            platform=platform,
            app_version=app_version,
        )

    def list_desktop_agents_for_user(self, user_id: str) -> tuple[DesktopAgent, ...]:
        return self._impl.list_desktop_agents_for_user(user_id)

    def user_has_desktop_agent(self, user_id: str, agent_id: str) -> bool:
        return self._impl.user_has_desktop_agent(user_id, agent_id)

    def get_desktop_agent_by_token(self, agent_token: str) -> DesktopAgent:
        return self._impl.get_desktop_agent_by_token(agent_token)

    def get_desktop_agent_by_refresh_token(self, refresh_token: str) -> DesktopAgent:
        return self._impl.get_desktop_agent_by_refresh_token(refresh_token)

    def refresh_desktop_agent_tokens(self, refresh_token: str) -> tuple[DesktopAgent, str, str]:
        return self._impl.refresh_desktop_agent_tokens(refresh_token)

    def get_desktop_agent(self, agent_id: str) -> DesktopAgent:
        return self._impl.get_desktop_agent(agent_id)

    def update_desktop_agent_presence(
        self,
        agent_id: str,
        *,
        status: DesktopAgentStatus,
        last_seen_at: str | None = None,
        device_name: str | None = None,
        app_version: str | None = None,
    ) -> DesktopAgent:
        return self._impl.update_desktop_agent_presence(
            agent_id,
            status=status,
            last_seen_at=last_seen_at,
            device_name=device_name,
            app_version=app_version,
        )

    def mark_stale_desktop_agents_offline(self, *, offline_before: str) -> int:
        return self._impl.mark_stale_desktop_agents_offline(offline_before=offline_before)

    def create_media_stream_session(self, stream: MediaStreamSession) -> MediaStreamSession:
        return self._impl.create_media_stream_session(stream)

    def get_media_stream_session(self, stream_id: str) -> MediaStreamSession:
        return self._impl.get_media_stream_session(stream_id)

    def list_media_stream_sessions_for_project(self, project_id: str) -> tuple[MediaStreamSession, ...]:
        return self._impl.list_media_stream_sessions_for_project(project_id)

    def list_all_media_stream_sessions(self) -> tuple[MediaStreamSession, ...]:
        return self._impl.list_all_media_stream_sessions()

    def mark_media_stream_session_streaming(self, stream_id: str) -> MediaStreamSession:
        return self._impl.mark_media_stream_session_streaming(stream_id)

    def add_media_stream_session_agent_bytes(self, stream_id: str, delta: int) -> MediaStreamSession:
        return self._impl.add_media_stream_session_agent_bytes(stream_id, delta)

    def add_media_stream_session_viewer_bytes(self, stream_id: str, delta: int) -> MediaStreamSession:
        return self._impl.add_media_stream_session_viewer_bytes(stream_id, delta)

    def finalize_media_stream_session(
        self,
        stream_id: str,
        *,
        status: str,
        failure_reason: str | None = None,
    ) -> MediaStreamSession:
        return self._impl.finalize_media_stream_session(
            stream_id,
            status=status,
            failure_reason=failure_reason,
        )

    def upsert_desktop_media_probe_cache(self, item: DesktopMediaProbeCache) -> DesktopMediaProbeCache:
        return self._impl.upsert_desktop_media_probe_cache(item)

    def get_desktop_media_probe_cache(
        self,
        project_id: str,
        instance_id: str,
        agent_id: str,
    ) -> DesktopMediaProbeCache | None:
        return self._impl.get_desktop_media_probe_cache(project_id, instance_id, agent_id)

    def delete_desktop_media_probe_cache(self, project_id: str, instance_id: str, agent_id: str) -> None:
        self._impl.delete_desktop_media_probe_cache(project_id, instance_id, agent_id)

    def upsert_hls_cache_entry(self, item: HlsCacheEntry) -> HlsCacheEntry:
        return self._impl.upsert_hls_cache_entry(item)

    def get_hls_cache_entry(self, cache_key: str, segment_name: str) -> HlsCacheEntry | None:
        return self._impl.get_hls_cache_entry(cache_key, segment_name)

    def list_hls_cache_entries(self, cache_key: str) -> tuple[HlsCacheEntry, ...]:
        return self._impl.list_hls_cache_entries(cache_key)

    def list_all_hls_cache_entries(self) -> tuple[HlsCacheEntry, ...]:
        return self._impl.list_all_hls_cache_entries()

    def touch_hls_cache_entry_access(
        self,
        cache_key: str,
        segment_name: str,
        *,
        last_accessed_at: str | None = None,
    ) -> HlsCacheEntry:
        return self._impl.touch_hls_cache_entry_access(
            cache_key,
            segment_name,
            last_accessed_at=last_accessed_at,
        )

    def delete_hls_cache_entry(self, cache_key: str, segment_name: str) -> None:
        self._impl.delete_hls_cache_entry(cache_key, segment_name)

    def upsert_desktop_agent_hls_job_audit(self, item: DesktopAgentHlsJobAudit) -> DesktopAgentHlsJobAudit:
        return self._impl.upsert_desktop_agent_hls_job_audit(item)

    def get_desktop_agent_hls_job_audit(self, job_id: str) -> DesktopAgentHlsJobAudit | None:
        return self._impl.get_desktop_agent_hls_job_audit(job_id)

    def get_latest_desktop_agent_hls_job_audit_by_cache_key(self, cache_key: str) -> DesktopAgentHlsJobAudit | None:
        return self._impl.get_latest_desktop_agent_hls_job_audit_by_cache_key(cache_key)

    def list_desktop_agent_hls_job_audits_for_project(self, project_id: str) -> tuple[DesktopAgentHlsJobAudit, ...]:
        return self._impl.list_desktop_agent_hls_job_audits_for_project(project_id)

    def list_all_desktop_agent_hls_job_audits(self) -> tuple[DesktopAgentHlsJobAudit, ...]:
        return self._impl.list_all_desktop_agent_hls_job_audits()

    def upsert_desktop_agent_metric_sample(self, item: DesktopAgentMetricSample) -> DesktopAgentMetricSample:
        return self._impl.upsert_desktop_agent_metric_sample(item)

    def get_desktop_agent_metric_sample(self, project_id: str, bucket_start: str) -> DesktopAgentMetricSample | None:
        return self._impl.get_desktop_agent_metric_sample(project_id, bucket_start)

    def list_desktop_agent_metric_samples_for_project(
        self,
        project_id: str,
        *,
        since: str | None = None,
    ) -> tuple[DesktopAgentMetricSample, ...]:
        return self._impl.list_desktop_agent_metric_samples_for_project(project_id, since=since)

    def list_all_desktop_agent_metric_samples(
        self,
        *,
        since: str | None = None,
    ) -> tuple[DesktopAgentMetricSample, ...]:
        return self._impl.list_all_desktop_agent_metric_samples(since=since)

    def delete_desktop_agent_metric_samples_before(self, before: str) -> int:
        return self._impl.delete_desktop_agent_metric_samples_before(before)

    def create_desktop_agent_diagnostic_event(self, item: DesktopAgentDiagnosticEvent) -> DesktopAgentDiagnosticEvent:
        return self._impl.create_desktop_agent_diagnostic_event(item)

    def list_desktop_agent_diagnostic_events_for_user(
        self,
        user_id: str,
        *,
        since: str | None = None,
        limit: int | None = None,
    ) -> tuple[DesktopAgentDiagnosticEvent, ...]:
        return self._impl.list_desktop_agent_diagnostic_events_for_user(user_id, since=since, limit=limit)

    def list_all_desktop_agent_diagnostic_events(
        self,
        *,
        since: str | None = None,
        limit: int | None = None,
    ) -> tuple[DesktopAgentDiagnosticEvent, ...]:
        return self._impl.list_all_desktop_agent_diagnostic_events(since=since, limit=limit)

    def delete_desktop_agent_diagnostic_events_before(self, before: str) -> int:
        return self._impl.delete_desktop_agent_diagnostic_events_before(before)

    def export_snapshot(self) -> dict[str, Any]:
        return self._impl.export_snapshot()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        self._impl.import_snapshot(snapshot, replace=replace)

    def healthcheck(self) -> dict[str, object]:
        return self._impl.healthcheck()
