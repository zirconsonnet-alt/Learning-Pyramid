from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
    get_membership_commission_store,
    get_membership_marketing_store,
    get_membership_payment_service,
    get_membership_store,
)
from adapter.main import create_app
from backend.models.enums import SessionMode
from backend.models.study_material import StudyMaterial, StudyMaterialType
from backend.models.types import ProjectId
from backend.system.inmemory_system import SessionState


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_commission_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


def _flatten_outline_from_learning_object_nodes(nodes: list[dict]) -> list[tuple[int, str]]:
    node_by_id = {item["nodeId"]: item for item in nodes}
    root_ids = sorted(
        [item["nodeId"] for item in nodes if item.get("parentId") is None],
        key=lambda node_id: (
            0 if node_by_id[node_id]["kind"] == "container" else 1,
            node_by_id[node_id].get("relativePath") or "",
            node_by_id[node_id]["title"],
            node_id,
        ),
    )

    outline: list[tuple[int, str]] = []

    def visit(node_id: str, depth: int) -> None:
        node = node_by_id[node_id]
        outline.append((depth, node["title"]))
        if node["kind"] == "container":
            for child_id in node.get("children", []):
                visit(child_id, depth + 1)

    for root_id in root_ids:
        visit(root_id, 0)

    return outline


def test_subject_creates_first_course_material_as_independent_project(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())

    create_resp = client.post("/api/subjects", json={"title": "高等数学"})
    assert create_resp.status_code == 200
    create_data = create_resp.json()["data"]
    subject_id = create_data["subjectId"]
    assert set(create_data) == {"subjectId"}
    assert "subjectProjectId" not in create_data
    assert "compatibilityProjectId" not in create_data

    subject_resp = client.get("/api/subjects")
    assert subject_resp.status_code == 200
    subjects = subject_resp.json()["data"]
    assert subjects == [
        {
            "subjectId": subject_id,
            "title": "高等数学",
            "state": "ACTIVE",
            "createdAt": subjects[0]["createdAt"],
            "deletedAt": None,
        }
    ]
    assert "subjectProjectId" not in subjects[0]
    assert "compatibilityProjectId" not in subjects[0]

    config_resp = client.get(f"/api/projects/{subject_id}/project-config")
    assert config_resp.status_code == 400
    assert config_resp.json()["error"]["code"] == "PRECONDITION"

    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    materials = materials_resp.json()["data"]
    assert len(materials) == 1
    first_course_material = materials[0]
    first_course_project_id = first_course_material["projectId"]
    assert first_course_material["subjectId"] == subject_id
    assert first_course_material["materialId"] != "legacy_main"
    assert first_course_material["materialType"] == "COURSE"
    assert first_course_material["title"] == "网课材料"
    assert first_course_project_id
    assert first_course_project_id != subject_id
    assert "compatibilityProjectId" not in first_course_material

    create_book_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "BOOK", "title": "高等数学教材"},
    )
    assert create_book_resp.status_code == 200
    book_material = create_book_resp.json()["data"]
    book_project_id = book_material["projectId"]
    assert book_material["subjectId"] == subject_id
    assert book_material["materialType"] == "BOOK"
    assert book_material["title"] == "高等数学教材"
    assert book_project_id
    assert book_project_id != subject_id
    assert "compatibilityProjectId" not in book_material

    subject_resp_after_material = client.get("/api/subjects")
    assert subject_resp_after_material.status_code == 200
    subjects_after_material = subject_resp_after_material.json()["data"]
    assert len(subjects_after_material) == 1
    assert subjects_after_material[0]["subjectId"] == subject_id

    projects_resp = client.get("/api/projects")
    assert projects_resp.status_code == 200
    project_ids = {item["projectId"] for item in projects_resp.json()["data"]}
    assert subject_id not in project_ids
    assert {first_course_project_id, book_project_id}.issubset(project_ids)

    materials_after_create = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_create.status_code == 200
    material_ids = {item["materialId"] for item in materials_after_create.json()["data"]}
    assert first_course_material["materialId"] in material_ids
    assert book_material["materialId"] in material_ids

    child_view = client.get(f"/api/subjects/{book_project_id}/materials")
    assert child_view.status_code == 200
    child_view_materials = child_view.json()["data"]
    assert len(child_view_materials) == 2
    assert {item["materialId"] for item in child_view_materials} == material_ids

    edit_child_resp = client.patch(f"/api/projects/{book_project_id}", json={"title": "高数教材精读"})
    assert edit_child_resp.status_code == 200
    materials_after_edit = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_edit.status_code == 200
    edited_book_material = next(item for item in materials_after_edit.json()["data"] if item["materialId"] == book_material["materialId"])
    assert edited_book_material["title"] == "高数教材精读"

    delete_subject_resp = client.delete(f"/api/projects/{subject_id}")
    assert delete_subject_resp.status_code == 400
    assert delete_subject_resp.json()["error"]["code"] == "PRECONDITION"
    delete_subject_resp = client.delete(f"/api/subjects/{subject_id}")
    assert delete_subject_resp.status_code == 200
    remaining_projects_resp = client.get("/api/projects")
    assert remaining_projects_resp.status_code == 200
    remaining_project_ids = {item["projectId"] for item in remaining_projects_resp.json()["data"]}
    assert subject_id not in remaining_project_ids
    assert first_course_project_id not in remaining_project_ids
    assert book_project_id not in remaining_project_ids
    remaining_subjects_resp = client.get("/api/subjects")
    assert remaining_subjects_resp.status_code == 200
    assert remaining_subjects_resp.json()["data"] == []

    _reset_caches()


