import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.subject_material_recovery import (
    SubjectMaterialRecoveryItem,
    build_subject_material_recovery_plan,
    validate_subject_material_relationship_integrity,
)

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None


def repair_postgres(conn: Any, *, apply: bool, updated_at: str) -> dict[str, object]:
    project_rows = _load_project_rows(conn)
    relationship_rows = _load_relationship_rows(conn)
    issues = validate_subject_material_relationship_integrity(
        project_rows=project_rows,
        relationship_rows=relationship_rows,
    )
    plan = build_subject_material_recovery_plan(
        project_rows=project_rows,
        relationship_rows=relationship_rows,
    )
    if apply:
        _insert_recovery_items(conn, plan, updated_at=str(updated_at))
    return {
        "ok": True,
        "mode": "apply" if apply else "dry-run",
        "plannedCount": len(plan),
        "appliedCount": len(plan) if apply else 0,
        "items": [item.to_json() for item in plan],
        "issues": [issue.to_json() for issue in issues],
    }


def _load_project_rows(conn: Any) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT p.project_id, p.project_title, p.project_state, p.created_at_ms,
               p.subject_id, p.scoped_project_id, c.config_json::jsonb ->> 'projectType' AS project_type
        FROM project_snapshots p
        LEFT JOIN project_config_index c ON c.project_id = p.project_id
        ORDER BY p.project_id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _load_relationship_rows(conn: Any) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT subject_id, material_id, scoped_project_id, internal_project_id
        FROM subject_material_relationship_index
        ORDER BY subject_id ASC, material_id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _insert_recovery_items(conn: Any, plan: list[SubjectMaterialRecoveryItem], *, updated_at: str) -> None:
    if not plan:
        return
    with conn.transaction():
        inserted_collections: set[str] = set()
        for item in plan:
            if item.subject_id not in inserted_collections:
                conn.execute(
                    """
                    INSERT INTO subject_material_collection_index (
                        subject_id,
                        initialized,
                        updated_at
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT(subject_id) DO UPDATE SET
                        initialized = TRUE,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (item.subject_id, True, str(updated_at)),
                )
                inserted_collections.add(item.subject_id)
            conn.execute(
                """
                INSERT INTO subject_material_relationship_index (
                    subject_id,
                    material_id,
                    material_type,
                    title,
                    created_at_ms,
                    scoped_project_id,
                    internal_project_id,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    item.subject_id,
                    item.material_id,
                    item.material_type,
                    item.title,
                    int(item.created_at_ms),
                    item.scoped_project_id,
                    item.internal_project_id,
                    str(updated_at),
                ),
            )


def _require_psycopg() -> Any:
    if psycopg is None:
        raise RuntimeError("psycopg[binary] is required to repair PostgreSQL data")
    return psycopg


def _default_postgres_dsn() -> str | None:
    for env_name in ("LEARNINGPYRAMID_STORE_POSTGRES_DSN", "LEARNINGPYRAMID_POSTGRES_DSN"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return None


def _default_updated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair missing subject_material_relationship_index rows.")
    parser.add_argument("--postgres-dsn", default=_default_postgres_dsn(), help="Target store PostgreSQL DSN")
    parser.add_argument("--apply", action="store_true", help="Write the planned repair rows. Omit for dry-run.")
    parser.add_argument("--updated-at", default=_default_updated_at(), help="updated_at value for inserted rows")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.postgres_dsn:
        raise ValueError("--postgres-dsn is required unless LEARNINGPYRAMID_STORE_POSTGRES_DSN or LEARNINGPYRAMID_POSTGRES_DSN is set")
    lib = _require_psycopg()
    conn = lib.connect(str(args.postgres_dsn), autocommit=True, row_factory=lib.rows.dict_row)
    try:
        result = repair_postgres(conn, apply=bool(args.apply), updated_at=str(args.updated_at))
    finally:
        conn.close()
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
