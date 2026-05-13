import argparse
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.backend_verification_gate import (
    identity_boundary_check,
    postgres_storage_check,
    run_postgres_workspace_restart_smoke,
    pure_checks,
    run_gate,
    sqlite_restart_recovery_check,
)
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore
from backend.system.postgres_store import PostgresStore
from tools.repair_subject_material_relationship_index import repair_postgres
from tools.verify_backend_boundaries import format_findings, verify_paths
from tools.verify_scoped_project_ids import verify_report
from tools.verify_scoped_project_routes import verify_scoped_project_routes


def _postgres_storage_smoke(dsn: str) -> dict[str, object]:
    payload = dict(run_postgres_workspace_restart_smoke(dsn))
    store = PostgresStore(dsn)
    conn = store._connect()
    try:
        repair = repair_postgres(
            conn,
            apply=False,
            updated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
    finally:
        conn.close()
    payload["repairPlannedCount"] = int(repair.get("plannedCount", 0))
    payload["repairIssueCount"] = len(list(repair.get("issues", [])))
    return payload


def _backend_boundary_issues() -> list[str]:
    findings = verify_paths((Path("adapter"), Path("backend/system/api.py")))
    return [] if not findings else [format_findings(findings)]


def _scoped_id_report(store_path: Path) -> dict[str, object]:
    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_path)))
    subject_id = api.create_subject("Backend Gate Identity Subject")
    material = api.list_subject_materials(subject_id)[0]
    report = {
        "blockingIssues": [],
        "mappings": [
            {
                "subjectId": str(subject_id),
                "scopedProjectId": str(material.scoped_project_id or ""),
                "internalProjectId": str(material.internal_project_id or ""),
            }
        ],
    }
    return verify_report(report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the backend release verification gate.")
    parser.add_argument("--scope", choices=("pure", "restart", "storage", "identity"), default="restart", help="Change scope to validate")
    parser.add_argument("--sqlite-store", type=Path, help="SQLite store path for restart recovery smoke")
    parser.add_argument("--postgres-dsn", help="PostgreSQL DSN for storage smoke")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cleanup: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.scope == "pure":
            checks = pure_checks()
        elif args.scope == "restart":
            store_path = args.sqlite_store
            if store_path is None:
                cleanup = tempfile.TemporaryDirectory(prefix="lp-backend-gate-")
                store_path = Path(cleanup.name) / "store.sqlite3"
            checks = (sqlite_restart_recovery_check(store_path),)
        elif args.scope == "storage":
            checks = (postgres_storage_check(args.postgres_dsn, smoke_runner=_postgres_storage_smoke),)
        else:
            store_path = args.sqlite_store
            if store_path is None:
                cleanup = tempfile.TemporaryDirectory(prefix="lp-backend-gate-")
                store_path = Path(cleanup.name) / "identity.sqlite3"
            checks = (
                identity_boundary_check(
                    route_checker=verify_scoped_project_routes,
                    backend_boundary_checker=_backend_boundary_issues,
                    scoped_id_checker=lambda: _scoped_id_report(store_path),
                ),
            )
        report = run_gate(checks)
    finally:
        if cleanup is not None:
            cleanup.cleanup()
    if args.json:
        print(report.to_json())
    else:
        print(report.to_text())
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
