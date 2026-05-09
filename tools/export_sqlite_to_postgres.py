import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.app_paths import resolve_auth_db_path, resolve_store_db_path
from backend.system.postgres_schema import export_sqlite_to_postgres_sql


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export LearningPyramid SQLite stores to a PostgreSQL SQL script.")
    parser.add_argument("--store-db", type=Path, default=resolve_store_db_path(), help="Path to plm_store.sqlite3")
    parser.add_argument("--auth-db", type=Path, default=resolve_auth_db_path(), help="Path to plm_auth.sqlite3")
    parser.add_argument("--skip-auth", action="store_true", help="Do not export the auth database")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--schema-only", action="store_true", help="Export schema and migration metadata without row data")
    mode.add_argument("--data-only", action="store_true", help="Export row data only; schema must already exist")
    parser.add_argument("--output", type=Path, help="Write SQL to this file instead of stdout")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_text = export_sqlite_to_postgres_sql(
        store_db=Path(args.store_db),
        auth_db=None if args.skip_auth else Path(args.auth_db),
        include_auth=not args.skip_auth,
        include_schema=not args.data_only,
        include_data=not args.schema_only,
    )

    if args.output is not None:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        return 0

    sys.stdout.write(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
