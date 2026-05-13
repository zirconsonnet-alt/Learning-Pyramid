import json
import os
import subprocess
import sys
import unittest


class BackendVerificationGateStorageTest(unittest.TestCase):
    def test_storage_scope_without_dsn_blocks_release(self) -> None:
        env = os.environ.copy()
        for key in ("LEARNINGPYRAMID_TEST_POSTGRES_DSN", "LEARNINGPYRAMID_STORE_POSTGRES_DSN", "LEARNINGPYRAMID_POSTGRES_DSN"):
            env.pop(key, None)

        completed = subprocess.run(
            [sys.executable, "tools/verify_backend_release_gate.py", "--scope", "storage", "--json"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(1, completed.returncode, completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["releaseBlocked"])
        self.assertEqual("postgres_storage_smoke", payload["skippedChecks"][0]["checkId"])
        self.assertIn("PostgreSQL DSN", payload["skippedChecks"][0]["message"])

    def test_postgres_storage_check_uses_smoke_runner_and_reports_identity(self) -> None:
        from backend.system.backend_verification_gate import GateOutcome, run_postgres_storage_smoke

        calls: list[str] = []

        def smoke_runner(dsn: str) -> dict[str, object]:
            calls.append(dsn)
            return {
                "subjectId": "subj_000001",
                "scopedProjectId": "proj_000001",
                "internalProjectId": "proj_000099",
                "repairPlannedCount": 0,
                "repairIssueCount": 0,
            }

        status = run_postgres_storage_smoke(
            "postgresql://learningpyramid:secret@127.0.0.1:5432/db",
            smoke_runner=smoke_runner,
        )

        self.assertEqual(GateOutcome.PASSED, status.outcome)
        self.assertEqual(["postgresql://learningpyramid:secret@127.0.0.1:5432/db"], calls)
        self.assertEqual("subj_000001", status.details["subjectId"])
        self.assertEqual("proj_000001", status.details["scopedProjectId"])
        self.assertEqual("proj_000099", status.details["internalProjectId"])

    def test_postgres_storage_check_reports_runner_failure(self) -> None:
        from backend.system.backend_verification_gate import GateOutcome, run_postgres_storage_smoke

        def smoke_runner(dsn: str) -> dict[str, object]:
            raise RuntimeError("missing column snapshot_json")

        status = run_postgres_storage_smoke(
            "postgresql://learningpyramid:secret@127.0.0.1:5432/db",
            smoke_runner=smoke_runner,
        )

        self.assertEqual(GateOutcome.FAILED, status.outcome)
        self.assertIn("missing column snapshot_json", status.message)
        self.assertEqual("storage", status.details["boundary"])


if __name__ == "__main__":
    unittest.main()
