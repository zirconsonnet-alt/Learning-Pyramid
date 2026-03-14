from __future__ import annotations

from pathlib import Path

import pytest

from backend.system.sql_backend import current_sql_runtime_config


def test_sql_backend_defaults_to_sqlite(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PLM_SQL_BACKEND", raising=False)
    monkeypatch.delenv("PLM_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path))

    cfg = current_sql_runtime_config()

    assert cfg.backend == "sqlite"
    assert cfg.store_db_path == tmp_path / "plm_store.sqlite3"
    assert cfg.auth_db_path == tmp_path / "plm_auth.sqlite3"
    assert cfg.store_postgres_dsn is None
    assert cfg.auth_postgres_dsn is None


def test_sql_backend_reads_postgres_dsn(monkeypatch) -> None:
    monkeypatch.setenv("PLM_SQL_BACKEND", "postgres")
    monkeypatch.setenv("PLM_POSTGRES_DSN", "postgresql://user:pass@localhost:5432/plm")
    monkeypatch.delenv("PLM_STORE_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("PLM_AUTH_POSTGRES_DSN", raising=False)

    cfg = current_sql_runtime_config()

    assert cfg.backend == "postgres"
    assert cfg.store_postgres_dsn == "postgresql://user:pass@localhost:5432/plm"
    assert cfg.auth_postgres_dsn == "postgresql://user:pass@localhost:5432/plm"
    assert cfg.store_db_path is None
    assert cfg.auth_db_path is None


def test_sql_backend_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setenv("PLM_SQL_BACKEND", "mysql")

    with pytest.raises(ValueError):
        current_sql_runtime_config()