def test_subject_context_and_material_management_endpoints(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())

    create_subject_resp = client.post("/api/subjects", json={"title": "高等数学"})
    assert create_subject_resp.status_code == 200
    subject_id = create_subject_resp.json()["data"]["subjectId"]
    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    first_course_material = materials_resp.json()["data"][0]
    first_course_material_id = first_course_material["materialId"]
    first_course_project_id = first_course_material["projectId"]
    assert first_course_material_id != "legacy_main"
    assert first_course_project_id != subject_id

    create_book_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "BOOK", "title": "高等数学教材"},
    )
    assert create_book_resp.status_code == 200
    book_material = create_book_resp.json()["data"]
    book_material_id = book_material["materialId"]
    book_project_id = book_material["projectId"]
    assert book_project_id
    assert "compatibilityProjectId" not in book_material

    root_context_resp = client.get(f"/api/projects/{subject_id}/subject-context")
    assert root_context_resp.status_code == 400
    assert root_context_resp.json()["error"]["code"] == "PRECONDITION"

    child_context_resp = client.get(f"/api/projects/{book_project_id}/subject-context")
    assert child_context_resp.status_code == 200
    child_context = child_context_resp.json()["data"]
    assert child_context["subject"]["subjectId"] == subject_id
    assert child_context["currentProjectId"] == book_project_id
    assert child_context["currentMaterial"]["materialId"] == book_material_id
    assert child_context["currentMaterial"]["projectId"] == book_project_id
    assert "compatibilityProjectId" not in child_context["currentMaterial"]
    assert child_context["currentMaterial"]["title"] == "高等数学教材"
    assert "isSubjectRoot" not in child_context
    assert "subjectProjectId" not in child_context

    rename_subject_resp = client.patch(f"/api/subjects/{subject_id}", json={"title": "高等数学进阶"})
    assert rename_subject_resp.status_code == 200
    renamed_subjects_resp = client.get("/api/subjects")
    assert renamed_subjects_resp.status_code == 200
    renamed_subject = renamed_subjects_resp.json()["data"][0]
    assert renamed_subject["title"] == "高等数学进阶"

    renamed_child_context_resp = client.get(f"/api/projects/{book_project_id}/subject-context")
    assert renamed_child_context_resp.status_code == 200
    assert renamed_child_context_resp.json()["data"]["subject"]["title"] == "高等数学进阶"

    rename_material_resp = client.patch(
        f"/api/subjects/{subject_id}/materials/{book_material_id}",
        json={"title": "教材精读"},
    )
    assert rename_material_resp.status_code == 200
    assert rename_material_resp.json()["data"]["title"] == "教材精读"

    materials_after_rename_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_rename_resp.status_code == 200
    renamed_book_material = next(
        item for item in materials_after_rename_resp.json()["data"] if item["materialId"] == book_material_id
    )
    assert renamed_book_material["title"] == "教材精读"

    delete_material_resp = client.delete(f"/api/subjects/{subject_id}/materials/{book_material_id}")
    assert delete_material_resp.status_code == 200
    remaining_materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert remaining_materials_resp.status_code == 200
    remaining_materials = remaining_materials_resp.json()["data"]
    assert [item["materialId"] for item in remaining_materials] == [first_course_material_id]

    remaining_projects_resp = client.get("/api/projects")
    assert remaining_projects_resp.status_code == 200
    remaining_project_ids = {item["projectId"] for item in remaining_projects_resp.json()["data"]}
    assert subject_id not in remaining_project_ids
    assert first_course_project_id in remaining_project_ids
    assert book_project_id not in remaining_project_ids

    delete_subject_resp = client.delete(f"/api/subjects/{subject_id}")
    assert delete_subject_resp.status_code == 200
    final_subjects_resp = client.get("/api/subjects")
    assert final_subjects_resp.status_code == 200
    assert final_subjects_resp.json()["data"] == []

    _reset_caches()


