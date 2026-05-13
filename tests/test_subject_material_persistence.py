import tempfile
import unittest
from pathlib import Path

from backend.models.study_material import StudyMaterialType
from backend.system.subject_material_recovery import (
    build_subject_material_recovery_plan,
    validate_subject_material_relationship_integrity,
)
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore


class SubjectMaterialPersistenceTest(unittest.TestCase):
    def _reload_sqlite_api(self, store_path: Path) -> SystemAPI:
        return SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_path)))

    def test_created_subject_default_material_survives_sqlite_reload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-subject-material-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"
            api = self._reload_sqlite_api(store_path)

            subject_id = api.create_subject("Subject")
            material = api.list_subject_materials(subject_id)[0]
            self.assertIsNotNone(material.scoped_project_id)
            self.assertIsNotNone(material.internal_project_id)

            reloaded = self._reload_sqlite_api(store_path)
            reloaded_materials = reloaded.list_subject_materials(subject_id)

            self.assertEqual(1, len(reloaded_materials))
            self.assertEqual(material.material_id, reloaded_materials[0].material_id)
            self.assertEqual(material.scoped_project_id, reloaded_materials[0].scoped_project_id)
            self.assertEqual(material.internal_project_id, reloaded_materials[0].internal_project_id)
            self.assertEqual(
                material.internal_project_id,
                reloaded.resolve_scoped_project_internal_key(subject_id, material.scoped_project_id),
            )

    def test_multiple_subject_materials_survive_sqlite_reload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-subject-material-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"
            api = self._reload_sqlite_api(store_path)
            subject_id = api.create_subject("Subject")
            api.create_subject_material(subject_id, material_type=StudyMaterialType.BOOK, title="Book")

            before = {
                str(item.scoped_project_id): str(item.internal_project_id)
                for item in api.list_subject_materials(subject_id)
                if item.scoped_project_id is not None and item.internal_project_id is not None
            }

            reloaded = self._reload_sqlite_api(store_path)
            after = {
                str(item.scoped_project_id): str(item.internal_project_id)
                for item in reloaded.list_subject_materials(subject_id)
                if item.scoped_project_id is not None and item.internal_project_id is not None
            }

            self.assertEqual(before, after)
            self.assertEqual(2, len(after))

    def test_deleted_subject_material_relationship_does_not_survive_sqlite_reload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-subject-material-delete-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"
            api = self._reload_sqlite_api(store_path)
            subject_id = api.create_subject("Subject")
            extra = api.create_subject_material(subject_id, material_type=StudyMaterialType.BOOK, title="Book")
            deleted_internal_project_id = extra.internal_project_id
            self.assertIsNotNone(deleted_internal_project_id)

            api.delete_subject_material(subject_id, extra.material_id)
            standalone_project_id = api.create_project("Standalone")

            reloaded = self._reload_sqlite_api(store_path)

            self.assertEqual(
                {item.material_id for item in api.list_subject_materials(subject_id)},
                {item.material_id for item in reloaded.list_subject_materials(subject_id)},
            )
            self.assertNotIn(
                extra.material_id,
                {item.material_id for item in reloaded.list_subject_materials(subject_id)},
            )
            self.assertIsNotNone(reloaded._get_project_store(standalone_project_id).project)
            self.assertEqual(
                "DELETED",
                reloaded._get_project_store(deleted_internal_project_id).project.state.value,
            )

    def test_recoverable_postgres_rows_build_deterministic_relationship_plan(self) -> None:
        plan = build_subject_material_recovery_plan(
            project_rows=[
                {
                    "project_id": "subj_000003",
                    "project_title": "Subject",
                    "project_state": "ACTIVE",
                    "created_at_ms": 1000,
                    "subject_id": None,
                    "scoped_project_id": None,
                    "project_type": "COURSE",
                },
                {
                    "project_id": "proj_000099",
                    "project_title": "网课材料",
                    "project_state": "ACTIVE",
                    "created_at_ms": 2000,
                    "subject_id": "subj_000003",
                    "scoped_project_id": "proj_000001",
                    "project_type": "COURSE",
                },
            ],
            relationship_rows=[],
        )

        self.assertEqual(1, len(plan))
        item = plan[0]
        self.assertEqual("subj_000003", item.subject_id)
        self.assertEqual("proj_000001", item.scoped_project_id)
        self.assertEqual("proj_000099", item.internal_project_id)
        self.assertEqual("mat_recovered_proj_000099", item.material_id)
        self.assertEqual("COURSE", item.material_type)
        self.assertEqual("网课材料", item.title)
        self.assertEqual(2000, item.created_at_ms)

    def test_subject_material_integrity_reports_missing_or_deleted_references(self) -> None:
        issues = validate_subject_material_relationship_integrity(
            project_rows=[
                {
                    "project_id": "subj_deleted",
                    "project_title": "Deleted Subject",
                    "project_state": "DELETED",
                    "created_at_ms": 1000,
                    "subject_id": None,
                    "scoped_project_id": None,
                    "project_type": "COURSE",
                },
                {
                    "project_id": "proj_deleted",
                    "project_title": "Deleted Material",
                    "project_state": "DELETED",
                    "created_at_ms": 2000,
                    "subject_id": "subj_deleted",
                    "scoped_project_id": "proj_000001",
                    "project_type": "COURSE",
                },
            ],
            relationship_rows=[
                {
                    "subject_id": "subj_missing",
                    "material_id": "mat_missing_subject",
                    "scoped_project_id": "proj_000001",
                    "internal_project_id": "proj_missing_internal",
                },
                {
                    "subject_id": "subj_deleted",
                    "material_id": "mat_deleted_internal",
                    "scoped_project_id": "proj_000002",
                    "internal_project_id": "proj_deleted",
                },
            ],
        )

        self.assertEqual(
            [
                "missing_subject",
                "missing_internal_project",
                "deleted_subject",
                "deleted_internal_project",
            ],
            [issue.kind for issue in issues],
        )
        self.assertEqual("subj_missing", issues[0].subject_id)
        self.assertEqual("proj_missing_internal", issues[1].internal_project_id)
        self.assertEqual("subj_deleted", issues[2].subject_id)
        self.assertEqual("proj_deleted", issues[3].internal_project_id)

    def test_subject_material_integrity_reports_unrecoverable_candidate_rows(self) -> None:
        issues = validate_subject_material_relationship_integrity(
            project_rows=[
                {
                    "project_id": "subj_000003",
                    "project_title": "Subject",
                    "project_state": "ACTIVE",
                    "created_at_ms": 1000,
                    "subject_id": None,
                    "scoped_project_id": None,
                    "project_type": "COURSE",
                },
                {
                    "project_id": "proj_missing_subject",
                    "project_title": "Missing Subject Material",
                    "project_state": "ACTIVE",
                    "created_at_ms": 2000,
                    "subject_id": "subj_missing",
                    "scoped_project_id": "proj_000001",
                    "project_type": "COURSE",
                },
                {
                    "project_id": "proj_missing_type",
                    "project_title": "Missing Type Material",
                    "project_state": "ACTIVE",
                    "created_at_ms": 3000,
                    "subject_id": "subj_000003",
                    "scoped_project_id": "proj_000002",
                    "project_type": None,
                },
                {
                    "project_id": "proj_standalone",
                    "project_title": "Standalone",
                    "project_state": "ACTIVE",
                    "created_at_ms": 4000,
                    "subject_id": None,
                    "scoped_project_id": None,
                    "project_type": None,
                },
            ],
            relationship_rows=[],
        )

        self.assertEqual(
            [
                "missing_subject",
                "unsupported_material_project_type",
            ],
            [issue.kind for issue in issues],
        )
        self.assertEqual("proj_missing_subject", issues[0].internal_project_id)
        self.assertEqual("proj_missing_type", issues[1].internal_project_id)


if __name__ == "__main__":
    unittest.main()
