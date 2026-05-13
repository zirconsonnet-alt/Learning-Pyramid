import tempfile
import unittest
from pathlib import Path

from adapter.mappers import study_material_to_dto
from backend.models.study_material import StudyMaterial, StudyMaterialType
from backend.models.types import ProjectId, now_utc_ms
from backend.system.subject_material_recovery import build_subject_material_recovery_plan
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore


class SubjectMaterialIdentityTest(unittest.TestCase):
    def _reload_sqlite_api(self, store_path: Path) -> SystemAPI:
        return SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_path)))

    def test_study_material_dto_exposes_scoped_project_id_not_project_id(self) -> None:
        material = StudyMaterial(
            subject_id=ProjectId("subj_000003"),
            material_id="mat_course_000001",
            material_type=StudyMaterialType.COURSE,
            title="网课材料",
            created_at=now_utc_ms(),
            scoped_project_id=ProjectId("proj_000001"),
            internal_project_id=ProjectId("proj_000099"),
        )

        dto = study_material_to_dto(material)

        self.assertEqual("proj_000001", dto["scopedProjectId"])
        self.assertNotIn("projectId", dto)
        self.assertNotIn("internalProjectId", dto)

    def test_same_scoped_material_id_under_different_subjects_resolves_after_reload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-subject-material-identity-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"
            api = self._reload_sqlite_api(store_path)

            first_subject_id = api.create_subject("First")
            second_subject_id = api.create_subject("Second")
            first_material = api.list_subject_materials(first_subject_id)[0]
            second_material = api.list_subject_materials(second_subject_id)[0]

            self.assertEqual(first_material.scoped_project_id, second_material.scoped_project_id)
            self.assertNotEqual(first_material.internal_project_id, second_material.internal_project_id)

            reloaded = self._reload_sqlite_api(store_path)

            self.assertEqual(
                first_material.internal_project_id,
                reloaded.resolve_scoped_project_internal_key(first_subject_id, first_material.scoped_project_id),
            )
            self.assertEqual(
                second_material.internal_project_id,
                reloaded.resolve_scoped_project_internal_key(second_subject_id, second_material.scoped_project_id),
            )

    def test_recovery_does_not_use_deleted_global_project_id_matching_scoped_id(self) -> None:
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
                    "project_id": "proj_000001",
                    "project_title": "Deleted global collision",
                    "project_state": "DELETED",
                    "created_at_ms": 1500,
                    "subject_id": None,
                    "scoped_project_id": None,
                    "project_type": "COURSE",
                },
                {
                    "project_id": "proj_000099",
                    "project_title": "Recovered Material",
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
        self.assertEqual("proj_000099", plan[0].internal_project_id)
        self.assertEqual("proj_000001", plan[0].scoped_project_id)


if __name__ == "__main__":
    unittest.main()
