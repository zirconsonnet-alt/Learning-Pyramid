import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.models.asr_artifact import AsrArtifact, AsrSegment
from backend.models.enums import AsrProvider, FsSyncPolicy, InstancePresence, SessionMode
from backend.models.errors import PreconditionFailure
from backend.models.instance import Instance
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf
from backend.models.project_config import LocalServiceConfig
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.rich_content import rich_text
from backend.models.types import (
    AsrArtifactId,
    InstanceId,
    RangeId,
    RecallPointId,
    now_utc_ms,
)
from backend.system.api import SystemAPI
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

    def test_set_external_services_config_updates_project_config(self) -> None:
        api, root = self._new_api()
        project_root, _ = self._make_project_dirs(root, "videos")

        project_id = api.create_project("ml", project_root.as_posix())
        api.set_external_services_config(
            project_id,
            asr=LocalServiceConfig(
                base_url="http://127.0.0.1:9001",
                api_key="asr-secret",
                model="small",
            ),
        )

        cfg = api.get_project_config(project_id)
        self.assertIsNotNone(cfg.external_services.asr)
        self.assertEqual(cfg.external_services.asr.base_url, "http://127.0.0.1:9001")
        self.assertEqual(cfg.external_services.asr.api_key, "asr-secret")
        self.assertEqual(cfg.external_services.asr.model, "small")

        audit_tail = api.list_audit_log_events(project_id)[-1]
        self.assertEqual(audit_tail.api_name, "set_external_services_config")
        self.assertNotIn("asr-secret", audit_tail.payload)

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
        api.set_external_services_config(
            project_id,
            asr=LocalServiceConfig(base_url="http://127.0.0.1:9001", model="small"),
        )

        captured_payloads: list[dict[str, object]] = []

        def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
            self.assertEqual(url, "http://127.0.0.1:9001/asr/request")
            self.assertIsNone(api_key)
            self.assertEqual(timeout_sec, 60.0)
            captured_payloads.append(payload)
            return {
                "segments": [
                    {
                        "startMs": 700,
                        "endMs": 1100,
                        "text": "task transcript",
                    }
                ]
            }

        with patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json):
            artifact_id = api.request_asr(project_id, recall_point_id, center_ms=1000, pre_ms=300, post_ms=300)

        self.assertTrue(str(artifact_id))
        self.assertEqual(len(captured_payloads), 1)
        self.assertEqual(captured_payloads[0]["provider"], "WHISPER")
        self.assertEqual(captured_payloads[0]["model"], "small")

    def test_request_asr_uses_local_whisper_when_config_is_missing(self) -> None:
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
            self.assertEqual(url, "http://127.0.0.1:9911/asr/request")
            self.assertIsNone(api_key)
            self.assertEqual(timeout_sec, 600.0)
            captured_payloads.append(payload)
            return {"segments": [{"startMs": 700, "endMs": 1100, "text": "auto transcript"}]}

        with (
            patch("backend.system.api.can_auto_use_local_whisper", return_value=True),
            patch("backend.system.api.ensure_local_whisper_runtime", return_value="http://127.0.0.1:9911"),
            patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json),
        ):
            artifact_id = api.request_asr(project_id, recall_point_id, center_ms=1000, pre_ms=300, post_ms=300)

        self.assertTrue(str(artifact_id))
        self.assertEqual(len(captured_payloads), 1)
        self.assertIsNone(captured_payloads[0]["model"])

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
        api.set_external_services_config(
            project_id,
            asr=LocalServiceConfig(base_url=BUILTIN_WHISPER_BASE_URL, model="medium"),
        )

        captured_payloads: list[dict[str, object]] = []

        def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
            self.assertEqual(url, "http://127.0.0.1:9912/asr/request")
            self.assertIsNone(api_key)
            self.assertEqual(timeout_sec, 600.0)
            captured_payloads.append(payload)
            return {"segments": [{"startMs": 700, "endMs": 1100, "text": "builtin transcript"}]}

        with (
            patch("backend.system.api.ensure_local_whisper_runtime", return_value="http://127.0.0.1:9912"),
            patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json),
        ):
            artifact_id = api.request_asr(project_id, recall_point_id, center_ms=1000, pre_ms=300, post_ms=300)

        self.assertTrue(str(artifact_id))
        self.assertEqual(len(captured_payloads), 1)
        self.assertEqual(captured_payloads[0]["model"], "medium")

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

        api.set_external_services_config(
            project_id,
            asr=LocalServiceConfig(base_url="http://127.0.0.1:9001", model="small"),
        )

        captured_payloads: list[dict[str, object]] = []

        def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
            self.assertEqual(url, "http://127.0.0.1:9001/asr/request")
            self.assertIsNone(api_key)
            self.assertEqual(timeout_sec, 60.0)
            captured_payloads.append(payload)
            return {"segments": [{"startMs": 700, "endMs": 1100, "text": "manual transcript"}]}

        with patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json):
            artifact_id = api.request_asr(project_id, RecallPointId("rp_manual_rel_1"), center_ms=1000, pre_ms=300, post_ms=300)

        self.assertTrue(str(artifact_id))
        self.assertEqual(len(captured_payloads), 1)
        source = captured_payloads[0]["source"]
        self.assertIsInstance(source, dict)
        self.assertEqual(source["filePath"], str(media_file.resolve()))

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
