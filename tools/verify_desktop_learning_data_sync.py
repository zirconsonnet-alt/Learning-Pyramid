import argparse
import sys
import tempfile
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.models.enums import ReviewChainTemplateItemKind
from backend.models.recall_point import Anchor
from backend.models.rich_content import RichContent, rich_text
from backend.models.review_chain import ReviewChainItemKind
from backend.models.types import InstanceId, RecallPointId, id_canonical_text
from backend.system.api import SystemAPI
from backend.system.backend_verification_gate import GateCheck, GateStatus, run_gate
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore


def _api(store_path: Path) -> SystemAPI:
    return SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_path)))


def _plain_text(content: RichContent) -> str:
    return "\n".join(str(block.text or "") for block in content if getattr(block.kind, "value", "") == "TEXT")


def _one(items: Sequence[object], label: str) -> object:
    if len(items) != 1:
        raise RuntimeError(f"expected exactly one {label}, got {len(items)}")
    return items[0]


def _first_instance_id(api: SystemAPI, project_id: object) -> InstanceId:
    instances = api.list_instances(project_id)  # type: ignore[arg-type]
    if not instances:
        raise RuntimeError("browser import did not create any instance")
    return instances[0].instance_id


def _first_review_task_id(api: SystemAPI, project_id: object, entry_node_id: object) -> object:
    registration = api.get_learning_task_node_entry_registration(project_id, entry_node_id)  # type: ignore[arg-type]
    chain = api.get_review_chain(project_id, registration.review_chain_id)  # type: ignore[arg-type]
    for item in chain.queue:
        if item.kind == ReviewChainItemKind.REVIEW_TASK:
            return item.id
    raise RuntimeError("submitted learning task did not create a review task")


def _assert_default_review_template_contains_review_task(api: SystemAPI, project_id: object) -> None:
    config = api.get_project_config(project_id)  # type: ignore[arg-type]
    template = config.layer_configs[0].review_chain_template
    if not any(item.kind == ReviewChainTemplateItemKind.REVIEW_TASK for item in template):
        raise RuntimeError("default review template does not contain REVIEW_TASK")


