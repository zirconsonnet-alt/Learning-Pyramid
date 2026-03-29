import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.models.asr_artifact import AsrArtifact, AsrSegment
from backend.models.enums import (
    AsrProvider,
    ClientRuntimeKind,
    FsSyncPolicy,
    InstancePresence,
    RecallPointState,
    ReviewChainTemplateItemKind,
    SessionMode,
)
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.instance import Instance
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf
from backend.models.project_config import (
    ProjectConfig,
    RecallPointPushConfig,
    ReviewChainTemplateItem,
)
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.review_chain import ReviewChainItemKind
from backend.models.rich_content import rich_text
from backend.models.types import (
    AsrArtifactId,
    InstanceId,
    RangeId,
    RecallPointId,
    now_utc_ms,
)
from backend.system.api import SystemAPI, TickAttemptResult
from backend.system.inmemory_system import InMemorySystem
from backend.system.local_whisper import BUILTIN_WHISPER_BASE_URL
from backend.system.persistence_store import JsonSnapshotStore, SnapshotStore, SQLiteSnapshotStore
from backend.system.postgres_store import PostgresStore
from tests.postgres_test_support import reset_postgres_database

try:
    import psycopg  # noqa: F401
except ImportError:  # pragma: no cover - exercised in environments without psycopg installed
    psycopg = None


