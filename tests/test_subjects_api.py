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


def test_subject_creates_default_course_material_project(monkeypatch, tmp_path: Path) -> None:
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
    assert create_data["subjectProjectId"] == subject_id
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
            "subjectProjectId": subject_id,
        }
    ]
    assert "compatibilityProjectId" not in subjects[0]

    config_resp = client.get(f"/api/projects/{subject_id}/project-config")
    assert config_resp.status_code == 200
    assert config_resp.json()["data"]["projectType"] == "COURSE"

    materials_resp = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_resp.status_code == 200
    materials = materials_resp.json()["data"]
    assert len(materials) == 1
    assert materials[0]["subjectId"] == subject_id
    assert materials[0]["materialId"] == "legacy_main"
    assert materials[0]["materialType"] == "COURSE"
    assert materials[0]["title"] == "网课材料"
    assert materials[0]["projectId"] == subject_id
    assert "compatibilityProjectId" not in materials[0]

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
    assert {subject_id, book_project_id}.issubset(project_ids)

    materials_after_create = client.get(f"/api/subjects/{subject_id}/materials")
    assert materials_after_create.status_code == 200
    material_ids = {item["materialId"] for item in materials_after_create.json()["data"]}
    assert "legacy_main" in material_ids
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
    assert delete_subject_resp.status_code == 200
    remaining_projects_resp = client.get("/api/projects")
    assert remaining_projects_resp.status_code == 200
    remaining_project_ids = {item["projectId"] for item in remaining_projects_resp.json()["data"]}
    assert subject_id not in remaining_project_ids
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
    assert root_context_resp.status_code == 200
    root_context = root_context_resp.json()["data"]
    assert root_context["isSubjectRoot"] is True
    assert root_context["subject"]["subjectId"] == subject_id
    assert root_context["subjectProjectId"] == subject_id
    assert root_context["currentProjectId"] == subject_id
    assert root_context["currentMaterial"]["materialId"] == "legacy_main"
    assert root_context["currentMaterial"]["projectId"] == subject_id
    assert "compatibilityProjectId" not in root_context["currentMaterial"]
    assert {item["materialId"] for item in root_context["materials"]} == {"legacy_main", book_material_id}

    child_context_resp = client.get(f"/api/projects/{book_project_id}/subject-context")
    assert child_context_resp.status_code == 200
    child_context = child_context_resp.json()["data"]
    assert child_context["isSubjectRoot"] is False
    assert child_context["subject"]["subjectId"] == subject_id
    assert child_context["subjectProjectId"] == subject_id
    assert child_context["currentProjectId"] == book_project_id
    assert child_context["currentMaterial"]["materialId"] == book_material_id
    assert child_context["currentMaterial"]["projectId"] == book_project_id
    assert "compatibilityProjectId" not in child_context["currentMaterial"]
    assert child_context["currentMaterial"]["title"] == "高等数学教材"

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
    assert [item["materialId"] for item in remaining_materials] == ["legacy_main"]

    remaining_projects_resp = client.get("/api/projects")
    assert remaining_projects_resp.status_code == 200
    remaining_project_ids = {item["projectId"] for item in remaining_projects_resp.json()["data"]}
    assert subject_id in remaining_project_ids
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
    assert [item["materialId"] for item in materials] == ["legacy_main"]

    delete_material_resp = client.delete(f"/api/subjects/{subject_id}/materials/legacy_main")
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


def test_deleting_default_subject_material_keeps_hosted_subject_access(monkeypatch, tmp_path: Path) -> None:
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

    create_course_resp = client.post(
        f"/api/subjects/{subject_id}/materials",
        json={"materialType": "COURSE", "title": "第二套网课"},
    )
    assert create_course_resp.status_code == 200
    second_course = create_course_resp.json()["data"]
    assert second_course["projectId"] != subject_id

    delete_default_resp = client.delete(f"/api/subjects/{subject_id}/materials/legacy_main")
    assert delete_default_resp.status_code == 200

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

    import_course_resp = client.post(
        f"/api/projects/{subject_id}/import-learning-objects-from-browser",
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
        json={"sourceMaterialId": "legacy_main"},
    )
    assert initialize_from_course_resp.status_code == 200
    init_data = initialize_from_course_resp.json()["data"]
    assert init_data["created_instances_count"] == 3
    assert init_data["created_learning_object_nodes_count"] == 6
    assert init_data["root_count"] == 1

    source_nodes_resp = client.get(f"/api/projects/{subject_id}/learning-object-nodes")
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
