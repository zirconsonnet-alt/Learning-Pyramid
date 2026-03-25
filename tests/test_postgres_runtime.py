from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import psycopg
import pytest
from backend.models.errors import PreconditionFailure
from backend.repositories.persistence_interfaces import ProjectSnapshotRecord
from backend.system.api import SystemAPI
from backend.system.auth_store import PostgresAuthStore, SQLiteAuthStore
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore
from backend.system.postgres_store import PostgresStore
from tests.postgres_test_support import require_postgres_test_dsn, reset_postgres_database
from tools.migrate_sqlite_to_postgres import migrate_sqlite_to_postgres


def test_postgres_store_persists_projects_across_restart(tmp_path: Path) -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    project_root = tmp_path / "project-postgres"
    api = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    project_id = api.create_project("Postgres Project", project_root=str(project_root))

    reloaded = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    projects = reloaded.list_projects()
    cfg = reloaded.get_project_storage_config(project_id)

    assert any(str(project.project_id) == str(project_id) for project in projects)
    assert cfg.project_root.as_posix() == project_root.as_posix()


def test_postgres_uow_allows_concurrent_open_transactions() -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    store = PostgresStore(dsn)
    writer_started = threading.Event()
    writer_entered = threading.Event()
    writer_finished = threading.Event()

    def _record(project_id: str) -> ProjectSnapshotRecord:
        return ProjectSnapshotRecord(
            project_id=project_id,
            project_title=project_id,
            project_state="ACTIVE",
            created_at_ms=1,
            deleted_at_ms=None,
            snapshot={"project": {"title": project_id, "state": "ACTIVE", "createdAtMs": 1}},
            updated_at="2026-03-09T00:00:00+00:00",
        )

    def _second_writer() -> None:
        writer_started.set()
        with store.begin_unit_of_work(project_id="proj_b") as uow:
            writer_entered.set()
            uow.project_snapshots.upsert(uow.session, _record("proj_b"))
        writer_finished.set()

    with store.begin_unit_of_work(project_id="proj_a") as uow:
        thread = threading.Thread(target=_second_writer, daemon=True)
        thread.start()
        assert writer_started.wait(1.0)
        assert writer_entered.wait(1.0)
        uow.project_snapshots.upsert(uow.session, _record("proj_a"))

    assert writer_finished.wait(1.0)
    thread.join(timeout=1.0)

    projects = store.list_projects_metadata(active_only=False)
    assert {str(project.project_id) for project in projects} == {"proj_a", "proj_b"}


def test_postgres_auth_store_round_trip() -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    auth = PostgresAuthStore(dsn)
    user = auth.create_user("user@example.com", "password-123")
    session_token = auth.create_session(user.user_id)

    resolved = auth.get_user_by_session(session_token)

    assert resolved.user_id == user.user_id
    assert auth.authenticate_user("user@example.com", "password-123").user_id == user.user_id
    with pytest.raises(PreconditionFailure, match="email already exists"):
        auth.create_user("user@example.com", "password-456")


def test_migrate_sqlite_to_postgres_round_trip(tmp_path: Path) -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    store_db = tmp_path / "plm_store.sqlite3"
    auth_db = tmp_path / "plm_auth.sqlite3"
    project_root = tmp_path / "project-migrated"

    sqlite_api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_db)))
    project_id = sqlite_api.create_project("Migrated Project", project_root=str(project_root))

    sqlite_auth = SQLiteAuthStore(auth_db)
    user = sqlite_auth.create_user("migrate@example.com", "password-123")
    sqlite_auth.add_project_owner(str(project_id), user.user_id)

    migrate_sqlite_to_postgres(store_db=store_db, auth_db=auth_db, postgres_dsn=dsn)

    pg_api = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    pg_auth = PostgresAuthStore(dsn)

    assert any(str(project.project_id) == str(project_id) for project in pg_api.list_projects())
    assert pg_api.get_project_storage_config(project_id).project_root.as_posix() == project_root.as_posix()
    assert pg_auth.authenticate_user("migrate@example.com", "password-123").user_id == user.user_id
    assert pg_auth.list_project_ids_for_user(user.user_id) == (str(project_id),)