def test_subject_material_projects_can_all_be_deleted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())

    create_subject_resp = client.post("/api/subjects", json={"title": "概率论与数理统计"})
    assert create_subject_resp.status_code == 200
    subject_id = create_subject_resp.json()["data"]["subjectId"]

    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    materials = materials_resp.json()["data"]
    assert len(materials) == 1
    first_course_material = materials[0]
    assert first_course_material["materialId"] != "legacy_main"
    assert first_course_material["projectId"] != subject_id

    delete_material_resp = client.delete(f"/api/subjects/{subject_id}/materials/{first_course_material['materialId']}")
    assert delete_material_resp.status_code == 200

    subjects_after_delete_resp = client.get("/api/subjects")
    assert subjects_after_delete_resp.status_code == 200
    assert [item["subjectId"] for item in subjects_after_delete_resp.json()["data"]] == [subject_id]

    materials_after_delete_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_delete_resp.status_code == 200
    assert materials_after_delete_resp.json()["data"] == []

    create_book_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "BOOK", "title": "习题集"},
    )
    assert create_book_resp.status_code == 200
    book_material = create_book_resp.json()["data"]
    assert book_material["materialId"] != "legacy_main"
    assert book_material["projectId"] != subject_id

    materials_after_recreate_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_recreate_resp.status_code == 200
    materials_after_recreate = materials_after_recreate_resp.json()["data"]
    assert [item["materialId"] for item in materials_after_recreate] == [book_material["materialId"]]

    delete_book_resp = client.delete(f"/api/subjects/{subject_id}/materials/{book_material['materialId']}")
    assert delete_book_resp.status_code == 200

    final_materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert final_materials_resp.status_code == 200
    assert final_materials_resp.json()["data"] == []

    final_subjects_resp = client.get("/api/subjects")
    assert final_subjects_resp.status_code == 200
    assert [item["subjectId"] for item in final_subjects_resp.json()["data"]] == [subject_id]

    _reset_caches()


def test_deleting_first_subject_material_keeps_hosted_subject_access(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    register_resp = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register_resp.status_code == 200

    create_subject_resp = client.post("/api/subjects", json={"title": "高等数学"})
    assert create_subject_resp.status_code == 200
    subject_id = create_subject_resp.json()["data"]["subjectId"]
    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    first_course = materials_resp.json()["data"][0]
    assert first_course["materialId"] != "legacy_main"
    assert first_course["projectId"] != subject_id

    create_course_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "COURSE", "title": "第二套网课"},
    )
    assert create_course_resp.status_code == 200
    second_course = create_course_resp.json()["data"]
    assert second_course["projectId"] != subject_id

    delete_first_resp = client.delete(f"/api/subjects/{subject_id}/materials/{first_course['materialId']}")
    assert delete_first_resp.status_code == 200

    subjects_after_delete_resp = client.get("/api/subjects")
    assert subjects_after_delete_resp.status_code == 200
    assert [item["subjectId"] for item in subjects_after_delete_resp.json()["data"]] == [subject_id]

    materials_after_delete_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_delete_resp.status_code == 200
    materials_after_delete = materials_after_delete_resp.json()["data"]
    assert [item["materialId"] for item in materials_after_delete] == [second_course["materialId"]]
    assert materials_after_delete[0]["projectId"] == second_course["projectId"]

    context_resp = client.get(f"/api/projects/{second_course['projectId']}/subject-context")
    assert context_resp.status_code == 200
    assert context_resp.json()["data"]["subject"]["subjectId"] == subject_id

    _reset_caches()


