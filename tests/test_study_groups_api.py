from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
    get_membership_marketing_store,
    get_membership_payment_service,
    get_membership_store,
)
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_ENABLE_COMMUNITY_GUARDRAILS", "true")
    monkeypatch.setenv("PLM_STUDY_GROUP_CREATE_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_REQUEST_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_POST_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_COMMENT_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_CREATE_MAX_ACTIONS_PER_WINDOW", "100")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_MAX_ACTIONS_PER_WINDOW", "100")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_REQUEST_MAX_ACTIONS_PER_WINDOW", "100")
    monkeypatch.setenv("PLM_STUDY_GROUP_POST_MAX_ACTIONS_PER_WINDOW", "100")
    monkeypatch.setenv("PLM_STUDY_GROUP_COMMENT_MAX_ACTIONS_PER_WINDOW", "200")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path / "runtime-data"))
    _reset_caches()
    yield
    _reset_caches()


def test_study_group_public_flow(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    member_client = TestClient(app)

    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    member_user_id = member_register.json()["data"]["userId"]

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Linear Algebra",
            "description": "每天一起刷题和总结",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]
    assert created.json()["data"]["memberRole"] == "owner"

    lobby = member_client.get("/api/study-groups")
    assert lobby.status_code == 200
    assert any(item["groupId"] == group_id for item in lobby.json()["data"])

    joined = member_client.post(f"/api/study-groups/{group_id}/join")
    assert joined.status_code == 200
    assert joined.json()["data"]["memberRole"] == "member"

    promoted = owner_client.patch(
        f"/api/study-groups/{group_id}/members/{member_user_id}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["data"]["role"] == "admin"

    transferred = owner_client.patch(
        f"/api/study-groups/{group_id}/members/{member_user_id}",
        json={"role": "owner"},
    )
    assert transferred.status_code == 200
    assert transferred.json()["data"]["role"] == "owner"

    post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "今晚 8 点一起过一遍矩阵变换。"},
    )
    assert post.status_code == 200
    assert post.json()["data"]["authorNickname"] == "member"
    post_id = post.json()["data"]["postId"]

    comment = member_client.post(
        f"/api/study-groups/{group_id}/posts/{post_id}/comments",
        json={"content": "我会提前整理几道典型题。"},
    )
    assert comment.status_code == 200
    assert comment.json()["data"]["postId"] == post_id
    assert comment.json()["data"]["authorNickname"] == "member"

    members = owner_client.get(f"/api/study-groups/{group_id}/members")
    assert members.status_code == 200
    member_uids = {item["publicUid"] for item in members.json()["data"]}
    assert len(member_uids) == 2

    owner_user_id = created.json()["data"]["ownerUserId"]
    removed = member_client.delete(f"/api/study-groups/{group_id}/members/{owner_user_id}")
    assert removed.status_code == 200

    remaining_members = member_client.get(f"/api/study-groups/{group_id}/members")
    assert remaining_members.status_code == 200
    assert len(remaining_members.json()["data"]) == 1

    posts = member_client.get(f"/api/study-groups/{group_id}/posts")
    assert posts.status_code == 200
    assert posts.json()["data"][0]["content"] == "今晚 8 点一起过一遍矩阵变换。"

    comments = member_client.get(f"/api/study-groups/{group_id}/comments")
    assert comments.status_code == 200
    assert comments.json()["data"][0]["content"] == "我会提前整理几道典型题。"


def test_private_study_group_blocks_non_members(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    stranger_client = TestClient(app)

    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    stranger_register = stranger_client.post("/api/auth/register", json={"email": "stranger@example.com", "password": "password123"})

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Private Group",
            "description": "仅限核心成员",
            "visibility": "private",
            "joinPolicy": "invite_only",
        },
    )
    group_id = created.json()["data"]["groupId"]

    detail = stranger_client.get(f"/api/study-groups/{group_id}")
    assert detail.status_code == 403
    assert detail.json()["error"]["message"] == "Study group access denied"

    joined = stranger_client.post(f"/api/study-groups/{group_id}/join")
    assert joined.status_code == 403
    assert joined.json()["error"]["message"] == "Private study groups do not allow direct join"

    outsider_comment = stranger_client.post(
        f"/api/study-groups/{group_id}/posts/post_missing/comments",
        json={"content": "让我也参与一下"},
    )
    assert outsider_comment.status_code == 403
    assert outsider_comment.json()["error"]["message"] == "Study group access denied"

    invited = owner_client.post(
        f"/api/study-groups/{group_id}/members/invite",
        json={"publicUid": stranger_register.json()["data"]["publicUid"], "role": "member"},
    )
    assert invited.status_code == 200
    assert invited.json()["data"]["role"] == "member"

    detail_after_invite = stranger_client.get(f"/api/study-groups/{group_id}")
    assert detail_after_invite.status_code == 200
    assert detail_after_invite.json()["data"]["memberRole"] == "member"


