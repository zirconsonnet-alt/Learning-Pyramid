from __future__ import annotations

import sqlite3
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal

MigrationScope = Literal["store", "auth"]
MigrationTarget = Literal["store", "auth", "all"]

STORE_TABLE_ORDER: tuple[str, ...] = (
    "system_state",
    "global_settings_index",
    "project_snapshots",
    "project_storage_config_index",
    "project_config_index",
    "instance_index",
    "instance_media_binding_index",
    "learning_object_node_index",
    "recall_point_index",
    "learning_task_index",
    "learning_task_node_index",
    "entry_registration_index",
    "range_snapshot_index",
    "review_task_index",
    "convergence_index",
    "review_chain_index",
    "review_task_queue_index",
    "layer_state_index",
    "audit_log_event_index",
    "asr_artifact_index",
    "aggregation_queue_index",
    "aggregation_event_index",
    "material_allowlist_index",
    "media_asset_index",
    "recall_point_review_record_index",
    "snapshot_state",
)

AUTH_TABLE_ORDER: tuple[str, ...] = (
    "users",
    "user_profiles",
    "user_service_configs",
    "user_global_settings",
    "user_cloud_accounts",
    "user_global_roles",
    "sessions",
    "project_memberships",
    "friend_requests",
    "friendships",
    "admin_action_logs",
)

_BOOTSTRAP_SQL_CACHE: dict[str, str] = {}
_BOOTSTRAP_SQL_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class PostgresMigration:
    scope: MigrationScope
    version: int
    name: str
    sql_factory: Callable[[], str]


