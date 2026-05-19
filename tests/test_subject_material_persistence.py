import tempfile
import unittest
from pathlib import Path

from backend.models.enums import FsSyncPolicy, InstancePresence, MaterialSourceKind
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf
from backend.models.recall_point import Anchor
from backend.models.rich_content import rich_text
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

    def test_learning_data_progress_recall_point_and_insight_survive_sqlite_reload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-learning-data-reload-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"
            api = self._reload_sqlite_api(store_path)
            subject_id = api.create_subject("Subject")
            material = api.list_subject_materials(subject_id)[0]
            project_id = material.internal_project_id
            self.assertIsNotNone(project_id)

            api.import_learning_objects_from_browser_scan(
                project_id,
                root_title="Progress Fixture",
                relative_file_paths=("lesson-a.mp4",),
            )
            instance_id = api.list_instances(project_id)[0].instance_id
            api.record_video_watch_progress_range(
                project_id,
                instance_id,
                start_ms=1_000,
                end_ms=5_000,
                duration_ms=12_000,
            )
            api.record_video_watch_progress_range(
                project_id,
                instance_id,
                start_ms=5_000,
                end_ms=8_000,
                duration_ms=12_000,
            )
            node_id = api.submit_learning_task(
                project_id,
                items=[
                    (
                        rich_text("question"),
                        rich_text("answer"),
                        Anchor(instance_id=instance_id, position="t=42000"),
                    )
                ],
                title="Task",
            )

            reloaded = self._reload_sqlite_api(store_path)
            reloaded_project_id = reloaded.resolve_scoped_project_internal_key(subject_id, material.scoped_project_id)
            progress = reloaded.list_video_watch_progress(reloaded_project_id, instance_ids=(instance_id,))
            self.assertEqual(1, len(progress))
            self.assertEqual(((1_000, 8_000),), progress[0].ranges)
            self.assertEqual(12_000, progress[0].duration_ms)
            self.assertEqual(7_000, progress[0].watched_ms)

            recall_point = reloaded.list_recall_points_by_learning_task_node(reloaded_project_id, node_id)[0]
            reloaded.edit_recall_point(
                reloaded_project_id,
                recall_point.recall_point_id,
                rich_text("edited question"),
                rich_text("edited answer"),
                Anchor(instance_id=instance_id, position="t=43000"),
            )
            review_task_id = reloaded.get_queue(reloaded_project_id)[0]
            self.assertIsNotNone(review_task_id)
            reloaded.executor_commit_review_task(
                reloaded_project_id,
                review_task_id,
                [1],
                appended_insights=((recall_point.recall_point_id, rich_text("persisted note")),),
            )

            reopened = self._reload_sqlite_api(store_path)
            reopened_project_id = reopened.resolve_scoped_project_internal_key(subject_id, material.scoped_project_id)
            persisted = reopened.get_recall_point(reopened_project_id, recall_point.recall_point_id)
            self.assertEqual("edited question", persisted.question[0].text)
            self.assertEqual("edited answer", persisted.answer[0].text)
            self.assertEqual("t=43000", persisted.anchor.position)
            self.assertEqual(1, len(persisted.insights))
            self.assertEqual("persisted note", persisted.insights[0][0].text)
            self.assertEqual(
                [recall_point.recall_point_id],
                list(reopened.list_recall_points_by_instance(reopened_project_id, instance_id)),
            )

    def test_native_local_directory_import_survives_sqlite_reload_and_marks_absent_instances(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lp-native-local-import-") as temp_dir:
            store_path = Path(temp_dir) / "store.sqlite3"
            project_root = str(Path(temp_dir) / "Course Files")
            api = self._reload_sqlite_api(store_path)
            subject_id = api.create_subject("Subject")
            material = api.list_subject_materials(subject_id)[0]
            project_id = material.internal_project_id
            self.assertIsNotNone(project_id)

            first = api.import_learning_objects_from_native_local_scan(
                project_id,
                project_root=project_root,
                root_title="Local Course",
                relative_file_paths=("intro.mp4", "chapter/lesson.webm"),
            )

            self.assertFalse(first["unchanged"])
            self.assertEqual(2, first["created_instances_count"])
            self.assertEqual(0, first["marked_missing_count"])
            self.assertEqual(4, first["replaced_learning_object_nodes_count"])

            binding = api.get_project_material_source_binding(project_id)
            self.assertEqual(MaterialSourceKind.NATIVE_LOCAL, binding.source_kind)
            self.assertEqual("Local Course", binding.source_root_label)

            storage = api.get_project_storage_config(project_id)
            self.assertEqual(project_root.replace("\\", "/"), storage.project_root.as_posix())
            self.assertEqual(".", storage.learning_object_root.as_posix())
            self.assertEqual(FsSyncPolicy.MANUAL_SYNC, storage.fs_sync_policy)

            instances = {item.material_id.as_posix(): item for item in api.list_instances(project_id)}
            self.assertEqual(["chapter/lesson.webm", "intro.mp4"], sorted(instances))
            self.assertEqual(InstancePresence.PRESENT, instances["intro.mp4"].presence)

            nodes = api.list_learning_object_nodes(project_id)
            containers = {node.relative_path.as_posix(): node for node in nodes if isinstance(node, LearningObjectContainer)}
            leaves = {node.relative_path.as_posix(): node for node in nodes if isinstance(node, LearningObjectLeaf)}
            self.assertEqual([".", "chapter"], sorted(containers))
            self.assertEqual("Local Course", containers["."].title)
            self.assertEqual(containers["."].node_id, containers["chapter"].parent_id)
            self.assertEqual(["chapter/lesson.webm", "intro.mp4"], sorted(leaves))

            second = api.import_learning_objects_from_native_local_scan(
                project_id,
                project_root=project_root,
                root_title="Local Course",
                relative_file_paths=("chapter/lesson.webm",),
            )

            self.assertFalse(second["unchanged"])
            self.assertEqual(0, second["created_instances_count"])
            self.assertEqual(1, second["marked_missing_count"])
            self.assertEqual(3, second["replaced_learning_object_nodes_count"])

            reloaded = self._reload_sqlite_api(store_path)
            reloaded_project_id = reloaded.resolve_scoped_project_internal_key(subject_id, material.scoped_project_id)
            reloaded_binding = reloaded.get_project_material_source_binding(reloaded_project_id)
            reloaded_storage = reloaded.get_project_storage_config(reloaded_project_id)
            reloaded_instances = {item.material_id.as_posix(): item for item in reloaded.list_instances(reloaded_project_id)}
            reloaded_leaves = {
                node.relative_path.as_posix()
                for node in reloaded.list_learning_object_nodes(reloaded_project_id)
                if isinstance(node, LearningObjectLeaf)
            }

            self.assertEqual(MaterialSourceKind.NATIVE_LOCAL, reloaded_binding.source_kind)
            self.assertEqual(project_root.replace("\\", "/"), reloaded_storage.project_root.as_posix())
            self.assertEqual(".", reloaded_storage.learning_object_root.as_posix())
            self.assertEqual(FsSyncPolicy.MANUAL_SYNC, reloaded_storage.fs_sync_policy)
            self.assertEqual(InstancePresence.MISSING, reloaded_instances["intro.mp4"].presence)
            self.assertEqual(InstancePresence.PRESENT, reloaded_instances["chapter/lesson.webm"].presence)
            self.assertEqual({"chapter/lesson.webm"}, reloaded_leaves)

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
