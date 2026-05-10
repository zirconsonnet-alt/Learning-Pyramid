import contextlib
import importlib
import io
import tempfile
import textwrap
import unittest
from pathlib import Path


EXPECTED_RULE_IDS = {"BBG001", "BBG002", "BBG003", "BBG004", "BBG005"}


def load_guard_module():
    try:
        return importlib.import_module("tools.verify_backend_boundaries")
    except ModuleNotFoundError as exc:
        if exc.name == "tools.verify_backend_boundaries":
            raise AssertionError("tools.verify_backend_boundaries is missing") from exc
        raise


def write_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


def findings_for(root: Path, *relative_paths: str):
    guard = load_guard_module()
    paths = tuple(root / path for path in relative_paths) if relative_paths else (root,)
    return guard.verify_paths(paths, root=root)


def rule_ids(findings) -> set[str]:
    return {finding.rule_id for finding in findings}


class BoundaryRuleMetadataTest(unittest.TestCase):
    def test_every_boundary_rule_has_required_metadata(self) -> None:
        guard = load_guard_module()

        self.assertEqual(EXPECTED_RULE_IDS, set(guard.RULES))
        for rule in guard.RULES.values():
            self.assertIn(rule.rule_id, EXPECTED_RULE_IDS)
            self.assertTrue(rule.owner)
            self.assertIn(rule.severity, {"low", "medium", "high"})
            self.assertTrue(rule.rationale)
            self.assertTrue(rule.forbidden_patterns)
            self.assertIsInstance(rule.approved_owner_paths, tuple)

    def test_rule_ids_appear_in_guard_output_metadata(self) -> None:
        guard = load_guard_module()
        findings = [
            guard.GuardFinding(
                rule_id=rule_id,
                severity="high",
                path=f"example/{rule_id}.py",
                line=1,
                message="example",
                evidence="example",
            )
            for rule_id in sorted(EXPECTED_RULE_IDS)
        ]

        output = guard.format_findings(findings)

        for rule_id in EXPECTED_RULE_IDS:
            self.assertIn(f"rule_id: {rule_id}", output)
        for field in ("severity:", "path:", "line:", "message:", "evidence:"):
            self.assertIn(field, output)


class BoundaryViolationDetectionTest(unittest.TestCase):
    def test_transport_layer_storage_internals_access_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/routers/example.py",
                """
                def route(api):
                    return api.sys.project_storage_config_repo.get("session")
                """,
            )

            findings = findings_for(root)

        self.assertIn("BBG001", rule_ids(findings))
        self.assertTrue(any("api.sys" in finding.evidence for finding in findings))

    def test_adapter_support_module_storage_internals_access_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/runtime_status.py",
                """
                def collect_runtime_status(api):
                    return api.sys._persist_store.healthcheck()
                """,
            )

            findings = findings_for(root)

        self.assertIn("BBG001", rule_ids(findings))

    def test_storage_only_authorization_ownership_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/routers/projects.py",
                """
                def bind_owner(auth_store, project, user):
                    auth_store.add_project_owner(project.internal_project_id, user.user_id)
                """,
            )

            findings = findings_for(root)

        self.assertIn("BBG003", rule_ids(findings))

    def test_scoped_route_without_identity_boundary_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/routers/materials.py",
                """
                from fastapi import APIRouter

                router = APIRouter()

                @router.get("/subjects/{subjectId}/projects/{projectId}/instances")
                def list_instances(subjectId: str, projectId: str, api):
                    return api.list_instances(projectId)
                """,
            )

            findings = findings_for(root)

        self.assertIn("BBG002", rule_ids(findings))

    def test_non_atomic_cross_project_mutation_bypass_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "backend/system/api.py",
                """
                class SystemAPI:
                    def delete_subject_material(self, material_project_id):
                        self.delete_project(material_project_id)
                """,
            )

            findings = findings_for(root)

        self.assertIn("BBG004", rule_ids(findings))

    def test_migration_compatibility_expansion_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/routers/example.py",
                """
                def legacy_project_fallback_shim():
                    return "compatibility"
                """,
            )

            findings = findings_for(root)

        self.assertIn("BBG005", rule_ids(findings))


class GuardModeTest(unittest.TestCase):
    def test_report_only_mode_returns_success_without_hiding_findings(self) -> None:
        guard = load_guard_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/routers/example.py",
                """
                def route(api):
                    return api.sys.projects
                """,
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = guard.main(["--root", str(root), "--report-only", str(root)])

        self.assertEqual(0, exit_code)
        self.assertIn("rule_id: BBG001", stdout.getvalue())

    def test_failing_mode_returns_error_when_findings_exist(self) -> None:
        guard = load_guard_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/routers/example.py",
                """
                def route(api):
                    return api.sys.projects
                """,
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = guard.main(["--root", str(root), str(root)])

        self.assertEqual(1, exit_code)
        self.assertIn("rule_id: BBG001", stdout.getvalue())


class BoundaryOwnerAllowlistTest(unittest.TestCase):
    def test_approved_boundary_owner_paths_are_not_reported_as_transport_violations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root,
                "adapter/scoped_projects.py",
                """
                def resolve_scoped_project(api, subjectId, projectId):
                    return api.resolve_scoped_project_internal_key(subjectId, projectId)
                """,
            )
            write_file(
                root,
                "backend/system/api.py",
                """
                class SystemAPI:
                    def _require_subject_root_project(self, subject_id):
                        return ()
                """,
            )

            findings = findings_for(root)

        self.assertNotIn("BBG001", rule_ids(findings))
        self.assertNotIn("BBG005", rule_ids(findings))


if __name__ == "__main__":
    unittest.main()