def test_hosted_legacy_root_material_migration_grants_child_project_access(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    register_resp = client.post("/api/auth/register", json={"email": "legacy-owner@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    user_id = register_resp.json()["data"]["userId"]

    api = get_api()
    auth_store = get_auth_store()
    subject_id = api.create_project("旧高数")
    auth_store.add_project_owner(subject_id, user_id)
    subject = api._get_active_project_metadata(subject_id)
    session = api.sys.begin_session(subject_id, SessionMode.READ_WRITE)
    try:
        session._staged.study_materials = {
            "legacy_main": StudyMaterial(
                subject_id=ProjectId(str(subject_id)),
                material_id="legacy_main",
                material_type=StudyMaterialType.COURSE,
                title="旧网课材料",
                created_at=subject.created_at,
                project_id=ProjectId(str(subject_id)),
            )
        }
        session._staged.study_materials_replaced = True
        api.sys.commit(session)
        sql_store = api._sql_store()
        assert sql_store is not None
        api._persist_project_store_sql_direct(sql_store, subject_id)
        api._reload_sql_state()
    except Exception:
        if session.state == SessionState.OPEN:
            api.sys.rollback(session)
        raise

    subjects_resp = client.get("/api/subjects")
    assert subjects_resp.status_code == 200
    subjects = subjects_resp.json()["data"]
    assert [item["subjectId"] for item in subjects] == [str(subject_id)]
    assert "subjectProjectId" not in subjects[0]

    materials = list(api.list_subject_materials(subject_id))
    assert len(materials) == 1
    migrated = materials[0]
    migrated_project_id = migrated.project_id
    assert migrated.material_id != "legacy_main"
    assert migrated_project_id is not None
    assert migrated_project_id != subject_id
    assert str(migrated_project_id) not in auth_store.list_project_ids_for_user(user_id)

    root_context_resp = client.get(f"/api/projects/{subject_id}/subject-context")
    assert root_context_resp.status_code == 400
    assert root_context_resp.json()["error"]["code"] == "PRECONDITION"

    context_resp = client.get(f"/api/projects/{migrated_project_id}/subject-context")
    assert context_resp.status_code == 200
    context = context_resp.json()["data"]
    assert context["subject"]["subjectId"] == str(subject_id)
    assert context["currentMaterial"]["projectId"] == str(migrated_project_id)
    assert str(migrated_project_id) in auth_store.list_project_ids_for_user(user_id)

    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    materials_data = materials_resp.json()["data"]
    assert len(materials_data) == 1
    assert materials_data[0]["projectId"] == str(migrated_project_id)

    projects_resp = client.get("/api/projects")
    assert projects_resp.status_code == 200
    project_ids = {item["projectId"] for item in projects_resp.json()["data"]}
    assert str(subject_id) not in project_ids
    assert str(migrated_project_id) in project_ids

    _reset_caches()


def test_initialize_book_from_course_material_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())

    create_subject_resp = client.post("/api/subjects", json={"title": "高等数学"})
    assert create_subject_resp.status_code == 200
    subject_id = create_subject_resp.json()["data"]["subjectId"]
    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    course_material = materials_resp.json()["data"][0]
    course_material_id = course_material["materialId"]
    course_project_id = course_material["projectId"]
    assert course_material_id != "legacy_main"
    assert course_project_id != subject_id

    import_course_resp = client.post(
        f"/api/projects/{course_project_id}/import-learning-objects-from-browser",
        json={
            "rootTitle": "高数网课",
            "relativeFilePaths": [
                "第一章/1.1 极限.mp4",
                "第一章/1.2 连续.mp4",
                "第二章/2.1 导数.mp4",
            ],
        },
    )
    assert import_course_resp.status_code == 200

    create_book_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "BOOK", "title": "高数教材"},
    )
    assert create_book_resp.status_code == 200
    create_book_data = create_book_resp.json()["data"]
    book_project_id = create_book_data["projectId"]
    assert book_project_id
    assert "compatibilityProjectId" not in create_book_data

    initialize_from_course_resp = client.post(
        f"/api/projects/{book_project_id}/initialize-book-learning-objects-from-material",
        json={"sourceMaterialId": course_material_id},
    )
    assert initialize_from_course_resp.status_code == 200
    init_data = initialize_from_course_resp.json()["data"]
    assert init_data["created_instances_count"] == 3
    assert init_data["created_learning_object_nodes_count"] == 6
    assert init_data["root_count"] == 1

    source_nodes_resp = client.get(f"/api/projects/{course_project_id}/learning-object-nodes")
    assert source_nodes_resp.status_code == 200
    target_nodes_resp = client.get(f"/api/projects/{book_project_id}/learning-object-nodes")
    assert target_nodes_resp.status_code == 200

    source_outline = _flatten_outline_from_learning_object_nodes(source_nodes_resp.json()["data"])
    target_outline = _flatten_outline_from_learning_object_nodes(target_nodes_resp.json()["data"])
    assert target_outline == source_outline

    target_instances_resp = client.get(f"/api/projects/{book_project_id}/instances")
    assert target_instances_resp.status_code == 200
    target_instances = target_instances_resp.json()["data"]
    assert len(target_instances) == 3
    assert all(item["presence"] == "PRESENT" for item in target_instances)

    _reset_caches()


def test_reject_removed_mistake_material_type(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())

    create_subject_resp = client.post("/api/subjects", json={"title": "高等数学"})
    assert create_subject_resp.status_code == 200
    subject_id = create_subject_resp.json()["data"]["subjectId"]

    create_mistake_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "MISTAKE_BOOK", "title": "高数错题"},
    )
    assert create_mistake_resp.status_code == 400
    payload = create_mistake_resp.json()
    assert payload["error"]["code"] == "PRECONDITION"
    assert payload["error"]["message"] == "materialType must be one of COURSE, BOOK, LOOSE_POINTS"

    _reset_caches()
