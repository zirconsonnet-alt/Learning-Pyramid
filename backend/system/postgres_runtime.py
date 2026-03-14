from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None
    dict_row = None


def _require_psycopg() -> Any:
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg[binary] is required for the PostgreSQL backend")
    return psycopg


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except Exception as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return max(minimum, value)


@dataclass(frozen=True, slots=True)
class PostgresConnectionConfig:
    dsn: str
    connect_timeout_seconds: int
    acquire_timeout_seconds: int
    min_pool_size: int
    max_pool_size: int
    statement_timeout_ms: int
    lock_timeout_ms: int
    idle_in_transaction_timeout_ms: int
    application_name: str


def current_postgres_connection_config(dsn: str) -> PostgresConnectionConfig:
    min_pool_size = _env_int("PLM_POSTGRES_POOL_MIN_SIZE", 1, minimum=1)
    max_pool_size = _env_int("PLM_POSTGRES_POOL_MAX_SIZE", 8, minimum=min_pool_size)
    return PostgresConnectionConfig(
        dsn=str(dsn).strip(),
        connect_timeout_seconds=_env_int("PLM_POSTGRES_CONNECT_TIMEOUT", 5, minimum=1),
        acquire_timeout_seconds=_env_int("PLM_POSTGRES_POOL_ACQUIRE_TIMEOUT", 10, minimum=1),
        min_pool_size=min_pool_size,
        max_pool_size=max_pool_size,
        statement_timeout_ms=_env_int("PLM_POSTGRES_STATEMENT_TIMEOUT_MS", 30000, minimum=1),
        lock_timeout_ms=_env_int("PLM_POSTGRES_LOCK_TIMEOUT_MS", 5000, minimum=1),
        idle_in_transaction_timeout_ms=_env_int("PLM_POSTGRES_IDLE_IN_TX_TIMEOUT_MS", 30000, minimum=1),
        application_name=(os.getenv("PLM_POSTGRES_APPLICATION_NAME") or "learningpyramid").strip() or "learningpyramid",
    )


class PostgresConnectionPool:
    def __init__(self, cfg: PostgresConnectionConfig) -> None:
        self._cfg = cfg
        self._idle: queue.LifoQueue[Any] = queue.LifoQueue(maxsize=int(cfg.max_pool_size))
        self._lock = threading.Lock()
        self._open_count = 0
        self._warm_pool()

    @property
    def config(self) -> PostgresConnectionConfig:
        return self._cfg

    def _connect_raw(self) -> Any:
        lib = _require_psycopg()
        options = " ".join(
            (
                f"-c statement_timeout={int(self._cfg.statement_timeout_ms)}",
                f"-c lock_timeout={int(self._cfg.lock_timeout_ms)}",
                f"-c idle_in_transaction_session_timeout={int(self._cfg.idle_in_transaction_timeout_ms)}",
            )
        )
        return lib.connect(
            self._cfg.dsn,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=int(self._cfg.connect_timeout_seconds),
            application_name=self._cfg.application_name,
            options=options,
        )

    def _discard(self, connection: Any) -> None:
        try:
            connection.close()
        finally:
            with self._lock:
                self._open_count = max(0, self._open_count - 1)

    def _warm_pool(self) -> None:
        target = int(self._cfg.min_pool_size)
        created: list[Any] = []
        for _ in range(target):
            created.append(self._connect_raw())
        with self._lock:
            self._open_count += len(created)
        for connection in created:
            self._idle.put_nowait(connection)

    def acquire(self) -> Any:
        while True:
            try:
                connection = self._idle.get_nowait()
            except queue.Empty:
                with self._lock:
                    if self._open_count < int(self._cfg.max_pool_size):
                        self._open_count += 1
                        create_new = True
                    else:
                        create_new = False
                if create_new:
                    try:
                        return self._connect_raw()
                    except Exception:
                        with self._lock:
                            self._open_count = max(0, self._open_count - 1)
                        raise
                try:
                    connection = self._idle.get(timeout=float(self._cfg.acquire_timeout_seconds))
                except queue.Empty as exc:
                    raise TimeoutError("Timed out acquiring a PostgreSQL connection from the pool") from exc

            if getattr(connection, "closed", False):
                self._discard(connection)
                continue
            return connection

    def release(self, connection: Any) -> None:
        if connection is None:
            return
        try:
            connection.rollback()
        except Exception:
            pass
        if getattr(connection, "closed", False):
            self._discard(connection)
            return
        try:
            self._idle.put_nowait(connection)
        except queue.Full:
            self._discard(connection)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connection = self.acquire()
        try:
            yield connection
        finally:
            self.release(connection)

    def stats(self) -> dict[str, int]:
        idle = int(self._idle.qsize())
        with self._lock:
            total = int(self._open_count)
        return {
            "totalConnections": total,
            "idleConnections": idle,
            "checkedOutConnections": max(0, total - idle),
            "minPoolSize": int(self._cfg.min_pool_size),
            "maxPoolSize": int(self._cfg.max_pool_size),
        }

    def healthcheck(self) -> dict[str, object]:
        try:
            with self.connection() as connection:
                row = connection.execute("SELECT 1 AS ok").fetchone()
            return {
                "ok": bool(row is not None and int(row["ok"]) == 1),
                "pool": self.stats(),
                "timeouts": {
                    "connectSeconds": int(self._cfg.connect_timeout_seconds),
                    "acquireSeconds": int(self._cfg.acquire_timeout_seconds),
                    "statementMs": int(self._cfg.statement_timeout_ms),
                    "lockMs": int(self._cfg.lock_timeout_ms),
                    "idleInTransactionMs": int(self._cfg.idle_in_transaction_timeout_ms),
                },
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "pool": self.stats(),
            }


_POOL_CACHE: dict[str, PostgresConnectionPool] = {}
_POOL_CACHE_LOCK = threading.Lock()


def get_postgres_pool(dsn: str) -> PostgresConnectionPool:
    key = str(dsn).strip()
    if not key:
        raise ValueError("PostgreSQL DSN must be non-empty")
    with _POOL_CACHE_LOCK:
        pool = _POOL_CACHE.get(key)
        if pool is None:
            pool = PostgresConnectionPool(current_postgres_connection_config(key))
            _POOL_CACHE[key] = pool
        return pool


def redact_postgres_dsn(dsn: str | None) -> str | None:
    text = str(dsn or "").strip()
    if not text:
        return None
    if "@" not in text or "://" not in text:
        return text
    scheme, rest = text.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" not in creds:
        return f"{scheme}://{creds}@{host}"
    username, _ = creds.split(":", 1)
    return f"{scheme}://{username}:***@{host}"
