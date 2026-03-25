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
from typing import Any, Iterable

PUBLIC_UID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
USER_STATUSES = {"active", "suspended", "deleted"}
GLOBAL_ROLES = {"super_admin", "admin"}
STUDY_GROUP_VISIBILITIES = {"public", "private"}
STUDY_GROUP_JOIN_POLICIES = {"free", "approval", "invite_only"}
STUDY_GROUP_STATUSES = {"active", "archived", "blocked", "dissolved"}
STUDY_GROUP_MEMBER_ROLES = {"owner", "admin", "member"}
STUDY_GROUP_POST_KINDS = {"notice", "discussion", "checkin"}
STUDY_GROUP_JOIN_REQUEST_STATUSES = {"pending", "approved", "rejected", "cancelled"}
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


def _normalize_group_visibility(visibility: str) -> str:
    value = str(visibility).strip().lower()
    if value not in STUDY_GROUP_VISIBILITIES:
        raise PreconditionFailure("visibility must be one of public, private")
    return value


def _normalize_group_join_policy(join_policy: str) -> str:
    value = str(join_policy).strip().lower()
    if value not in STUDY_GROUP_JOIN_POLICIES:
        raise PreconditionFailure("joinPolicy must be one of free, approval, invite_only")
    return value


def _normalize_group_status(status: str) -> str:
    value = str(status).strip().lower()
    if value not in STUDY_GROUP_STATUSES:
        raise PreconditionFailure("group status must be one of active, archived, blocked, dissolved")
    return value


def _normalize_group_name(name: str) -> str:
    value = str(name).strip()
    if not value:
        raise PreconditionFailure("group name must be non-empty")
    if len(value) > 60:
        raise PreconditionFailure("group name must be at most 60 characters")
    return value


def _normalize_group_description(description: str | None) -> str:
    value = str(description or "").strip()
    if len(value) > 1000:
        raise PreconditionFailure("group description must be at most 1000 characters")
    return value


def _normalize_group_member_role(role: str) -> str:
    value = str(role).strip().lower()
    if value not in STUDY_GROUP_MEMBER_ROLES:
        raise PreconditionFailure("group member role must be one of owner, admin, member")
    return value


def _normalize_group_post_kind(kind: str) -> str:
    value = str(kind).strip().lower()
    if value not in STUDY_GROUP_POST_KINDS:
        raise PreconditionFailure("post kind must be one of notice, discussion, checkin")
    return value


def _normalize_group_post_content(content: str) -> str:
    value = str(content).strip()
    if not value:
        raise PreconditionFailure("content must be non-empty")
    if len(value) > 2000:
        raise PreconditionFailure("content must be at most 2000 characters")
    return value


def _normalize_group_post_comment_content(content: str) -> str:
    value = str(content).strip()
    if not value:
        raise PreconditionFailure("comment content must be non-empty")
    if len(value) > 1000:
        raise PreconditionFailure("comment content must be at most 1000 characters")
    return value


def _normalize_admin_action_field(value: str, *, field_name: str, maximum: int) -> str:
    text = str(value).strip()
    if not text:
        raise PreconditionFailure(f"{field_name} must be non-empty")
    if len(text) > maximum:
        raise PreconditionFailure(f"{field_name} must be at most {maximum} characters")
    return text


def _normalize_join_request_message(message: str | None) -> str:
    value = str(message or "").strip()
    if len(value) > 300:
        raise PreconditionFailure("join request message must be at most 300 characters")
    return value


def _normalize_join_request_status(status: str) -> str:
    value = str(status).strip().lower()
    if value not in STUDY_GROUP_JOIN_REQUEST_STATUSES:
        raise PreconditionFailure("join request status must be one of pending, approved, rejected, cancelled")
    return value


def _normalize_limit(limit: int, *, default: int = 100, maximum: int = 200) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, maximum))


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
class AdminUserStudyGroup:
    group_id: str
    name: str
    description: str
    visibility: str
    join_policy: str
    status: str
    owner_user_id: str
    owner_public_uid: str
    owner_nickname: str
    avatar_key: str | None
    created_at: str
    updated_at: str
    member_count: int
    member_role: str
    joined_at: str


@dataclass(frozen=True, slots=True)
class AdminStudyGroupPost:
    post_id: str
    group_id: str
    group_name: str
    author_user_id: str
    author_public_uid: str
    author_nickname: str
    author_avatar_key: str | None
    kind: str
    content: str
    created_at: str
    updated_at: str
    comment_count: int


@dataclass(frozen=True, slots=True)
class AdminStudyGroupComment:
    comment_id: str
    group_id: str
    group_name: str
    post_id: str
    post_kind: str
    post_excerpt: str
    author_user_id: str
    author_public_uid: str
    author_nickname: str
    author_avatar_key: str | None
    content: str
    created_at: str
    updated_at: str


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
class StudyGroup:
    group_id: str
    name: str
    description: str
    visibility: str
    join_policy: str
    status: str
    owner_user_id: str
    owner_public_uid: str
    owner_nickname: str
    avatar_key: str | None
    created_at: str
    updated_at: str
    member_count: int
    member_role: str | None
    join_request_status: str | None


@dataclass(frozen=True, slots=True)
class StudyGroupMember:
    user_id: str
    public_uid: str
    nickname: str
    email: str
    avatar_key: str | None
    role: str
    joined_at: str


