from __future__ import annotations

from pathlib import Path

from backend.models.enums import ContentBlockKind
from backend.models.recall_point import Anchor
from backend.models.rich_content import ContentBlock
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_create_media_asset_persists_file_and_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-media"
    (project_root / "learning_objects").mkdir(parents=True)

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Media Asset", project_root=str(project_root))

    asset = api.create_media_asset(project_id, content=PNG_BYTES, mime_type="image/png", filename="clip.png")
    file_path = api.resolve_media_asset_file_path(project_id, asset.asset_id)

    assert asset.relative_path.as_posix().startswith("media/asset_")
    assert asset.mime_type == "image/png"
    assert file_path.exists()
    assert file_path.read_bytes() == PNG_BYTES

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    restored = reloaded.get_media_asset(project_id, asset.asset_id)
    restored_path = reloaded.resolve_media_asset_file_path(project_id, restored.asset_id)

    assert str(restored.asset_id) == str(asset.asset_id)
    assert restored.relative_path.as_posix() == asset.relative_path.as_posix()
    assert restored_path.read_bytes() == PNG_BYTES


def test_submit_learning_task_accepts_image_rich_content(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-learning"
    learning_root = project_root / "learning_objects"
    learning_root.mkdir(parents=True)
    (learning_root / "lesson.mp4").write_bytes(b"video")

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Image Recall", project_root=str(project_root))
    api.sync_learning_objects_from_fs(project_id)
    instance = api.list_instances(project_id)[0]
    asset = api.create_media_asset(project_id, content=PNG_BYTES, mime_type="image/png", filename="formula.png")

    question = (
        ContentBlock(kind=ContentBlockKind.TEXT, text="图里是什么公式？"),
        ContentBlock(kind=ContentBlockKind.IMAGE, asset_id=asset.asset_id),
    )
    answer = (
        ContentBlock(kind=ContentBlockKind.TEXT, text="这是均方误差公式"),
        ContentBlock(kind=ContentBlockKind.IMAGE, asset_id=asset.asset_id),
    )

    entry_node_id = api.submit_learning_task(
        project_id,
        items=[(question, answer, Anchor(instance_id=instance.instance_id, position="t=102017"))],
        title="带图复述点",
    )
    recall_points = api.list_recall_points_by_learning_task_node(project_id, entry_node_id)

    assert len(recall_points) == 1
    assert any(block.kind == ContentBlockKind.IMAGE and str(block.asset_id) == str(asset.asset_id) for block in recall_points[0].question)
    assert any(block.kind == ContentBlockKind.IMAGE and str(block.asset_id) == str(asset.asset_id) for block in recall_points[0].answer)