def run_learning_data_sync_smoke(store_path: Path) -> GateStatus:
    try:
        writer = _api(store_path)
        subject_id = writer.create_subject("Desktop Learning Data Sync Gate")
        material = _one(writer.list_subject_materials(subject_id), "subject material")
        if material.scoped_project_id is None or material.internal_project_id is None:
            return GateStatus.failed(
                "created subject material relationship is incomplete",
                details={"subjectId": str(subject_id)},
            )
        project_id = material.internal_project_id
        scoped_project_id = material.scoped_project_id

        import_report = writer.import_learning_objects_from_browser_scan(
            project_id,
            root_title="Desktop Sync Fixture",
            relative_file_paths=("lesson-a.mp4", "module/lesson-b.mp4"),
        )
        if int(import_report.get("created_instances_count", 0)) != 2:
            raise RuntimeError(f"browser import created unexpected instances: {import_report}")

        instance_id = _first_instance_id(writer, project_id)
        writer.record_video_watch_progress_range(
            project_id,
            instance_id,
            start_ms=1_000,
            end_ms=5_000,
            duration_ms=12_000,
        )
        writer.record_video_watch_progress_range(
            project_id,
            instance_id,
            start_ms=5_000,
            end_ms=8_000,
            duration_ms=12_000,
        )

        entry_node_id = writer.submit_learning_task(
            project_id,
            items=[
                (
                    rich_text("sync gate original question"),
                    rich_text("sync gate original answer"),
                    Anchor(instance_id=instance_id, position="t=42000"),
                )
            ],
            title="Desktop sync gate task",
        )
        recall_point_id = _one(
            writer.list_recall_points_by_learning_task_node(project_id, entry_node_id),
            "recall point",
        ).recall_point_id

        second_client = _api(store_path)
        resolved_project_id = second_client.resolve_scoped_project_internal_key(subject_id, scoped_project_id)
        if str(resolved_project_id) != str(project_id):
            raise RuntimeError("reloaded client resolved a different scoped project")

        progress_items = second_client.list_video_watch_progress(
            resolved_project_id,
            instance_ids=(instance_id,),
        )
        progress = _one(progress_items, "video watch progress")
        if progress.duration_ms != 12_000 or progress.ranges != ((1_000, 8_000),) or progress.watched_ms != 7_000:
            raise RuntimeError(
                "video watch progress did not persist with the expected normalized range: "
                f"duration={progress.duration_ms} ranges={progress.ranges} watched={progress.watched_ms}"
            )

        persisted_rp = second_client.get_recall_point(resolved_project_id, recall_point_id)
        if _plain_text(persisted_rp.question) != "sync gate original question":
            raise RuntimeError("recall point question did not persist")
        if _plain_text(persisted_rp.answer) != "sync gate original answer":
            raise RuntimeError("recall point answer did not persist")
        if persisted_rp.anchor is None or persisted_rp.anchor.position != "t=42000":
            raise RuntimeError("recall point anchor did not persist")

        _assert_default_review_template_contains_review_task(second_client, resolved_project_id)
        second_client.edit_recall_point(
            resolved_project_id,
            recall_point_id,
            rich_text("sync gate edited question"),
            rich_text("sync gate edited answer"),
            Anchor(instance_id=instance_id, position="t=43000"),
        )
        review_task_id = _first_review_task_id(second_client, resolved_project_id, entry_node_id)
        second_client.executor_commit_review_task(
            resolved_project_id,
            review_task_id,
            [1],
            appended_insights=((RecallPointId(str(recall_point_id)), rich_text("sync gate persisted note")),),
        )

        third_client = _api(store_path)
        final_project_id = third_client.resolve_scoped_project_internal_key(subject_id, scoped_project_id)
        final_rp = third_client.get_recall_point(final_project_id, recall_point_id)
        if _plain_text(final_rp.question) != "sync gate edited question":
            raise RuntimeError("edited recall point question did not persist")
        if _plain_text(final_rp.answer) != "sync gate edited answer":
            raise RuntimeError("edited recall point answer did not persist")
        if final_rp.anchor is None or final_rp.anchor.position != "t=43000":
            raise RuntimeError("edited recall point anchor did not persist")
        if len(final_rp.insights) != 1 or _plain_text(final_rp.insights[0]) != "sync gate persisted note":
            raise RuntimeError("appended recall point note did not persist")

        final_progress = _one(
            third_client.list_video_watch_progress(final_project_id, instance_ids=(instance_id,)),
            "final video watch progress",
        )
        if final_progress.ranges != ((1_000, 8_000),):
            raise RuntimeError("video watch progress changed after recall/note sync")
        if list(third_client.list_recall_points_by_instance(final_project_id, instance_id)) != [recall_point_id]:
            raise RuntimeError("instance recall point index did not persist")

        return GateStatus.passed(
            "learning data persisted across client reloads",
            details={
                "subjectId": str(subject_id),
                "scopedProjectId": str(scoped_project_id),
                "internalProjectId": str(project_id),
                "instanceId": str(instance_id),
                "recallPointId": str(recall_point_id),
                "entryNodeId": str(entry_node_id),
                "reviewTaskId": str(review_task_id),
                "progressRanges": "1000-8000",
                "insightsCount": len(final_rp.insights),
                "store": str(store_path),
            },
        )
    except Exception as exc:
        return GateStatus.failed(
            f"learning data sync smoke failed: {exc}",
            details={"errorType": type(exc).__name__, "store": str(store_path)},
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify desktop MVP learning data persistence with an isolated SQLite store.")
    parser.add_argument("--sqlite-store", type=Path, help="SQLite store path to use. Defaults to a temporary isolated store.")
    parser.add_argument("--keep-store", action="store_true", help="Keep the temporary store after the run.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cleanup: tempfile.TemporaryDirectory[str] | None = None
    store_path = args.sqlite_store
    if store_path is None:
        cleanup = tempfile.TemporaryDirectory(prefix="lp-desktop-sync-gate-")
        store_path = Path(cleanup.name) / "store.sqlite3"

    try:
        report = run_gate(
            (
                GateCheck(
                    check_id="learning_data_restart_sync",
                    label="Desktop learning data restart sync",
                    required=True,
                    run=lambda: run_learning_data_sync_smoke(store_path),
                ),
            ),
            gate_name="desktop-learning-data-sync-gate",
        )
    finally:
        if cleanup is not None and not args.keep_store:
            cleanup.cleanup()

    if args.json:
        print(report.to_json())
    else:
        print(report.to_text())
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
