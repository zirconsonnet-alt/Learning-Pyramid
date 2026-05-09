import hashlib
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.system.postgres_runtime import get_postgres_pool
from backend.system.runtime_features import current_runtime_features
from backend.system.sql_backend import current_sql_runtime_config


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, int(default))
    try:
        value = int(str(raw).strip())
    except Exception:
        value = int(default)
    return max(minimum, value)


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_email(value: str | None) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _normalize_client_ip(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _bucket_key(scope: str, raw_key: str) -> str:
    return hashlib.sha256(f"{scope}:{raw_key}".encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthRateLimitConfig:
    enabled: bool
    login_window_seconds: int
    login_max_failures_per_ip: int
    login_max_failures_per_email: int
    signup_window_seconds: int
    signup_max_attempts_per_ip: int
    signup_max_attempts_per_email: int
    retention_seconds: int


@dataclass(frozen=True, slots=True)
class AuthRateLimitDecision:
    allowed: bool
    retry_after_seconds: int


def current_auth_rate_limit_config() -> AuthRateLimitConfig:
    hosted = current_runtime_features().app_mode == "hosted"
    return AuthRateLimitConfig(
        enabled=_env_bool("PLM_ENABLE_AUTH_RATE_LIMITS", hosted),
        login_window_seconds=_env_int("PLM_AUTH_LOGIN_WINDOW_SECONDS", 600, minimum=1),
        login_max_failures_per_ip=_env_int("PLM_AUTH_LOGIN_MAX_FAILURES_PER_IP", 20, minimum=0),
        login_max_failures_per_email=_env_int("PLM_AUTH_LOGIN_MAX_FAILURES_PER_EMAIL", 8, minimum=0),
        signup_window_seconds=_env_int("PLM_AUTH_SIGNUP_WINDOW_SECONDS", 3600, minimum=1),
        signup_max_attempts_per_ip=_env_int("PLM_AUTH_SIGNUP_MAX_ATTEMPTS_PER_IP", 8, minimum=0),
        signup_max_attempts_per_email=_env_int("PLM_AUTH_SIGNUP_MAX_ATTEMPTS_PER_EMAIL", 3, minimum=0),
        retention_seconds=_env_int("PLM_AUTH_RATE_LIMIT_RETENTION_SECONDS", 86400, minimum=60),
    )


class AuthRateLimitStore:
    _TABLE_NAME = "auth_rate_limit_counters"

    def __init__(self, db_path: Path | None = None, *, postgres_dsn: str | None = None) -> None:
        cfg = current_sql_runtime_config()
        self._config = current_auth_rate_limit_config()
        self._lock = threading.Lock()
        if postgres_dsn is not None:
            self._backend = "postgres"
            self._postgres_dsn = str(postgres_dsn).strip()
            self._db_path = None
        elif db_path is not None:
            self._backend = "sqlite"
            self._db_path = Path(db_path)
            self._postgres_dsn = None
        elif cfg.backend == "postgres":
            if cfg.auth_postgres_dsn is None:
                raise RuntimeError("PostgreSQL auth backend selected without a DSN")
            self._backend = "postgres"
            self._postgres_dsn = str(cfg.auth_postgres_dsn).strip()
            self._db_path = None
        else:
            if cfg.auth_db_path is None:
                raise RuntimeError("SQLite auth backend selected without a path")
            self._backend = "sqlite"
            self._db_path = Path(cfg.auth_db_path)
            self._postgres_dsn = None
        self._init_db()

    @property
    def config(self) -> AuthRateLimitConfig:
        return self._config

    def check_login_allowed(self, *, client_ip: str | None, email: str | None) -> AuthRateLimitDecision:
        return self._check_many(
            (
                ("login_ip", _normalize_client_ip(client_ip), self._config.login_max_failures_per_ip, self._config.login_window_seconds),
                ("login_email", _normalize_email(email), self._config.login_max_failures_per_email, self._config.login_window_seconds),
            )
        )

    def record_login_failure(self, *, client_ip: str | None, email: str | None) -> None:
        self._record_many(
            (
                ("login_ip", _normalize_client_ip(client_ip), self._config.login_window_seconds),
                ("login_email", _normalize_email(email), self._config.login_window_seconds),
            )
        )

    def reset_login_failures(self, *, email: str | None) -> None:
        self._delete_scope_key("login_email", _normalize_email(email))

    def check_signup_allowed(self, *, client_ip: str | None, email: str | None) -> AuthRateLimitDecision:
        return self._check_many(
            (
                ("signup_ip", _normalize_client_ip(client_ip), self._config.signup_max_attempts_per_ip, self._config.signup_window_seconds),
                ("signup_email", _normalize_email(email), self._config.signup_max_attempts_per_email, self._config.signup_window_seconds),
            )
        )

    def record_signup_attempt(self, *, client_ip: str | None, email: str | None) -> None:
        self._record_many(
            (
                ("signup_ip", _normalize_client_ip(client_ip), self._config.signup_window_seconds),
                ("signup_email", _normalize_email(email), self._config.signup_window_seconds),
            )
        )

    def check_scope_allowed(
        self,
        *,
        scope: str,
        raw_key: str | None,
        limit: int,
        window_seconds: int,
    ) -> AuthRateLimitDecision:
        return self._check_many(((str(scope), str(raw_key or "").strip() or None, int(limit), int(window_seconds)),))

    def record_scope_action(
        self,
        *,
        scope: str,
        raw_key: str | None,
        window_seconds: int,
    ) -> None:
        self._record_many(((str(scope), str(raw_key or "").strip() or None, int(window_seconds)),))

    def _connect_sqlite(self) -> sqlite3.Connection:
        if self._db_path is None:
            raise RuntimeError("SQLite auth rate limit store has no db path")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (
            scope TEXT NOT NULL,
            bucket_key TEXT NOT NULL,
            window_started_at TEXT NOT NULL,
            attempt_count INTEGER NOT NULL,
            last_attempt_at TEXT NOT NULL,
            PRIMARY KEY(scope, bucket_key)
        );
        CREATE INDEX IF NOT EXISTS idx_{self._TABLE_NAME}_last_attempt_at
        ON {self._TABLE_NAME} (last_attempt_at);
        """
        with self._lock:
            if self._backend == "sqlite":
                conn = self._connect_sqlite()
                try:
                    conn.executescript(sql)
                    conn.commit()
                finally:
                    conn.close()
                return

            pool = get_postgres_pool(str(self._postgres_dsn))
            with pool.connection() as conn:
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (
                        scope TEXT NOT NULL,
                        bucket_key TEXT NOT NULL,
                        window_started_at TEXT NOT NULL,
                        attempt_count BIGINT NOT NULL,
                        last_attempt_at TEXT NOT NULL,
                        PRIMARY KEY(scope, bucket_key)
                    )
                    """
                )
                conn.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{self._TABLE_NAME}_last_attempt_at
                    ON {self._TABLE_NAME} (last_attempt_at)
                    """
                )

    def _check_many(self, items: tuple[tuple[str, str | None, int, int], ...]) -> AuthRateLimitDecision:
        if not self._config.enabled:
            return AuthRateLimitDecision(allowed=True, retry_after_seconds=0)
        now = _utc_now()
        retry_after_seconds = 0
        with self._lock:
            conn = self._connect_sqlite() if self._backend == "sqlite" else get_postgres_pool(str(self._postgres_dsn)).acquire()
            try:
                self._delete_stale_rows(conn, now=now)
                blocked = False
                for scope, raw_key, limit, window_seconds in items:
                    if not raw_key or limit <= 0:
                        continue
                    row = self._fetch_row(conn, scope=scope, bucket_key=_bucket_key(scope, raw_key))
                    if row is None:
                        continue
                    window_started_at = _parse_dt(str(row["window_started_at"]))
                    if window_started_at + timedelta(seconds=window_seconds) <= now:
                        self._delete_row(conn, scope=scope, bucket_key=_bucket_key(scope, raw_key))
                        continue
                    attempt_count = int(row["attempt_count"])
                    if attempt_count >= limit:
                        blocked = True
                        window_ends_at = window_started_at + timedelta(seconds=window_seconds)
                        retry_after_seconds = max(retry_after_seconds, max(1, int((window_ends_at - now).total_seconds())))
                if self._backend == "sqlite":
                    conn.commit()
            finally:
                if self._backend == "sqlite":
                    conn.close()
                else:
                    get_postgres_pool(str(self._postgres_dsn)).release(conn)
        return AuthRateLimitDecision(allowed=not blocked, retry_after_seconds=retry_after_seconds)

    def _record_many(self, items: tuple[tuple[str, str | None, int], ...]) -> None:
        if not self._config.enabled:
            return
        now = _utc_now()
        with self._lock:
            conn = self._connect_sqlite() if self._backend == "sqlite" else get_postgres_pool(str(self._postgres_dsn)).acquire()
            try:
                self._delete_stale_rows(conn, now=now)
                for scope, raw_key, window_seconds in items:
                    if not raw_key:
                        continue
                    bucket_key = _bucket_key(scope, raw_key)
                    row = self._fetch_row(conn, scope=scope, bucket_key=bucket_key)
                    if row is None:
                        self._upsert_row(
                            conn,
                            scope=scope,
                            bucket_key=bucket_key,
                            window_started_at=now.isoformat(),
                            attempt_count=1,
                            last_attempt_at=now.isoformat(),
                        )
                        continue
                    window_started_at = _parse_dt(str(row["window_started_at"]))
                    if window_started_at + timedelta(seconds=window_seconds) <= now:
                        self._upsert_row(
                            conn,
                            scope=scope,
                            bucket_key=bucket_key,
                            window_started_at=now.isoformat(),
                            attempt_count=1,
                            last_attempt_at=now.isoformat(),
                        )
                        continue
                    self._upsert_row(
                        conn,
                        scope=scope,
                        bucket_key=bucket_key,
                        window_started_at=str(row["window_started_at"]),
                        attempt_count=int(row["attempt_count"]) + 1,
                        last_attempt_at=now.isoformat(),
                    )
                if self._backend == "sqlite":
                    conn.commit()
            finally:
                if self._backend == "sqlite":
                    conn.close()
                else:
                    get_postgres_pool(str(self._postgres_dsn)).release(conn)

    def _delete_scope_key(self, scope: str, raw_key: str | None) -> None:
        if not self._config.enabled or not raw_key:
            return
        bucket_key = _bucket_key(scope, raw_key)
        with self._lock:
            conn = self._connect_sqlite() if self._backend == "sqlite" else get_postgres_pool(str(self._postgres_dsn)).acquire()
            try:
                self._delete_row(conn, scope=scope, bucket_key=bucket_key)
                if self._backend == "sqlite":
                    conn.commit()
            finally:
                if self._backend == "sqlite":
                    conn.close()
                else:
                    get_postgres_pool(str(self._postgres_dsn)).release(conn)

    def _fetch_row(self, conn: Any, *, scope: str, bucket_key: str) -> Any | None:
        if self._backend == "sqlite":
            return conn.execute(
                f"SELECT * FROM {self._TABLE_NAME} WHERE scope = ? AND bucket_key = ? LIMIT 1",
                (scope, bucket_key),
            ).fetchone()
        return conn.execute(
            f"SELECT * FROM {self._TABLE_NAME} WHERE scope = %s AND bucket_key = %s LIMIT 1",
            (scope, bucket_key),
        ).fetchone()

    def _upsert_row(
        self,
        conn: Any,
        *,
        scope: str,
        bucket_key: str,
        window_started_at: str,
        attempt_count: int,
        last_attempt_at: str,
    ) -> None:
        if self._backend == "sqlite":
            conn.execute(
                f"""
                INSERT INTO {self._TABLE_NAME} (scope, bucket_key, window_started_at, attempt_count, last_attempt_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scope, bucket_key) DO UPDATE SET
                    window_started_at = excluded.window_started_at,
                    attempt_count = excluded.attempt_count,
                    last_attempt_at = excluded.last_attempt_at
                """,
                (scope, bucket_key, window_started_at, int(attempt_count), last_attempt_at),
            )
            return
        conn.execute(
            f"""
            INSERT INTO {self._TABLE_NAME} (scope, bucket_key, window_started_at, attempt_count, last_attempt_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(scope, bucket_key) DO UPDATE SET
                window_started_at = EXCLUDED.window_started_at,
                attempt_count = EXCLUDED.attempt_count,
                last_attempt_at = EXCLUDED.last_attempt_at
            """,
            (scope, bucket_key, window_started_at, int(attempt_count), last_attempt_at),
        )

    def _delete_row(self, conn: Any, *, scope: str, bucket_key: str) -> None:
        if self._backend == "sqlite":
            conn.execute(
                f"DELETE FROM {self._TABLE_NAME} WHERE scope = ? AND bucket_key = ?",
                (scope, bucket_key),
            )
            return
        conn.execute(
            f"DELETE FROM {self._TABLE_NAME} WHERE scope = %s AND bucket_key = %s",
            (scope, bucket_key),
        )

    def _delete_stale_rows(self, conn: Any, *, now: datetime) -> None:
        cutoff = (now - timedelta(seconds=self._config.retention_seconds)).isoformat()
        if self._backend == "sqlite":
            conn.execute(
                f"DELETE FROM {self._TABLE_NAME} WHERE last_attempt_at < ?",
                (cutoff,),
            )
            return
        conn.execute(
            f"DELETE FROM {self._TABLE_NAME} WHERE last_attempt_at < %s",
            (cutoff,),
        )
