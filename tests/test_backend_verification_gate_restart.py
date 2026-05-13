import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore


class BackendVerificationGateRestartTest(unittest.TestCase):
    def test_restart_recovery_check_reopens_same_scoped_workspace(self) -> None:
        from backend.system.backend_verification_gate import run_gate, sqlite_restart_recovery_check

        with tempfile.TemporaryDirectory(prefix="lp-gate-restart-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"

            result = run_gate((sqlite_restart_recovery_check(store_path),))

        self.assertEqual(0, result.exit_code, result.to_text())
        report = result.to_dict()
        self.assertEqual([], report["failedChecks"])
        self.assertEqual([], report["skippedChecks"])
        text = result.to_text()
        self.assertIn("restart_recovery", text)
        self.assertIn("subjectId=", text)
        self.assertIn("scopedProjectId=", text)
        self.assertIn("internalProjectId=", text)

    def test_cli_runs_restart_scope_with_local_sqlite_store(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-gate-cli-restart-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"

            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_backend_release_gate.py",
                    "--scope",
                    "restart",
                    "--sqlite-store",
                    str(store_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("restart_recovery", completed.stdout)
        self.assertIn("subjectId=", completed.stdout)

    def test_restart_recovery_check_blocks_when_relationship_is_not_reloaded(self) -> None:
        from backend.system.backend_verification_gate import GateStatus, run_sqlite_restart_recovery_smoke

        with tempfile.TemporaryDirectory(prefix="lp-gate-broken-restart-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"

            def broken_reload(path: Path) -> SystemAPI:
                api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(path)))
                for project_store in api.sys.projects.values():
                    if getattr(project_store, "study_materials", None):
                        project_store.study_materials = {}
                    if hasattr(project_store, "study_materials_initialized"):
                        project_store.study_materials_initialized = False
                return api

            status = run_sqlite_restart_recovery_smoke(
                store_path,
                reload_api=broken_reload,
            )

        self.assertEqual(GateStatus.failed("unused").outcome, status.outcome)
        self.assertIn("relationship", status.message)
        self.assertEqual("restart", status.details.get("boundary"))


if __name__ == "__main__":
    unittest.main()
