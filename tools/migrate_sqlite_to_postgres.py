import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.app_paths import resolve_auth_db_path, resolve_store_db_path
from backend.system.postgres_schema import apply_postgres_migrations, export_sqlite_to_postgres_sql, split_sql_statements

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None


def _require_psycopg():
    if psycopg is None:
        raise RuntimeError("psycopg[binary] is required to run the PostgreSQL migration")
    return psycopg


def _default_postgres_dsn() -> str | None:
    for env_name in ("PLM_POSTGRES_DSN", "PLM_STORE_POSTGRES_DSN"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return None


def migrate_sqlite_to_postgres(
    *,
    store_db: Path,
    auth_db: Path | None,
    postgres_dsn: str,
    include_auth: bool = True,
) -> str:
    sql_text = export_sqlite_to_postgres_sql(
        store_db=store_db,
        auth_db=auth_db,
        include_auth=include_auth,
        include_schema=False,
        include_data=True,
    )
    lib = _require_psycopg()
    conn = lib.connect(str(postgres_dsn))
    try:
        apply_postgres_migrations(conn, target="all" if include_auth else "store")
        for statement in split_sql_statements(sql_text):
            conn.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return sql_text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate LearningPyramid SQLite runtime data into PostgreSQL.")
    parser.add_argument("--store-db", type=Path, default=resolve_store_db_path(), help="Path to plm_store.sqlite3")
    parser.add_argument("--auth-db", type=Path, default=resolve_auth_db_path(), help="Path to plm_auth.sqlite3")
    parser.add_argument("--skip-auth", action="store_true", help="Do not migrate the auth database")
    parser.add_argument("--postgres-dsn", default=_default_postgres_dsn(), help="Target PostgreSQL DSN")
    parser.add_argument("--sql-output", type=Path, help="Optional path to also persist the generated data-only SQL that was applied")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.postgres_dsn:
        raise ValueError("--postgres-dsn is required unless PLM_POSTGRES_DSN or PLM_STORE_POSTGRES_DSN is set")

    sql_text = migrate_sqlite_to_postgres(
        store_db=Path(args.store_db),
        auth_db=None if args.skip_auth else Path(args.auth_db),
        postgres_dsn=str(args.postgres_dsn),
        include_auth=not args.skip_auth,
    )

    if args.sql_output is not None:
        output_path = Path(args.sql_output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(sql_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
