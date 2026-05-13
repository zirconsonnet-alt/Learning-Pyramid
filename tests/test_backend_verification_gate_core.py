import subprocess
import sys
import unittest
from pathlib import Path


class BackendVerificationGateCoreTest(unittest.TestCase):
    def test_required_check_failure_blocks_gate_and_report_names_check(self) -> None:
        from backend.system.backend_verification_gate import GateCheck, GateStatus, run_gate

        result = run_gate(
            checks=(
                GateCheck(
                    check_id="example_restart",
                    label="Example restart check",
                    required=True,
                    run=lambda: GateStatus.failed("restart relationship missing", details={"boundary": "restart"}),
                ),
            )
        )

        self.assertEqual(1, result.exit_code)
        self.assertIn("example_restart", result.to_text())
        self.assertIn("restart relationship missing", result.to_text())
        self.assertIn("boundary=restart", result.to_text())

    def test_skipped_required_check_blocks_gate(self) -> None:
        from backend.system.backend_verification_gate import GateCheck, GateStatus, run_gate

        result = run_gate(
            checks=(
                GateCheck(
                    check_id="postgres_smoke",
                    label="PostgreSQL smoke",
                    required=True,
                    run=lambda: GateStatus.skipped("LEARNINGPYRAMID_TEST_POSTGRES_DSN is not set"),
                ),
            )
        )

        self.assertEqual(1, result.exit_code)
        self.assertIn("SKIPPED", result.to_text())
        self.assertIn("LEARNINGPYRAMID_TEST_POSTGRES_DSN is not set", result.to_text())

    def test_cli_exists_and_prints_report(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/verify_backend_release_gate.py", "--scope", "pure", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn('"gateName"', completed.stdout)
        self.assertIn('"executedChecks"', completed.stdout)

    def test_backend_gate_module_does_not_import_tools_layer(self) -> None:
        text = Path("backend/system/backend_verification_gate.py").read_text(encoding="utf-8")

        self.assertNotIn("from tools", text)
        self.assertNotIn("import tools", text)

    def test_temporary_workspace_helper_is_context_manager(self) -> None:
        from tests.backend_verification_gate_support import temporary_workspace

        with temporary_workspace() as path:
            self.assertTrue(path.exists())
            workspace_path = path

        self.assertFalse(workspace_path.exists())


if __name__ == "__main__":
    unittest.main()
