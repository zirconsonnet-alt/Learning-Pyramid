from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend.system.app_paths import resolve_auth_db_path, resolve_legacy_store_path, resolve_store_db_path
from backend.system.persistence_store import SnapshotStore, SQLiteStore
from backend.system.postgres_store import PostgresStore

SqlBackend = Literal["sqlite", "postgres"]


def _normalize_backend(raw: str | None) -> SqlBackend:
    value = str(raw or "sqlite").strip().lower()
    if value in {"", "sqlite"}:
        return "sqlite"
    if value in {"postgres", "postgresql"}:
        return "postgres"
    raise ValueError("PLM_SQL_BACKEND must be either 'sqlite' or 'postgres'")


def _resolve_postgres_dsn(*env_names: str) -> str | None:
    for env_name in env_names:
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return None


@dataclass(frozen=True, slots=True)
class SqlRuntimeConfig:
    backend: SqlBackend
    store_db_path: Path | None
    auth_db_path: Path | None
    store_postgres_dsn: str | None
    auth_postgres_dsn: str | None


def current_sql_runtime_config() -> SqlRuntimeConfig:
    backend = _normalize_backend(os.getenv("PLM_SQL_BACKEND"))
    if backend == "sqlite":
        return SqlRuntimeConfig(
            backend=backend,
            store_db_path=resolve_store_db_path(),
            auth_db_path=resolve_auth_db_path(),
            store_postgres_dsn=None,
            auth_postgres_dsn=None,
        )

    store_dsn = _resolve_postgres_dsn("PLM_STORE_POSTGRES_DSN", "PLM_POSTGRES_DSN")
    auth_dsn = _resolve_postgres_dsn("PLM_AUTH_POSTGRES_DSN", "PLM_POSTGRES_DSN")
    if not store_dsn:
        raise ValueError("PLM_SQL_BACKEND=postgres requires PLM_STORE_POSTGRES_DSN or PLM_POSTGRES_DSN")
    if not auth_dsn:
        raise ValueError("PLM_SQL_BACKEND=postgres requires PLM_AUTH_POSTGRES_DSN or PLM_POSTGRES_DSN")
    return SqlRuntimeConfig(
        backend=backend,
        store_db_path=None,
        auth_db_path=None,
        store_postgres_dsn=store_dsn,
        auth_postgres_dsn=auth_dsn,
    )


def create_persist_store(*, legacy_root: Path | None = None) -> SnapshotStore:
    cfg = current_sql_runtime_config()
    legacy_store_path = resolve_legacy_store_path(legacy_root=legacy_root)
    if cfg.backend == "postgres":
        if cfg.store_postgres_dsn is None:
            raise RuntimeError("PostgreSQL backend selected without a DSN")
        return PostgresStore(cfg.store_postgres_dsn, legacy_json_path=legacy_store_path)
    if cfg.store_db_path is None:
        raise RuntimeError("SQLite backend selected without a store path")
    return SQLiteStore(cfg.store_db_path, legacy_json_path=legacy_store_path)
