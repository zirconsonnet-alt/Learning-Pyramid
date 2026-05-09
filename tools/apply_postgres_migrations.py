import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.postgres_schema import (
    apply_postgres_migrations,
    conflicting_postgres_migrations,
    pending_postgres_migrations,
    postgres_migration_status,
    validate_postgres_migration_plan,
)

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None


def _require_psycopg():
    if psycopg is None:
        raise RuntimeError("psycopg[binary] is required to run PostgreSQL migrations")
    return psycopg


def _default_postgres_dsn() -> str | None:
    for env_name in ("PLM_POSTGRES_DSN", "PLM_STORE_POSTGRES_DSN", "PLM_AUTH_POSTGRES_DSN"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply LearningPyramid PostgreSQL schema migrations.")
    parser.add_argument("--postgres-dsn", default=_default_postgres_dsn(), help="Target PostgreSQL DSN")
    parser.add_argument("--scope", choices=("all", "store", "auth"), default="all", help="Which migration scope to apply")
    parser.add_argument("--status", action="store_true", help="Print current/applied/pending migration status as JSON")
    parser.add_argument("--check", action="store_true", help="Validate the migration plan and fail if there are pending migrations")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    validate_postgres_migration_plan()
    if not args.postgres_dsn:
        raise ValueError("--postgres-dsn is required unless a PLM_*POSTGRES_DSN environment variable is set")

    lib = _require_psycopg()
    conn = lib.connect(str(args.postgres_dsn))
    try:
        if args.status:
            sys.stdout.write(json.dumps(postgres_migration_status(conn, target=str(args.scope)), ensure_ascii=False, indent=2))
            sys.stdout.write("\n")
            return 0
        if args.check:
            pending = pending_postgres_migrations(conn, target=str(args.scope))
            conflicts = conflicting_postgres_migrations(conn, target=str(args.scope))
            if pending or conflicts:
                sys.stdout.write(
                    json.dumps(
                        {
                            "ok": False,
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
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                sys.stdout.write("\n")
                return 1
            sys.stdout.write(json.dumps({"ok": True, "pending": [], "conflicts": []}, ensure_ascii=False, indent=2))
            sys.stdout.write("\n")
            return 0
        apply_postgres_migrations(conn, target=str(args.scope))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
