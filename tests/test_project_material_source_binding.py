import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adapter.mappers import project_material_source_binding_to_dto
from backend.models.enums import MaterialSourceKind, SessionMode
from backend.models.errors import PreconditionFailure
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.types import DesktopAgentId, ProjectId
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import JsonSnapshotStore


class ProjectMaterialSourceBindingTests(unittest.TestCase):
    def test_create_defaults_to_server_fs_without_agent(self) -> None:
        binding = ProjectMaterialSourceBinding.create(ProjectId("proj_1"))

        self.assertEqual(binding.source_kind, MaterialSourceKind.SERVER_FS)
        self.assertIsNone(binding.desktop_agent_id)
        self.assertIsNone(binding.source_root_label)

    def test_create_desktop_agent_manifest_requires_agent_id(self) -> None:
        with self.assertRaises(PreconditionFailure):
            ProjectMaterialSourceBinding.create(
                ProjectId("proj_1"),
                source_kind=MaterialSourceKind.DESKTOP_AGENT_MANIFEST,
            )

    def test_create_server_fs_rejects_agent_id(self) -> None:
        with self.assertRaises(PreconditionFailure):
            ProjectMaterialSourceBinding.create(
                ProjectId("proj_1"),
                source_kind=MaterialSourceKind.SERVER_FS,
                desktop_agent_id=DesktopAgentId("agent_1"),
            )

    def test_create_trims_root_label_and_keeps_agent_for_manifest(self) -> None:
        binding = ProjectMaterialSourceBinding.create(
            ProjectId("proj_1"),
            source_kind=MaterialSourceKind.DESKTOP_AGENT_MANIFEST,
            desktop_agent_id=" agent_1 ",
            source_root_label="  Videos  ",
        )

        self.assertEqual(binding.desktop_agent_id, DesktopAgentId("agent_1"))
        self.assertEqual(binding.source_root_label, "Videos")

    def test_mapper_serializes_binding(self) -> None:
        binding = ProjectMaterialSourceBinding.create(
            ProjectId("proj_1"),
            source_kind=MaterialSourceKind.DESKTOP_AGENT_MANIFEST,
            desktop_agent_id=DesktopAgentId("agent_1"),
            source_root_label="Videos",
        )

        dto = project_material_source_binding_to_dto(binding)

        self.assertEqual(
            dto,
            {
                "projectId": "proj_1",
                "sourceKind": "DESKTOP_AGENT_MANIFEST",
                "desktopAgentId": "agent_1",
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
        self.assertIsNone(binding.desktop_agent_id)

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
        self.assertIsNone(binding.desktop_agent_id)


if __name__ == "__main__":
    unittest.main()