def test_study_group_join_request_flow(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    group_admin_client = TestClient(app)
    applicant_client = TestClient(app)
    outsider_client = TestClient(app)

    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    group_admin_register = group_admin_client.post("/api/auth/register", json={"email": "group-admin@example.com", "password": "password123"})
    applicant_register = applicant_client.post("/api/auth/register", json={"email": "applicant@example.com", "password": "password123"})
    outsider_client.post("/api/auth/register", json={"email": "outsider@example.com", "password": "password123"})

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Algorithms Sprint",
            "description": "先申请，再审核入组",
            "visibility": "public",
            "joinPolicy": "approval",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    invited_admin = owner_client.post(
        f"/api/study-groups/{group_id}/members/invite",
        json={"publicUid": group_admin_register.json()["data"]["publicUid"], "role": "admin"},
    )
    assert invited_admin.status_code == 200
    assert invited_admin.json()["data"]["role"] == "admin"

    join_request = applicant_client.post(
        f"/api/study-groups/{group_id}/join-requests",
        json={"message": "想一起刷 LeetCode 并做每周复盘。"},
    )
    assert join_request.status_code == 200
    assert join_request.json()["data"]["status"] == "pending"
    request_id = join_request.json()["data"]["requestId"]

    applicant_detail = applicant_client.get(f"/api/study-groups/{group_id}")
    assert applicant_detail.status_code == 200
    assert applicant_detail.json()["data"]["joinRequestStatus"] == "pending"

    forbidden_review = outsider_client.get(f"/api/study-groups/{group_id}/join-requests")
    assert forbidden_review.status_code == 403
    assert forbidden_review.json()["error"]["message"] == "Study group management denied"

    pending_requests = group_admin_client.get(f"/api/study-groups/{group_id}/join-requests")
    assert pending_requests.status_code == 200
    assert [item["requestId"] for item in pending_requests.json()["data"]] == [request_id]

    approved = group_admin_client.patch(
        f"/api/study-groups/{group_id}/join-requests/{request_id}",
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"

    member_detail = applicant_client.get(f"/api/study-groups/{group_id}")
    assert member_detail.status_code == 200
    assert member_detail.json()["data"]["memberRole"] == "member"


def test_study_group_avatar_upload(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    member_client = TestClient(app)

    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Avatar Group",
            "description": "测试小组头像上传",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00\x00\x04\x00\x01\xf6\x178U"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    uploaded = owner_client.put(f"/api/study-groups/{group_id}/avatar", content=png_bytes, headers={"Content-Type": "image/png"})
    assert uploaded.status_code == 200
    avatar_url = uploaded.json()["data"]["avatarUrl"]
    assert avatar_url

    avatar = member_client.get(avatar_url)
    assert avatar.status_code == 200
    assert avatar.headers["content-type"].startswith("image/png")


def test_study_group_author_can_delete_own_content(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    member_client = TestClient(app)

    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Delete My Own Content",
            "description": "测试作者自行删除动态和评论",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    joined = member_client.post(f"/api/study-groups/{group_id}/join")
    assert joined.status_code == 200

    post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "这条动态等会由作者自己删除。"},
    )
    assert post.status_code == 200
    post_id = post.json()["data"]["postId"]

    comment = member_client.post(
        f"/api/study-groups/{group_id}/posts/{post_id}/comments",
        json={"content": "这条评论也会一起测试删除。"},
    )
    assert comment.status_code == 200
    comment_id = comment.json()["data"]["commentId"]

    deleted_comment = member_client.delete(f"/api/study-groups/{group_id}/comments/{comment_id}")
    assert deleted_comment.status_code == 200
    assert deleted_comment.json()["data"]["commentId"] == comment_id

    deleted_post = member_client.delete(f"/api/study-groups/{group_id}/posts/{post_id}")
    assert deleted_post.status_code == 200
    assert deleted_post.json()["data"]["postId"] == post_id

    posts = member_client.get(f"/api/study-groups/{group_id}/posts")
    assert posts.status_code == 200
    assert posts.json()["data"] == []

    comments = member_client.get(f"/api/study-groups/{group_id}/comments")
    assert comments.status_code == 200
    assert comments.json()["data"] == []


def test_study_group_managers_can_delete_member_content(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    member_client = TestClient(app)
    reviewer_client = TestClient(app)

    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    reviewer_register = reviewer_client.post("/api/auth/register", json={"email": "reviewer@example.com", "password": "password123"})

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Moderation Flow",
            "description": "测试小组管理员的内容治理权限",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    assert member_client.post(f"/api/study-groups/{group_id}/join").status_code == 200
    assert reviewer_client.post(f"/api/study-groups/{group_id}/join").status_code == 200

    first_post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "普通成员先发一条动态。"},
    )
    assert first_post.status_code == 200
    first_post_id = first_post.json()["data"]["postId"]

    first_comment = member_client.post(
        f"/api/study-groups/{group_id}/posts/{first_post_id}/comments",
        json={"content": "普通成员再留一条评论。"},
    )
    assert first_comment.status_code == 200
    first_comment_id = first_comment.json()["data"]["commentId"]

    forbidden_delete_post = reviewer_client.delete(f"/api/study-groups/{group_id}/posts/{first_post_id}")
    assert forbidden_delete_post.status_code == 400
    assert forbidden_delete_post.json()["error"]["message"] == "only the author or group managers can delete this post"

    forbidden_delete_comment = reviewer_client.delete(f"/api/study-groups/{group_id}/comments/{first_comment_id}")
    assert forbidden_delete_comment.status_code == 400
    assert forbidden_delete_comment.json()["error"]["message"] == "only the author or group managers can delete this comment"

    promoted = owner_client.patch(
        f"/api/study-groups/{group_id}/members/{reviewer_register.json()['data']['userId']}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["data"]["role"] == "admin"

    second_post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "notice", "content": "这条动态会由小组管理员删除。"},
    )
    assert second_post.status_code == 200
    second_post_id = second_post.json()["data"]["postId"]

    second_comment = member_client.post(
        f"/api/study-groups/{group_id}/posts/{second_post_id}/comments",
        json={"content": "这条评论也会由小组管理员删除。"},
    )
    assert second_comment.status_code == 200
    second_comment_id = second_comment.json()["data"]["commentId"]

    deleted_comment = reviewer_client.delete(f"/api/study-groups/{group_id}/comments/{second_comment_id}")
    assert deleted_comment.status_code == 200
    assert deleted_comment.json()["data"]["commentId"] == second_comment_id

    deleted_post = reviewer_client.delete(f"/api/study-groups/{group_id}/posts/{second_post_id}")
    assert deleted_post.status_code == 200
    assert deleted_post.json()["data"]["postId"] == second_post_id

    remaining_posts = member_client.get(f"/api/study-groups/{group_id}/posts")
    assert remaining_posts.status_code == 200
    assert [item["postId"] for item in remaining_posts.json()["data"]] == [first_post_id]

    remaining_comments = member_client.get(f"/api/study-groups/{group_id}/comments")
    assert remaining_comments.status_code == 200
    assert [item["commentId"] for item in remaining_comments.json()["data"]] == [first_comment_id]


