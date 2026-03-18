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
    "project_snapshots",
    "project_storage_config_index",
    "project_config_index",
    "instance_index",
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
    "sessions",
    "project_memberships",
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


POSTGRES_MIGRATIONS: tuple[PostgresMigration, ...] = (
    PostgresMigration(scope="store", version=1, name="initial_store_schema", sql_factory=_bootstrap_store_schema_sql),
    PostgresMigration(scope="store", version=2, name="store_hot_indexes", sql_factory=_store_hot_index_sql),
    PostgresMigration(scope="auth", version=1, name="initial_auth_schema", sql_factory=_bootstrap_auth_schema_sql),
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


def postgres_migration_status(conn, *, target: MigrationTarget = "all") -> dict[str, object]:
    applied = applied_postgres_migrations(conn)
    expected = expected_postgres_migration_status(target=target)
    pending = pending_postgres_migrations(conn, target=target)
    payload: dict[str, object] = {
        "scopes": {},
        "expected": expected,
        "pending": [{"scope": item[0], "version": item[1], "name": item[2]} for item in pending],
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
