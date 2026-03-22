import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adapter.mappers import project_material_source_binding_to_dto
from backend.models.enums import MaterialSourceKind, SessionMode
from backend.models.errors import PreconditionFailure
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.types import ProjectId
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import JsonSnapshotStore


class ProjectMaterialSourceBindingTests(unittest.TestCase):
    def test_create_defaults_to_server_fs(self) -> None:
        binding = ProjectMaterialSourceBinding.create(ProjectId("proj_1"))

        self.assertEqual(binding.source_kind, MaterialSourceKind.SERVER_FS)
        self.assertIsNone(binding.source_root_label)

    def test_create_rejects_non_enum_source_kind(self) -> None:
        with self.assertRaises(PreconditionFailure):
            ProjectMaterialSourceBinding.create(
                ProjectId("proj_1"),
                source_kind="INVALID_KIND",  # type: ignore[arg-type]
            )

    def test_create_trims_root_label(self) -> None:
        binding = ProjectMaterialSourceBinding.create(
            ProjectId("proj_1"),
            source_kind=MaterialSourceKind.SERVER_FS,
            source_root_label="  Videos  ",
        )

        self.assertEqual(binding.source_root_label, "Videos")

    def test_create_allows_browser_local_source_kind(self) -> None:
        binding = ProjectMaterialSourceBinding.create(
            ProjectId("proj_1"),
            source_kind=MaterialSourceKind.BROWSER_LOCAL,
            source_root_label="Authorized Videos",
        )

        self.assertEqual(binding.source_kind, MaterialSourceKind.BROWSER_LOCAL)
        self.assertEqual(binding.source_root_label, "Authorized Videos")

    def test_create_allows_manual_source_kind(self) -> None:
        binding = ProjectMaterialSourceBinding.create(
            ProjectId("proj_1"),
            source_kind=MaterialSourceKind.MANUAL,
            source_root_label="Paper Materials",
        )

        self.assertEqual(binding.source_kind, MaterialSourceKind.MANUAL)
        self.assertEqual(binding.source_root_label, "Paper Materials")

    def test_mapper_serializes_binding(self) -> None:
        binding = ProjectMaterialSourceBinding.create(
            ProjectId("proj_1"),
            source_kind=MaterialSourceKind.SERVER_FS,
            source_root_label="Videos",
        )

        dto = project_material_source_binding_to_dto(binding)

        self.assertEqual(
            dto,
            {
                "projectId": "proj_1",
                "sourceKind": "SERVER_FS",
                "sourceRootLabel": "Videos",
                "updatedAt": binding.updated_at.isoformat(timespec="milliseconds"),
            },
        )

    def test_create_project_bootstraps_default_binding(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project("proj")

        session = api.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            binding = api.sys.project_material_source_binding_repo.get(session)
        finally:
            api.sys.rollback(session)

        self.assertEqual(binding.source_kind, MaterialSourceKind.SERVER_FS)

    def test_create_project_supports_manual_initial_binding(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project("proj", initial_source_kind=MaterialSourceKind.MANUAL)

        session = api.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            binding = api.sys.project_material_source_binding_repo.get(session)
        finally:
            api.sys.rollback(session)

        self.assertEqual(binding.source_kind, MaterialSourceKind.MANUAL)

    def test_manual_project_allows_manual_instance_and_reports_reachable(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project("proj", initial_source_kind=MaterialSourceKind.MANUAL)

        instance_id = api.add_instance(project_id, "books/calculus/chapter-1/page-12-q4")
        instance = api.get_instance(project_id, instance_id)

        self.assertEqual(instance.material_id.as_posix(), "books/calculus/chapter-1/page-12-q4")
        self.assertEqual(api.validate_material_reachable(project_id, instance_id).code.value, "OK")

    def test_json_snapshot_round_trip_preserves_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "store.json"
            api = SystemAPI(InMemorySystem(persist_store=JsonSnapshotStore(store_path)))
            project_id = api.create_project("proj")

            reloaded = SystemAPI(InMemorySystem(persist_store=JsonSnapshotStore(store_path)))
            session = reloaded.sys.begin_session(project_id, SessionMode.READ_ONLY)
            try:
                binding = reloaded.sys.project_material_source_binding_repo.get(session)
            finally:
                reloaded.sys.rollback(session)

        self.assertEqual(binding.source_kind, MaterialSourceKind.SERVER_FS)


if __name__ == "__main__":
    unittest.main()
