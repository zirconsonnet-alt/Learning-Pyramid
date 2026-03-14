from __future__ import annotations

import os
import time

import pytest

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None


def require_postgres_test_dsn() -> str:
    dsn = os.getenv("PLM_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("set PLM_TEST_POSTGRES_DSN to run PostgreSQL integration tests")
    if psycopg is None:
        pytest.skip("psycopg is required to run PostgreSQL integration tests")
    return dsn


def wait_for_postgres_database(dsn: str, *, timeout_seconds: float = 30.0) -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required to wait for the PostgreSQL test database")
    deadline = time.monotonic() + float(timeout_seconds)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            conn = psycopg.connect(dsn, connect_timeout=2)
            try:
                conn.execute("SELECT 1")
            finally:
                conn.close()
            return
        except Exception as exc:  # pragma: no cover - only exercised during cold starts
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"PostgreSQL test database did not become ready within {timeout_seconds:.0f}s") from last_error


def reset_postgres_database(dsn: str) -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required to reset the PostgreSQL test database")
    wait_for_postgres_database(dsn)
    conn = psycopg.connect(dsn)
    try:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.commit()
    finally:
        conn.close()