def test_new_account_cannot_immediately_create_study_group_when_guardrails_are_enabled(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_STUDY_GROUP_CREATE_MIN_ACCOUNT_AGE_SECONDS", "600")
    _reset_caches()

    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)
    assert admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"}).status_code == 200
    register = member_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register.status_code == 200

    created = member_client.post(
        "/api/study-groups",
        json={
            "name": "Guardrail Group",
            "description": "新号冷却测试",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )

    assert created.status_code == 403
    assert created.json()["error"]["code"] == "FORBIDDEN"
    assert "before they can create study groups" in created.json()["error"]["message"]
    assert int(created.headers["Retry-After"]) >= 1


def test_study_group_post_rate_limit_blocks_repeated_posts(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_STUDY_GROUP_CREATE_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_POST_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_POST_MAX_ACTIONS_PER_WINDOW", "1")
    monkeypatch.setenv("PLM_STUDY_GROUP_POST_WINDOW_SECONDS", "600")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    member_client = TestClient(app)

    owner_register = owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert owner_register.status_code == 200
    assert member_register.status_code == 200

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Post Limit Group",
            "description": "发帖频控测试",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    joined = member_client.post(f"/api/study-groups/{group_id}/join")
    assert joined.status_code == 200

    first = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "第一条动态。"},
    )
    blocked = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "第二条动态。"},
    )

    assert first.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert blocked.json()["error"]["message"] == "Too many study group posts in a short period. Try again later."
    assert int(blocked.headers["Retry-After"]) >= 1