class _SpecAlignmentBackendMixin:
    BACKEND = "json"
    POSTGRES_DSN: str | None = None

    def _make_store(self, root: Path) -> SnapshotStore:
        if self.BACKEND == "json":
            return JsonSnapshotStore(root / "store.json")
        if self.BACKEND == "sqlite":
            return SQLiteSnapshotStore(root / "store.sqlite3")
        if self.BACKEND == "postgres":
            assert self.POSTGRES_DSN is not None
            return PostgresStore(self.POSTGRES_DSN)
        raise AssertionError(f"Unsupported backend: {self.BACKEND}")

    def _reset_backend(self, root: Path) -> None:
        if self.BACKEND == "postgres":
            assert self.POSTGRES_DSN is not None
            reset_postgres_database(self.POSTGRES_DSN)

    def _create_api(self, root: Path) -> SystemAPI:
        return SystemAPI(InMemorySystem(persist_store=self._make_store(root)))

    def _new_api(self) -> tuple[SystemAPI, Path]:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self._reset_backend(root)
        api = self._create_api(root)
        return api, root

    def _reload_api(self, root: Path) -> SystemAPI:
        return self._create_api(root)

    def _load_raw_snapshot(self, root: Path) -> dict[str, object]:
        snapshot = self._make_store(root).load_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        return snapshot

    def _save_raw_snapshot(self, root: Path, snapshot: dict[str, object]) -> None:
        self._make_store(root).save_snapshot(snapshot)

    def _make_project_dirs(self, root: Path, name: str) -> tuple[Path, Path]:
        project_root = root / name
        learning_root = project_root / "learning_objects"
        learning_root.mkdir(parents=True)
        return project_root, learning_root

    def _tick_once(self, api: SystemAPI, project_id: object, layer_index: int = 0) -> TickAttemptResult:
        system = api.sys
        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            result = api._orchestrator_tick_once(session, layer_index)
            system.commit(session)
            return result
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

    def _build_review_then_convergence_fixture(self) -> dict[str, object]:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]
        api.set_layer_config(
            project_id,
            0,
            (
                ReviewChainTemplateItem(kind=ReviewChainTemplateItemKind.REVIEW_TASK),
                ReviewChainTemplateItem(kind=ReviewChainTemplateItemKind.CONVERGENCE),
            ),
            None,
            None,
        )

        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=0"))],
            title="Lesson 1",
        )
        reg = api.get_learning_task_node_entry_registration(project_id, entry_node_id)
        queue_head, queue_ids = api.get_queue(project_id)

        return {
            "api": api,
            "project_id": project_id,
            "entry_node_id": entry_node_id,
            "review_chain_id": reg.review_chain_id,
            "queue_head": queue_head,
            "queue_ids": queue_ids,
        }

    def _build_export_fixture(self) -> dict[str, object]:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "project")
        (learning_root / "lesson.txt").write_text("lesson body", encoding="utf-8")

        project_id = api.create_project("proj", project_root.as_posix())
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            instance = Instance.create(project_id, InstanceId("inst_manual_1"), "lesson.txt")
            system.instance_repo.add(session, instance)

            recall_point = RecallPoint(
                project_id=project_id,
                recall_point_id=RecallPointId("rp_manual_1"),
                created_at=now_utc_ms(),
                question=rich_text("What is PLM?"),
                answer=rich_text("A layered recall system."),
                anchor=Anchor(instance_id=instance.instance_id, position="t=1200"),
            )
            system.recall_point_repo.add(session, recall_point)

            snapshot = RangeSnapshot(
                project_id=project_id,
                range_id=RangeId("range_manual_1"),
                recall_point_ids=(recall_point.recall_point_id,),
            )
            system.range_repo.add(session, snapshot)

            artifact = AsrArtifact(
                project_id=project_id,
                asr_artifact_id=AsrArtifactId("asr_manual_1"),
                created_at=now_utc_ms(),
                provider=AsrProvider.WHISPER,
                producer_runtime_kind=ClientRuntimeKind.DESKTOP_NATIVE,
                recall_point_id=recall_point.recall_point_id,
                source_instance_id=instance.instance_id,
                center_ms=1200,
                pre_ms=300,
                post_ms=300,
                segments=(
                    AsrSegment(start_ms=1000, end_ms=1100, text="alpha beta"),
                    AsrSegment(start_ms=1100, end_ms=1200, text="gamma delta"),
                ),
            )
            system.asr_artifact_repo.add(session, artifact)
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        return {
            "api": api,
            "project_id": project_id,
            "instance": instance,
            "recall_point": recall_point,
            "snapshot": snapshot,
            "artifact": artifact,
        }

    def test_list_projects_excludes_deleted_projects(self) -> None:
        api, root = self._new_api()

        project_root_1, _ = self._make_project_dirs(root, "p1")
        project_root_2, _ = self._make_project_dirs(root, "p2")
        project_root_3, _ = self._make_project_dirs(root, "p3")

        project_id_1 = api.create_project("p1", project_root_1.as_posix())
        project_id_2 = api.create_project("p2", project_root_2.as_posix())
        project_id_3 = api.create_project("p3", project_root_3.as_posix())

        api.delete_project(project_id_2)

        visible_projects = api.list_projects()
        self.assertEqual(
            [str(project.project_id) for project in visible_projects],
            [str(project_id_1), str(project_id_3)],
        )

    def test_create_project_defaults_to_startup_sync_directory(self) -> None:
        api, root = self._new_api()
        project_root, _ = self._make_project_dirs(root, "videos")

        project_id = api.create_project("ml", project_root.as_posix())
        cfg = api.get_project_storage_config(project_id)

        self.assertEqual(cfg.project_root.as_posix(), project_root.as_posix())
        self.assertEqual(cfg.learning_object_root.as_posix(), "learning_objects")
        self.assertEqual(cfg.fs_sync_policy, FsSyncPolicy.STARTUP_SYNC)

    def test_create_project_auto_creates_project_dir_under_workspace_data_root(self) -> None:
        api, root = self._new_api()
        projects_root = root / "data-root"

        with patch.dict(os.environ, {"PLM_PROJECTS_ROOT": projects_root.as_posix()}):
            project_id = api.create_project("机器学习 入门")

        cfg = api.get_project_storage_config(project_id)
        project_root = Path(cfg.project_root.as_posix())
        learning_root = project_root / cfg.learning_object_root.as_posix()

        self.assertEqual(project_root.parent.resolve(), projects_root.resolve())
        self.assertTrue(project_root.is_dir())
        self.assertTrue(learning_root.is_dir())
        self.assertEqual(cfg.learning_object_root.as_posix(), "learning_objects")

    def test_startup_sync_runs_before_material_reads(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())

        instances = api.list_instances(project_id)
        object_nodes = api.list_learning_object_nodes(project_id)

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].material_id.as_posix(), "lesson.mp4")
        self.assertEqual(len(object_nodes), 2)

    def test_legacy_scan_root_migrates_to_relative_learning_object_root(self) -> None:
        cfg = ProjectStorageConfig.from_legacy_scan_root("proj_1", "C:/data/videos", updated_at=now_utc_ms())  # type: ignore[arg-type]
        self.assertEqual(cfg.project_root.as_posix(), "C:/data")
        self.assertEqual(cfg.learning_object_root.as_posix(), "videos")
        self.assertEqual(cfg.fs_sync_policy, FsSyncPolicy.STARTUP_SYNC)

    def test_persisted_dot_learning_object_root_is_rewritten_on_load(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())

        raw = self._load_raw_snapshot(root)
        raw["projects"][str(project_id)]["projectStorageConfig"]["projectRoot"] = learning_root.as_posix()
        raw["projects"][str(project_id)]["projectStorageConfig"]["learningObjectRoot"] = "."
        self._save_raw_snapshot(root, raw)

        reloaded = self._reload_api(root)
        cfg = reloaded.get_project_storage_config(project_id)
        self.assertEqual(cfg.project_root.as_posix(), project_root.as_posix())
        self.assertEqual(cfg.learning_object_root.as_posix(), "learning_objects")

        rewritten = self._load_raw_snapshot(root)
        stored_cfg = rewritten["projects"][str(project_id)]["projectStorageConfig"]
        self.assertEqual(stored_cfg["projectRoot"], project_root.as_posix())
        self.assertEqual(stored_cfg["learningObjectRoot"], "learning_objects")

    def test_add_instance_is_disabled(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")

        project_id = api.create_project("ml", project_root.as_posix())
        with self.assertRaises(PreconditionFailure):
            api.add_instance(project_id, (learning_root / "lesson.mp4").as_posix())

    def test_startup_sync_reuses_existing_instance_id_for_matching_material(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video-bytes", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            system.instance_repo.add(
                session,
                Instance.create(project_id, InstanceId("inst_legacy_1"), "lesson.mp4"),
            )
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        api.sync_learning_objects_from_fs(project_id)
        items = api.list_instances(project_id)
        self.assertEqual(len(items), 1)
        self.assertEqual(str(items[0].instance_id), "inst_legacy_1")
        self.assertEqual(items[0].material_id.as_posix(), "lesson.mp4")

    def test_list_missing_instances_does_not_trigger_startup_sync_after_restart(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        lesson_path = learning_root / "lesson.mp4"
        lesson_path.write_text("video-bytes", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())

        api.sync_learning_objects_from_fs(project_id)
        items = api.list_instances(project_id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].presence, InstancePresence.PRESENT)

        lesson_path.unlink()

        restarted_api = self._reload_api(root)
        audit_before = len(restarted_api.list_audit_log_events(project_id))
        missing_ids = restarted_api.list_missing_instances(project_id)
        self.assertEqual(missing_ids, ())
        self.assertEqual(len(restarted_api.list_audit_log_events(project_id)), audit_before)

    def test_begin_session_read_write_triggers_startup_sync_before_open(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        lesson_path = learning_root / "lesson.mp4"
        lesson_path.write_text("video-bytes", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        original_instance_id = str(api.list_instances(project_id)[0].instance_id)

        lesson_path.unlink()

        restarted_api = self._reload_api(root)
        session = restarted_api.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            self.assertEqual(session.state, "OPEN")
        finally:
            restarted_api.sys.rollback(session)

        missing_ids = restarted_api.list_missing_instances(project_id)
        self.assertEqual([str(x) for x in missing_ids], [original_instance_id])

    def test_begin_session_read_write_rejects_missing_startup_sync_root(self) -> None:
        api, root = self._new_api()
        missing_root = root / "missing-root"

        project_id = api.create_project("ml", missing_root.as_posix())
        with self.assertRaises(PreconditionFailure):
            api.begin_session(project_id, SessionMode.READ_WRITE)

    def test_bulk_remap_recall_points_instance_prunes_missing_source_instance_when_no_active_refs_remain(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        lesson_path = learning_root / "lesson.mp4"
        lesson_path.write_text("video-bytes", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        original_instance = next(item for item in api.list_instances(project_id) if item.material_id.as_posix() == "lesson.mp4")

        api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(original_instance.instance_id, position="t=0"))],
            title="Lesson 1",
        )

        renamed_path = learning_root / "lesson-renamed.mp4"
        lesson_path.rename(renamed_path)
        api.sync_learning_objects_from_fs(project_id)

        instances_after_sync = api.list_instances(project_id)
        missing_source = next(item for item in instances_after_sync if item.material_id.as_posix() == "lesson.mp4")
        present_target = next(item for item in instances_after_sync if item.material_id.as_posix() == "lesson-renamed.mp4")
        self.assertEqual(missing_source.presence, InstancePresence.MISSING)
        self.assertEqual(present_target.presence, InstancePresence.PRESENT)

        moved = api.bulk_remap_recall_points_instance(project_id, missing_source.instance_id, present_target.instance_id)
        self.assertEqual(moved, 1)
        self.assertEqual(len(api.list_recall_points_by_instance(project_id, present_target.instance_id)), 1)
        self.assertEqual(api.list_missing_instances(project_id), tuple())
        self.assertNotIn(str(missing_source.instance_id), {str(item.instance_id) for item in api.list_instances(project_id)})
        with self.assertRaises(NotFound):
            api.get_instance(project_id, missing_source.instance_id)

    def test_begin_session_read_write_skips_server_startup_sync_for_browser_local_projects(self) -> None:
        api, root = self._new_api()
        project_root, _learning_root = self._make_project_dirs(root, "videos")
        project_id = api.create_project("ml", project_root.as_posix())

        with patch.dict(
            os.environ,
            {
                "PLM_ENABLE_SERVER_MEDIA_STREAM": "true",
                "PLM_ENABLE_BROWSER_LOCAL_MEDIA": "true",
            },
            clear=False,
        ):
            report = api.import_learning_objects_from_browser_scan(
                project_id,
                root_title="Videos",
                relative_file_paths=("lesson.mp4",),
            )
            self.assertFalse(report["unchanged"])

            restarted_api = self._reload_api(root)
            session = restarted_api.begin_session(project_id, SessionMode.READ_WRITE)
            try:
                self.assertEqual(session.state, "OPEN")
            finally:
                restarted_api.sys.rollback(session)

            items = restarted_api.list_instances(project_id)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].material_id.as_posix(), "lesson.mp4")
            self.assertEqual(items[0].presence, InstancePresence.PRESENT)

            object_nodes = restarted_api.list_learning_object_nodes(project_id)
            self.assertEqual([node.title for node in object_nodes if getattr(node, "parent_id", None) is None], ["Videos"])
            self.assertFalse(any(node.title == "Files" for node in object_nodes))
            leaf_nodes = [node for node in object_nodes if hasattr(node, "instance_id")]
            self.assertEqual(len(leaf_nodes), 1)
            self.assertEqual(leaf_nodes[0].parent_id, restarted_api.list_learning_object_roots(project_id)[0])

    def test_sync_learning_objects_from_fs_noop_does_not_write_audit(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())

        first_report = api.sync_learning_objects_from_fs(project_id)
        self.assertFalse(first_report["unchanged"])
        audit_count_after_first_sync = len(api.list_audit_log_events(project_id))

        second_report = api.sync_learning_objects_from_fs(project_id)
        self.assertTrue(second_report["unchanged"])
        self.assertEqual(second_report["created_instances_count"], 0)
        self.assertEqual(second_report["marked_missing_count"], 0)
        self.assertEqual(second_report["replaced_learning_object_nodes_count"], 0)
        self.assertEqual(len(api.list_audit_log_events(project_id)), audit_count_after_first_sync)

    def test_export_recall_points_by_learning_object_node_returns_scoped_points(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        chapter_dir = learning_root / "chapter-1"
        chapter_dir.mkdir()
        (chapter_dir / "lesson-1.txt").write_text("lesson one", encoding="utf-8")
        (chapter_dir / "lesson-2.txt").write_text("lesson two", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)

        items = api.list_instances(project_id)
        instance_by_material = {item.material_id.as_posix(): item for item in items}
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            system.recall_point_repo.add(
                session,
                RecallPoint(
                    project_id=project_id,
                    recall_point_id=RecallPointId("rp_obj_scope_1"),
                    created_at=now_utc_ms(),
                    question=rich_text("lesson one?"),
                    answer=rich_text("lesson one answer"),
                    anchor=Anchor(instance_id=instance_by_material["chapter-1/lesson-1.txt"].instance_id, position="t=1000"),
                ),
            )
            system.recall_point_repo.add(
                session,
                RecallPoint(
                    project_id=project_id,
                    recall_point_id=RecallPointId("rp_obj_scope_2"),
                    created_at=now_utc_ms(),
                    question=rich_text("lesson two?"),
                    answer=rich_text("lesson two answer"),
                    anchor=Anchor(instance_id=instance_by_material["chapter-1/lesson-2.txt"].instance_id, position="t=2000"),
                ),
            )
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        root_node_id = api.list_learning_object_roots(project_id)[0]
        items = api.export_recall_points_by_learning_object_node(project_id, root_node_id)
        self.assertEqual([str(item.recall_point_id) for item in items], ["rp_obj_scope_1", "rp_obj_scope_2"])

    def test_removed_llm_api_is_not_exposed(self) -> None:
        api, root = self._new_api()
        project_root, _ = self._make_project_dirs(root, "videos")

        project_id = api.create_project("ml", project_root.as_posix())
        self.assertFalse(hasattr(api, "create_llm_session"))
        self.assertFalse(hasattr(api, "llm_chat_turn"))
        self.assertFalse(hasattr(api, "close_llm_session"))
        self.assertFalse(hasattr(api, "get_llm_session"))
        self.assertFalse(hasattr(api, "list_llm_sessions"))

    def test_project_config_does_not_store_runtime_local_services(self) -> None:
        api, root = self._new_api()
        project_root, _ = self._make_project_dirs(root, "videos")

        project_id = api.create_project("ml", project_root.as_posix())
        cfg = api.get_project_config(project_id)
        self.assertFalse(hasattr(cfg, "external_services"))
        self.assertFalse(hasattr(api, "set_external_services_config"))

    def test_request_asr_passes_configured_model_to_external_service(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]
        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=1000"))],
            title="Lesson 1",
        )
        entry_node = api.get_learning_task_node(project_id, entry_node_id)
        learning_task = api.get_learning_task(project_id, entry_node.bound_learning_task_id)  # type: ignore[attr-defined]
        recall_point_id = learning_task.recall_point_ids[0]

        captured_calls: list[dict[str, object]] = []

        def fake_extract_audio_clip(
            *,
            ffmpeg_bin: str,
            source_path: Path,
            start_ms: int,
            duration_ms: int,
            out_path: Path,
            timeout_sec: float | None = None,
        ) -> None:
            self.assertEqual(ffmpeg_bin, "ffmpeg")
            self.assertEqual(source_path, learning_root / "lesson.mp4")
            self.assertEqual(start_ms, 700)
            self.assertEqual(duration_ms, 600)
            self.assertEqual(timeout_sec, 120.0)
            out_path.write_bytes(b"wav")

        def fake_post_multipart_json(
            *,
            url: str,
            form_fields: dict[str, object],
            file_field_name: str,
            file_path: Path,
            file_name: str,
            file_content_type: str,
            api_key: str | None,
            timeout_sec: float,
        ) -> dict[str, object]:
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(file_field_name, "file")
            self.assertEqual(file_name, "clip.wav")
            self.assertEqual(file_content_type, "audio/wav")
            self.assertEqual(api_key, "sk-user-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertTrue(file_path.exists())
            captured_calls.append(form_fields)
            return {
                "segments": [
                    {
                        "start": 0.0,
                        "end": 0.4,
                        "text": "task transcript",
                    }
                ]
            }

        with (
            patch("backend.system.api.shutil.which", return_value="ffmpeg"),
            patch.object(SystemAPI, "_extract_audio_clip", side_effect=fake_extract_audio_clip),
            patch.object(SystemAPI, "_http_post_multipart_json", side_effect=fake_post_multipart_json),
        ):
            result = api.request_asr(
                project_id,
                recall_point_id,
                center_ms=1000,
                pre_ms=300,
                post_ms=300,
                service_config={
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "whisper-1",
                    "api_key": "sk-user-12345678",
                },
            )

        self.assertEqual(len(captured_calls), 1)
        self.assertEqual(captured_calls[0]["model"], "whisper-1")
        self.assertEqual(result.provider, AsrProvider.WHISPER)
        self.assertEqual(str(result.recall_point_id), str(recall_point_id))
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].text, "task transcript")

    def test_request_asr_uses_deployment_asr_service_when_request_config_missing(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]
        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=1000"))],
            title="Lesson 1",
        )
        entry_node = api.get_learning_task_node(project_id, entry_node_id)
        learning_task = api.get_learning_task(project_id, entry_node.bound_learning_task_id)  # type: ignore[attr-defined]
        recall_point_id = learning_task.recall_point_ids[0]

        captured_calls: list[dict[str, object]] = []

        def fake_extract_audio_clip(
            *,
            ffmpeg_bin: str,
            source_path: Path,
            start_ms: int,
            duration_ms: int,
            out_path: Path,
            timeout_sec: float | None = None,
        ) -> None:
            self.assertEqual(ffmpeg_bin, "ffmpeg")
            self.assertEqual(source_path, learning_root / "lesson.mp4")
            self.assertEqual(start_ms, 700)
            self.assertEqual(duration_ms, 600)
            self.assertEqual(timeout_sec, 120.0)
            out_path.write_bytes(b"wav")

        def fake_post_multipart_json(
            *,
            url: str,
            form_fields: dict[str, object],
            file_field_name: str,
            file_path: Path,
            file_name: str,
            file_content_type: str,
            api_key: str | None,
            timeout_sec: float,
        ) -> dict[str, object]:
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(api_key, "sk-env-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertTrue(file_path.exists())
            captured_calls.append(form_fields)
            return {"segments": [{"start": 0.0, "end": 0.4, "text": "env transcript"}]}

        with (
            patch.dict(
                os.environ,
                {
                    "PLM_NATIVE_ASR_BASE_URL": "https://api.openai.com/v1",
                    "PLM_NATIVE_ASR_MODEL": "whisper-1",
                    "PLM_NATIVE_ASR_API_KEY": "sk-env-12345678",
                },
                clear=False,
            ),
            patch("backend.system.api.shutil.which", return_value="ffmpeg"),
            patch.object(SystemAPI, "_extract_audio_clip", side_effect=fake_extract_audio_clip),
            patch.object(SystemAPI, "_http_post_multipart_json", side_effect=fake_post_multipart_json),
        ):
            result = api.request_asr(project_id, recall_point_id, center_ms=1000, pre_ms=300, post_ms=300)

        self.assertEqual(len(captured_calls), 1)
        self.assertEqual(captured_calls[0]["model"], "whisper-1")
        self.assertEqual(result.segments[0].text, "env transcript")

    def test_request_asr_uses_builtin_whisper_config_without_http_base_url(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]
        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=1000"))],
            title="Lesson 1",
        )
        entry_node = api.get_learning_task_node(project_id, entry_node_id)
        learning_task = api.get_learning_task(project_id, entry_node.bound_learning_task_id)  # type: ignore[attr-defined]
        recall_point_id = learning_task.recall_point_ids[0]

        captured_payloads: list[dict[str, object]] = []

        def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
            self.assertEqual(url, "http://127.0.0.1:9912/asr/request")
            self.assertIsNone(api_key)
            self.assertEqual(timeout_sec, 600.0)
            captured_payloads.append(payload)
            return {"segments": [{"startMs": 700, "endMs": 1100, "text": "builtin transcript"}]}

        with (
            patch.dict(
                os.environ,
                {
                    "PLM_NATIVE_ASR_BASE_URL": BUILTIN_WHISPER_BASE_URL,
                    "PLM_NATIVE_ASR_MODEL": "medium",
                },
                clear=False,
            ),
            patch("backend.system.api.ensure_local_whisper_runtime", return_value="http://127.0.0.1:9912"),
            patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json),
        ):
            result = api.request_asr(project_id, recall_point_id, center_ms=1000, pre_ms=300, post_ms=300)

        self.assertEqual(len(captured_payloads), 1)
        self.assertEqual(captured_payloads[0]["model"], "medium")
        self.assertEqual(result.segments[0].text, "builtin transcript")

    def test_request_asr_resolves_manual_relative_material_under_project_root(self) -> None:
        api, root = self._new_api()
        project_root = root / "manual"
        media_dir = project_root / "materials"
        media_dir.mkdir(parents=True)
        media_file = media_dir / "lesson.mp4"
        media_file.write_text("video", encoding="utf-8")

        project_id = api.create_project("manual", project_root.as_posix())
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            system.project_storage_config_repo.set(
                session,
                ProjectStorageConfig.create(
                    project_id=project_id,
                    project_root=project_root.as_posix(),
                    learning_object_root="learning_objects",
                    fs_sync_policy=FsSyncPolicy.DISABLED,
                    updated_at=now_utc_ms(),
                ),
            )
            instance = Instance.create(project_id, InstanceId("inst_manual_rel_1"), "materials/lesson.mp4")
            system.instance_repo.add(session, instance)
            recall_point = RecallPoint(
                project_id=project_id,
                recall_point_id=RecallPointId("rp_manual_rel_1"),
                created_at=now_utc_ms(),
                question=rich_text("Q1"),
                answer=rich_text("A1"),
                anchor=Anchor(instance.instance_id, position="t=1000"),
            )
            system.recall_point_repo.add(session, recall_point)
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        captured_source_paths: list[Path] = []

        def fake_extract_audio_clip(
            *,
            ffmpeg_bin: str,
            source_path: Path,
            start_ms: int,
            duration_ms: int,
            out_path: Path,
            timeout_sec: float | None = None,
        ) -> None:
            self.assertEqual(ffmpeg_bin, "ffmpeg")
            self.assertEqual(start_ms, 700)
            self.assertEqual(duration_ms, 600)
            self.assertEqual(timeout_sec, 120.0)
            captured_source_paths.append(source_path)
            out_path.write_bytes(b"wav")

        def fake_post_multipart_json(
            *,
            url: str,
            form_fields: dict[str, object],
            file_field_name: str,
            file_path: Path,
            file_name: str,
            file_content_type: str,
            api_key: str | None,
            timeout_sec: float,
        ) -> dict[str, object]:
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(api_key, "sk-manual-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertTrue(file_path.exists())
            return {"segments": [{"start": 0.0, "end": 0.4, "text": "manual transcript"}]}

        with (
            patch("backend.system.api.shutil.which", return_value="ffmpeg"),
            patch.object(SystemAPI, "_extract_audio_clip", side_effect=fake_extract_audio_clip),
            patch.object(SystemAPI, "_http_post_multipart_json", side_effect=fake_post_multipart_json),
        ):
            result = api.request_asr(
                project_id,
                RecallPointId("rp_manual_rel_1"),
                center_ms=1000,
                pre_ms=300,
                post_ms=300,
                service_config={
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "whisper-1",
                    "api_key": "sk-manual-12345678",
                },
            )

        self.assertEqual(result.segments[0].text, "manual transcript")
        self.assertEqual(captured_source_paths, [media_file.resolve()])

    def test_request_asr_from_audio_upload_uses_uploaded_clip_without_server_ffmpeg(self) -> None:
        api, root = self._new_api()
        project_root = root / "browser_local"
        project_root.mkdir(parents=True)
        project_id = api.create_project("browser-local", project_root.as_posix())
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            instance = Instance.create(project_id, InstanceId("inst_browser_local_1"), "lesson/clip.mp4")
            system.instance_repo.add(session, instance)
            recall_point = RecallPoint(
                project_id=project_id,
                recall_point_id=RecallPointId("rp_browser_local_1"),
                created_at=now_utc_ms(),
                question=rich_text("Q1"),
                answer=rich_text("A1"),
                anchor=Anchor(instance.instance_id, position="t=1000"),
            )
            system.recall_point_repo.add(session, recall_point)
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        captured_calls: list[dict[str, object]] = []

        def fake_post_multipart_json(
            *,
            url: str,
            form_fields: dict[str, object],
            file_field_name: str,
            file_path: Path,
            file_name: str,
            file_content_type: str,
            api_key: str | None,
            timeout_sec: float,
        ) -> dict[str, object]:
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(file_field_name, "file")
            self.assertEqual(file_name, "browser-clip.wav")
            self.assertEqual(file_content_type, "audio/wav")
            self.assertEqual(api_key, "sk-browser-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertEqual(file_path.read_bytes(), b"wav")
            captured_calls.append(form_fields)
            return {"segments": [{"start": 0.0, "end": 0.5, "text": "browser transcript"}]}

        with patch.object(SystemAPI, "_http_post_multipart_json", side_effect=fake_post_multipart_json):
            result = api.request_asr_from_audio_upload(
                project_id,
                RecallPointId("rp_browser_local_1"),
                center_ms=1000,
                pre_ms=300,
                post_ms=300,
                audio_bytes=b"wav",
                audio_filename="browser-clip.wav",
                audio_content_type="audio/wav",
                service_config={
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "whisper-1",
                    "api_key": "sk-browser-12345678",
                },
            )

        self.assertEqual(len(captured_calls), 1)
        self.assertEqual(captured_calls[0]["model"], "whisper-1")
        self.assertEqual(result.provider, AsrProvider.WHISPER)
        self.assertEqual(str(result.recall_point_id), "rp_browser_local_1")
        self.assertEqual(result.segments[0].text, "browser transcript")

    def test_request_asr_uses_dashscope_native_file_transcription_for_fun_asr_models(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "dashscope_videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("dashscope", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]
        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=1000"))],
            title="Lesson 1",
        )
        entry_node = api.get_learning_task_node(project_id, entry_node_id)
        learning_task = api.get_learning_task(project_id, entry_node.bound_learning_task_id)  # type: ignore[attr-defined]
        recall_point_id = learning_task.recall_point_ids[0]

        captured_submit_calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []
        captured_get_urls: list[str] = []

        def fake_extract_audio_clip(
            *,
            ffmpeg_bin: str,
            source_path: Path,
            start_ms: int,
            duration_ms: int,
            out_path: Path,
            timeout_sec: float | None = None,
        ) -> None:
            self.assertEqual(ffmpeg_bin, "ffmpeg")
            self.assertEqual(source_path, learning_root / "lesson.mp4")
            self.assertEqual(start_ms, 700)
            self.assertEqual(duration_ms, 600)
            self.assertEqual(timeout_sec, 120.0)
            out_path.write_bytes(b"wav")

        def fake_post_json(
            *,
            url: str,
            payload: dict[str, object] | None,
            api_key: str | None,
            timeout_sec: float,
            extra_headers: dict[str, str] | None = None,
        ) -> dict[str, object]:
            captured_submit_calls.append((url, {} if payload is None else payload, extra_headers))
            self.assertEqual(url, "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription")
            self.assertEqual(api_key, "sk-dashscope-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertEqual(extra_headers, {"X-DashScope-Async": "enable"})
            self.assertEqual(payload, {"model": "fun-asr-mtl", "input": {"file_urls": ["https://plm.xuebao.chat/api/public/asr-bridge/token-123/clip.wav"]}})
            return {"output": {"task_id": "task-123"}}

        def fake_get_json(
            *,
            url: str,
            api_key: str | None,
            timeout_sec: float,
            extra_headers: dict[str, str] | None = None,
        ) -> dict[str, object]:
            captured_get_urls.append(url)
            self.assertIsNone(extra_headers)
            if url == "https://dashscope.aliyuncs.com/api/v1/tasks/task-123":
                self.assertEqual(api_key, "sk-dashscope-12345678")
                self.assertEqual(timeout_sec, 60.0)
                return {
                    "output": {
                        "task_status": "SUCCEEDED",
                        "results": [
                            {
                                "subtask_status": "SUCCEEDED",
                                "transcription_url": "https://dashscope-result.example/result.json",
                            }
                        ],
                    }
                }
            if url == "https://dashscope-result.example/result.json":
                self.assertIsNone(api_key)
                self.assertEqual(timeout_sec, 60.0)
                return {
                    "transcripts": [
                        {
                            "sentences": [
                                {
                                    "begin_time": 0,
                                    "end_time": 400,
                                    "text": "dashscope transcript",
                                }
                            ]
                        }
                    ]
                }
            raise AssertionError(f"Unexpected GET url: {url}")

        with (
            patch("backend.system.api.shutil.which", return_value="ffmpeg"),
            patch.object(SystemAPI, "_extract_audio_clip", side_effect=fake_extract_audio_clip),
            patch.object(SystemAPI, "_register_public_asr_temp_asset", return_value=("token-123", "https://plm.xuebao.chat/api/public/asr-bridge/token-123/clip.wav")),
            patch.object(SystemAPI, "_unregister_public_asr_temp_asset") as unregister_mock,
            patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json),
            patch.object(SystemAPI, "_http_get_json", side_effect=fake_get_json),
            patch.object(SystemAPI, "_http_post_multipart_json") as multipart_mock,
        ):
            result = api.request_asr(
                project_id,
                recall_point_id,
                center_ms=1000,
                pre_ms=300,
                post_ms=300,
                service_config={
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model_name": "fun-asr-mtl",
                    "api_key": "sk-dashscope-12345678",
                },
            )

        self.assertEqual(len(captured_submit_calls), 1)
        self.assertEqual(
            captured_get_urls,
            [
                "https://dashscope.aliyuncs.com/api/v1/tasks/task-123",
                "https://dashscope-result.example/result.json",
            ],
        )
        multipart_mock.assert_not_called()
        unregister_mock.assert_called_once_with("token-123")
        self.assertEqual(result.segments[0].text, "dashscope transcript")
        self.assertEqual(result.segments[0].start_ms, 700)
        self.assertEqual(result.segments[0].end_ms, 1100)

    def test_request_instance_asr_extracts_server_clip_without_recall_point_binding(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "subtitle_videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("subtitle-project", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]

        captured_calls: list[dict[str, object]] = []

        def fake_extract_audio_clip(
            *,
            ffmpeg_bin: str,
            source_path: Path,
            start_ms: int,
            duration_ms: int,
            out_path: Path,
            timeout_sec: float | None = None,
        ) -> None:
            self.assertEqual(ffmpeg_bin, "ffmpeg")
            self.assertEqual(source_path, learning_root / "lesson.mp4")
            self.assertEqual(start_ms, 120000)
            self.assertEqual(duration_ms, 90000)
            self.assertEqual(timeout_sec, 120.0)
            out_path.write_bytes(b"wav")

        def fake_post_multipart_json(
            *,
            url: str,
            form_fields: dict[str, object],
            file_field_name: str,
            file_path: Path,
            file_name: str,
            file_content_type: str,
            api_key: str | None,
            timeout_sec: float,
        ) -> dict[str, object]:
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(file_field_name, "file")
            self.assertEqual(file_name, "clip.wav")
            self.assertEqual(file_content_type, "audio/wav")
            self.assertEqual(api_key, "sk-instance-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertTrue(file_path.exists())
            captured_calls.append(form_fields)
            return {"segments": [{"start": 0.0, "end": 0.5, "text": "subtitle chunk"}]}

        with (
            patch("backend.system.api.shutil.which", return_value="ffmpeg"),
            patch.object(SystemAPI, "_extract_audio_clip", side_effect=fake_extract_audio_clip),
            patch.object(SystemAPI, "_http_post_multipart_json", side_effect=fake_post_multipart_json),
        ):
            result = api.request_instance_asr(
                project_id,
                instance.instance_id,
                start_ms=120000,
                end_ms=210000,
                service_config={
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "whisper-1",
                    "api_key": "sk-instance-12345678",
                },
            )

        self.assertEqual(len(captured_calls), 1)
        self.assertEqual(captured_calls[0]["model"], "whisper-1")
        self.assertEqual(result.provider, AsrProvider.WHISPER)
        self.assertEqual(str(result.source_instance_id), str(instance.instance_id))
        self.assertEqual(result.start_ms, 120000)
        self.assertEqual(result.end_ms, 210000)
        self.assertEqual(result.segments[0].text, "subtitle chunk")

    def test_request_instance_asr_from_audio_upload_uses_uploaded_chunk_without_server_ffmpeg(self) -> None:
        api, root = self._new_api()
        project_root = root / "browser_subtitles"
        project_root.mkdir(parents=True)
        project_id = api.create_project("browser-subtitles", project_root.as_posix())
        system = api.sys
        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            instance_id = InstanceId("inst_browser_subtitle_1")
            system.instance_repo.add(session, Instance.create(project_id, instance_id, "lesson/clip.mp4"))
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        captured_calls: list[dict[str, object]] = []

        def fake_post_multipart_json(
            *,
            url: str,
            form_fields: dict[str, object],
            file_field_name: str,
            file_path: Path,
            file_name: str,
            file_content_type: str,
            api_key: str | None,
            timeout_sec: float,
        ) -> dict[str, object]:
            self.assertEqual(url, "https://api.openai.com/v1/audio/transcriptions")
            self.assertEqual(file_field_name, "file")
            self.assertEqual(file_name, "subtitle.wav")
            self.assertEqual(file_content_type, "audio/wav")
            self.assertEqual(api_key, "sk-subtitle-12345678")
            self.assertEqual(timeout_sec, 120.0)
            self.assertEqual(file_path.read_bytes(), b"wav")
            captured_calls.append(form_fields)
            return {"segments": [{"start": 0.0, "end": 0.5, "text": "browser subtitle"}]}

        with patch.object(SystemAPI, "_http_post_multipart_json", side_effect=fake_post_multipart_json):
            result = api.request_instance_asr_from_audio_upload(
                project_id,
                instance_id,
                start_ms=0,
                end_ms=45000,
                audio_bytes=b"wav",
                audio_filename="subtitle.wav",
                audio_content_type="audio/wav",
                service_config={
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "whisper-1",
                    "api_key": "sk-subtitle-12345678",
                },
            )

        self.assertEqual(len(captured_calls), 1)
        self.assertEqual(captured_calls[0]["model"], "whisper-1")
        self.assertEqual(result.provider, AsrProvider.WHISPER)
        self.assertEqual(str(result.source_instance_id), str(instance_id))
        self.assertEqual(result.start_ms, 0)
        self.assertEqual(result.end_ms, 45000)
        self.assertEqual(result.segments[0].text, "browser subtitle")

    def test_get_instance_subtitle_file_reads_same_stem_subtitle(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "subtitle_files")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")
        (learning_root / "lesson.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,500\n第一行字幕\n\n2\n00:00:03,000 --> 00:00:04,000\nSecond line\n",
            encoding="utf-8",
        )

        project_id = api.create_project("subtitle-files", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]

        result = api.get_instance_subtitle_file(project_id, instance.instance_id)

        self.assertTrue(result["found"])
        self.assertEqual(result["instanceId"], str(instance.instance_id))
        self.assertEqual(result["fileName"], "lesson.srt")
        self.assertEqual(result["format"], "srt")
        segments = result["segments"]
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["startMs"], 1000)
        self.assertEqual(segments[0]["endMs"], 2500)
        self.assertEqual(segments[0]["text"], "第一行字幕")
        self.assertEqual(segments[1]["text"], "Second line")

    def test_request_project_llm_text_appends_supplemental_context(self) -> None:
        api, root = self._new_api()
        project_root, _ = self._make_project_dirs(root, "llm_subtitle_context")
        project_id = api.create_project("llm-subtitle-context", project_root.as_posix())

        captured_messages: list[dict[str, str]] = []

        def fake_request_llm_chat_completion(*args, **kwargs):
            nonlocal captured_messages
            captured_messages = kwargs["messages"]
            return {"choices": [{"message": {"content": "ok"}}]}

        with patch.object(SystemAPI, "request_llm_chat_completion", side_effect=fake_request_llm_chat_completion):
            content = api.request_project_llm_text(
                project_id=project_id,
                user_prompt="请总结一下",
                supplemental_context="Supplemental subtitle context for test.",
            )

        self.assertEqual(content, "ok")
        self.assertGreaterEqual(len(captured_messages), 3)
        self.assertEqual(captured_messages[1]["role"], "system")
        self.assertIn("Project Context", captured_messages[1]["content"])
        self.assertEqual(captured_messages[2]["role"], "system")
        self.assertEqual(captured_messages[2]["content"], "Supplemental subtitle context for test.")

    def test_deleted_recall_point_stays_historical_but_leaves_current_views(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]

        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=1000"))],
            title="Lesson 1",
        )
        entry_node = api.get_learning_task_node(project_id, entry_node_id)
        learning_task = api.get_learning_task(project_id, entry_node.bound_learning_task_id)  # type: ignore[attr-defined]
        recall_point_id = learning_task.recall_point_ids[0]
        learning_object_leaf = next(
            node
            for node in api.list_learning_object_nodes(project_id)
            if getattr(node, "instance_id", None) == instance.instance_id
        )

        system = api.sys
        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            system.asr_artifact_repo.add(
                session,
                AsrArtifact(
                    project_id=project_id,
                    asr_artifact_id=AsrArtifactId("asr_deleted_scope_1"),
                    created_at=now_utc_ms(),
                    provider=AsrProvider.WHISPER,
                    producer_runtime_kind=ClientRuntimeKind.DESKTOP_NATIVE,
                    recall_point_id=recall_point_id,
                    source_instance_id=instance.instance_id,
                    center_ms=1000,
                    pre_ms=300,
                    post_ms=300,
                    segments=(AsrSegment(start_ms=900, end_ms=1100, text="task transcript"),),
                ),
            )
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        api.delete_recall_point(project_id, recall_point_id)

        deleted = api.get_recall_point(project_id, recall_point_id)
        self.assertEqual(deleted.state, RecallPointState.DELETED)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(str(api.get_asr_artifact(project_id, AsrArtifactId("asr_deleted_scope_1")).recall_point_id), str(recall_point_id))
        self.assertTrue(
            any(event.api_name == "delete_recall_point" for event in api.list_audit_log_events(project_id))
        )

        api.edit_learning_task(project_id, learning_task.learning_task_id, "Lesson 1 Renamed")
        renamed = api.get_learning_task(project_id, learning_task.learning_task_id)
        self.assertEqual(renamed.title, "Lesson 1 Renamed")
        self.assertEqual(tuple(renamed.recall_point_ids), tuple(learning_task.recall_point_ids))

        self.assertEqual(api.list_recall_points_by_instance(project_id, instance.instance_id), tuple())
        self.assertEqual(api.list_recall_points_by_learning_task_node(project_id, entry_node_id), tuple())
        self.assertEqual(api.export_recall_points_by_learning_task_node(project_id, entry_node_id), tuple())
        self.assertEqual(api.list_recall_points_by_learning_object_node(project_id, learning_object_leaf.node_id), tuple())
        self.assertEqual(api.export_recall_points_by_learning_object_node(project_id, learning_object_leaf.node_id), tuple())
        self.assertEqual(api.export_asr_by_learning_task_node(project_id, entry_node_id), tuple())
        self.assertEqual(api.export_asr_by_learning_object_node(project_id, learning_object_leaf.node_id), tuple())

        read_session = system.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            historical_instances = system.learning_task_repo.covered_instance_id_set(
                read_session,
                learning_task.learning_task_id,
                system.recall_point_repo,
            )
            self.assertEqual(historical_instances, {instance.instance_id})
        finally:
            system.rollback(read_session)

        with self.assertRaises(PreconditionFailure):
            api.request_asr(project_id, recall_point_id, center_ms=1000, pre_ms=300, post_ms=300)

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cfg = system.project_config_repo.get(session)
            system.project_config_repo.set(
                session,
                ProjectConfig(
                    project_id=cfg.project_id,
                    layer_configs=dict(cfg.layer_configs),
                    push_config=RecallPointPushConfig(
                        min_recall_points_to_enable=1,
                        max_history_len=cfg.push_config.max_history_len,
                    ),
                    updated_at=now_utc_ms(),
                ),
            )
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        self.assertEqual(api.get_push_candidates(project_id, max_results=5), tuple())

    def test_export_asr_by_learning_task_node_returns_scoped_artifacts(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]

        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=1000"))],
            title="Lesson 1",
        )

        learning_task = api.get_learning_task(project_id, api.get_learning_task_node(project_id, entry_node_id).bound_learning_task_id)  # type: ignore[attr-defined]
        scoped_rp_id = learning_task.recall_point_ids[0]
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            system.asr_artifact_repo.add(
                session,
                AsrArtifact(
                    project_id=project_id,
                    asr_artifact_id=AsrArtifactId("asr_task_1"),
                    created_at=now_utc_ms(),
                    provider=AsrProvider.WHISPER,
                    producer_runtime_kind=ClientRuntimeKind.DESKTOP_NATIVE,
                    recall_point_id=scoped_rp_id,
                    source_instance_id=instance.instance_id,
                    center_ms=1000,
                    pre_ms=300,
                    post_ms=300,
                    segments=(AsrSegment(start_ms=900, end_ms=1100, text="task transcript"),),
                ),
            )
            system.commit(session)
        except Exception:
            if session.state == "OPEN":
                system.rollback(session)
            raise

        items = api.export_asr_by_learning_task_node(project_id, entry_node_id)
        self.assertEqual([str(item.asr_artifact_id) for item in items], ["asr_task_1"])

    def test_default_aggregation_title_keeps_layer_suffix_and_avoids_duplicates(self) -> None:
        api, root = self._new_api()
        project_root, _ = self._make_project_dirs(root, "videos")
        project_id = api.create_project("ml", project_root.as_posix())
        system = api.sys

        session = system.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            system.learning_task_node_repo.add(
                session,
                LearningTaskContainer(
                    project_id=project_id,
                    node_id="agg_existing_1",
                    parent_id=None,
                    children=tuple(),
                    title="聚合节点@L1",
                ),
            )
            system.learning_task_node_repo.add(
                session,
                LearningTaskContainer(
                    project_id=project_id,
                    node_id="agg_existing_2",
                    parent_id=None,
                    children=tuple(),
                    title="聚合节点@L1-2",
                ),
            )

            self.assertEqual(api._next_default_aggregation_title(session, 0), "聚合节点@L0")
            self.assertEqual(api._next_default_aggregation_title(session, 1), "聚合节点@L1-3")
        finally:
            if session.state == "OPEN":
                system.rollback(session)

    def test_learning_task_and_review_chain_bindings_are_resolvable(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]
        entry_node_id = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=0"))],
            title="Lesson 1",
        )

        entry_node = api.get_learning_task_node(project_id, entry_node_id)
        self.assertIsInstance(entry_node, LearningTaskLeaf)
        assert isinstance(entry_node, LearningTaskLeaf)

        task = api.get_learning_task(project_id, entry_node.bound_learning_task_id)
        self.assertEqual(task.title, "Lesson 1")
        self.assertEqual(task.size, 1)

        reg_from_task = api.get_learning_task_entry_registration(project_id, entry_node.bound_learning_task_id)
        self.assertEqual(reg_from_task.entry_node, entry_node_id)

        reg_from_chain = api.get_review_chain_entry_registration(project_id, reg_from_task.review_chain_id)
        self.assertEqual(reg_from_chain.entry_node, entry_node_id)
        self.assertEqual(reg_from_chain.target_layer_index, 0)
        self.assertEqual(reg_from_chain.registration_seq, 1)

    def test_review_task_head_template_enqueues_on_first_tick(self) -> None:
        fx = self._build_review_then_convergence_fixture()
        api = fx["api"]
        project_id = fx["project_id"]
        review_chain_id = fx["review_chain_id"]
        queue_head = fx["queue_head"]
        queue_ids = fx["queue_ids"]

        chain = api.get_review_chain(project_id, review_chain_id)
        head = chain.head_item()
        self.assertIsNotNone(head)
        assert head is not None
        self.assertEqual(head.kind, ReviewChainItemKind.REVIEW_TASK)
        self.assertIsNotNone(queue_head)
        self.assertEqual(queue_ids, (queue_head,))
        self.assertEqual(str(queue_head), str(head.id))

    def test_done_review_task_head_produces_followup_task_on_next_tick(self) -> None:
        fx = self._build_review_then_convergence_fixture()
        api = fx["api"]
        project_id = fx["project_id"]
        review_chain_id = fx["review_chain_id"]
        first_head = fx["queue_head"]

        self.assertIsNotNone(first_head)
        assert first_head is not None
        api.executor_commit_review_task(project_id, first_head, [0])

        empty_head, empty_queue = api.get_queue(project_id)
        self.assertIsNone(empty_head)
        self.assertEqual(empty_queue, tuple())

        tick_res = self._tick_once(api, project_id, 0)
        self.assertEqual(tick_res, TickAttemptResult.PRODUCED)

        chain = api.get_review_chain(project_id, review_chain_id)
        head = chain.head_item()
        self.assertIsNotNone(head)
        assert head is not None
        self.assertEqual(head.kind, ReviewChainItemKind.CONVERGENCE)

        next_head, next_queue = api.get_queue(project_id)
        self.assertIsNotNone(next_head)
        self.assertEqual(next_queue, (next_head,))
        self.assertNotEqual(str(next_head), str(first_head))

    def test_submit_b_batches_old_chain_before_new_chain(self) -> None:
        fx = self._build_review_then_convergence_fixture()
        api = fx["api"]
        project_id = fx["project_id"]
        first_head = fx["queue_head"]

        self.assertIsNotNone(first_head)
        assert first_head is not None
        api.executor_commit_review_task(project_id, first_head, [0])

        empty_head, empty_queue = api.get_queue(project_id)
        self.assertIsNone(empty_head)
        self.assertEqual(empty_queue, tuple())

        instance = api.list_instances(project_id)[0]
        entry_node_b = api.submit_learning_task(
            project_id,
            items=[(rich_text("Q2"), rich_text("A2"), Anchor(instance.instance_id, position="t=10"))],
            title="Lesson 2",
        )

        reg_a = api.get_learning_task_node_entry_registration(project_id, fx["entry_node_id"])
        reg_b = api.get_learning_task_node_entry_registration(project_id, entry_node_b)
        self.assertEqual(reg_a.registration_seq, 1)
        self.assertEqual(reg_b.registration_seq, 2)

        queue_head, queue_ids = api.get_queue(project_id)
        self.assertEqual(len(queue_ids), 2)
        self.assertEqual(queue_head, queue_ids[0])

        chain_a = api.get_review_chain(project_id, reg_a.review_chain_id)
        head_a = chain_a.head_item()
        self.assertIsNotNone(head_a)
        assert head_a is not None
        self.assertEqual(head_a.kind, ReviewChainItemKind.CONVERGENCE)
        convergence_a = api.get_convergence(project_id, head_a.id)
        self.assertEqual(str(queue_ids[0]), str(convergence_a.review_task_ids[-1]))

        chain_b = api.get_review_chain(project_id, reg_b.review_chain_id)
        head_b = chain_b.head_item()
        self.assertIsNotNone(head_b)
        assert head_b is not None
        self.assertEqual(head_b.kind, ReviewChainItemKind.REVIEW_TASK)
        self.assertEqual(str(queue_ids[1]), str(head_b.id))

    def test_orchestrator_tick_stays_blocked_while_global_queue_non_empty(self) -> None:
        fx = self._build_review_then_convergence_fixture()
        api = fx["api"]
        project_id = fx["project_id"]
        review_chain_id = fx["review_chain_id"]

        before_chain = api.get_review_chain(project_id, review_chain_id)
        before_head, before_queue = api.get_queue(project_id)

        self.assertIsNotNone(before_head)
        self.assertEqual(before_queue, (before_head,))

        tick_res = self._tick_once(api, project_id, 0)
        self.assertEqual(tick_res, TickAttemptResult.GATE_BLOCKED)

        after_chain = api.get_review_chain(project_id, review_chain_id)
        after_head, after_queue = api.get_queue(project_id)
        self.assertEqual(after_chain.head_index, before_chain.head_index)
        self.assertEqual(after_chain.queue, before_chain.queue)
        self.assertEqual(after_head, before_head)
        self.assertEqual(after_queue, before_queue)

    def test_first_failed_review_does_not_immediately_enqueue_followup_round(self) -> None:
        api, root = self._new_api()
        project_root, learning_root = self._make_project_dirs(root, "videos")
        (learning_root / "lesson.mp4").write_text("video", encoding="utf-8")

        project_id = api.create_project("ml", project_root.as_posix())
        api.sync_learning_objects_from_fs(project_id)
        instance = api.list_instances(project_id)[0]

        api.submit_learning_task(
            project_id,
            items=[(rich_text("Q1"), rich_text("A1"), Anchor(instance.instance_id, position="t=0"))],
            title="Lesson 1",
        )
        first_head, first_queue = api.get_queue(project_id)
        self.assertIsNotNone(first_head)
        self.assertEqual(len(first_queue), 1)

        assert first_head is not None
        api.executor_commit_review_task(project_id, first_head, [0])

        next_head, next_queue = api.get_queue(project_id)
        self.assertIsNone(next_head)
        self.assertEqual(next_queue, tuple())


class TestSpecAlignmentJson(_SpecAlignmentBackendMixin, unittest.TestCase):
    BACKEND = "json"


class TestSpecAlignmentSQLite(_SpecAlignmentBackendMixin, unittest.TestCase):
    BACKEND = "sqlite"


class TestSpecAlignmentPostgres(_SpecAlignmentBackendMixin, unittest.TestCase):
    BACKEND = "postgres"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        dsn = os.getenv("PLM_TEST_POSTGRES_DSN", "").strip()
        if not dsn:
            raise unittest.SkipTest("set PLM_TEST_POSTGRES_DSN to run PostgreSQL spec alignment tests")
        if psycopg is None:
            raise unittest.SkipTest("psycopg is required to run PostgreSQL spec alignment tests")
        cls.POSTGRES_DSN = dsn


if __name__ == "__main__":
    unittest.main()
