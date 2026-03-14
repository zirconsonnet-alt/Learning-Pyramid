from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore


def test_export_sqlite_to_postgres_script_emits_core_tables(tmp_path: Path) -> None:
    store_db = tmp_path / "plm_store.sqlite3"
    auth_db = tmp_path / "plm_auth.sqlite3"
    output_sql = tmp_path / "export.sql"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_db)))
    project_id = api.create_project("PG Export")

    result = subprocess.run(
        [
            sys.executable,
            "tools/export_sqlite_to_postgres.py",
            "--store-db",
            str(store_db),
            "--auth-db",
            str(auth_db),
            "--output",
            str(output_sql),
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    sql_text = output_sql.read_text(encoding="utf-8")
    assert 'CREATE TABLE IF NOT EXISTS "project_snapshots"' in sql_text
    assert 'CREATE TABLE IF NOT EXISTS "project_config_index"' in sql_text
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in sql_text
    assert "idx_recall_point_index_instance" in sql_text
    assert f"VALUES ('{project_id}'" in sql_text
    assert "::jsonb" not in sql_text
    assert "::timestamptz" not in sql_text
    assert "COMMIT;" in sql_text


def test_export_sqlite_to_postgres_script_supports_data_only(tmp_path: Path) -> None:
    store_db = tmp_path / "plm_store.sqlite3"
    auth_db = tmp_path / "plm_auth.sqlite3"
    output_sql = tmp_path / "export-data.sql"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_db)))
    project_id = api.create_project("PG Export Data Only")

    result = subprocess.run(
        [
            sys.executable,
            "tools/export_sqlite_to_postgres.py",
            "--store-db",
            str(store_db),
            "--auth-db",
            str(auth_db),
            "--data-only",
            "--output",
            str(output_sql),
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    sql_text = output_sql.read_text(encoding="utf-8")
    assert 'CREATE TABLE IF NOT EXISTS "project_snapshots"' not in sql_text
    assert "schema_migrations" not in sql_text
    assert f"VALUES ('{project_id}'" in sql_text
    assert "COMMIT;" in sql_text
