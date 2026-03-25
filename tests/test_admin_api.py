from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapter.deps import get_api, get_auth_store
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_store.cache_clear()


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()
    yield
    _reset_caches()


def test_admin_can_manage_users_and_groups(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    assert admin_register.json()["data"]["roles"] == ["super_admin"]

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_user_id = member_register.json()["data"]["userId"]

    granted = admin_client.patch(
        f"/api/admin/users/{member_user_id}/roles",
        json={"role": "admin", "enabled": True},
    )
    assert granted.status_code == 200
    assert "admin" in granted.json()["data"]["roles"]

    member_overview = member_client.get("/api/admin/overview")
    assert member_overview.status_code == 200

    forbidden_role_update = member_client.patch(
        f"/api/admin/users/{member_user_id}/roles",
        json={"role": "admin", "enabled": False},
    )
    assert forbidden_role_update.status_code == 403
    assert forbidden_role_update.json()["error"]["message"] == "Super administrator access required"

    created_group = member_client.post(
        "/api/study-groups",
        json={
            "name": "Admin Target Group",
            "description": "等待后台管理操作",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    group_id = created_group.json()["data"]["groupId"]

    post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "这是一条需要后台能看到的动态。"},
    )
    assert post.status_code == 200
    post_id = post.json()["data"]["postId"]

    comment = member_client.post(
        f"/api/study-groups/{group_id}/posts/{post_id}/comments",
        json={"content": "这是一条需要后台能处理的评论。"},
    )
    assert comment.status_code == 200
    comment_id = comment.json()["data"]["commentId"]

    overview = admin_client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["data"]["users"] == 2
    assert overview.json()["data"]["groups"] == 1
    assert overview.json()["data"]["posts"] == 1
    assert overview.json()["data"]["comments"] == 1

    users = admin_client.get("/api/admin/users")
    assert users.status_code == 200
    payload_by_id = {item["userId"]: item for item in users.json()["data"]}
    assert payload_by_id[member_user_id]["status"] == "active"

    user_detail = admin_client.get(f"/api/admin/users/{member_user_id}")
    assert user_detail.status_code == 200
    assert user_detail.json()["data"]["userId"] == member_user_id
    assert user_detail.json()["data"]["groups"][0]["groupId"] == group_id
    assert user_detail.json()["data"]["groups"][0]["memberRole"] == "owner"

    suspended = admin_client.patch(f"/api/admin/users/{member_user_id}/status", json={"status": "suspended"})
    assert suspended.status_code == 200
    assert suspended.json()["data"]["status"] == "suspended"

    denied = member_client.get("/api/study-groups")
    assert denied.status_code == 401
    assert denied.json()["error"]["message"] == "Authentication required"

    archived = admin_client.patch(f"/api/admin/groups/{group_id}/status", json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"

    group_detail = admin_client.get(f"/api/admin/groups/{group_id}")
    assert group_detail.status_code == 200
    assert group_detail.json()["data"]["groupId"] == group_id
    assert group_detail.json()["data"]["members"][0]["userId"] == member_user_id
    assert group_detail.json()["data"]["posts"][0]["postId"] == post_id
    assert group_detail.json()["data"]["comments"][0]["commentId"] == comment_id

    admin_posts = admin_client.get("/api/admin/content/posts")
    assert admin_posts.status_code == 200
    assert admin_posts.json()["data"][0]["postId"] == post_id

    admin_comments = admin_client.get("/api/admin/content/comments")
    assert admin_comments.status_code == 200
    assert admin_comments.json()["data"][0]["commentId"] == comment_id

    deleted_comment = admin_client.delete(f"/api/admin/content/comments/{comment_id}")
    assert deleted_comment.status_code == 200
    assert deleted_comment.json()["data"]["commentId"] == comment_id

    deleted_post = admin_client.delete(f"/api/admin/content/posts/{post_id}")
    assert deleted_post.status_code == 200
    assert deleted_post.json()["data"]["postId"] == post_id

    activity = admin_client.get("/api/admin/activity")
    assert activity.status_code == 200
    action_types = [item["actionType"] for item in activity.json()["data"]]
    assert "user.role_updated" in action_types
    assert "user.status_updated" in action_types
    assert "group.status_updated" in action_types
    assert "content.comment_deleted" in action_types
    assert "content.post_deleted" in action_types

    audit_logs = admin_client.get("/api/admin/audit-logs")
    assert audit_logs.status_code == 200
    assert [item["actionType"] for item in audit_logs.json()["data"]] == action_types


def test_non_admin_cannot_access_admin_endpoints(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    normal_client = TestClient(app)

    admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    normal_client.post("/api/auth/register", json={"email": "normal@example.com", "password": "password123"})

    denied = normal_client.get("/api/admin/overview")
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "Administrator access required"


def test_admin_user_role_filter(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    role_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    admin_user_id = admin_register.json()["data"]["userId"]

    role_register = role_client.post("/api/auth/register", json={"email": "role@example.com", "password": "password123"})
    assert role_register.status_code == 200
    role_user_id = role_register.json()["data"]["userId"]

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_user_id = member_register.json()["data"]["userId"]

    granted = admin_client.patch(f"/api/admin/users/{role_user_id}/roles", json={"role": "admin", "enabled": True})
    assert granted.status_code == 200

    admin_only = admin_client.get("/api/admin/users?role=admin")
    assert admin_only.status_code == 200
    assert [item["userId"] for item in admin_only.json()["data"]] == [role_user_id]

    super_admin_only = admin_client.get("/api/admin/users?role=super_admin")
    assert super_admin_only.status_code == 200
    assert [item["userId"] for item in super_admin_only.json()["data"]] == [admin_user_id]

    no_role = admin_client.get("/api/admin/users?role=none")
    assert no_role.status_code == 200
    assert [item["userId"] for item in no_role.json()["data"]] == [member_user_id]
