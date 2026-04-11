from __future__ import annotations

from pathlib import Path

from backend.models.enums import ContentBlockKind, SessionMode
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.rich_content import ContentBlock, rich_text
from backend.models.types import now_utc_ms
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


def test_submit_learning_task_persists_recall_point_references(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-references"
    learning_root = project_root / "learning_objects"
    learning_root.mkdir(parents=True)
    (learning_root / "lesson.mp4").write_bytes(b"video")

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Recall References", project_root=str(project_root))
    api.sync_learning_objects_from_fs(project_id)
    instance = api.list_instances(project_id)[0]

    session = api.sys.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        first_recall_point = RecallPoint(
            project_id=project_id,
            recall_point_id=api.idgen.new_recall_point_id(project_id),
            created_at=now_utc_ms(),
            question=rich_text("第一问"),
            answer=rich_text("第一答"),
            anchor=Anchor(instance_id=instance.instance_id, position="t=1024"),
        )
        api.sys.recall_point_repo.add(session, first_recall_point)
        api.sys.commit(session)
    except Exception:
        api.sys.rollback(session)
        raise

    second_entry_node_id = api.submit_learning_task(
        project_id,
        items=[
            (
                tuple([ContentBlock(kind=ContentBlockKind.TEXT, text="第二问")]),
                tuple([ContentBlock(kind=ContentBlockKind.TEXT, text="第二答")]),
                Anchor(instance_id=instance.instance_id, position="t=2048"),
                (first_recall_point.recall_point_id,),
            )
        ],
        title="第二条",
    )
    second_recall_point = api.list_recall_points_by_learning_task_node(project_id, second_entry_node_id)[0]

    assert tuple(second_recall_point.references) == (first_recall_point.recall_point_id,)
    assert "第一问" not in str(second_recall_point)
    listed = api.list_recall_points(project_id)
    assert [str(item.recall_point_id) for item in listed] == [
        str(first_recall_point.recall_point_id),
        str(second_recall_point.recall_point_id),
    ]

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    restored = reloaded.get_recall_point(project_id, second_recall_point.recall_point_id)
    assert tuple(restored.references) == (first_recall_point.recall_point_id,)


def test_search_recall_points_filters_and_limits_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-search-references"
    learning_root = project_root / "learning_objects"
    learning_root.mkdir(parents=True)
    (learning_root / "lesson.mp4").write_bytes(b"video")

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Recall Search", project_root=str(project_root))
    api.sync_learning_objects_from_fs(project_id)
    instance = api.list_instances(project_id)[0]

    session = api.sys.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        created_ids: list[str] = []
        for question_text, answer_text in [
            ("导数定义", "极限刻画"),
            ("导数法则", "乘法求导"),
            ("积分技巧", "换元积分"),
        ]:
            recall_point = RecallPoint(
                project_id=project_id,
                recall_point_id=api.idgen.new_recall_point_id(project_id),
                created_at=now_utc_ms(),
                question=rich_text(question_text),
                answer=rich_text(answer_text),
                anchor=Anchor(instance_id=instance.instance_id, position=f"t={1000 + len(created_ids)}"),
            )
            api.sys.recall_point_repo.add(session, recall_point)
            created_ids.append(str(recall_point.recall_point_id))
        api.sys.commit(session)
    except Exception:
        api.sys.rollback(session)
        raise

    search_results = api.search_recall_points(project_id, query="导数", limit=5)
    assert [str(item.recall_point_id) for item in search_results] == [created_ids[1], created_ids[0]]

    latest_results = api.search_recall_points(project_id, limit=2)
    assert [str(item.recall_point_id) for item in latest_results] == [created_ids[2], created_ids[1]]


def test_edit_recall_point_keeps_server_image_assets_after_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-edit-image"
    learning_root = project_root / "learning_objects"
    learning_root.mkdir(parents=True)
    (learning_root / "lesson.mp4").write_bytes(b"video")

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Edit Recall Image", project_root=str(project_root))
    api.sync_learning_objects_from_fs(project_id)
    instance = api.list_instances(project_id)[0]
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[(tuple([ContentBlock(kind=ContentBlockKind.TEXT, text="原问题")]), tuple([ContentBlock(kind=ContentBlockKind.TEXT, text="原答案")]), Anchor(instance_id=instance.instance_id, position="t=2048"))],
        title="先建一条复述点",
    )
    recall_point = api.list_recall_points_by_learning_task_node(project_id, entry_node_id)[0]
    asset = api.create_media_asset(project_id, content=PNG_BYTES, mime_type="image/png", filename="kept.png")

    question = (
        ContentBlock(kind=ContentBlockKind.TEXT, text="图里是什么？"),
        ContentBlock(kind=ContentBlockKind.IMAGE, asset_id=asset.asset_id),
    )
    answer = (
        ContentBlock(kind=ContentBlockKind.TEXT, text="这是会被服务器持久化的图片"),
        ContentBlock(kind=ContentBlockKind.IMAGE, asset_id=asset.asset_id),
    )
    api.edit_recall_point(project_id, recall_point.recall_point_id, question, answer, recall_point.anchor)

    updated = api.get_recall_point(project_id, recall_point.recall_point_id)
    assert any(block.kind == ContentBlockKind.IMAGE and str(block.asset_id) == str(asset.asset_id) for block in updated.question)
    assert any(block.kind == ContentBlockKind.IMAGE and str(block.asset_id) == str(asset.asset_id) for block in updated.answer)

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    restored = reloaded.get_recall_point(project_id, recall_point.recall_point_id)
    restored_path = reloaded.resolve_media_asset_file_path(project_id, asset.asset_id)

    assert any(block.kind == ContentBlockKind.IMAGE and str(block.asset_id) == str(asset.asset_id) for block in restored.question)
    assert any(block.kind == ContentBlockKind.IMAGE and str(block.asset_id) == str(asset.asset_id) for block in restored.answer)
    assert restored_path.read_bytes() == PNG_BYTES