def test_new_account_cannot_immediately_join_public_study_group_when_guardrails_are_enabled(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_MIN_ACCOUNT_AGE_SECONDS", "600")
    _reset_caches()

    app = create_app()
    admin_client = TestClient(app)
    owner_client = TestClient(app)
    member_client = TestClient(app)

    assert admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"}).status_code == 200
    assert owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"}).status_code == 200
    assert member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"}).status_code == 200

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Join Guardrail Group",
            "description": "新号入组冷却测试",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    joined = member_client.post(f"/api/study-groups/{group_id}/join")

    assert joined.status_code == 403
    assert joined.json()["error"]["code"] == "FORBIDDEN"
    assert "before they can join study groups" in joined.json()["error"]["message"]
    assert int(joined.headers["Retry-After"]) >= 1


def test_new_account_cannot_immediately_comment_when_guardrails_are_enabled(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_STUDY_GROUP_CREATE_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_POST_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_COMMENT_MIN_ACCOUNT_AGE_SECONDS", "600")
    monkeypatch.setenv("PLM_STUDY_GROUP_COMMENT_MAX_ACTIONS_PER_WINDOW", "100")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    member_client = TestClient(app)

    owner_register = owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert owner_register.status_code == 200
    assert member_register.status_code == 200

    created = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Comment Guardrail Group",
            "description": "评论冷却测试",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["groupId"]

    joined = member_client.post(f"/api/study-groups/{group_id}/join")
    assert joined.status_code == 200

    post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "先发一条动态。"},
    )
    assert post.status_code == 200
    post_id = post.json()["data"]["postId"]

    blocked = member_client.post(
        f"/api/study-groups/{group_id}/posts/{post_id}/comments",
        json={"content": "我想立刻评论。"},
    )

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "FORBIDDEN"
    assert "before they can comment in study groups" in blocked.json()["error"]["message"]
    assert int(blocked.headers["Retry-After"]) >= 1


def test_study_group_join_request_rate_limit_blocks_repeated_requests(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_STUDY_GROUP_CREATE_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_REQUEST_MIN_ACCOUNT_AGE_SECONDS", "0")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_REQUEST_MAX_ACTIONS_PER_WINDOW", "1")
    monkeypatch.setenv("PLM_STUDY_GROUP_JOIN_REQUEST_WINDOW_SECONDS", "1800")
    _reset_caches()

    app = create_app()
    admin_client = TestClient(app)
    owner_client = TestClient(app)
    member_client = TestClient(app)

    assert admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"}).status_code == 200
    assert owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"}).status_code == 200
    assert member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"}).status_code == 200

    first_group = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Approval Group One",
            "description": "第一次申请",
            "visibility": "public",
            "joinPolicy": "approval",
        },
    )
    second_group = owner_client.post(
        "/api/study-groups",
        json={
            "name": "Approval Group Two",
            "description": "第二次申请",
            "visibility": "public",
            "joinPolicy": "approval",
        },
    )
    assert first_group.status_code == 200
    assert second_group.status_code == 200

    first_request = member_client.post(
        f"/api/study-groups/{first_group.json()['data']['groupId']}/join-requests",
        json={"message": "我先申请第一个小组。"},
    )
    blocked = member_client.post(
        f"/api/study-groups/{second_group.json()['data']['groupId']}/join-requests",
        json={"message": "我再申请第二个小组。"},
    )

    assert first_request.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert blocked.json()["error"]["message"] == "Too many study group join requests in a short period. Try again later."
    assert int(blocked.headers["Retry-After"]) >= 1