@dataclass(frozen=True, slots=True)
class StudyGroupPost:
    post_id: str
    group_id: str
    author_user_id: str
    author_public_uid: str
    author_nickname: str
    author_avatar_key: str | None
    kind: str
    content: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class StudyGroupPostComment:
    comment_id: str
    group_id: str
    post_id: str
    author_user_id: str
    author_public_uid: str
    author_nickname: str
    author_avatar_key: str | None
    content: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class StudyGroupJoinRequest:
    request_id: str
    group_id: str
    requester_user_id: str
    requester_public_uid: str
    requester_nickname: str
    requester_avatar_key: str | None
    message: str
    status: str
    created_at: str
    reviewed_at: str | None
    reviewed_by_user_id: str | None


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
    def _row_to_admin_group_post(row: Any) -> AdminStudyGroupPost:
        return AdminStudyGroupPost(
            post_id=str(row["post_id"]),
            group_id=str(row["group_id"]),
            group_name=str(row["group_name"]),
            author_user_id=str(row["author_user_id"]),
            author_public_uid=str(row["author_public_uid"]),
            author_nickname=str(row["author_nickname"]),
            author_avatar_key=_normalize_avatar_key(row["author_avatar_key"]),
            kind=str(row["kind"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            comment_count=int(row["comment_count"]),
        )

    @staticmethod
    def _row_to_admin_group_comment(row: Any) -> AdminStudyGroupComment:
        return AdminStudyGroupComment(
            comment_id=str(row["comment_id"]),
            group_id=str(row["group_id"]),
            group_name=str(row["group_name"]),
            post_id=str(row["post_id"]),
            post_kind=str(row["post_kind"]),
            post_excerpt=str(row["post_excerpt"]),
            author_user_id=str(row["author_user_id"]),
            author_public_uid=str(row["author_public_uid"]),
            author_nickname=str(row["author_nickname"]),
            author_avatar_key=_normalize_avatar_key(row["author_avatar_key"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

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
    def _row_to_group(row: Any) -> StudyGroup:
        member_role = row["member_role"]
        join_request_status = row["join_request_status"]
        return StudyGroup(
            group_id=str(row["group_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            visibility=str(row["visibility"]),
            join_policy=str(row["join_policy"]),
            status=str(row["status"]),
            owner_user_id=str(row["owner_user_id"]),
            owner_public_uid=str(row["owner_public_uid"]),
            owner_nickname=str(row["owner_nickname"]),
            avatar_key=_normalize_avatar_key(row["avatar_key"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            member_count=int(row["member_count"]),
            member_role=None if member_role is None else str(member_role),
            join_request_status=None if join_request_status is None else str(join_request_status),
        )

    @staticmethod
    def _row_to_group_member(row: Any) -> StudyGroupMember:
        return StudyGroupMember(
            user_id=str(row["user_id"]),
            public_uid=str(row["public_uid"]),
            nickname=str(row["nickname"]),
            email=str(row["email"]),
            avatar_key=_normalize_avatar_key(row["avatar_key"]),
            role=str(row["role"]),
            joined_at=str(row["joined_at"]),
        )

    @staticmethod
    def _row_to_admin_user_group(row: Any) -> AdminUserStudyGroup:
        return AdminUserStudyGroup(
            group_id=str(row["group_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            visibility=str(row["visibility"]),
            join_policy=str(row["join_policy"]),
            status=str(row["status"]),
            owner_user_id=str(row["owner_user_id"]),
            owner_public_uid=str(row["owner_public_uid"]),
            owner_nickname=str(row["owner_nickname"]),
            avatar_key=_normalize_avatar_key(row["avatar_key"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            member_count=int(row["member_count"]),
            member_role=str(row["member_role"]),
            joined_at=str(row["joined_at"]),
        )

    @staticmethod
    def _row_to_group_post(row: Any) -> StudyGroupPost:
        return StudyGroupPost(
            post_id=str(row["post_id"]),
            group_id=str(row["group_id"]),
            author_user_id=str(row["author_user_id"]),
            author_public_uid=str(row["author_public_uid"]),
            author_nickname=str(row["author_nickname"]),
            author_avatar_key=_normalize_avatar_key(row["author_avatar_key"]),
            kind=str(row["kind"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_group_post_comment(row: Any) -> StudyGroupPostComment:
        return StudyGroupPostComment(
            comment_id=str(row["comment_id"]),
            group_id=str(row["group_id"]),
            post_id=str(row["post_id"]),
            author_user_id=str(row["author_user_id"]),
            author_public_uid=str(row["author_public_uid"]),
            author_nickname=str(row["author_nickname"]),
            author_avatar_key=_normalize_avatar_key(row["author_avatar_key"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_join_request(row: Any) -> StudyGroupJoinRequest:
        return StudyGroupJoinRequest(
            request_id=str(row["request_id"]),
            group_id=str(row["group_id"]),
            requester_user_id=str(row["requester_user_id"]),
            requester_public_uid=str(row["requester_public_uid"]),
            requester_nickname=str(row["requester_nickname"]),
            requester_avatar_key=_normalize_avatar_key(row["requester_avatar_key"]),
            message=str(row["message"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            reviewed_at=None if row["reviewed_at"] is None else str(row["reviewed_at"]),
            reviewed_by_user_id=None if row["reviewed_by_user_id"] is None else str(row["reviewed_by_user_id"]),
        )

    @staticmethod
    def _snapshot_payload(
        *,
        users: list[dict[str, str]],
        sessions: list[dict[str, str]],
        memberships: list[dict[str, str]],
        profiles: list[dict[str, str | None]],
        roles: list[dict[str, str]],
        study_groups: list[dict[str, str | None]],
        study_group_members: list[dict[str, str]],
        study_group_posts: list[dict[str, str | None]],
        study_group_post_comments: list[dict[str, str | None]],
        study_group_join_requests: list[dict[str, str | None]],
        admin_action_logs: list[dict[str, str | None]],
    ) -> dict[str, Any]:
        return {
            "users": users,
            "sessions": sessions,
            "projectMemberships": memberships,
            "userProfiles": profiles,
            "userGlobalRoles": roles,
            "studyGroups": study_groups,
            "studyGroupMembers": study_group_members,
            "studyGroupPosts": study_group_posts,
            "studyGroupPostComments": study_group_post_comments,
            "studyGroupJoinRequests": study_group_join_requests,
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

    def _bootstrap_super_admin(self, conn: sqlite3.Connection) -> None:
        count_row = conn.execute("SELECT COUNT(*) AS count FROM user_global_roles").fetchone()
        if count_row is not None and int(count_row["count"]) > 0:
            return
        owner_row = conn.execute("SELECT user_id, created_at FROM users ORDER BY created_at ASC, user_id ASC LIMIT 1").fetchone()
        if owner_row is None:
            return
        conn.execute(
            """
            INSERT OR IGNORE INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
            VALUES (?, 'super_admin', ?, ?)
            """,
            (str(owner_row["user_id"]), str(owner_row["user_id"]), str(owner_row["created_at"])),
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

                    CREATE TABLE IF NOT EXISTS user_global_roles (
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        granted_by_user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, role),
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY(granted_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS study_groups (
                        group_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        visibility TEXT NOT NULL,
                        join_policy TEXT NOT NULL,
                        status TEXT NOT NULL,
                        owner_user_id TEXT NOT NULL,
                        avatar_key TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS study_group_members (
                        group_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        joined_at TEXT NOT NULL,
                        PRIMARY KEY(group_id, user_id),
                        FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS study_group_posts (
                        post_id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        author_user_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                        FOREIGN KEY(author_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS study_group_post_comments (
                        comment_id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        post_id TEXT NOT NULL,
                        author_user_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                        FOREIGN KEY(post_id) REFERENCES study_group_posts(post_id) ON DELETE CASCADE,
                        FOREIGN KEY(author_user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS study_group_join_requests (
                        request_id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        requester_user_id TEXT NOT NULL,
                        message TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        reviewed_at TEXT,
                        reviewed_by_user_id TEXT,
                        FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                        FOREIGN KEY(requester_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY(reviewed_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
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

                    CREATE INDEX IF NOT EXISTS idx_user_profiles_public_uid ON user_profiles (public_uid);
                    CREATE INDEX IF NOT EXISTS idx_user_global_roles_role ON user_global_roles (role, user_id);
                    CREATE INDEX IF NOT EXISTS idx_study_group_members_user_id ON study_group_members (user_id, joined_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_study_group_posts_group_id ON study_group_posts (group_id, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_study_group_post_comments_post_id ON study_group_post_comments (post_id, created_at ASC);
                    CREATE INDEX IF NOT EXISTS idx_study_group_join_requests_group_status
                    ON study_group_join_requests (group_id, status, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_admin_action_logs_created_at ON admin_action_logs (created_at DESC);
                    """
                )
                self._backfill_user_profiles(conn)
                self._bootstrap_super_admin(conn)
                conn.commit()
            finally:
                conn.close()

    def create_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        now_text = _utc_now().isoformat()
        user_id = f"user_{uuid.uuid4().hex}"
        password_hash = self._hash_password(password)
        with self._lock:
            conn = self._connect()
            try:
                is_first_user = int(conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]) == 0
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, normalized_email, password_hash, now_text),
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
                if is_first_user:
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
                SELECT {USER_COLUMNS_SQL}, u.password_hash
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
        if str(row["status"]) != "active":
            raise PreconditionFailure("account is not active")
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
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE s.session_token = ? AND s.expires_at > ? AND p.status = 'active'
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

    def delete_other_sessions_for_user(self, user_id: str, *, except_session_token: str | None = None) -> None:
        with self._lock:
            conn = self._connect()
            try:
                if except_session_token:
                    conn.execute(
                        "DELETE FROM sessions WHERE user_id = ? AND session_token <> ?",
                        (str(user_id), str(except_session_token)),
                    )
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
            groups = int(conn.execute("SELECT COUNT(*) AS count FROM study_groups").fetchone()["count"])
            active_groups = int(conn.execute("SELECT COUNT(*) AS count FROM study_groups WHERE status = 'active'").fetchone()["count"])
            posts = int(conn.execute("SELECT COUNT(*) AS count FROM study_group_posts").fetchone()["count"])
            comments = int(conn.execute("SELECT COUNT(*) AS count FROM study_group_post_comments").fetchone()["count"])
        finally:
            conn.close()
        return {
            "users": users,
            "activeUsers": active_users,
            "groups": groups,
            "activeGroups": active_groups,
            "posts": posts,
            "comments": comments,
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

    def list_admin_study_group_posts(self, *, search: str | None = None, limit: int = 100) -> tuple[AdminStudyGroupPost, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(g.name LIKE ? OR p.content LIKE ? OR profile.nickname LIKE ? OR profile.public_uid LIKE ?)")
            params.extend((needle, needle, needle, needle))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    p.post_id,
                    p.group_id,
                    g.name AS group_name,
                    p.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    p.kind,
                    p.content,
                    p.created_at,
                    p.updated_at,
                    COALESCE(comment_counts.comment_count, 0) AS comment_count
                FROM study_group_posts p
                JOIN study_groups g ON g.group_id = p.group_id
                JOIN user_profiles profile ON profile.user_id = p.author_user_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS comment_count
                    FROM study_group_post_comments
                    GROUP BY post_id
                ) comment_counts ON comment_counts.post_id = p.post_id
                WHERE {' AND '.join(clauses)}
                ORDER BY p.created_at DESC, p.post_id DESC
                LIMIT ?
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_admin_group_post(row) for row in rows)

    def list_admin_study_group_comments(self, *, search: str | None = None, limit: int = 100) -> tuple[AdminStudyGroupComment, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(g.name LIKE ? OR c.content LIKE ? OR p.content LIKE ? OR profile.nickname LIKE ? OR profile.public_uid LIKE ?)")
            params.extend((needle, needle, needle, needle, needle))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    c.comment_id,
                    c.group_id,
                    g.name AS group_name,
                    c.post_id,
                    p.kind AS post_kind,
                    SUBSTR(p.content, 1, 120) AS post_excerpt,
                    c.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    c.content,
                    c.created_at,
                    c.updated_at
                FROM study_group_post_comments c
                JOIN study_group_posts p ON p.post_id = c.post_id AND p.group_id = c.group_id
                JOIN study_groups g ON g.group_id = c.group_id
                JOIN user_profiles profile ON profile.user_id = c.author_user_id
                WHERE {' AND '.join(clauses)}
                ORDER BY c.created_at DESC, c.comment_id DESC
                LIMIT ?
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_admin_group_comment(row) for row in rows)

    def delete_admin_study_group_post(self, post_id: str) -> AdminStudyGroupPost:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT
                        p.post_id,
                        p.group_id,
                        g.name AS group_name,
                        p.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        p.kind,
                        p.content,
                        p.created_at,
                        p.updated_at,
                        COALESCE(comment_counts.comment_count, 0) AS comment_count
                    FROM study_group_posts p
                    JOIN study_groups g ON g.group_id = p.group_id
                    JOIN user_profiles profile ON profile.user_id = p.author_user_id
                    LEFT JOIN (
                        SELECT post_id, COUNT(*) AS comment_count
                        FROM study_group_post_comments
                        GROUP BY post_id
                    ) comment_counts ON comment_counts.post_id = p.post_id
                    WHERE p.post_id = ?
                    """,
                    (str(post_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post")
                deleted = self._row_to_admin_group_post(row)
                now_text = _utc_now().isoformat()
                conn.execute("DELETE FROM study_group_posts WHERE post_id = ?", (str(post_id),))
                conn.execute("UPDATE study_groups SET updated_at = ? WHERE group_id = ?", (now_text, deleted.group_id))
                conn.commit()
                return deleted
            finally:
                conn.close()

    def delete_admin_study_group_comment(self, comment_id: str) -> AdminStudyGroupComment:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT
                        c.comment_id,
                        c.group_id,
                        g.name AS group_name,
                        c.post_id,
                        p.kind AS post_kind,
                        SUBSTR(p.content, 1, 120) AS post_excerpt,
                        c.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        c.content,
                        c.created_at,
                        c.updated_at
                    FROM study_group_post_comments c
                    JOIN study_group_posts p ON p.post_id = c.post_id AND p.group_id = c.group_id
                    JOIN study_groups g ON g.group_id = c.group_id
                    JOIN user_profiles profile ON profile.user_id = c.author_user_id
                    WHERE c.comment_id = ?
                    """,
                    (str(comment_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post_comment")
                deleted = self._row_to_admin_group_comment(row)
                now_text = _utc_now().isoformat()
                conn.execute("DELETE FROM study_group_post_comments WHERE comment_id = ?", (str(comment_id),))
                conn.execute("UPDATE study_groups SET updated_at = ? WHERE group_id = ?", (now_text, deleted.group_id))
                conn.commit()
                return deleted
            finally:
                conn.close()

    def _get_study_group(self, conn: sqlite3.Connection, group_id: str, *, viewer_user_id: str | None) -> StudyGroup:
        row = conn.execute(
            """
            SELECT
                g.group_id,
                g.name,
                g.description,
                g.visibility,
                g.join_policy,
                g.status,
                g.owner_user_id,
                owner_profile.public_uid AS owner_public_uid,
                owner_profile.nickname AS owner_nickname,
                g.avatar_key,
                g.created_at,
                g.updated_at,
                COALESCE(member_counts.member_count, 0) AS member_count,
                viewer_member.role AS member_role,
                viewer_request.status AS join_request_status
            FROM study_groups g
            JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
            LEFT JOIN (
                SELECT group_id, COUNT(*) AS member_count
                FROM study_group_members
                GROUP BY group_id
            ) member_counts ON member_counts.group_id = g.group_id
            LEFT JOIN study_group_members viewer_member
                ON viewer_member.group_id = g.group_id AND viewer_member.user_id = ?
            LEFT JOIN study_group_join_requests viewer_request
                ON viewer_request.group_id = g.group_id
               AND viewer_request.requester_user_id = ?
               AND viewer_request.status = 'pending'
            WHERE g.group_id = ?
            """,
            (
                None if viewer_user_id is None else str(viewer_user_id),
                None if viewer_user_id is None else str(viewer_user_id),
                str(group_id),
            ),
        ).fetchone()
        if row is None:
            raise NotFound("study_group")
        return self._row_to_group(row)

    def create_study_group(
        self,
        *,
        owner_user_id: str,
        name: str,
        description: str | None,
        visibility: str,
        join_policy: str,
    ) -> StudyGroup:
        normalized_name = _normalize_group_name(name)
        normalized_description = _normalize_group_description(description)
        normalized_visibility = _normalize_group_visibility(visibility)
        normalized_join_policy = _normalize_group_join_policy(join_policy)
        now_text = _utc_now().isoformat()
        group_id = f"group_{uuid.uuid4().hex}"
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO study_groups (
                        group_id, name, description, visibility, join_policy, status, owner_user_id, avatar_key, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'active', ?, NULL, ?, ?)
                    """,
                    (
                        group_id,
                        normalized_name,
                        normalized_description,
                        normalized_visibility,
                        normalized_join_policy,
                        str(owner_user_id),
                        now_text,
                        now_text,
                    ),
                )
                conn.execute(
                    "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
                    (group_id, str(owner_user_id), now_text),
                )
                conn.commit()
            finally:
                conn.close()
        conn = self._connect()
        try:
            return self._get_study_group(conn, group_id, viewer_user_id=owner_user_id)
        finally:
            conn.close()

    def list_study_groups_for_user(self, user_id: str, *, limit: int = 100) -> tuple[StudyGroup, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    g.group_id,
                    g.name,
                    g.description,
                    g.visibility,
                    g.join_policy,
                    g.status,
                    g.owner_user_id,
                    owner_profile.public_uid AS owner_public_uid,
                    owner_profile.nickname AS owner_nickname,
                    g.avatar_key,
                    g.created_at,
                    g.updated_at,
                    COALESCE(member_counts.member_count, 0) AS member_count,
                    viewer_member.role AS member_role,
                    viewer_request.status AS join_request_status
                FROM study_groups g
                JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
                LEFT JOIN (
                    SELECT group_id, COUNT(*) AS member_count
                    FROM study_group_members
                    GROUP BY group_id
                ) member_counts ON member_counts.group_id = g.group_id
                LEFT JOIN study_group_members viewer_member
                    ON viewer_member.group_id = g.group_id AND viewer_member.user_id = ?
                LEFT JOIN study_group_join_requests viewer_request
                    ON viewer_request.group_id = g.group_id
                   AND viewer_request.requester_user_id = ?
                   AND viewer_request.status = 'pending'
                WHERE g.status <> 'dissolved' AND (g.visibility = 'public' OR viewer_member.user_id IS NOT NULL)
                ORDER BY CASE WHEN viewer_member.user_id IS NOT NULL THEN 0 ELSE 1 END, g.updated_at DESC, g.group_id ASC
                LIMIT ?
                """,
                (str(user_id), str(user_id), _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_group(row) for row in rows)

    def list_all_study_groups(self, *, search: str | None = None, status: str | None = None, limit: int = 100) -> tuple[StudyGroup, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(g.name LIKE ? OR g.description LIKE ?)")
            params.extend((needle, needle))
        if status and str(status).strip():
            clauses.append("g.status = ?")
            params.append(_normalize_group_status(status))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    g.group_id,
                    g.name,
                    g.description,
                    g.visibility,
                    g.join_policy,
                    g.status,
                    g.owner_user_id,
                    owner_profile.public_uid AS owner_public_uid,
                    owner_profile.nickname AS owner_nickname,
                    g.avatar_key,
                    g.created_at,
                    g.updated_at,
                    COALESCE(member_counts.member_count, 0) AS member_count,
                    NULL AS member_role,
                    NULL AS join_request_status
                FROM study_groups g
                JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
                LEFT JOIN (
                    SELECT group_id, COUNT(*) AS member_count
                    FROM study_group_members
                    GROUP BY group_id
                ) member_counts ON member_counts.group_id = g.group_id
                WHERE {' AND '.join(clauses)}
                ORDER BY g.updated_at DESC, g.group_id ASC
                LIMIT ?
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_group(row) for row in rows)

    def get_study_group(self, group_id: str, *, viewer_user_id: str | None) -> StudyGroup:
        conn = self._connect()
        try:
            return self._get_study_group(conn, group_id, viewer_user_id=viewer_user_id)
        finally:
            conn.close()

    def get_study_group_member_role(self, group_id: str, user_id: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                (str(group_id), str(user_id)),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else str(row["role"])

    def update_study_group_member_role(
        self,
        group_id: str,
        *,
        target_user_id: str,
        role: str,
        actor_user_id: str,
    ) -> StudyGroupMember:
        normalized_role = _normalize_group_member_role(role)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role != "owner":
                    raise PreconditionFailure("only the group owner can manage member roles")

                target_row = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(target_user_id)),
                ).fetchone()
                if target_row is None:
                    raise NotFound("study_group_member")
                current_role = str(target_row["role"])

                if normalized_role == current_role:
                    conn.commit()
                elif normalized_role == "owner":
                    if not actor_is_admin and str(actor_user_id) != str(group.owner_user_id):
                        raise PreconditionFailure("only the current owner can transfer ownership")
                    conn.execute(
                        "UPDATE study_group_members SET role = 'admin' WHERE group_id = ? AND user_id = ?",
                        (str(group_id), str(group.owner_user_id)),
                    )
                    conn.execute(
                        "UPDATE study_group_members SET role = 'owner' WHERE group_id = ? AND user_id = ?",
                        (str(group_id), str(target_user_id)),
                    )
                    conn.execute(
                        "UPDATE study_groups SET owner_user_id = ?, updated_at = ? WHERE group_id = ?",
                        (str(target_user_id), now_text, str(group_id)),
                    )
                    conn.commit()
                else:
                    if current_role == "owner":
                        raise PreconditionFailure("transfer ownership before changing the current owner role")
                    conn.execute(
                        "UPDATE study_group_members SET role = ? WHERE group_id = ? AND user_id = ?",
                        (normalized_role, str(group_id), str(target_user_id)),
                    )
                    conn.execute(
                        "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                        (now_text, str(group_id)),
                    )
                    conn.commit()
            finally:
                conn.close()
        members = self.list_study_group_members(group_id)
        for member in members:
            if member.user_id == str(target_user_id):
                return member
        raise NotFound("study_group_member")

    def remove_study_group_member(self, group_id: str, *, target_user_id: str, actor_user_id: str) -> None:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role != "owner":
                    raise PreconditionFailure("only the group owner can remove members")

                target_row = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(target_user_id)),
                ).fetchone()
                if target_row is None:
                    raise NotFound("study_group_member")
                if str(target_row["role"]) == "owner":
                    raise PreconditionFailure("group owner cannot be removed")
                conn.execute(
                    "DELETE FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(target_user_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                    (now_text, str(group_id)),
                )
                conn.commit()
            finally:
                conn.close()

    def invite_study_group_member(
        self,
        group_id: str,
        *,
        target_user_id: str,
        role: str,
        actor_user_id: str,
    ) -> StudyGroupMember:
        normalized_role = _normalize_group_member_role(role)
        if normalized_role == "owner":
            raise PreconditionFailure("use ownership transfer to assign the owner role")
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role not in {"owner", "admin"}:
                    raise PreconditionFailure("only group managers can invite members")
                target_user = conn.execute(
                    "SELECT status FROM user_profiles WHERE user_id = ?",
                    (str(target_user_id),),
                ).fetchone()
                if target_user is None:
                    raise NotFound("user")
                if str(target_user["status"]) != "active":
                    raise PreconditionFailure("only active users can be invited")
                existing = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(target_user_id)),
                ).fetchone()
                if existing is not None:
                    raise PreconditionFailure("user is already a group member")
                conn.execute(
                    "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                    (str(group_id), str(target_user_id), normalized_role, now_text),
                )
                conn.execute(
                    """
                    UPDATE study_group_join_requests
                    SET status = 'approved', reviewed_at = ?, reviewed_by_user_id = ?
                    WHERE group_id = ? AND requester_user_id = ? AND status = 'pending'
                    """,
                    (now_text, str(actor_user_id), str(group_id), str(target_user_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                    (now_text, str(group_id)),
                )
                conn.commit()
            finally:
                conn.close()
        members = self.list_study_group_members(group_id)
        for member in members:
            if member.user_id == str(target_user_id):
                return member
        raise NotFound("study_group_member")

    def update_study_group(
        self,
        group_id: str,
        *,
        name: str,
        description: str | None,
        visibility: str,
        join_policy: str,
    ) -> StudyGroup:
        normalized_name = _normalize_group_name(name)
        normalized_description = _normalize_group_description(description)
        normalized_visibility = _normalize_group_visibility(visibility)
        normalized_join_policy = _normalize_group_join_policy(join_policy)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    UPDATE study_groups
                    SET name = ?, description = ?, visibility = ?, join_policy = ?, updated_at = ?
                    WHERE group_id = ?
                    RETURNING group_id
                    """,
                    (
                        normalized_name,
                        normalized_description,
                        normalized_visibility,
                        normalized_join_policy,
                        now_text,
                        str(group_id),
                    ),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group")
                conn.commit()
            finally:
                conn.close()
        return self.get_study_group(group_id, viewer_user_id=None)

    def update_study_group_avatar(self, group_id: str, *, avatar_key: str | None) -> StudyGroup:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "UPDATE study_groups SET avatar_key = ?, updated_at = ? WHERE group_id = ? RETURNING group_id",
                    (_normalize_avatar_key(avatar_key), now_text, str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group")
                conn.commit()
            finally:
                conn.close()
        return self.get_study_group(group_id, viewer_user_id=None)

    def set_study_group_status(self, group_id: str, *, status: str) -> StudyGroup:
        normalized_status = _normalize_group_status(status)
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "UPDATE study_groups SET status = ?, updated_at = ? WHERE group_id = ? RETURNING group_id",
                    (normalized_status, now_text, str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group")
                conn.commit()
            finally:
                conn.close()
        return self.get_study_group(group_id, viewer_user_id=None)

    def join_study_group(self, group_id: str, *, user_id: str) -> StudyGroup:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=user_id)
                if group.member_role is not None:
                    return group
                if group.status != "active":
                    raise PreconditionFailure("group is not open for joining")
                if group.join_policy != "free":
                    raise PreconditionFailure("this group requires approval or invitation")
                conn.execute(
                    "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                    (str(group_id), str(user_id), now_text),
                )
                conn.commit()
                return self._get_study_group(conn, group_id, viewer_user_id=user_id)
            finally:
                conn.close()

    def leave_study_group(self, group_id: str, *, user_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_member")
                if str(row["role"]) == "owner":
                    raise PreconditionFailure("group owner cannot leave before transferring ownership")
                conn.execute(
                    "DELETE FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(user_id)),
                )
                conn.commit()
            finally:
                conn.close()

    def list_study_group_members(self, group_id: str) -> tuple[StudyGroupMember, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    m.user_id,
                    p.public_uid,
                    p.nickname,
                    u.email,
                    p.avatar_key,
                    m.role,
                    m.joined_at
                FROM study_group_members m
                JOIN users u ON u.user_id = m.user_id
                JOIN user_profiles p ON p.user_id = m.user_id
                WHERE m.group_id = ?
                ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, m.joined_at ASC
                """,
                (str(group_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_group_member(row) for row in rows)

    def list_admin_user_study_groups(self, user_id: str, *, limit: int = 100) -> tuple[AdminUserStudyGroup, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    g.group_id,
                    g.name,
                    g.description,
                    g.visibility,
                    g.join_policy,
                    g.status,
                    g.owner_user_id,
                    owner_profile.public_uid AS owner_public_uid,
                    owner_profile.nickname AS owner_nickname,
                    g.avatar_key,
                    g.created_at,
                    g.updated_at,
                    COALESCE(member_counts.member_count, 0) AS member_count,
                    m.role AS member_role,
                    m.joined_at
                FROM study_group_members m
                JOIN study_groups g ON g.group_id = m.group_id
                JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
                LEFT JOIN (
                    SELECT group_id, COUNT(*) AS member_count
                    FROM study_group_members
                    GROUP BY group_id
                ) member_counts ON member_counts.group_id = g.group_id
                WHERE m.user_id = ?
                ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, m.joined_at ASC, g.group_id ASC
                LIMIT ?
                """,
                (str(user_id), _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_admin_user_group(row) for row in rows)

    def create_study_group_join_request(self, group_id: str, *, requester_user_id: str, message: str | None) -> StudyGroupJoinRequest:
        normalized_message = _normalize_join_request_message(message)
        now_text = _utc_now().isoformat()
        request_id = f"joinreq_{uuid.uuid4().hex}"
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=requester_user_id)
                if group.member_role is not None:
                    raise PreconditionFailure("you are already a group member")
                if group.status != "active":
                    raise PreconditionFailure("group is not open for join requests")
                if group.join_policy != "approval":
                    raise PreconditionFailure("this group does not accept join requests")
                if group.visibility != "public":
                    raise PreconditionFailure("this group is not discoverable")
                existing = conn.execute(
                    """
                    SELECT 1
                    FROM study_group_join_requests
                    WHERE group_id = ? AND requester_user_id = ? AND status = 'pending'
                    LIMIT 1
                    """,
                    (str(group_id), str(requester_user_id)),
                ).fetchone()
                if existing is not None:
                    raise PreconditionFailure("join request already pending")
                conn.execute(
                    """
                    INSERT INTO study_group_join_requests (
                        request_id, group_id, requester_user_id, message, status, created_at, reviewed_at, reviewed_by_user_id
                    )
                    VALUES (?, ?, ?, ?, 'pending', ?, NULL, NULL)
                    """,
                    (request_id, str(group_id), str(requester_user_id), normalized_message, now_text),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                    (now_text, str(group_id)),
                )
                conn.commit()
            finally:
                conn.close()
        return self.list_study_group_join_requests(group_id, status="pending", limit=200)[0]

    def list_study_group_join_requests(
        self,
        group_id: str,
        *,
        status: str | None = "pending",
        limit: int = 100,
    ) -> tuple[StudyGroupJoinRequest, ...]:
        clauses = ["r.group_id = ?"]
        params: list[Any] = [str(group_id)]
        if status and str(status).strip():
            clauses.append("r.status = ?")
            params.append(_normalize_join_request_status(status))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    r.request_id,
                    r.group_id,
                    r.requester_user_id,
                    p.public_uid AS requester_public_uid,
                    p.nickname AS requester_nickname,
                    p.avatar_key AS requester_avatar_key,
                    r.message,
                    r.status,
                    r.created_at,
                    r.reviewed_at,
                    r.reviewed_by_user_id
                FROM study_group_join_requests r
                JOIN user_profiles p ON p.user_id = r.requester_user_id
                WHERE {' AND '.join(clauses)}
                ORDER BY r.created_at DESC, r.request_id DESC
                LIMIT ?
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_join_request(row) for row in rows)

    def review_study_group_join_request(
        self,
        group_id: str,
        *,
        request_id: str,
        actor_user_id: str,
        status: str,
    ) -> StudyGroupJoinRequest:
        normalized_status = _normalize_join_request_status(status)
        if normalized_status not in {"approved", "rejected"}:
            raise PreconditionFailure("join request review status must be approved or rejected")
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role not in {"owner", "admin"}:
                    raise PreconditionFailure("only group managers can review join requests")
                row = conn.execute(
                    """
                    SELECT request_id, requester_user_id, status
                    FROM study_group_join_requests
                    WHERE request_id = ? AND group_id = ?
                    """,
                    (str(request_id), str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_join_request")
                if str(row["status"]) != "pending":
                    raise PreconditionFailure("join request has already been reviewed")
                if normalized_status == "approved":
                    existing_member = conn.execute(
                        "SELECT 1 FROM study_group_members WHERE group_id = ? AND user_id = ? LIMIT 1",
                        (str(group_id), str(row["requester_user_id"])),
                    ).fetchone()
                    if existing_member is None:
                        conn.execute(
                            "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                            (str(group_id), str(row["requester_user_id"]), now_text),
                        )
                conn.execute(
                    """
                    UPDATE study_group_join_requests
                    SET status = ?, reviewed_at = ?, reviewed_by_user_id = ?
                    WHERE request_id = ? AND group_id = ?
                    """,
                    (normalized_status, now_text, str(actor_user_id), str(request_id), str(group_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                    (now_text, str(group_id)),
                )
                conn.commit()
            finally:
                conn.close()
        requests = self.list_study_group_join_requests(group_id, status=None, limit=200)
        for item in requests:
            if item.request_id == str(request_id):
                return item
        raise NotFound("study_group_join_request")

    def list_study_group_posts(self, group_id: str, *, limit: int = 100) -> tuple[StudyGroupPost, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    p.post_id,
                    p.group_id,
                    p.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    p.kind,
                    p.content,
                    p.created_at,
                    p.updated_at
                FROM study_group_posts p
                JOIN user_profiles profile ON profile.user_id = p.author_user_id
                WHERE p.group_id = ?
                ORDER BY p.created_at DESC, p.post_id DESC
                LIMIT ?
                """,
                (str(group_id), _normalize_limit(limit)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_group_post(row) for row in rows)

    def create_study_group_post(self, group_id: str, *, author_user_id: str, kind: str, content: str) -> StudyGroupPost:
        normalized_kind = _normalize_group_post_kind(kind)
        normalized_content = _normalize_group_post_content(content)
        now_text = _utc_now().isoformat()
        post_id = f"post_{uuid.uuid4().hex}"
        with self._lock:
            conn = self._connect()
            try:
                membership = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(author_user_id)),
                ).fetchone()
                if membership is None:
                    raise PreconditionFailure("only group members can post")
                conn.execute(
                    """
                    INSERT INTO study_group_posts (post_id, group_id, author_user_id, kind, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (post_id, str(group_id), str(author_user_id), normalized_kind, normalized_content, now_text, now_text),
                )
                conn.commit()
            finally:
                conn.close()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                    p.post_id,
                    p.group_id,
                    p.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    p.kind,
                    p.content,
                    p.created_at,
                    p.updated_at
                FROM study_group_posts p
                JOIN user_profiles profile ON profile.user_id = p.author_user_id
                WHERE p.post_id = ?
                """,
                (post_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("study_group_post")
        return self._row_to_group_post(row)

    def delete_study_group_post(self, group_id: str, post_id: str, *, actor_user_id: str) -> StudyGroupPost:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                row = conn.execute(
                    """
                    SELECT
                        p.post_id,
                        p.group_id,
                        p.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        p.kind,
                        p.content,
                        p.created_at,
                        p.updated_at
                    FROM study_group_posts p
                    JOIN user_profiles profile ON profile.user_id = p.author_user_id
                    WHERE p.post_id = ? AND p.group_id = ?
                    """,
                    (str(post_id), str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post")
                deleted = self._row_to_group_post(row)
                if not actor_is_admin and group.member_role not in {"owner", "admin"} and str(actor_user_id) != deleted.author_user_id:
                    raise PreconditionFailure("only the author or group managers can delete this post")
                conn.execute(
                    "DELETE FROM study_group_posts WHERE post_id = ? AND group_id = ?",
                    (str(post_id), str(group_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                    (now_text, str(group_id)),
                )
                conn.commit()
                return deleted
            finally:
                conn.close()

    def list_study_group_post_comments(self, group_id: str, *, limit: int = 200) -> tuple[StudyGroupPostComment, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    c.comment_id,
                    c.group_id,
                    c.post_id,
                    c.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    c.content,
                    c.created_at,
                    c.updated_at
                FROM study_group_post_comments c
                JOIN study_group_posts p ON p.post_id = c.post_id AND p.group_id = c.group_id
                JOIN user_profiles profile ON profile.user_id = c.author_user_id
                WHERE c.group_id = ?
                ORDER BY c.created_at ASC, c.comment_id ASC
                LIMIT ?
                """,
                (str(group_id), _normalize_limit(limit, default=200, maximum=500)),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_group_post_comment(row) for row in rows)

    def create_study_group_post_comment(
        self,
        group_id: str,
        post_id: str,
        *,
        author_user_id: str,
        content: str,
    ) -> StudyGroupPostComment:
        normalized_content = _normalize_group_post_comment_content(content)
        now_text = _utc_now().isoformat()
        comment_id = f"comment_{uuid.uuid4().hex}"
        with self._lock:
            conn = self._connect()
            try:
                membership = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = ? AND user_id = ?",
                    (str(group_id), str(author_user_id)),
                ).fetchone()
                if membership is None:
                    raise PreconditionFailure("only group members can comment")
                post_row = conn.execute(
                    "SELECT 1 FROM study_group_posts WHERE post_id = ? AND group_id = ?",
                    (str(post_id), str(group_id)),
                ).fetchone()
                if post_row is None:
                    raise NotFound("study_group_post")
                conn.execute(
                    """
                    INSERT INTO study_group_post_comments (
                        comment_id, group_id, post_id, author_user_id, content, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (comment_id, str(group_id), str(post_id), str(author_user_id), normalized_content, now_text, now_text),
                )
                conn.commit()
            finally:
                conn.close()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                    c.comment_id,
                    c.group_id,
                    c.post_id,
                    c.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    c.content,
                    c.created_at,
                    c.updated_at
                FROM study_group_post_comments c
                JOIN user_profiles profile ON profile.user_id = c.author_user_id
                WHERE c.comment_id = ?
                """,
                (comment_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFound("study_group_post_comment")
        return self._row_to_group_post_comment(row)

    def delete_study_group_post_comment(self, group_id: str, comment_id: str, *, actor_user_id: str) -> StudyGroupPostComment:
        now_text = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                row = conn.execute(
                    """
                    SELECT
                        c.comment_id,
                        c.group_id,
                        c.post_id,
                        c.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        c.content,
                        c.created_at,
                        c.updated_at
                    FROM study_group_post_comments c
                    JOIN user_profiles profile ON profile.user_id = c.author_user_id
                    WHERE c.comment_id = ? AND c.group_id = ?
                    """,
                    (str(comment_id), str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post_comment")
                deleted = self._row_to_group_post_comment(row)
                if not actor_is_admin and group.member_role not in {"owner", "admin"} and str(actor_user_id) != deleted.author_user_id:
                    raise PreconditionFailure("only the author or group managers can delete this comment")
                conn.execute(
                    "DELETE FROM study_group_post_comments WHERE comment_id = ? AND group_id = ?",
                    (str(comment_id), str(group_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = ? WHERE group_id = ?",
                    (now_text, str(group_id)),
                )
                conn.commit()
                return deleted
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
            study_groups = [
                {
                    "groupId": str(row["group_id"]),
                    "name": str(row["name"]),
                    "description": str(row["description"]),
                    "visibility": str(row["visibility"]),
                    "joinPolicy": str(row["join_policy"]),
                    "status": str(row["status"]),
                    "ownerUserId": str(row["owner_user_id"]),
                    "avatarKey": None if row["avatar_key"] is None else str(row["avatar_key"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT group_id, name, description, visibility, join_policy, status, owner_user_id, avatar_key, created_at, updated_at
                    FROM study_groups
                    ORDER BY created_at ASC, group_id ASC
                    """
                ).fetchall()
            ]
            study_group_members = [
                {
                    "groupId": str(row["group_id"]),
                    "userId": str(row["user_id"]),
                    "role": str(row["role"]),
                    "joinedAt": str(row["joined_at"]),
                }
                for row in conn.execute(
                    "SELECT group_id, user_id, role, joined_at FROM study_group_members ORDER BY group_id ASC, user_id ASC"
                ).fetchall()
            ]
            study_group_posts = [
                {
                    "postId": str(row["post_id"]),
                    "groupId": str(row["group_id"]),
                    "authorUserId": str(row["author_user_id"]),
                    "kind": str(row["kind"]),
                    "content": str(row["content"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    "SELECT post_id, group_id, author_user_id, kind, content, created_at, updated_at FROM study_group_posts ORDER BY created_at ASC, post_id ASC"
                ).fetchall()
            ]
            study_group_post_comments = [
                {
                    "commentId": str(row["comment_id"]),
                    "groupId": str(row["group_id"]),
                    "postId": str(row["post_id"]),
                    "authorUserId": str(row["author_user_id"]),
                    "content": str(row["content"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT comment_id, group_id, post_id, author_user_id, content, created_at, updated_at
                    FROM study_group_post_comments
                    ORDER BY created_at ASC, comment_id ASC
                    """
                ).fetchall()
            ]
            study_group_join_requests = [
                {
                    "requestId": str(row["request_id"]),
                    "groupId": str(row["group_id"]),
                    "requesterUserId": str(row["requester_user_id"]),
                    "message": str(row["message"]),
                    "status": str(row["status"]),
                    "createdAt": str(row["created_at"]),
                    "reviewedAt": None if row["reviewed_at"] is None else str(row["reviewed_at"]),
                    "reviewedByUserId": None if row["reviewed_by_user_id"] is None else str(row["reviewed_by_user_id"]),
                }
                for row in conn.execute(
                    """
                    SELECT request_id, group_id, requester_user_id, message, status, created_at, reviewed_at, reviewed_by_user_id
                    FROM study_group_join_requests
                    ORDER BY created_at ASC, request_id ASC
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
                roles=roles,
                study_groups=study_groups,
                study_group_members=study_group_members,
                study_group_posts=study_group_posts,
                study_group_post_comments=study_group_post_comments,
                study_group_join_requests=study_group_join_requests,
                admin_action_logs=admin_action_logs,
            )
        finally:
            conn.close()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        profiles = list(snapshot.get("userProfiles", []))
        roles = list(snapshot.get("userGlobalRoles", []))
        study_groups = list(snapshot.get("studyGroups", []))
        study_group_members = list(snapshot.get("studyGroupMembers", []))
        study_group_posts = list(snapshot.get("studyGroupPosts", []))
        study_group_post_comments = list(snapshot.get("studyGroupPostComments", []))
        study_group_join_requests = list(snapshot.get("studyGroupJoinRequests", []))
        admin_action_logs = list(snapshot.get("adminActionLogs", []))
        with self._lock:
            conn = self._connect()
            try:
                if replace:
                    conn.execute("DELETE FROM admin_action_logs")
                    conn.execute("DELETE FROM study_group_post_comments")
                    conn.execute("DELETE FROM study_group_join_requests")
                    conn.execute("DELETE FROM study_group_posts")
                    conn.execute("DELETE FROM study_group_members")
                    conn.execute("DELETE FROM study_groups")
                    conn.execute("DELETE FROM user_global_roles")
                    conn.execute("DELETE FROM project_memberships")
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM user_profiles")
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
                    self._bootstrap_super_admin(conn)
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
                for item in study_groups:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_groups (group_id, name, description, visibility, join_policy, status, owner_user_id, avatar_key, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("groupId", "")),
                            str(row.get("name", "")),
                            str(row.get("description", "")),
                            str(row.get("visibility", "public")),
                            str(row.get("joinPolicy", "free")),
                            str(row.get("status", "active")),
                            str(row.get("ownerUserId", "")),
                            _normalize_avatar_key(row.get("avatarKey")),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", row.get("createdAt", ""))),
                        ),
                    )
                for item in study_group_members:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_members (group_id, user_id, role, joined_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            str(row.get("groupId", "")),
                            str(row.get("userId", "")),
                            str(row.get("role", "member")),
                            str(row.get("joinedAt", "")),
                        ),
                    )
                for item in study_group_posts:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_posts (post_id, group_id, author_user_id, kind, content, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("postId", "")),
                            str(row.get("groupId", "")),
                            str(row.get("authorUserId", "")),
                            str(row.get("kind", "discussion")),
                            str(row.get("content", "")),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", row.get("createdAt", ""))),
                        ),
                    )
                for item in study_group_post_comments:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_post_comments (
                            comment_id, group_id, post_id, author_user_id, content, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("commentId", "")),
                            str(row.get("groupId", "")),
                            str(row.get("postId", "")),
                            str(row.get("authorUserId", "")),
                            str(row.get("content", "")),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", row.get("createdAt", ""))),
                        ),
                    )
                for item in study_group_join_requests:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_join_requests (
                            request_id, group_id, requester_user_id, message, status, created_at, reviewed_at, reviewed_by_user_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("requestId", "")),
                            str(row.get("groupId", "")),
                            str(row.get("requesterUserId", "")),
                            str(row.get("message", "")),
                            str(row.get("status", "pending")),
                            str(row.get("createdAt", "")),
                            row.get("reviewedAt"),
                            row.get("reviewedByUserId"),
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

    def create_user(self, email: str, password: str) -> AuthUser:
        normalized_email = _normalize_email(email)
        now_text = _utc_now().isoformat()
        user_id = f"user_{uuid.uuid4().hex}"
        password_hash = self._hash_password(password)
        with self._lock:
            conn = self._pool.acquire()
            try:
                is_first_user = int(conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]) == 0
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash, created_at) VALUES (%s, %s, %s, %s)",
                    (user_id, normalized_email, password_hash, now_text),
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
                if is_first_user:
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
                SELECT {USER_COLUMNS_SQL}, u.password_hash
                FROM users u
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE u.email = %s
                """,
                (normalized_email,),
            ).fetchone()
        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise PreconditionFailure("invalid email or password")
        if str(row["status"]) != "active":
            raise PreconditionFailure("account is not active")
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
                f"""
                SELECT {USER_COLUMNS_SQL}
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                JOIN user_profiles p ON p.user_id = u.user_id
                WHERE s.session_token = %s AND s.expires_at > %s AND p.status = 'active'
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

    def delete_other_sessions_for_user(self, user_id: str, *, except_session_token: str | None = None) -> None:
        with self._lock:
            with self._connect() as conn:
                if except_session_token:
                    conn.execute(
                        "DELETE FROM sessions WHERE user_id = %s AND session_token <> %s",
                        (str(user_id), str(except_session_token)),
                    )
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
            groups = int(conn.execute("SELECT COUNT(*) AS count FROM study_groups").fetchone()["count"])
            active_groups = int(conn.execute("SELECT COUNT(*) AS count FROM study_groups WHERE status = 'active'").fetchone()["count"])
            posts = int(conn.execute("SELECT COUNT(*) AS count FROM study_group_posts").fetchone()["count"])
            comments = int(conn.execute("SELECT COUNT(*) AS count FROM study_group_post_comments").fetchone()["count"])
        return {
            "users": users,
            "activeUsers": active_users,
            "groups": groups,
            "activeGroups": active_groups,
            "posts": posts,
            "comments": comments,
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

    def list_admin_study_group_posts(self, *, search: str | None = None, limit: int = 100) -> tuple[AdminStudyGroupPost, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(g.name ILIKE %s OR p.content ILIKE %s OR profile.nickname ILIKE %s OR profile.public_uid ILIKE %s)")
            params.extend((needle, needle, needle, needle))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.post_id,
                    p.group_id,
                    g.name AS group_name,
                    p.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    p.kind,
                    p.content,
                    p.created_at,
                    p.updated_at,
                    COALESCE(comment_counts.comment_count, 0) AS comment_count
                FROM study_group_posts p
                JOIN study_groups g ON g.group_id = p.group_id
                JOIN user_profiles profile ON profile.user_id = p.author_user_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS comment_count
                    FROM study_group_post_comments
                    GROUP BY post_id
                ) comment_counts ON comment_counts.post_id = p.post_id
                WHERE {' AND '.join(clauses)}
                ORDER BY p.created_at DESC, p.post_id DESC
                LIMIT %s
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_admin_group_post(row) for row in rows)

    def list_admin_study_group_comments(self, *, search: str | None = None, limit: int = 100) -> tuple[AdminStudyGroupComment, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(g.name ILIKE %s OR c.content ILIKE %s OR p.content ILIKE %s OR profile.nickname ILIKE %s OR profile.public_uid ILIKE %s)")
            params.extend((needle, needle, needle, needle, needle))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    c.comment_id,
                    c.group_id,
                    g.name AS group_name,
                    c.post_id,
                    p.kind AS post_kind,
                    SUBSTRING(p.content FROM 1 FOR 120) AS post_excerpt,
                    c.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    c.content,
                    c.created_at,
                    c.updated_at
                FROM study_group_post_comments c
                JOIN study_group_posts p ON p.post_id = c.post_id AND p.group_id = c.group_id
                JOIN study_groups g ON g.group_id = c.group_id
                JOIN user_profiles profile ON profile.user_id = c.author_user_id
                WHERE {' AND '.join(clauses)}
                ORDER BY c.created_at DESC, c.comment_id DESC
                LIMIT %s
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_admin_group_comment(row) for row in rows)

    def delete_admin_study_group_post(self, post_id: str) -> AdminStudyGroupPost:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        p.post_id,
                        p.group_id,
                        g.name AS group_name,
                        p.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        p.kind,
                        p.content,
                        p.created_at,
                        p.updated_at,
                        COALESCE(comment_counts.comment_count, 0) AS comment_count
                    FROM study_group_posts p
                    JOIN study_groups g ON g.group_id = p.group_id
                    JOIN user_profiles profile ON profile.user_id = p.author_user_id
                    LEFT JOIN (
                        SELECT post_id, COUNT(*) AS comment_count
                        FROM study_group_post_comments
                        GROUP BY post_id
                    ) comment_counts ON comment_counts.post_id = p.post_id
                    WHERE p.post_id = %s
                    """,
                    (str(post_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post")
                deleted = self._row_to_admin_group_post(row)
                now_text = _utc_now().isoformat()
                conn.execute("DELETE FROM study_group_posts WHERE post_id = %s", (str(post_id),))
                conn.execute("UPDATE study_groups SET updated_at = %s WHERE group_id = %s", (now_text, deleted.group_id))
                conn.commit()
                return deleted

    def delete_admin_study_group_comment(self, comment_id: str) -> AdminStudyGroupComment:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                        c.comment_id,
                        c.group_id,
                        g.name AS group_name,
                        c.post_id,
                        p.kind AS post_kind,
                        SUBSTRING(p.content FROM 1 FOR 120) AS post_excerpt,
                        c.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        c.content,
                        c.created_at,
                        c.updated_at
                    FROM study_group_post_comments c
                    JOIN study_group_posts p ON p.post_id = c.post_id AND p.group_id = c.group_id
                    JOIN study_groups g ON g.group_id = c.group_id
                    JOIN user_profiles profile ON profile.user_id = c.author_user_id
                    WHERE c.comment_id = %s
                    """,
                    (str(comment_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post_comment")
                deleted = self._row_to_admin_group_comment(row)
                now_text = _utc_now().isoformat()
                conn.execute("DELETE FROM study_group_post_comments WHERE comment_id = %s", (str(comment_id),))
                conn.execute("UPDATE study_groups SET updated_at = %s WHERE group_id = %s", (now_text, deleted.group_id))
                conn.commit()
                return deleted

    def _get_study_group(self, conn, group_id: str, *, viewer_user_id: str | None) -> StudyGroup:
        row = conn.execute(
            """
            SELECT
                g.group_id,
                g.name,
                g.description,
                g.visibility,
                g.join_policy,
                g.status,
                g.owner_user_id,
                owner_profile.public_uid AS owner_public_uid,
                owner_profile.nickname AS owner_nickname,
                g.avatar_key,
                g.created_at,
                g.updated_at,
                COALESCE(member_counts.member_count, 0) AS member_count,
                viewer_member.role AS member_role,
                viewer_request.status AS join_request_status
            FROM study_groups g
            JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
            LEFT JOIN (
                SELECT group_id, COUNT(*) AS member_count
                FROM study_group_members
                GROUP BY group_id
            ) member_counts ON member_counts.group_id = g.group_id
            LEFT JOIN study_group_members viewer_member
                ON viewer_member.group_id = g.group_id AND viewer_member.user_id = %s
            LEFT JOIN study_group_join_requests viewer_request
                ON viewer_request.group_id = g.group_id
               AND viewer_request.requester_user_id = %s
               AND viewer_request.status = 'pending'
            WHERE g.group_id = %s
            """,
            (
                None if viewer_user_id is None else str(viewer_user_id),
                None if viewer_user_id is None else str(viewer_user_id),
                str(group_id),
            ),
        ).fetchone()
        if row is None:
            raise NotFound("study_group")
        return self._row_to_group(row)

    def create_study_group(
        self,
        *,
        owner_user_id: str,
        name: str,
        description: str | None,
        visibility: str,
        join_policy: str,
    ) -> StudyGroup:
        normalized_name = _normalize_group_name(name)
        normalized_description = _normalize_group_description(description)
        normalized_visibility = _normalize_group_visibility(visibility)
        normalized_join_policy = _normalize_group_join_policy(join_policy)
        now_text = _utc_now().isoformat()
        group_id = f"group_{uuid.uuid4().hex}"
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO study_groups (
                        group_id, name, description, visibility, join_policy, status, owner_user_id, avatar_key, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 'active', %s, NULL, %s, %s)
                    """,
                    (
                        group_id,
                        normalized_name,
                        normalized_description,
                        normalized_visibility,
                        normalized_join_policy,
                        str(owner_user_id),
                        now_text,
                        now_text,
                    ),
                )
                conn.execute(
                    "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (%s, %s, 'owner', %s)",
                    (group_id, str(owner_user_id), now_text),
                )
                conn.commit()
        return self.get_study_group(group_id, viewer_user_id=owner_user_id)

    def list_study_groups_for_user(self, user_id: str, *, limit: int = 100) -> tuple[StudyGroup, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    g.group_id,
                    g.name,
                    g.description,
                    g.visibility,
                    g.join_policy,
                    g.status,
                    g.owner_user_id,
                    owner_profile.public_uid AS owner_public_uid,
                    owner_profile.nickname AS owner_nickname,
                    g.avatar_key,
                    g.created_at,
                    g.updated_at,
                    COALESCE(member_counts.member_count, 0) AS member_count,
                    viewer_member.role AS member_role,
                    viewer_request.status AS join_request_status
                FROM study_groups g
                JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
                LEFT JOIN (
                    SELECT group_id, COUNT(*) AS member_count
                    FROM study_group_members
                    GROUP BY group_id
                ) member_counts ON member_counts.group_id = g.group_id
                LEFT JOIN study_group_members viewer_member
                    ON viewer_member.group_id = g.group_id AND viewer_member.user_id = %s
                LEFT JOIN study_group_join_requests viewer_request
                    ON viewer_request.group_id = g.group_id
                   AND viewer_request.requester_user_id = %s
                   AND viewer_request.status = 'pending'
                WHERE g.status <> 'dissolved' AND (g.visibility = 'public' OR viewer_member.user_id IS NOT NULL)
                ORDER BY CASE WHEN viewer_member.user_id IS NOT NULL THEN 0 ELSE 1 END, g.updated_at DESC, g.group_id ASC
                LIMIT %s
                """,
                (str(user_id), str(user_id), _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_group(row) for row in rows)

    def list_all_study_groups(self, *, search: str | None = None, status: str | None = None, limit: int = 100) -> tuple[StudyGroup, ...]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search and str(search).strip():
            needle = f"%{str(search).strip()}%"
            clauses.append("(g.name ILIKE %s OR g.description ILIKE %s)")
            params.extend((needle, needle))
        if status and str(status).strip():
            clauses.append("g.status = %s")
            params.append(_normalize_group_status(status))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    g.group_id,
                    g.name,
                    g.description,
                    g.visibility,
                    g.join_policy,
                    g.status,
                    g.owner_user_id,
                    owner_profile.public_uid AS owner_public_uid,
                    owner_profile.nickname AS owner_nickname,
                    g.avatar_key,
                    g.created_at,
                    g.updated_at,
                    COALESCE(member_counts.member_count, 0) AS member_count,
                    NULL AS member_role,
                    NULL AS join_request_status
                FROM study_groups g
                JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
                LEFT JOIN (
                    SELECT group_id, COUNT(*) AS member_count
                    FROM study_group_members
                    GROUP BY group_id
                ) member_counts ON member_counts.group_id = g.group_id
                WHERE {' AND '.join(clauses)}
                ORDER BY g.updated_at DESC, g.group_id ASC
                LIMIT %s
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_group(row) for row in rows)

    def get_study_group(self, group_id: str, *, viewer_user_id: str | None) -> StudyGroup:
        with self._connect() as conn:
            return self._get_study_group(conn, group_id, viewer_user_id=viewer_user_id)

    def get_study_group_member_role(self, group_id: str, user_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                (str(group_id), str(user_id)),
            ).fetchone()
        return None if row is None else str(row["role"])

    def update_study_group_member_role(
        self,
        group_id: str,
        *,
        target_user_id: str,
        role: str,
        actor_user_id: str,
    ) -> StudyGroupMember:
        normalized_role = _normalize_group_member_role(role)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role != "owner":
                    raise PreconditionFailure("only the group owner can manage member roles")

                target_row = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(target_user_id)),
                ).fetchone()
                if target_row is None:
                    raise NotFound("study_group_member")
                current_role = str(target_row["role"])

                if normalized_role == current_role:
                    conn.commit()
                elif normalized_role == "owner":
                    if not actor_is_admin and str(actor_user_id) != str(group.owner_user_id):
                        raise PreconditionFailure("only the current owner can transfer ownership")
                    conn.execute(
                        "UPDATE study_group_members SET role = 'admin' WHERE group_id = %s AND user_id = %s",
                        (str(group_id), str(group.owner_user_id)),
                    )
                    conn.execute(
                        "UPDATE study_group_members SET role = 'owner' WHERE group_id = %s AND user_id = %s",
                        (str(group_id), str(target_user_id)),
                    )
                    conn.execute(
                        "UPDATE study_groups SET owner_user_id = %s, updated_at = %s WHERE group_id = %s",
                        (str(target_user_id), now_text, str(group_id)),
                    )
                    conn.commit()
                else:
                    if current_role == "owner":
                        raise PreconditionFailure("transfer ownership before changing the current owner role")
                    conn.execute(
                        "UPDATE study_group_members SET role = %s WHERE group_id = %s AND user_id = %s",
                        (normalized_role, str(group_id), str(target_user_id)),
                    )
                    conn.execute(
                        "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                        (now_text, str(group_id)),
                    )
                    conn.commit()
        members = self.list_study_group_members(group_id)
        for member in members:
            if member.user_id == str(target_user_id):
                return member
        raise NotFound("study_group_member")

    def remove_study_group_member(self, group_id: str, *, target_user_id: str, actor_user_id: str) -> None:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role != "owner":
                    raise PreconditionFailure("only the group owner can remove members")

                target_row = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(target_user_id)),
                ).fetchone()
                if target_row is None:
                    raise NotFound("study_group_member")
                if str(target_row["role"]) == "owner":
                    raise PreconditionFailure("group owner cannot be removed")
                conn.execute(
                    "DELETE FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(target_user_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                    (now_text, str(group_id)),
                )
                conn.commit()

    def invite_study_group_member(
        self,
        group_id: str,
        *,
        target_user_id: str,
        role: str,
        actor_user_id: str,
    ) -> StudyGroupMember:
        normalized_role = _normalize_group_member_role(role)
        if normalized_role == "owner":
            raise PreconditionFailure("use ownership transfer to assign the owner role")
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role not in {"owner", "admin"}:
                    raise PreconditionFailure("only group managers can invite members")
                target_user = conn.execute(
                    "SELECT status FROM user_profiles WHERE user_id = %s",
                    (str(target_user_id),),
                ).fetchone()
                if target_user is None:
                    raise NotFound("user")
                if str(target_user["status"]) != "active":
                    raise PreconditionFailure("only active users can be invited")
                existing = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(target_user_id)),
                ).fetchone()
                if existing is not None:
                    raise PreconditionFailure("user is already a group member")
                conn.execute(
                    "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)",
                    (str(group_id), str(target_user_id), normalized_role, now_text),
                )
                conn.execute(
                    """
                    UPDATE study_group_join_requests
                    SET status = 'approved', reviewed_at = %s, reviewed_by_user_id = %s
                    WHERE group_id = %s AND requester_user_id = %s AND status = 'pending'
                    """,
                    (now_text, str(actor_user_id), str(group_id), str(target_user_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                    (now_text, str(group_id)),
                )
                conn.commit()
        members = self.list_study_group_members(group_id)
        for member in members:
            if member.user_id == str(target_user_id):
                return member
        raise NotFound("study_group_member")

    def update_study_group(
        self,
        group_id: str,
        *,
        name: str,
        description: str | None,
        visibility: str,
        join_policy: str,
    ) -> StudyGroup:
        normalized_name = _normalize_group_name(name)
        normalized_description = _normalize_group_description(description)
        normalized_visibility = _normalize_group_visibility(visibility)
        normalized_join_policy = _normalize_group_join_policy(join_policy)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    UPDATE study_groups
                    SET name = %s, description = %s, visibility = %s, join_policy = %s, updated_at = %s
                    WHERE group_id = %s
                    RETURNING group_id
                    """,
                    (
                        normalized_name,
                        normalized_description,
                        normalized_visibility,
                        normalized_join_policy,
                        now_text,
                        str(group_id),
                    ),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group")
                conn.commit()
        return self.get_study_group(group_id, viewer_user_id=None)

    def update_study_group_avatar(self, group_id: str, *, avatar_key: str | None) -> StudyGroup:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "UPDATE study_groups SET avatar_key = %s, updated_at = %s WHERE group_id = %s RETURNING group_id",
                    (_normalize_avatar_key(avatar_key), now_text, str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group")
                conn.commit()
        return self.get_study_group(group_id, viewer_user_id=None)

    def set_study_group_status(self, group_id: str, *, status: str) -> StudyGroup:
        normalized_status = _normalize_group_status(status)
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "UPDATE study_groups SET status = %s, updated_at = %s WHERE group_id = %s RETURNING group_id",
                    (normalized_status, now_text, str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group")
                conn.commit()
        return self.get_study_group(group_id, viewer_user_id=None)

    def join_study_group(self, group_id: str, *, user_id: str) -> StudyGroup:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=user_id)
                if group.member_role is not None:
                    return group
                if group.status != "active":
                    raise PreconditionFailure("group is not open for joining")
                if group.join_policy != "free":
                    raise PreconditionFailure("this group requires approval or invitation")
                conn.execute(
                    "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (%s, %s, 'member', %s)",
                    (str(group_id), str(user_id), now_text),
                )
                conn.commit()
                return self._get_study_group(conn, group_id, viewer_user_id=user_id)

    def leave_study_group(self, group_id: str, *, user_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_member")
                if str(row["role"]) == "owner":
                    raise PreconditionFailure("group owner cannot leave before transferring ownership")
                conn.execute(
                    "DELETE FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(user_id)),
                )
                conn.commit()

    def list_study_group_members(self, group_id: str) -> tuple[StudyGroupMember, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.user_id,
                    p.public_uid,
                    p.nickname,
                    u.email,
                    p.avatar_key,
                    m.role,
                    m.joined_at
                FROM study_group_members m
                JOIN users u ON u.user_id = m.user_id
                JOIN user_profiles p ON p.user_id = m.user_id
                WHERE m.group_id = %s
                ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, m.joined_at ASC
                """,
                (str(group_id),),
            ).fetchall()
        return tuple(self._row_to_group_member(row) for row in rows)

    def list_admin_user_study_groups(self, user_id: str, *, limit: int = 100) -> tuple[AdminUserStudyGroup, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    g.group_id,
                    g.name,
                    g.description,
                    g.visibility,
                    g.join_policy,
                    g.status,
                    g.owner_user_id,
                    owner_profile.public_uid AS owner_public_uid,
                    owner_profile.nickname AS owner_nickname,
                    g.avatar_key,
                    g.created_at,
                    g.updated_at,
                    COALESCE(member_counts.member_count, 0) AS member_count,
                    m.role AS member_role,
                    m.joined_at
                FROM study_group_members m
                JOIN study_groups g ON g.group_id = m.group_id
                JOIN user_profiles owner_profile ON owner_profile.user_id = g.owner_user_id
                LEFT JOIN (
                    SELECT group_id, COUNT(*) AS member_count
                    FROM study_group_members
                    GROUP BY group_id
                ) member_counts ON member_counts.group_id = g.group_id
                WHERE m.user_id = %s
                ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, m.joined_at ASC, g.group_id ASC
                LIMIT %s
                """,
                (str(user_id), _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_admin_user_group(row) for row in rows)

    def create_study_group_join_request(self, group_id: str, *, requester_user_id: str, message: str | None) -> StudyGroupJoinRequest:
        normalized_message = _normalize_join_request_message(message)
        now_text = _utc_now().isoformat()
        request_id = f"joinreq_{uuid.uuid4().hex}"
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=requester_user_id)
                if group.member_role is not None:
                    raise PreconditionFailure("you are already a group member")
                if group.status != "active":
                    raise PreconditionFailure("group is not open for join requests")
                if group.join_policy != "approval":
                    raise PreconditionFailure("this group does not accept join requests")
                if group.visibility != "public":
                    raise PreconditionFailure("this group is not discoverable")
                existing = conn.execute(
                    """
                    SELECT 1
                    FROM study_group_join_requests
                    WHERE group_id = %s AND requester_user_id = %s AND status = 'pending'
                    LIMIT 1
                    """,
                    (str(group_id), str(requester_user_id)),
                ).fetchone()
                if existing is not None:
                    raise PreconditionFailure("join request already pending")
                conn.execute(
                    """
                    INSERT INTO study_group_join_requests (
                        request_id, group_id, requester_user_id, message, status, created_at, reviewed_at, reviewed_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, 'pending', %s, NULL, NULL)
                    """,
                    (request_id, str(group_id), str(requester_user_id), normalized_message, now_text),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                    (now_text, str(group_id)),
                )
                conn.commit()
        requests = self.list_study_group_join_requests(group_id, status="pending", limit=200)
        for item in requests:
            if item.request_id == request_id:
                return item
        raise NotFound("study_group_join_request")

    def list_study_group_join_requests(
        self,
        group_id: str,
        *,
        status: str | None = "pending",
        limit: int = 100,
    ) -> tuple[StudyGroupJoinRequest, ...]:
        clauses = ["r.group_id = %s"]
        params: list[Any] = [str(group_id)]
        if status and str(status).strip():
            clauses.append("r.status = %s")
            params.append(_normalize_join_request_status(status))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    r.request_id,
                    r.group_id,
                    r.requester_user_id,
                    p.public_uid AS requester_public_uid,
                    p.nickname AS requester_nickname,
                    p.avatar_key AS requester_avatar_key,
                    r.message,
                    r.status,
                    r.created_at,
                    r.reviewed_at,
                    r.reviewed_by_user_id
                FROM study_group_join_requests r
                JOIN user_profiles p ON p.user_id = r.requester_user_id
                WHERE {' AND '.join(clauses)}
                ORDER BY r.created_at DESC, r.request_id DESC
                LIMIT %s
                """,
                (*params, _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_join_request(row) for row in rows)

    def review_study_group_join_request(
        self,
        group_id: str,
        *,
        request_id: str,
        actor_user_id: str,
        status: str,
    ) -> StudyGroupJoinRequest:
        normalized_status = _normalize_join_request_status(status)
        if normalized_status not in {"approved", "rejected"}:
            raise PreconditionFailure("join request review status must be approved or rejected")
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                if not actor_is_admin and group.member_role not in {"owner", "admin"}:
                    raise PreconditionFailure("only group managers can review join requests")
                row = conn.execute(
                    """
                    SELECT request_id, requester_user_id, status
                    FROM study_group_join_requests
                    WHERE request_id = %s AND group_id = %s
                    """,
                    (str(request_id), str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_join_request")
                if str(row["status"]) != "pending":
                    raise PreconditionFailure("join request has already been reviewed")
                if normalized_status == "approved":
                    existing_member = conn.execute(
                        "SELECT 1 FROM study_group_members WHERE group_id = %s AND user_id = %s LIMIT 1",
                        (str(group_id), str(row["requester_user_id"])),
                    ).fetchone()
                    if existing_member is None:
                        conn.execute(
                            "INSERT INTO study_group_members (group_id, user_id, role, joined_at) VALUES (%s, %s, 'member', %s)",
                            (str(group_id), str(row["requester_user_id"]), now_text),
                        )
                conn.execute(
                    """
                    UPDATE study_group_join_requests
                    SET status = %s, reviewed_at = %s, reviewed_by_user_id = %s
                    WHERE request_id = %s AND group_id = %s
                    """,
                    (normalized_status, now_text, str(actor_user_id), str(request_id), str(group_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                    (now_text, str(group_id)),
                )
                conn.commit()
        requests = self.list_study_group_join_requests(group_id, status=None, limit=200)
        for item in requests:
            if item.request_id == str(request_id):
                return item
        raise NotFound("study_group_join_request")

    def list_study_group_posts(self, group_id: str, *, limit: int = 100) -> tuple[StudyGroupPost, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.post_id,
                    p.group_id,
                    p.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    p.kind,
                    p.content,
                    p.created_at,
                    p.updated_at
                FROM study_group_posts p
                JOIN user_profiles profile ON profile.user_id = p.author_user_id
                WHERE p.group_id = %s
                ORDER BY p.created_at DESC, p.post_id DESC
                LIMIT %s
                """,
                (str(group_id), _normalize_limit(limit)),
            ).fetchall()
        return tuple(self._row_to_group_post(row) for row in rows)

    def create_study_group_post(self, group_id: str, *, author_user_id: str, kind: str, content: str) -> StudyGroupPost:
        normalized_kind = _normalize_group_post_kind(kind)
        normalized_content = _normalize_group_post_content(content)
        now_text = _utc_now().isoformat()
        post_id = f"post_{uuid.uuid4().hex}"
        with self._lock:
            with self._connect() as conn:
                membership = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(author_user_id)),
                ).fetchone()
                if membership is None:
                    raise PreconditionFailure("only group members can post")
                conn.execute(
                    """
                    INSERT INTO study_group_posts (post_id, group_id, author_user_id, kind, content, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (post_id, str(group_id), str(author_user_id), normalized_kind, normalized_content, now_text, now_text),
                )
                conn.commit()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    p.post_id,
                    p.group_id,
                    p.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    p.kind,
                    p.content,
                    p.created_at,
                    p.updated_at
                FROM study_group_posts p
                JOIN user_profiles profile ON profile.user_id = p.author_user_id
                WHERE p.post_id = %s
                """,
                (post_id,),
            ).fetchone()
        if row is None:
            raise NotFound("study_group_post")
        return self._row_to_group_post(row)

    def delete_study_group_post(self, group_id: str, post_id: str, *, actor_user_id: str) -> StudyGroupPost:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                row = conn.execute(
                    """
                    SELECT
                        p.post_id,
                        p.group_id,
                        p.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        p.kind,
                        p.content,
                        p.created_at,
                        p.updated_at
                    FROM study_group_posts p
                    JOIN user_profiles profile ON profile.user_id = p.author_user_id
                    WHERE p.post_id = %s AND p.group_id = %s
                    """,
                    (str(post_id), str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post")
                deleted = self._row_to_group_post(row)
                if not actor_is_admin and group.member_role not in {"owner", "admin"} and str(actor_user_id) != deleted.author_user_id:
                    raise PreconditionFailure("only the author or group managers can delete this post")
                conn.execute(
                    "DELETE FROM study_group_posts WHERE post_id = %s AND group_id = %s",
                    (str(post_id), str(group_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                    (now_text, str(group_id)),
                )
                conn.commit()
                return deleted

    def list_study_group_post_comments(self, group_id: str, *, limit: int = 200) -> tuple[StudyGroupPostComment, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.comment_id,
                    c.group_id,
                    c.post_id,
                    c.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    c.content,
                    c.created_at,
                    c.updated_at
                FROM study_group_post_comments c
                JOIN study_group_posts p ON p.post_id = c.post_id AND p.group_id = c.group_id
                JOIN user_profiles profile ON profile.user_id = c.author_user_id
                WHERE c.group_id = %s
                ORDER BY c.created_at ASC, c.comment_id ASC
                LIMIT %s
                """,
                (str(group_id), _normalize_limit(limit, default=200, maximum=500)),
            ).fetchall()
        return tuple(self._row_to_group_post_comment(row) for row in rows)

    def create_study_group_post_comment(
        self,
        group_id: str,
        post_id: str,
        *,
        author_user_id: str,
        content: str,
    ) -> StudyGroupPostComment:
        normalized_content = _normalize_group_post_comment_content(content)
        now_text = _utc_now().isoformat()
        comment_id = f"comment_{uuid.uuid4().hex}"
        with self._lock:
            with self._connect() as conn:
                membership = conn.execute(
                    "SELECT role FROM study_group_members WHERE group_id = %s AND user_id = %s",
                    (str(group_id), str(author_user_id)),
                ).fetchone()
                if membership is None:
                    raise PreconditionFailure("only group members can comment")
                post_row = conn.execute(
                    "SELECT 1 FROM study_group_posts WHERE post_id = %s AND group_id = %s",
                    (str(post_id), str(group_id)),
                ).fetchone()
                if post_row is None:
                    raise NotFound("study_group_post")
                conn.execute(
                    """
                    INSERT INTO study_group_post_comments (
                        comment_id, group_id, post_id, author_user_id, content, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (comment_id, str(group_id), str(post_id), str(author_user_id), normalized_content, now_text, now_text),
                )
                conn.commit()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    c.comment_id,
                    c.group_id,
                    c.post_id,
                    c.author_user_id,
                    profile.public_uid AS author_public_uid,
                    profile.nickname AS author_nickname,
                    profile.avatar_key AS author_avatar_key,
                    c.content,
                    c.created_at,
                    c.updated_at
                FROM study_group_post_comments c
                JOIN user_profiles profile ON profile.user_id = c.author_user_id
                WHERE c.comment_id = %s
                """,
                (comment_id,),
            ).fetchone()
        if row is None:
            raise NotFound("study_group_post_comment")
        return self._row_to_group_post_comment(row)

    def delete_study_group_post_comment(self, group_id: str, comment_id: str, *, actor_user_id: str) -> StudyGroupPostComment:
        now_text = _utc_now().isoformat()
        with self._lock:
            with self._connect() as conn:
                group = self._get_study_group(conn, group_id, viewer_user_id=actor_user_id)
                actor_roles = set(self._roles_by_user_id(conn, (str(actor_user_id),)).get(str(actor_user_id), ()))
                actor_is_admin = bool(actor_roles.intersection(GLOBAL_ROLES))
                row = conn.execute(
                    """
                    SELECT
                        c.comment_id,
                        c.group_id,
                        c.post_id,
                        c.author_user_id,
                        profile.public_uid AS author_public_uid,
                        profile.nickname AS author_nickname,
                        profile.avatar_key AS author_avatar_key,
                        c.content,
                        c.created_at,
                        c.updated_at
                    FROM study_group_post_comments c
                    JOIN user_profiles profile ON profile.user_id = c.author_user_id
                    WHERE c.comment_id = %s AND c.group_id = %s
                    """,
                    (str(comment_id), str(group_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("study_group_post_comment")
                deleted = self._row_to_group_post_comment(row)
                if not actor_is_admin and group.member_role not in {"owner", "admin"} and str(actor_user_id) != deleted.author_user_id:
                    raise PreconditionFailure("only the author or group managers can delete this comment")
                conn.execute(
                    "DELETE FROM study_group_post_comments WHERE comment_id = %s AND group_id = %s",
                    (str(comment_id), str(group_id)),
                )
                conn.execute(
                    "UPDATE study_groups SET updated_at = %s WHERE group_id = %s",
                    (now_text, str(group_id)),
                )
                conn.commit()
                return deleted

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
            study_groups = [
                {
                    "groupId": str(row["group_id"]),
                    "name": str(row["name"]),
                    "description": str(row["description"]),
                    "visibility": str(row["visibility"]),
                    "joinPolicy": str(row["join_policy"]),
                    "status": str(row["status"]),
                    "ownerUserId": str(row["owner_user_id"]),
                    "avatarKey": None if row["avatar_key"] is None else str(row["avatar_key"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT group_id, name, description, visibility, join_policy, status, owner_user_id, avatar_key, created_at, updated_at
                    FROM study_groups
                    ORDER BY created_at ASC, group_id ASC
                    """
                ).fetchall()
            ]
            study_group_members = [
                {
                    "groupId": str(row["group_id"]),
                    "userId": str(row["user_id"]),
                    "role": str(row["role"]),
                    "joinedAt": str(row["joined_at"]),
                }
                for row in conn.execute(
                    "SELECT group_id, user_id, role, joined_at FROM study_group_members ORDER BY group_id ASC, user_id ASC"
                ).fetchall()
            ]
            study_group_posts = [
                {
                    "postId": str(row["post_id"]),
                    "groupId": str(row["group_id"]),
                    "authorUserId": str(row["author_user_id"]),
                    "kind": str(row["kind"]),
                    "content": str(row["content"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    "SELECT post_id, group_id, author_user_id, kind, content, created_at, updated_at FROM study_group_posts ORDER BY created_at ASC, post_id ASC"
                ).fetchall()
            ]
            study_group_post_comments = [
                {
                    "commentId": str(row["comment_id"]),
                    "groupId": str(row["group_id"]),
                    "postId": str(row["post_id"]),
                    "authorUserId": str(row["author_user_id"]),
                    "content": str(row["content"]),
                    "createdAt": str(row["created_at"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in conn.execute(
                    """
                    SELECT comment_id, group_id, post_id, author_user_id, content, created_at, updated_at
                    FROM study_group_post_comments
                    ORDER BY created_at ASC, comment_id ASC
                    """
                ).fetchall()
            ]
            study_group_join_requests = [
                {
                    "requestId": str(row["request_id"]),
                    "groupId": str(row["group_id"]),
                    "requesterUserId": str(row["requester_user_id"]),
                    "message": str(row["message"]),
                    "status": str(row["status"]),
                    "createdAt": str(row["created_at"]),
                    "reviewedAt": None if row["reviewed_at"] is None else str(row["reviewed_at"]),
                    "reviewedByUserId": None if row["reviewed_by_user_id"] is None else str(row["reviewed_by_user_id"]),
                }
                for row in conn.execute(
                    """
                    SELECT request_id, group_id, requester_user_id, message, status, created_at, reviewed_at, reviewed_by_user_id
                    FROM study_group_join_requests
                    ORDER BY created_at ASC, request_id ASC
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
            roles=roles,
            study_groups=study_groups,
            study_group_members=study_group_members,
            study_group_posts=study_group_posts,
            study_group_post_comments=study_group_post_comments,
            study_group_join_requests=study_group_join_requests,
            admin_action_logs=admin_action_logs,
        )

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        users = list(snapshot.get("users", []))
        sessions = list(snapshot.get("sessions", []))
        memberships = list(snapshot.get("projectMemberships", []))
        profiles = list(snapshot.get("userProfiles", []))
        roles = list(snapshot.get("userGlobalRoles", []))
        study_groups = list(snapshot.get("studyGroups", []))
        study_group_members = list(snapshot.get("studyGroupMembers", []))
        study_group_posts = list(snapshot.get("studyGroupPosts", []))
        study_group_post_comments = list(snapshot.get("studyGroupPostComments", []))
        study_group_join_requests = list(snapshot.get("studyGroupJoinRequests", []))
        admin_action_logs = list(snapshot.get("adminActionLogs", []))
        with self._lock:
            with self._connect() as conn:
                if replace:
                    conn.execute("DELETE FROM admin_action_logs")
                    conn.execute("DELETE FROM study_group_post_comments")
                    conn.execute("DELETE FROM study_group_join_requests")
                    conn.execute("DELETE FROM study_group_posts")
                    conn.execute("DELETE FROM study_group_members")
                    conn.execute("DELETE FROM study_groups")
                    conn.execute("DELETE FROM user_global_roles")
                    conn.execute("DELETE FROM project_memberships")
                    conn.execute("DELETE FROM sessions")
                    conn.execute("DELETE FROM user_profiles")
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
                    conn.execute(
                        """
                        INSERT INTO user_global_roles (user_id, role, granted_by_user_id, created_at)
                        SELECT user_id, 'super_admin', user_id, created_at
                        FROM users
                        ORDER BY created_at ASC, user_id ASC
                        LIMIT 1
                        ON CONFLICT(user_id, role) DO NOTHING
                        """
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
                for item in study_groups:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_groups (group_id, name, description, visibility, join_policy, status, owner_user_id, avatar_key, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(group_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            visibility = EXCLUDED.visibility,
                            join_policy = EXCLUDED.join_policy,
                            status = EXCLUDED.status,
                            owner_user_id = EXCLUDED.owner_user_id,
                            avatar_key = EXCLUDED.avatar_key,
                            created_at = EXCLUDED.created_at,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(row.get("groupId", "")),
                            str(row.get("name", "")),
                            str(row.get("description", "")),
                            str(row.get("visibility", "public")),
                            str(row.get("joinPolicy", "free")),
                            str(row.get("status", "active")),
                            str(row.get("ownerUserId", "")),
                            _normalize_avatar_key(row.get("avatarKey")),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", row.get("createdAt", ""))),
                        ),
                    )
                for item in study_group_members:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_members (group_id, user_id, role, joined_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(group_id, user_id) DO UPDATE SET
                            role = EXCLUDED.role,
                            joined_at = EXCLUDED.joined_at
                        """,
                        (
                            str(row.get("groupId", "")),
                            str(row.get("userId", "")),
                            str(row.get("role", "member")),
                            str(row.get("joinedAt", "")),
                        ),
                    )
                for item in study_group_posts:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_posts (post_id, group_id, author_user_id, kind, content, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(post_id) DO UPDATE SET
                            group_id = EXCLUDED.group_id,
                            author_user_id = EXCLUDED.author_user_id,
                            kind = EXCLUDED.kind,
                            content = EXCLUDED.content,
                            created_at = EXCLUDED.created_at,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(row.get("postId", "")),
                            str(row.get("groupId", "")),
                            str(row.get("authorUserId", "")),
                            str(row.get("kind", "discussion")),
                            str(row.get("content", "")),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", row.get("createdAt", ""))),
                        ),
                    )
                for item in study_group_post_comments:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_post_comments (comment_id, group_id, post_id, author_user_id, content, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(comment_id) DO UPDATE SET
                            group_id = EXCLUDED.group_id,
                            post_id = EXCLUDED.post_id,
                            author_user_id = EXCLUDED.author_user_id,
                            content = EXCLUDED.content,
                            created_at = EXCLUDED.created_at,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(row.get("commentId", "")),
                            str(row.get("groupId", "")),
                            str(row.get("postId", "")),
                            str(row.get("authorUserId", "")),
                            str(row.get("content", "")),
                            str(row.get("createdAt", "")),
                            str(row.get("updatedAt", row.get("createdAt", ""))),
                        ),
                    )
                for item in study_group_join_requests:
                    row = dict(item)
                    conn.execute(
                        """
                        INSERT INTO study_group_join_requests (
                            request_id, group_id, requester_user_id, message, status, created_at, reviewed_at, reviewed_by_user_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(request_id) DO UPDATE SET
                            group_id = EXCLUDED.group_id,
                            requester_user_id = EXCLUDED.requester_user_id,
                            message = EXCLUDED.message,
                            status = EXCLUDED.status,
                            created_at = EXCLUDED.created_at,
                            reviewed_at = EXCLUDED.reviewed_at,
                            reviewed_by_user_id = EXCLUDED.reviewed_by_user_id
                        """,
                        (
                            str(row.get("requestId", "")),
                            str(row.get("groupId", "")),
                            str(row.get("requesterUserId", "")),
                            str(row.get("message", "")),
                            str(row.get("status", "pending")),
                            str(row.get("createdAt", "")),
                            row.get("reviewedAt"),
                            row.get("reviewedByUserId"),
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
                    conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                    conn.execute("SELECT 1 FROM user_profiles LIMIT 1").fetchone()
                    conn.execute("SELECT 1 FROM sessions LIMIT 1").fetchone()
                    conn.execute("SELECT 1 FROM user_global_roles LIMIT 1").fetchone()
                    health["probe"] = {
                        "ok": True,
                        "targets": ["users", "user_profiles", "sessions", "user_global_roles"],
                    }
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

    def get_user_by_id(self, user_id: str) -> AuthUser:
        return self._impl.get_user_by_id(user_id)

    def get_user_by_public_uid(self, public_uid: str) -> AuthUser:
        return self._impl.get_user_by_public_uid(public_uid)

    def update_user_profile(self, user_id: str, *, nickname: str, bio: str | None) -> AuthUser:
        return self._impl.update_user_profile(user_id, nickname=nickname, bio=bio)

    def update_user_avatar(self, user_id: str, *, avatar_key: str | None) -> AuthUser:
        return self._impl.update_user_avatar(user_id, avatar_key=avatar_key)

    def change_password(self, user_id: str, *, current_password: str, new_password: str) -> None:
        self._impl.change_password(user_id, current_password=current_password, new_password=new_password)

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

    def list_admin_study_group_posts(self, *, search: str | None = None, limit: int = 100) -> tuple[AdminStudyGroupPost, ...]:
        return self._impl.list_admin_study_group_posts(search=search, limit=limit)

    def list_admin_study_group_comments(
        self,
        *,
        search: str | None = None,
        limit: int = 100,
    ) -> tuple[AdminStudyGroupComment, ...]:
        return self._impl.list_admin_study_group_comments(search=search, limit=limit)

    def delete_admin_study_group_post(self, post_id: str) -> AdminStudyGroupPost:
        return self._impl.delete_admin_study_group_post(post_id)

    def delete_admin_study_group_comment(self, comment_id: str) -> AdminStudyGroupComment:
        return self._impl.delete_admin_study_group_comment(comment_id)

    def create_study_group(
        self,
        *,
        owner_user_id: str,
        name: str,
        description: str | None,
        visibility: str,
        join_policy: str,
    ) -> StudyGroup:
        return self._impl.create_study_group(
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            visibility=visibility,
            join_policy=join_policy,
        )

    def list_study_groups_for_user(self, user_id: str, *, limit: int = 100) -> tuple[StudyGroup, ...]:
        return self._impl.list_study_groups_for_user(user_id, limit=limit)

    def list_all_study_groups(self, *, search: str | None = None, status: str | None = None, limit: int = 100) -> tuple[StudyGroup, ...]:
        return self._impl.list_all_study_groups(search=search, status=status, limit=limit)

    def get_study_group(self, group_id: str, *, viewer_user_id: str | None) -> StudyGroup:
        return self._impl.get_study_group(group_id, viewer_user_id=viewer_user_id)

    def get_study_group_member_role(self, group_id: str, user_id: str) -> str | None:
        return self._impl.get_study_group_member_role(group_id, user_id)

    def update_study_group_member_role(
        self,
        group_id: str,
        *,
        target_user_id: str,
        role: str,
        actor_user_id: str,
    ) -> StudyGroupMember:
        return self._impl.update_study_group_member_role(
            group_id,
            target_user_id=target_user_id,
            role=role,
            actor_user_id=actor_user_id,
        )

    def remove_study_group_member(self, group_id: str, *, target_user_id: str, actor_user_id: str) -> None:
        self._impl.remove_study_group_member(group_id, target_user_id=target_user_id, actor_user_id=actor_user_id)

    def invite_study_group_member(
        self,
        group_id: str,
        *,
        target_user_id: str,
        role: str,
        actor_user_id: str,
    ) -> StudyGroupMember:
        return self._impl.invite_study_group_member(
            group_id,
            target_user_id=target_user_id,
            role=role,
            actor_user_id=actor_user_id,
        )

    def update_study_group(
        self,
        group_id: str,
        *,
        name: str,
        description: str | None,
        visibility: str,
        join_policy: str,
    ) -> StudyGroup:
        return self._impl.update_study_group(
            group_id,
            name=name,
            description=description,
            visibility=visibility,
            join_policy=join_policy,
        )

    def update_study_group_avatar(self, group_id: str, *, avatar_key: str | None) -> StudyGroup:
        return self._impl.update_study_group_avatar(group_id, avatar_key=avatar_key)

    def set_study_group_status(self, group_id: str, *, status: str) -> StudyGroup:
        return self._impl.set_study_group_status(group_id, status=status)

    def join_study_group(self, group_id: str, *, user_id: str) -> StudyGroup:
        return self._impl.join_study_group(group_id, user_id=user_id)

    def leave_study_group(self, group_id: str, *, user_id: str) -> None:
        self._impl.leave_study_group(group_id, user_id=user_id)

    def list_study_group_members(self, group_id: str) -> tuple[StudyGroupMember, ...]:
        return self._impl.list_study_group_members(group_id)

    def list_admin_user_study_groups(self, user_id: str, *, limit: int = 100) -> tuple[AdminUserStudyGroup, ...]:
        return self._impl.list_admin_user_study_groups(user_id, limit=limit)

    def create_study_group_join_request(self, group_id: str, *, requester_user_id: str, message: str | None) -> StudyGroupJoinRequest:
        return self._impl.create_study_group_join_request(group_id, requester_user_id=requester_user_id, message=message)

    def list_study_group_join_requests(
        self,
        group_id: str,
        *,
        status: str | None = "pending",
        limit: int = 100,
    ) -> tuple[StudyGroupJoinRequest, ...]:
        return self._impl.list_study_group_join_requests(group_id, status=status, limit=limit)

    def review_study_group_join_request(
        self,
        group_id: str,
        *,
        request_id: str,
        actor_user_id: str,
        status: str,
    ) -> StudyGroupJoinRequest:
        return self._impl.review_study_group_join_request(
            group_id,
            request_id=request_id,
            actor_user_id=actor_user_id,
            status=status,
        )

    def list_study_group_posts(self, group_id: str, *, limit: int = 100) -> tuple[StudyGroupPost, ...]:
        return self._impl.list_study_group_posts(group_id, limit=limit)

    def list_study_group_post_comments(self, group_id: str, *, limit: int = 200) -> tuple[StudyGroupPostComment, ...]:
        return self._impl.list_study_group_post_comments(group_id, limit=limit)

    def create_study_group_post(self, group_id: str, *, author_user_id: str, kind: str, content: str) -> StudyGroupPost:
        return self._impl.create_study_group_post(group_id, author_user_id=author_user_id, kind=kind, content=content)

    def delete_study_group_post(self, group_id: str, post_id: str, *, actor_user_id: str) -> StudyGroupPost:
        return self._impl.delete_study_group_post(group_id, post_id, actor_user_id=actor_user_id)

    def create_study_group_post_comment(
        self,
        group_id: str,
        post_id: str,
        *,
        author_user_id: str,
        content: str,
    ) -> StudyGroupPostComment:
        return self._impl.create_study_group_post_comment(
            group_id,
            post_id,
            author_user_id=author_user_id,
            content=content,
        )

    def delete_study_group_post_comment(self, group_id: str, comment_id: str, *, actor_user_id: str) -> StudyGroupPostComment:
        return self._impl.delete_study_group_post_comment(group_id, comment_id, actor_user_id=actor_user_id)

    def export_snapshot(self) -> dict[str, Any]:
        return self._impl.export_snapshot()

    def import_snapshot(self, snapshot: dict[str, Any], *, replace: bool = True) -> None:
        self._impl.import_snapshot(snapshot, replace=replace)

    def healthcheck(self) -> dict[str, object]:
        return self._impl.healthcheck()
