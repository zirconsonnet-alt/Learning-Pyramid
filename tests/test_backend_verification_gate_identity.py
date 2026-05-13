import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BackendVerificationGateIdentityTest(unittest.TestCase):
    def test_identity_check_reports_boundary_tool_failure(self) -> None:
        from backend.system.backend_verification_gate import GateOutcome, run_identity_boundary_smoke

        status = run_identity_boundary_smoke(
            route_checker=lambda: [],
            backend_boundary_checker=lambda: ["rule_id: BBG002\nmessage: scoped route omits resolve_scoped_project"],
            scoped_id_checker=lambda: {"ok": True, "projectsVerified": 1, "blockingIssues": [], "duplicateScopedProjectIds": []},
        )

        self.assertEqual(GateOutcome.FAILED, status.outcome)
        self.assertIn("identity boundary", status.message)
        self.assertEqual("identity", status.details["boundary"])
        self.assertIn("BBG002", str(status.details["backendBoundaryIssues"]))

    def test_identity_check_reports_duplicate_scoped_ids(self) -> None:
        from backend.system.backend_verification_gate import GateOutcome, run_identity_boundary_smoke

        status = run_identity_boundary_smoke(
            route_checker=lambda: [],
            backend_boundary_checker=lambda: [],
            scoped_id_checker=lambda: {
                "ok": False,
                "projectsVerified": 2,
                "blockingIssues": [],
                "duplicateScopedProjectIds": [{"subjectId": "subj_000001", "scopedProjectId": "proj_000001"}],
            },
        )

        self.assertEqual(GateOutcome.FAILED, status.outcome)
        self.assertIn("duplicateScopedProjectIds", status.details)

    def test_scoped_id_report_rejects_ambiguous_project_id_mapping(self) -> None:
        from tools.verify_scoped_project_ids import verify_report

        result = verify_report(
            {
                "blockingIssues": [],
                "mappings": [{"subjectId": "subj_000001", "projectId": "proj_000001"}],
            }
        )

        self.assertFalse(result["ok"])
        self.assertEqual("INCOMPLETE_SCOPED_PROJECT_IDENTITY", result["blockingIssues"][0]["code"])

    def test_scoped_migration_report_outputs_unambiguous_identity_fields(self) -> None:
        from tools.migrate_scoped_project_ids import build_migration_report

        store = {
            "projects": {
                "subj_000001": {
                    "project": {"state": "ACTIVE"},
                    "studyMaterials": {"mat_000001": {"subjectId": "subj_000001"}},
                },
                "proj_000099": {
                    "project": {"state": "ACTIVE"},
                    "subjectMaterialLink": {"subjectId": "subj_000001", "projectId": "proj_000001"},
                },
            }
        }
        with tempfile.TemporaryDirectory(prefix="lp-scoped-id-report-") as temp_dir:
            store_path = Path(temp_dir) / "store.json"
            store_path.write_text(json.dumps(store), encoding="utf-8")

            report = build_migration_report(store_path)

        self.assertEqual(
            [{"internalProjectId": "proj_000099", "subjectId": "subj_000001", "scopedProjectId": "proj_000001"}],
            report["mappings"],
        )

    def test_identity_check_requires_at_least_one_verified_scoped_project(self) -> None:
        from backend.system.backend_verification_gate import GateOutcome, run_identity_boundary_smoke

        status = run_identity_boundary_smoke(
            route_checker=lambda: [],
            backend_boundary_checker=lambda: [],
            scoped_id_checker=lambda: {
                "ok": True,
                "projectsVerified": 0,
                "blockingIssues": [],
                "duplicateScopedProjectIds": [],
            },
        )

        self.assertEqual(GateOutcome.FAILED, status.outcome)
        self.assertIn("no scoped project identity sample", str(status.details["blockingIssues"]))

    def test_cli_identity_scope_prints_diagnostic_report(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/verify_backend_release_gate.py", "--scope", "identity", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertIn("identity_boundary", completed.stdout)
        self.assertIn("diagnosticFields", completed.stdout)
        self.assertIn("releaseBlocked", payload)
        self.assertEqual(0, completed.returncode, completed.stdout)
        details = payload["executedChecks"][0]["details"]
        self.assertGreaterEqual(details["projectsVerified"], 1)
        self.assertIn("internalProjectId", completed.stdout)


if __name__ == "__main__":
    unittest.main()
