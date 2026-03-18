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
    def _snapshot_payload(
        *,
        users: list[dict[str, str]],
        sessions: list[dict[str, str]],
        memberships: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "users": users,
            "sessions": sessions,
            "projectMemberships": memberships,
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
                    """
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
                    "SELECT user_id, email, password_hash, created_at FROM users ORDER BY created_at ASC, user_id ASC"
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
            return self._snapshot_payload(users=users, sessions=sessions, memberships=memberships)
        finally:
            conn.close()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        with self._lock:
            conn = self._connect()
            try:
                if replace:
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
                            str(row.get("role", "owner") or "owner"),
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
                    "SELECT user_id, email, password_hash, created_at FROM users ORDER BY created_at ASC, user_id ASC"
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
        return self._snapshot_payload(users=users, sessions=sessions, memberships=memberships)

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        with self._lock:
            with self._connect() as conn:
                if replace:
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
                raise RuntimeError("PostgreSQL auth backend selected without a DSN")
            self._impl = PostgresAuthStore(cfg.auth_postgres_dsn)
            return
        self._impl = SQLiteAuthStore(cfg.auth_db_path)

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

    def export_snapshot(self) -> dict[str, Any]:
        return self._impl.export_snapshot()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        self._impl.import_snapshot(snapshot, replace=replace)

    def healthcheck(self) -> dict[str, object]:
        return self._impl.healthcheck()