def test_postgres_runtime_records_schema_migrations_and_uses_hot_indexes() -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    PostgresStore(dsn)
    PostgresAuthStore(dsn)

    conn = psycopg.connect(dsn)
    try:
        rows = conn.execute(
            "SELECT scope, version, name FROM schema_migrations ORDER BY scope ASC, version ASC"
        ).fetchall()
        assert rows == [
            ("auth", 1, "initial_auth_schema"),
            ("auth", 2, "auth_user_profiles"),
            ("auth", 3, "auth_roles_and_study_groups"),
            ("auth", 4, "auth_group_join_requests"),
            ("auth", 5, "auth_group_post_comments"),
            ("auth", 6, "auth_admin_action_logs"),
            ("auth", 7, "auth_identity_uniques"),
            ("store", 1, "initial_store_schema"),
            ("store", 2, "store_hot_indexes"),
            ("store", 3, "entry_registration_seq"),
        ]

        index_rows = conn.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'recall_point_index'
            ORDER BY indexname ASC
            """
        ).fetchall()
        index_names = {str(row[0]) for row in index_rows}
        assert "idx_recall_point_index_instance" in index_names

        auth_index_rows = conn.execute(
            """
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename IN ('users', 'user_profiles')
            ORDER BY tablename ASC, indexname ASC
            """
        ).fetchall()
        auth_indexes = {(str(row[0]), str(row[1])) for row in auth_index_rows}
        assert ("users", "idx_users_email_unique") in auth_indexes
        assert ("user_profiles", "idx_user_profiles_public_uid_unique") in auth_indexes

        conn.execute(
            """
            INSERT INTO project_snapshots (
                project_id, project_title, project_state, created_at_ms, deleted_at_ms, snapshot_json, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("proj_perf", "Performance", "ACTIVE", 1, None, "{}", "2026-03-09T00:00:00+00:00"),
        )
        for index in range(64):
            conn.execute(
                """
                INSERT INTO recall_point_index (
                    project_id,
                    recall_point_id,
                    created_at_ms,
                    anchor_instance_id,
                    anchor_position,
                    question_plain_text,
                    answer_plain_text,
                    insights_count,
                    payload_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    "proj_perf",
                    f"rp_{index}",
                    index,
                    "inst_hot" if index % 2 == 0 else "inst_cold",
                    '{"startMs":0,"endMs":1}',
                    f"q{index}",
                    f"a{index}",
                    0,
                    "{}",
                ),
            )
        conn.commit()

        conn.execute("SET enable_seqscan = off")
        plan_rows = conn.execute(
            """
            EXPLAIN (FORMAT TEXT)
            SELECT recall_point_id
            FROM recall_point_index
            WHERE project_id = %s AND anchor_instance_id = %s
            ORDER BY recall_point_id ASC
            """,
            ("proj_perf", "inst_hot"),
        ).fetchall()
        plan_text = "\n".join(str(row[0]) for row in plan_rows)
        assert "idx_recall_point_index_instance" in plan_text
    finally:
        conn.close()


def test_postgres_public_read_apis_do_not_depend_on_compat_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    project_root = tmp_path / "project-native-reads"
    api = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    project_id = api.create_project("Native Reads", project_root=str(project_root))

    store = PostgresStore(dsn)

    def _fail_connect():
        raise AssertionError("compat _connect should not be used for native read APIs")

    monkeypatch.setattr(store, "_connect", _fail_connect)

    projects = store.list_projects_metadata()
    storage_cfg = store.get_project_storage_config(project_id)
    project_cfg = store.get_project_config(project_id)
    snapshot = store.load_snapshot()
    learning_object_nodes = store.list_learning_object_nodes(project_id)
    learning_task_nodes = store.list_learning_task_nodes(project_id)

    assert [str(item.project_id) for item in projects] == [str(project_id)]
    assert storage_cfg is not None and storage_cfg.project_root.as_posix() == project_root.as_posix()
    assert project_cfg is not None and str(project_cfg.project_id) == str(project_id)
    assert snapshot is not None and str(project_id) in snapshot["projects"]
    assert isinstance(learning_object_nodes, tuple)
    assert isinstance(learning_task_nodes, tuple)


def test_postgres_compaction_does_not_revive_shell_only_externalized_rows(tmp_path: Path) -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    project_root = tmp_path / "project-shell-clean"
    api = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    project_id = api.create_project("Shell Cleanup", project_root=str(project_root))

    store = PostgresStore(dsn)
    snapshot = store.load_snapshot()
    assert snapshot is not None

    full_payload = dict(snapshot["projects"][str(project_id)])
    full_payload["instances"] = {
        **dict(full_payload.get("instances", {})),
        "inst_shell_only": {
            "projectId": str(project_id),
            "instanceId": "inst_shell_only",
            "materialId": "course/shell-only.mp4",
            "presence": "PRESENT",
            "lastSeenAtMs": None,
        },
    }

    conn = psycopg.connect(dsn)
    try:
        conn.execute(
            "UPDATE project_snapshots SET snapshot_json = %s WHERE project_id = %s",
            (json.dumps(full_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), str(project_id)),
        )
        conn.commit()
    finally:
        conn.close()

    reloaded = PostgresStore(dsn)
    loaded_again = reloaded.load_snapshot()
    assert loaded_again is not None
    restored_project = dict(loaded_again["projects"][str(project_id)])
    assert "inst_shell_only" not in dict(restored_project.get("instances", {}))


def test_apply_postgres_migrations_status_and_check_commands() -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    repo_root = Path(__file__).resolve().parent.parent

    pending = subprocess.run(
        [
            sys.executable,
            "tools/apply_postgres_migrations.py",
            "--postgres-dsn",
            dsn,
            "--check",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert pending.returncode == 1
    pending_body = json.loads(pending.stdout)
    assert pending_body["ok"] is False
    assert any(item["scope"] == "store" for item in pending_body["pending"])
    assert pending_body["conflicts"] == []

    applied = subprocess.run(
        [
            sys.executable,
            "tools/apply_postgres_migrations.py",
            "--postgres-dsn",
            dsn,
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr

    status = subprocess.run(
        [
            sys.executable,
            "tools/apply_postgres_migrations.py",
            "--postgres-dsn",
            dsn,
            "--status",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    status_body = json.loads(status.stdout)
    assert status_body["pending"] == []
    assert status_body["conflicts"] == []
    assert status_body["scopes"]["store"]["version"] == 3
    assert status_body["scopes"]["auth"]["version"] == 7


def test_postgres_auth_conflicts_fail_check_and_startup() -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    repo_root = Path(__file__).resolve().parent.parent
    conn = psycopg.connect(dsn)
    try:
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
        conn.execute(
            "INSERT INTO schema_migrations (scope, version, name) VALUES (%s, %s, %s)",
            ("auth", 1, "initial_auth_schema"),
        )
        conn.execute(
            "INSERT INTO schema_migrations (scope, version, name) VALUES (%s, %s, %s)",
            ("auth", 2, "desktop_agent_auth_tables"),
        )
        conn.execute(
            "INSERT INTO schema_migrations (scope, version, name) VALUES (%s, %s, %s)",
            ("auth", 8, "desktop_agent_diagnostic_events"),
        )
        conn.commit()
    finally:
        conn.close()

    checked = subprocess.run(
        [
            sys.executable,
            "tools/apply_postgres_migrations.py",
            "--postgres-dsn",
            dsn,
            "--scope",
            "auth",
            "--check",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 1
    checked_body = json.loads(checked.stdout)
    assert checked_body["pending"] != []
    assert checked_body["conflicts"] == [
        {
            "scope": "auth",
            "version": 2,
            "appliedName": "desktop_agent_auth_tables",
            "expectedName": "auth_user_profiles",
        },
        {
            "scope": "auth",
            "version": 8,
            "appliedName": "desktop_agent_diagnostic_events",
            "expectedName": None,
        },
    ]

    with pytest.raises(RuntimeError, match="Conflicting PostgreSQL schema_migrations rows detected"):
        PostgresAuthStore(dsn)


def test_postgres_auth_healthcheck_detects_missing_required_tables() -> None:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)

    auth = PostgresAuthStore(dsn)
    conn = psycopg.connect(dsn)
    try:
        conn.execute("DROP TABLE user_profiles")
        conn.commit()
    finally:
        conn.close()

    health = auth.healthcheck()
    assert health["ok"] is False
    assert "user_profiles" in str(health.get("error", ""))
    assert health["probe"] == {"ok": False, "error": health["error"]}
