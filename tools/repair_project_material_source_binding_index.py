import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None


SUPPORTED_PROJECT_TYPES = {"COURSE", "BOOK", "LOOSE_POINTS"}


@dataclass(frozen=True, slots=True)
class RepairItem:
    project_id: str
    project_type: str
    source_kind: str
    source_root_label: str | None
    updated_at_ms: int

    def to_json(self) -> dict[str, object]:
        return {
            "projectId": self.project_id,
            "projectType": self.project_type,
            "sourceKind": self.source_kind,
            "sourceRootLabel": self.source_root_label,
            "updatedAtMs": self.updated_at_ms,
        }


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def source_kind_for_project_type(project_type: str) -> str:
    value = str(project_type or "").strip().upper()
    if value == "COURSE":
        return "SERVER_FS"
    if value in {"BOOK", "LOOSE_POINTS"}:
        return "MANUAL"
    raise ValueError(f"Unsupported projectType: {project_type!r}")


def _project_type_from_config(project_id: str, config_json: Any) -> str:
    try:
        payload = json.loads(str(config_json))
    except Exception as exc:
        raise ValueError(f"project {project_id} has invalid config_json") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"project {project_id} config_json must be a JSON object")
    project_type = str(payload.get("projectType") or "").strip().upper()
    if project_type not in SUPPORTED_PROJECT_TYPES:
        raise ValueError(f"project {project_id} has unsupported projectType: {project_type!r}")
    return project_type


def build_repair_plan(rows: Iterable[dict[str, Any]], *, updated_at_ms: int) -> list[RepairItem]:
    plan: list[RepairItem] = []
    for row in rows:
        state = str(row.get("project_state") or "").strip().upper()
        if state == "DELETED":
            continue
        project_id = str(row.get("project_id") or "").strip()
        if not project_id:
            raise ValueError("missing project_id in repair row")
        project_type = _project_type_from_config(project_id, row.get("config_json"))
        plan.append(
            RepairItem(
                project_id=project_id,
                project_type=project_type,
                source_kind=source_kind_for_project_type(project_type),
                source_root_label=None,
                updated_at_ms=int(updated_at_ms),
            )
        )
    return plan


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


def _load_missing_rows(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.project_id, p.project_state, c.config_json
        FROM project_snapshots p
        JOIN project_config_index c ON c.project_id = p.project_id
        LEFT JOIN project_material_source_binding_index b ON b.project_id = p.project_id
        WHERE p.project_state <> 'DELETED' AND b.project_id IS NULL
        ORDER BY p.project_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _load_missing_config_project_ids(conn: Any) -> list[str]:
    rows = conn.execute(
        """
        SELECT p.project_id
        FROM project_snapshots p
        LEFT JOIN project_config_index c ON c.project_id = p.project_id
        WHERE p.project_state <> 'DELETED' AND c.project_id IS NULL
        ORDER BY p.project_id
        """
    ).fetchall()
    return [str(row["project_id"]) for row in rows]


def _insert_repair_items(conn: Any, plan: list[RepairItem]) -> None:
    if not plan:
        return
    with conn.transaction():
        for item in plan:
            conn.execute(
                """
                INSERT INTO project_material_source_binding_index (
                    project_id,
                    source_kind,
                    source_root_label,
                    updated_at_ms
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (project_id) DO NOTHING
                """,
                (item.project_id, item.source_kind, item.source_root_label, item.updated_at_ms),
            )


def repair_postgres(conn: Any, *, apply: bool, updated_at_ms: int) -> dict[str, object]:
    missing_config_project_ids = _load_missing_config_project_ids(conn)
    if missing_config_project_ids:
        raise ValueError(
            "Cannot repair material source bindings while active projects are missing project_config_index rows: "
            + ", ".join(missing_config_project_ids)
        )

    plan = build_repair_plan(_load_missing_rows(conn), updated_at_ms=updated_at_ms)
    if apply:
        _insert_repair_items(conn, plan)
    return {
        "ok": True,
        "mode": "apply" if apply else "dry-run",
        "plannedCount": len(plan),
        "appliedCount": len(plan) if apply else 0,
        "items": [item.to_json() for item in plan],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair missing project_material_source_binding_index rows.")
    parser.add_argument("--postgres-dsn", default=_default_postgres_dsn(), help="Target store PostgreSQL DSN")
    parser.add_argument("--apply", action="store_true", help="Write the planned repair rows. Omit for dry-run.")
    parser.add_argument("--updated-at-ms", type=int, default=now_ms(), help="updated_at_ms value for inserted rows")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.postgres_dsn:
        raise ValueError("--postgres-dsn is required unless LEARNINGPYRAMID_STORE_POSTGRES_DSN or LEARNINGPYRAMID_POSTGRES_DSN is set")
    lib = _require_psycopg()
    conn = lib.connect(str(args.postgres_dsn), autocommit=True, row_factory=lib.rows.dict_row)
    try:
        result = repair_postgres(conn, apply=bool(args.apply), updated_at_ms=int(args.updated_at_ms))
    finally:
        conn.close()
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