def _connect_sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _pg_column_type(*, sqlite_type: str) -> str:
    normalized = str(sqlite_type or "").strip().upper()
    if "INT" in normalized:
        return "BIGINT"
    if any(token in normalized for token in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE PRECISION"
    if "BLOB" in normalized:
        return "BYTEA"
    return "TEXT"


def _group_foreign_keys(rows: Iterable[sqlite3.Row]) -> list[tuple[tuple[str, ...], str, tuple[str, ...], str | None, str | None]]:
    grouped: dict[int, dict[str, object]] = {}
    for row in rows:
        key = int(row["id"])
        grouped.setdefault(
            key,
            {
                "table": str(row["table"]),
                "from_cols": [],
                "to_cols": [],
                "on_delete": None if row["on_delete"] is None else str(row["on_delete"]),
                "on_update": None if row["on_update"] is None else str(row["on_update"]),
            },
        )
        grouped[key]["from_cols"].append(str(row["from"]))  # type: ignore[index]
        grouped[key]["to_cols"].append(str(row["to"]))  # type: ignore[index]

    ordered: list[tuple[tuple[str, ...], str, tuple[str, ...], str | None, str | None]] = []
    for key in sorted(grouped.keys()):
        item = grouped[key]
        ordered.append(
            (
                tuple(item["from_cols"]),  # type: ignore[arg-type]
                str(item["table"]),
                tuple(item["to_cols"]),  # type: ignore[arg-type]
                None if item["on_delete"] in (None, "NO ACTION") else str(item["on_delete"]),
                None if item["on_update"] in (None, "NO ACTION") else str(item["on_update"]),
            )
        )
    return ordered


def _render_create_table(conn: sqlite3.Connection, table_name: str) -> str:
    columns = conn.execute(f"PRAGMA table_info({_quote_ident(table_name)})").fetchall()
    if not columns:
        raise ValueError(f"SQLite table not found: {table_name}")
    foreign_keys = conn.execute(f"PRAGMA foreign_key_list({_quote_ident(table_name)})").fetchall()

    lines: list[str] = []
    pk_columns = [str(row["name"]) for row in sorted(columns, key=lambda row: int(row["pk"])) if int(row["pk"]) > 0]
    for column in columns:
        parts = [_quote_ident(str(column["name"])), _pg_column_type(sqlite_type=str(column["type"]))]
        if int(column["notnull"]) != 0:
            parts.append("NOT NULL")
        default_value = column["dflt_value"]
        if default_value is not None:
            parts.append(f"DEFAULT {default_value}")
        lines.append("    " + " ".join(parts))

    if pk_columns:
        pk = ", ".join(_quote_ident(name) for name in pk_columns)
        lines.append(f"    PRIMARY KEY ({pk})")

    for from_cols, ref_table, to_cols, on_delete, on_update in _group_foreign_keys(foreign_keys):
        from_sql = ", ".join(_quote_ident(name) for name in from_cols)
        to_sql = ", ".join(_quote_ident(name) for name in to_cols)
        clause = f"    FOREIGN KEY ({from_sql}) REFERENCES {_quote_ident(ref_table)} ({to_sql})"
        if on_delete:
            clause += f" ON DELETE {on_delete}"
        if on_update:
            clause += f" ON UPDATE {on_update}"
        lines.append(clause)

    body = ",\n".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {_quote_ident(table_name)} (\n{body}\n);"


def _render_indexes(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL
        ORDER BY name ASC
        """,
        (str(table_name),),
    ).fetchall()
    return [str(row["sql"]).strip() + ";" for row in rows]


def _pg_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _render_inserts(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"SELECT * FROM {_quote_ident(table_name)}").fetchall()
    if not rows:
        return []
    column_names = [str(key) for key in rows[0].keys()]
    columns_sql = ", ".join(_quote_ident(name) for name in column_names)
    statements: list[str] = []
    for row in rows:
        values_sql = ", ".join(_pg_literal(row[name]) for name in column_names)
        statements.append(f"INSERT INTO {_quote_ident(table_name)} ({columns_sql}) VALUES ({values_sql});")
    return statements


def _render_schema_section(title: str, conn: sqlite3.Connection, tables: tuple[str, ...]) -> list[str]:
    lines = [f"-- {title}"]
    for table_name in tables:
        existing = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (str(table_name),),
        ).fetchone()
        if existing is None:
            continue
        lines.append("")
        lines.append(_render_create_table(conn, table_name))
        lines.extend(_render_indexes(conn, table_name))
    return lines


def _render_data_section(title: str, conn: sqlite3.Connection, tables: tuple[str, ...]) -> list[str]:
    lines = [f"-- {title}"]
    for table_name in tables:
        existing = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (str(table_name),),
        ).fetchone()
        if existing is None:
            continue
        inserts = _render_inserts(conn, table_name)
        if not inserts:
            continue
        lines.append("")
        lines.append(f"-- Data for {table_name}")
        lines.extend(inserts)
    return lines


def _bootstrap_store_schema_sql() -> str:
    cache_key = "store"
    with _BOOTSTRAP_SQL_LOCK:
        cached = _BOOTSTRAP_SQL_CACHE.get(cache_key)
        if cached is not None:
            return cached

        from backend.system.persistence_store import SQLiteSnapshotStore

        with tempfile.TemporaryDirectory(prefix="learningpyramid-store-schema-") as temp_dir:
            store_db = Path(temp_dir) / "plm_store.sqlite3"
            SQLiteSnapshotStore(store_db)
            conn = _connect_sqlite(store_db)
            try:
                cached = "\n".join(_render_schema_section("Core store", conn, STORE_TABLE_ORDER))
            finally:
                conn.close()

        _BOOTSTRAP_SQL_CACHE[cache_key] = cached
        return cached


def _bootstrap_auth_schema_sql() -> str:
    cache_key = "auth"
    with _BOOTSTRAP_SQL_LOCK:
        cached = _BOOTSTRAP_SQL_CACHE.get(cache_key)
        if cached is not None:
            return cached

        from backend.system.auth_store import SQLiteAuthStore

        with tempfile.TemporaryDirectory(prefix="learningpyramid-auth-schema-") as temp_dir:
            auth_db = Path(temp_dir) / "plm_auth.sqlite3"
            SQLiteAuthStore(auth_db)
            conn = _connect_sqlite(auth_db)
            try:
                cached = "\n".join(_render_schema_section("Auth store", conn, AUTH_TABLE_ORDER))
            finally:
                conn.close()

        _BOOTSTRAP_SQL_CACHE[cache_key] = cached
        return cached


def _store_hot_index_sql() -> str:
    return "\n".join(
        (
            "-- Store performance indexes",
            "CREATE INDEX IF NOT EXISTS idx_learning_object_node_index_parent",
            "ON learning_object_node_index (project_id, parent_id);",
            "CREATE INDEX IF NOT EXISTS idx_learning_task_node_index_parent",
            "ON learning_task_node_index (project_id, parent_id);",
            "CREATE INDEX IF NOT EXISTS idx_recall_point_index_instance",
            "ON recall_point_index (project_id, anchor_instance_id, recall_point_id);",
        )
    )


def _store_entry_registration_seq_sql() -> str:
    return "\n".join(
        (
            "-- Add registration sequence for entry registrations",
            "ALTER TABLE entry_registration_index",
            "ADD COLUMN IF NOT EXISTS registration_seq BIGINT NOT NULL DEFAULT 0;",
            "WITH existing_max AS (",
            "    SELECT",
            "        project_id,",
            "        target_layer_index,",
            "        COALESCE(MAX(NULLIF(registration_seq, 0)), 0) AS max_seq",
            "    FROM entry_registration_index",
            "    GROUP BY project_id, target_layer_index",
            "),",
            "zero_rows AS (",
            "    SELECT",
            "        project_id,",
            "        entry_node,",
            "        target_layer_index,",
            "        ROW_NUMBER() OVER (PARTITION BY project_id, target_layer_index ORDER BY entry_node ASC) AS rn",
            "    FROM entry_registration_index",
            "    WHERE registration_seq = 0",
            ")",
            "UPDATE entry_registration_index eri",
            "SET registration_seq = existing_max.max_seq + zero_rows.rn",
            "FROM zero_rows",
            "JOIN existing_max",
            "  ON existing_max.project_id = zero_rows.project_id",
            " AND existing_max.target_layer_index = zero_rows.target_layer_index",
            "WHERE eri.project_id = zero_rows.project_id",
            "  AND eri.entry_node = zero_rows.entry_node;",
            "CREATE INDEX IF NOT EXISTS idx_entry_registration_index_layer_seq",
            "ON entry_registration_index (project_id, target_layer_index, registration_seq, entry_node);",
        )
    )


def _store_global_settings_sql() -> str:
    return "\n".join(
        (
            "-- Add global settings table for deployment-wide runtime settings",
            "CREATE TABLE IF NOT EXISTS global_settings_index (",
            "    settings_key TEXT PRIMARY KEY,",
            "    payload_json TEXT NOT NULL,",
            "    updated_at TEXT NOT NULL",
            ");",
        )
    )


def _store_instance_media_binding_index_sql() -> str:
    return "\n".join(
        (
            "-- Add instance-level media binding index for mixed media sources",
            "CREATE TABLE IF NOT EXISTS instance_media_binding_index (",
            "    project_id TEXT NOT NULL,",
            "    instance_id TEXT NOT NULL,",
            "    source_kind TEXT NOT NULL,",
            "    playback_kind TEXT NOT NULL DEFAULT 'FILE',",
            "    account_id TEXT,",
            "    remote_file_id TEXT,",
            "    remote_path TEXT,",
            "    mime_type TEXT,",
            "    size_bytes BIGINT,",
            "    duration_ms BIGINT,",
            "    source_payload_json TEXT NOT NULL DEFAULT '{}',",
            "    updated_at_ms BIGINT NOT NULL,",
            "    PRIMARY KEY(project_id, instance_id),",
            "    FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(project_id, instance_id) REFERENCES instance_index(project_id, instance_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_instance_media_binding_index_project",
            "ON instance_media_binding_index (project_id, source_kind, updated_at_ms DESC);",
        )
    )


def _store_learning_task_node_object_mirror_sql() -> str:
    return "\n".join(
        (
            "-- Add legacy learning task node metadata columns",
            "ALTER TABLE learning_task_node_index",
            "ADD COLUMN IF NOT EXISTS node_origin TEXT NOT NULL DEFAULT 'AGGREGATION';",
            "ALTER TABLE learning_task_node_index",
            "ADD COLUMN IF NOT EXISTS bound_learning_object_node_id TEXT NULL;",
            "ALTER TABLE learning_task_node_index",
            "ADD COLUMN IF NOT EXISTS object_mirror_status TEXT NULL;",
        )
    )


def _auth_user_profiles_sql() -> str:
    return "\n".join(
        (
            "-- Add user profile table for hosted user settings",
            "CREATE TABLE IF NOT EXISTS user_profiles (",
            "    user_id TEXT PRIMARY KEY,",
            "    public_uid TEXT NOT NULL UNIQUE,",
            "    nickname TEXT NOT NULL,",
            "    bio TEXT NOT NULL DEFAULT '',",
            "    avatar_key TEXT,",
            "    status TEXT NOT NULL DEFAULT 'active',",
            "    updated_at TEXT NOT NULL,",
            "    password_changed_at TEXT NOT NULL,",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "INSERT INTO user_profiles (user_id, public_uid, nickname, bio, avatar_key, status, updated_at, password_changed_at)",
            "SELECT",
            "    u.user_id,",
            "    CONCAT('LP', UPPER(SUBSTRING(MD5(u.user_id || ':' || u.email) FROM 1 FOR 8))),",
            "    SPLIT_PART(u.email, '@', 1),",
            "    '',",
            "    NULL,",
            "    'active',",
            "    u.created_at,",
            "    u.created_at",
            "FROM users u",
            "ON CONFLICT (user_id) DO NOTHING;",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_public_uid ON user_profiles (public_uid);",
        )
    )


#
# Historical note:
# Auth migrations 3-5 introduced the study-group tables in deployed databases.
# We keep those migration definitions intact so existing schema histories remain valid,
# then remove the deprecated tables in auth migration 11 below.
#
def _auth_roles_and_study_groups_sql() -> str:
    return "\n".join(
        (
            "-- Add global roles and study group tables for hosted collaboration",
            "CREATE TABLE IF NOT EXISTS user_global_roles (",
            "    user_id TEXT NOT NULL,",
            "    role TEXT NOT NULL,",
            "    granted_by_user_id TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    PRIMARY KEY(user_id, role),",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(granted_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE TABLE IF NOT EXISTS study_groups (",
            "    group_id TEXT PRIMARY KEY,",
            "    name TEXT NOT NULL,",
            "    description TEXT NOT NULL DEFAULT '',",
            "    visibility TEXT NOT NULL,",
            "    join_policy TEXT NOT NULL,",
            "    status TEXT NOT NULL,",
            "    owner_user_id TEXT NOT NULL,",
            "    avatar_key TEXT,",
            "    created_at TEXT NOT NULL,",
            "    updated_at TEXT NOT NULL,",
            "    FOREIGN KEY(owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE TABLE IF NOT EXISTS study_group_members (",
            "    group_id TEXT NOT NULL,",
            "    user_id TEXT NOT NULL,",
            "    role TEXT NOT NULL,",
            "    joined_at TEXT NOT NULL,",
            "    PRIMARY KEY(group_id, user_id),",
            "    FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE TABLE IF NOT EXISTS study_group_posts (",
            "    post_id TEXT PRIMARY KEY,",
            "    group_id TEXT NOT NULL,",
            "    author_user_id TEXT NOT NULL,",
            "    kind TEXT NOT NULL,",
            "    content TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    updated_at TEXT NOT NULL,",
            "    FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(author_user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_user_global_roles_role ON user_global_roles (role, created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_study_group_members_user_id ON study_group_members (user_id, joined_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_study_group_posts_group_id ON study_group_posts (group_id, created_at DESC);",
        )
    )


def _auth_group_join_requests_sql() -> str:
    return "\n".join(
        (
            "-- Add study group join request workflow",
            "CREATE TABLE IF NOT EXISTS study_group_join_requests (",
            "    request_id TEXT PRIMARY KEY,",
            "    group_id TEXT NOT NULL,",
            "    requester_user_id TEXT NOT NULL,",
            "    message TEXT NOT NULL DEFAULT '',",
            "    status TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    reviewed_at TEXT,",
            "    reviewed_by_user_id TEXT,",
            "    FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(requester_user_id) REFERENCES users(user_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(reviewed_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_study_group_join_requests_group_status",
            "ON study_group_join_requests (group_id, status, created_at DESC);",
        )
    )


def _auth_group_post_comments_sql() -> str:
    return "\n".join(
        (
            "-- Add study group post comments for group interaction",
            "CREATE TABLE IF NOT EXISTS study_group_post_comments (",
            "    comment_id TEXT PRIMARY KEY,",
            "    group_id TEXT NOT NULL,",
            "    post_id TEXT NOT NULL,",
            "    author_user_id TEXT NOT NULL,",
            "    content TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    updated_at TEXT NOT NULL,",
            "    FOREIGN KEY(group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(post_id) REFERENCES study_group_posts(post_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(author_user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_study_group_post_comments_post_id",
            "ON study_group_post_comments (post_id, created_at ASC);",
        )
    )


def _auth_admin_action_logs_sql() -> str:
    return "\n".join(
        (
            "-- Add admin action logs for hosted moderation traceability",
            "CREATE TABLE IF NOT EXISTS admin_action_logs (",
            "    log_id TEXT PRIMARY KEY,",
            "    actor_user_id TEXT NOT NULL,",
            "    action_type TEXT NOT NULL,",
            "    target_kind TEXT NOT NULL,",
            "    target_id TEXT NOT NULL,",
            "    summary TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    FOREIGN KEY(actor_user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_admin_action_logs_created_at",
            "ON admin_action_logs (created_at DESC);",
        )
    )


def _auth_friendships_sql() -> str:
    return "\n".join(
        (
            "-- Add friend request workflow and friendship graph",
            "CREATE TABLE IF NOT EXISTS friend_requests (",
            "    request_id TEXT PRIMARY KEY,",
            "    requester_user_id TEXT NOT NULL,",
            "    receiver_user_id TEXT NOT NULL,",
            "    message TEXT NOT NULL DEFAULT '',",
            "    status TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    handled_at TEXT,",
            "    handled_by_user_id TEXT,",
            "    FOREIGN KEY(requester_user_id) REFERENCES users(user_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(receiver_user_id) REFERENCES users(user_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(handled_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL",
            ");",
            "CREATE TABLE IF NOT EXISTS friendships (",
            "    user_low_id TEXT NOT NULL,",
            "    user_high_id TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    source_request_id TEXT,",
            "    PRIMARY KEY(user_low_id, user_high_id),",
            "    FOREIGN KEY(user_low_id) REFERENCES users(user_id) ON DELETE CASCADE,",
            "    FOREIGN KEY(user_high_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_friend_requests_receiver_status",
            "ON friend_requests (receiver_user_id, status, created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_friend_requests_requester_status",
            "ON friend_requests (requester_user_id, status, created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_friend_requests_pair_status",
            "ON friend_requests (requester_user_id, receiver_user_id, status, created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_friendships_user_low_created",
            "ON friendships (user_low_id, created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_friendships_user_high_created",
            "ON friendships (user_high_id, created_at DESC);",
        )
    )


def _auth_remove_study_group_tables_sql() -> str:
    return "\n".join(
        (
            "-- Remove deprecated study group tables after the friend-based rollout",
            "DROP TABLE IF EXISTS study_group_post_comments;",
            "DROP TABLE IF EXISTS study_group_join_requests;",
            "DROP TABLE IF EXISTS study_group_posts;",
            "DROP TABLE IF EXISTS study_group_members;",
            "DROP TABLE IF EXISTS study_groups;",
        )
    )


def _auth_identity_uniques_sql() -> str:
    return "\n".join(
        (
            "-- Enforce unique hosted auth identifiers",
            "DROP INDEX IF EXISTS idx_user_profiles_public_uid;",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique",
            "ON users (email);",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_public_uid_unique",
            "ON user_profiles (public_uid);",
        )
    )


def _auth_user_service_configs_sql() -> str:
    return "\n".join(
        (
            "-- Add per-user saved service configuration table",
            "CREATE TABLE IF NOT EXISTS user_service_configs (",
            "    user_id TEXT NOT NULL,",
            "    service_kind TEXT NOT NULL,",
            "    base_url TEXT NOT NULL,",
            "    model_name TEXT NOT NULL DEFAULT '',",
            "    api_key TEXT,",
            "    updated_at TEXT NOT NULL,",
            "    PRIMARY KEY(user_id, service_kind),",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_user_service_configs_kind",
            "ON user_service_configs (service_kind, updated_at DESC);",
        )
    )


def _auth_user_global_settings_sql() -> str:
    return "\n".join(
        (
            "-- Add per-user global client settings table",
            "CREATE TABLE IF NOT EXISTS user_global_settings (",
            "    user_id TEXT PRIMARY KEY,",
            "    payload_json TEXT NOT NULL DEFAULT '{}',",
            "    updated_at TEXT NOT NULL,",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_user_global_settings_updated_at",
            "ON user_global_settings (updated_at DESC);",
        )
    )


def _auth_password_reset_tokens_sql() -> str:
    return "\n".join(
        (
            "-- Add password reset tokens for hosted account recovery",
            "CREATE TABLE IF NOT EXISTS password_reset_tokens (",
            "    token_hash TEXT PRIMARY KEY,",
            "    user_id TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    expires_at TEXT NOT NULL,",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_expires",
            "ON password_reset_tokens (user_id, expires_at DESC);",
        )
    )


def _auth_email_verification_sql() -> str:
    return "\n".join(
        (
            "-- Add persistent email verification state and one-time verification tokens",
            "ALTER TABLE users",
            "ADD COLUMN IF NOT EXISTS email_verified_at TEXT;",
            "UPDATE users",
            "SET email_verified_at = created_at",
            "WHERE email_verified_at IS NULL OR BTRIM(email_verified_at) = '';",
            "CREATE TABLE IF NOT EXISTS email_verification_tokens (",
            "    token_hash TEXT PRIMARY KEY,",
            "    user_id TEXT NOT NULL,",
            "    created_at TEXT NOT NULL,",
            "    expires_at TEXT NOT NULL,",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user_expires",
            "ON email_verification_tokens (user_id, expires_at DESC);",
        )
    )


def _auth_user_service_prompt_mode_sql() -> str:
    return "\n".join(
        (
            "-- Add prompt assembly mode for user service configs",
            "ALTER TABLE user_service_configs",
            "ADD COLUMN IF NOT EXISTS prompt_assembly_mode TEXT;",
            "UPDATE user_service_configs",
            "SET prompt_assembly_mode = 'system'",
            "WHERE prompt_assembly_mode IS NULL OR BTRIM(prompt_assembly_mode) = '';",
            "ALTER TABLE user_service_configs",
            "ALTER COLUMN prompt_assembly_mode SET DEFAULT 'system';",
            "ALTER TABLE user_service_configs",
            "ALTER COLUMN prompt_assembly_mode SET NOT NULL;",
        )
    )


def _auth_user_cloud_accounts_sql() -> str:
    return "\n".join(
        (
            "-- Add cloud account bindings for user-owned media providers",
            "CREATE TABLE IF NOT EXISTS user_cloud_accounts (",
            "    account_id TEXT PRIMARY KEY,",
            "    user_id TEXT NOT NULL,",
            "    provider TEXT NOT NULL,",
            "    provider_user_id TEXT NOT NULL,",
            "    display_name TEXT NOT NULL,",
            "    avatar_url TEXT,",
            "    access_token_ciphertext TEXT NOT NULL,",
            "    refresh_token_ciphertext TEXT NOT NULL,",
            "    expires_at TEXT,",
            "    scope TEXT NOT NULL DEFAULT '',",
            "    meta_json TEXT NOT NULL DEFAULT '{}',",
            "    created_at TEXT NOT NULL,",
            "    updated_at TEXT NOT NULL,",
            "    disabled_at TEXT,",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,",
            "    UNIQUE(user_id, provider, provider_user_id)",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_user_cloud_accounts_user_provider",
            "ON user_cloud_accounts (user_id, provider, updated_at DESC);",
        )
    )


def _auth_user_project_daily_study_stats_sql() -> str:
    return "\n".join(
        (
            "-- Add per-user per-project daily study metric snapshots",
            "CREATE TABLE IF NOT EXISTS user_project_daily_study_stats (",
            "    user_id TEXT NOT NULL,",
            "    project_id TEXT NOT NULL,",
            "    date_key TEXT NOT NULL,",
            "    effective_ms BIGINT NOT NULL DEFAULT 0,",
            "    watch_ms BIGINT NOT NULL DEFAULT 0,",
            "    compose_ms BIGINT NOT NULL DEFAULT 0,",
            "    review_ms BIGINT NOT NULL DEFAULT 0,",
            "    qa_ms BIGINT NOT NULL DEFAULT 0,",
            "    effective_ranges_json TEXT NOT NULL DEFAULT '[]',",
            "    watch_ranges_json TEXT NOT NULL DEFAULT '[]',",
            "    compose_ranges_json TEXT NOT NULL DEFAULT '[]',",
            "    review_ranges_json TEXT NOT NULL DEFAULT '[]',",
            "    qa_ranges_json TEXT NOT NULL DEFAULT '[]',",
            "    updated_at TEXT NOT NULL,",
            "    PRIMARY KEY(user_id, project_id, date_key),",
            "    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_user_project_daily_study_stats_user_project_date",
            "ON user_project_daily_study_stats (user_id, project_id, date_key DESC);",
            "CREATE INDEX IF NOT EXISTS idx_user_project_daily_study_stats_user_date",
            "ON user_project_daily_study_stats (user_id, date_key DESC);",
        )
    )


POSTGRES_MIGRATIONS: tuple[PostgresMigration, ...] = (
    PostgresMigration(scope="store", version=1, name="initial_store_schema", sql_factory=_bootstrap_store_schema_sql),
    PostgresMigration(scope="store", version=2, name="store_hot_indexes", sql_factory=_store_hot_index_sql),
    PostgresMigration(scope="store", version=3, name="entry_registration_seq", sql_factory=_store_entry_registration_seq_sql),
    PostgresMigration(scope="store", version=4, name="global_settings_index", sql_factory=_store_global_settings_sql),
    PostgresMigration(
        scope="store",
        version=5,
        name="instance_media_binding_index",
        sql_factory=_store_instance_media_binding_index_sql,
    ),
    PostgresMigration(
        scope="store",
        version=6,
        name="learning_task_node_object_mirror",
        sql_factory=_store_learning_task_node_object_mirror_sql,
    ),
    PostgresMigration(scope="auth", version=1, name="initial_auth_schema", sql_factory=_bootstrap_auth_schema_sql),
    PostgresMigration(scope="auth", version=2, name="auth_user_profiles", sql_factory=_auth_user_profiles_sql),
    PostgresMigration(scope="auth", version=3, name="auth_roles_and_study_groups", sql_factory=_auth_roles_and_study_groups_sql),
    PostgresMigration(scope="auth", version=4, name="auth_group_join_requests", sql_factory=_auth_group_join_requests_sql),
    PostgresMigration(scope="auth", version=5, name="auth_group_post_comments", sql_factory=_auth_group_post_comments_sql),
    PostgresMigration(scope="auth", version=6, name="auth_admin_action_logs", sql_factory=_auth_admin_action_logs_sql),
    PostgresMigration(scope="auth", version=7, name="auth_identity_uniques", sql_factory=_auth_identity_uniques_sql),
    PostgresMigration(scope="auth", version=8, name="auth_user_service_configs", sql_factory=_auth_user_service_configs_sql),
    PostgresMigration(scope="auth", version=9, name="auth_user_service_prompt_mode", sql_factory=_auth_user_service_prompt_mode_sql),
    PostgresMigration(scope="auth", version=10, name="auth_friendships", sql_factory=_auth_friendships_sql),
    PostgresMigration(scope="auth", version=11, name="auth_remove_study_group_tables", sql_factory=_auth_remove_study_group_tables_sql),
    PostgresMigration(scope="auth", version=12, name="auth_user_cloud_accounts", sql_factory=_auth_user_cloud_accounts_sql),
    PostgresMigration(scope="auth", version=13, name="auth_user_project_daily_study_stats", sql_factory=_auth_user_project_daily_study_stats_sql),
    PostgresMigration(scope="auth", version=14, name="auth_user_global_settings", sql_factory=_auth_user_global_settings_sql),
    PostgresMigration(scope="auth", version=15, name="auth_password_reset_tokens", sql_factory=_auth_password_reset_tokens_sql),
    PostgresMigration(scope="auth", version=16, name="auth_email_verification", sql_factory=_auth_email_verification_sql),
)


def _selected_migrations(target: MigrationTarget) -> tuple[PostgresMigration, ...]:
    if target == "all":
        return POSTGRES_MIGRATIONS
    return tuple(migration for migration in POSTGRES_MIGRATIONS if migration.scope == target)


def validate_postgres_migration_plan() -> None:
    versions_by_scope: dict[str, list[int]] = {}
    seen_pairs: set[tuple[str, int]] = set()
    for migration in POSTGRES_MIGRATIONS:
        key = (migration.scope, int(migration.version))
        if key in seen_pairs:
            raise ValueError(f"Duplicate PostgreSQL migration version detected for {migration.scope}:{migration.version}")
        seen_pairs.add(key)
        versions_by_scope.setdefault(str(migration.scope), []).append(int(migration.version))

    for scope, versions in versions_by_scope.items():
        ordered = sorted(versions)
        expected = list(range(1, len(ordered) + 1))
        if ordered != expected:
            raise ValueError(f"PostgreSQL migrations for scope {scope} must be contiguous starting at 1")


def expected_postgres_migration_status(*, target: MigrationTarget = "all") -> dict[str, object]:
    validate_postgres_migration_plan()
    scopes: dict[str, dict[str, object]] = {}
    for scope in ("store", "auth"):
        migrations = [item for item in _selected_migrations(target) if item.scope == scope]
        if not migrations and target != "all":
            continue
        scopes[scope] = {
            "version": max((int(item.version) for item in migrations), default=0),
            "defined": [{"version": int(item.version), "name": item.name} for item in migrations],
        }
    return {"scopes": scopes}


def split_sql_statements(sql_text: str) -> list[str]:
    content_lines = [line for line in str(sql_text).splitlines() if not line.strip().startswith("--")]
    text = "\n".join(content_lines)
    statements: list[str] = []
    chunk: list[str] = []
    in_single_quote = False
    index = 0
    while index < len(text):
        ch = text[index]
        if ch == "'":
            chunk.append(ch)
            if in_single_quote and index + 1 < len(text) and text[index + 1] == "'":
                chunk.append("'")
                index += 2
                continue
            in_single_quote = not in_single_quote
            index += 1
            continue
        if ch == ";" and not in_single_quote:
            statement = "".join(chunk).strip()
            if statement and statement.upper() not in {"BEGIN", "COMMIT"}:
                statements.append(statement)
            chunk = []
            index += 1
            continue
        chunk.append(ch)
        index += 1

    tail = "".join(chunk).strip()
    if tail and tail.upper() not in {"BEGIN", "COMMIT"}:
        statements.append(tail)
    return statements


def _ensure_schema_migrations_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            scope TEXT NOT NULL,
            version BIGINT NOT NULL,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (scope, version)
        )
        """
    )


def applied_postgres_migrations(conn, *, scope: MigrationScope | None = None) -> tuple[tuple[str, int, str], ...]:
    _ensure_schema_migrations_table(conn)
    if scope is None:
        rows = conn.execute(
            "SELECT scope, version, name FROM schema_migrations ORDER BY scope ASC, version ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT scope, version, name FROM schema_migrations WHERE scope = %s ORDER BY version ASC",
            (str(scope),),
        ).fetchall()
    normalized: list[tuple[str, int, str]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append((str(row["scope"]), int(row["version"]), str(row["name"])))
            continue
        normalized.append((str(row[0]), int(row[1]), str(row[2])))
    return tuple(normalized)


def current_postgres_schema_version(conn, *, scope: MigrationScope) -> int:
    _ensure_schema_migrations_table(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations WHERE scope = %s",
        (str(scope),),
    ).fetchone()
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(row["version"])
    return int(row[0])


def pending_postgres_migrations(conn, *, target: MigrationTarget = "all") -> tuple[tuple[str, int, str], ...]:
    applied = {(scope, version) for scope, version, _ in applied_postgres_migrations(conn)}
    pending: list[tuple[str, int, str]] = []
    for migration in _selected_migrations(target):
        key = (migration.scope, int(migration.version))
        if key not in applied:
            pending.append((migration.scope, int(migration.version), migration.name))
    return tuple(pending)


def conflicting_postgres_migrations(conn, *, target: MigrationTarget = "all") -> tuple[tuple[str, int, str, str | None], ...]:
    expected_by_key = {
        (str(migration.scope), int(migration.version)): migration.name for migration in _selected_migrations(target)
    }
    target_scopes = {scope for scope, _ in expected_by_key.keys()}
    conflicts: list[tuple[str, int, str, str | None]] = []
    for scope, version, applied_name in applied_postgres_migrations(conn):
        if scope not in target_scopes:
            continue
        expected_name = expected_by_key.get((scope, int(version)))
        if expected_name != applied_name:
            conflicts.append((scope, int(version), applied_name, expected_name))
    return tuple(conflicts)


def postgres_migration_status(conn, *, target: MigrationTarget = "all") -> dict[str, object]:
    applied = applied_postgres_migrations(conn)
    expected = expected_postgres_migration_status(target=target)
    pending = pending_postgres_migrations(conn, target=target)
    conflicts = conflicting_postgres_migrations(conn, target=target)
    payload: dict[str, object] = {
        "scopes": {},
        "expected": expected,
        "pending": [{"scope": item[0], "version": item[1], "name": item[2]} for item in pending],
        "conflicts": [
            {
                "scope": item[0],
                "version": item[1],
                "appliedName": item[2],
                "expectedName": item[3],
            }
            for item in conflicts
        ],
    }
    scopes: dict[str, dict[str, object]] = {}
    for scope in ("store", "auth"):
        items = [item for item in applied if item[0] == scope]
        if scope not in dict(expected.get("scopes", {})):
            continue
        scopes[scope] = {
            "version": max((item[1] for item in items), default=0),
            "applied": [{"version": item[1], "name": item[2]} for item in items],
        }
    payload["scopes"] = scopes
    return payload


def apply_postgres_migrations(conn, *, target: MigrationTarget = "all") -> tuple[tuple[str, int, str], ...]:
    _ensure_schema_migrations_table(conn)
    conn.commit()
    conflicts = conflicting_postgres_migrations(conn, target=target)
    if conflicts:
        details = ", ".join(
            f"{scope}:{version} applied={applied_name} expected={expected_name or '<none>'}"
            for scope, version, applied_name, expected_name in conflicts
        )
        raise RuntimeError(f"Conflicting PostgreSQL schema_migrations rows detected: {details}")
    applied = {(scope, version) for scope, version, _ in applied_postgres_migrations(conn)}
    executed: list[tuple[str, int, str]] = []

    for migration in _selected_migrations(target):
        key = (migration.scope, migration.version)
        if key in applied:
            continue
        try:
            for statement in split_sql_statements(migration.sql_factory()):
                conn.execute(statement)
            conn.execute(
                """
                INSERT INTO schema_migrations (scope, version, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (scope, version) DO UPDATE SET name = EXCLUDED.name
                """,
                (migration.scope, int(migration.version), migration.name),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        applied.add(key)
        executed.append((migration.scope, migration.version, migration.name))

    return tuple(executed)


def render_postgres_schema_sql(*, include_store: bool = True, include_auth: bool = True, include_migration_metadata: bool = True) -> str:
    lines = [
        "-- LearningPyramid PostgreSQL runtime schema",
        """
CREATE TABLE IF NOT EXISTS schema_migrations (
    scope TEXT NOT NULL,
    version BIGINT NOT NULL,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (scope, version)
);
""".strip(),
    ]

    selected = []
    if include_store:
        selected.extend(_selected_migrations("store"))
    if include_auth:
        selected.extend(_selected_migrations("auth"))

    for migration in selected:
        lines.append("")
        lines.append(f"-- Migration {migration.scope}:{migration.version} {migration.name}")
        lines.append(migration.sql_factory().strip())
        if include_migration_metadata:
            lines.append(
                "INSERT INTO schema_migrations (scope, version, name) "
                f"VALUES ('{migration.scope}', {int(migration.version)}, '{migration.name}') "
                "ON CONFLICT (scope, version) DO UPDATE SET name = EXCLUDED.name;"
            )

    return "\n".join(lines).strip() + "\n"


def export_sqlite_to_postgres_sql(
    *,
    store_db: Path,
    auth_db: Path | None = None,
    include_auth: bool = True,
    include_schema: bool = True,
    include_data: bool = True,
) -> str:
    if not include_schema and not include_data:
        raise ValueError("At least one of include_schema/include_data must be true")

    sql_lines: list[str] = [
        "-- LearningPyramid SQLite -> PostgreSQL export",
        "-- Runtime-compatible PostgreSQL schema and seed data.",
        "BEGIN;",
        "",
    ]

    if include_schema:
        sql_lines.append(render_postgres_schema_sql(include_store=True, include_auth=include_auth, include_migration_metadata=True).strip())

    if include_data:
        store_path = Path(store_db).expanduser().resolve()
        if not store_path.exists():
            raise FileNotFoundError(f"store db not found: {store_path}")
        store_conn = _connect_sqlite(store_path)
        try:
            if sql_lines[-1] != "":
                sql_lines.append("")
            sql_lines.extend(_render_data_section("Core store data", store_conn, STORE_TABLE_ORDER))
        finally:
            store_conn.close()

        if include_auth and auth_db is not None:
            auth_path = Path(auth_db).expanduser().resolve()
            if auth_path.exists():
                auth_conn = _connect_sqlite(auth_path)
                try:
                    sql_lines.append("")
                    sql_lines.extend(_render_data_section("Auth store data", auth_conn, AUTH_TABLE_ORDER))
                finally:
                    auth_conn.close()

    sql_lines.extend(["", "COMMIT;", ""])
    return "\n".join(sql_lines)
