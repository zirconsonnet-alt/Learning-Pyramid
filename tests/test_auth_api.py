from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from altcha import Challenge, solve_challenge
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
from backend.models.errors import NotFound
from backend.system.auth_store import SQLiteAuthStore


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_commission_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


def _enable_password_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_ENABLE_PASSWORD_RESET", "true")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://example.com")
    monkeypatch.setenv("PLM_TRUSTED_HOSTS", "testserver,example.com")
    monkeypatch.setenv("PLM_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PLM_SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")


def _enable_email_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_ENABLE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("PLM_EMAIL_VERIFICATION_TOKEN_TTL_MINUTES", "60")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://example.com")
    monkeypatch.setenv("PLM_TRUSTED_HOSTS", "testserver,example.com")
    monkeypatch.setenv("PLM_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PLM_SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")


def _enable_signup_human_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_ENABLE_SIGNUP_HUMAN_CHECK", "true")
    monkeypatch.setenv("PLM_ALTCHA_HMAC_SECRET", "altcha-hmac-secret")
    monkeypatch.setenv("PLM_ALTCHA_CHALLENGE_TTL_SECONDS", "120")


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "true")
    monkeypatch.setenv(
        "PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS",
        "owner@example.com,stranger@example.com,member@example.com,first@example.com,second@example.com,third@example.com",
    )
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    _reset_caches()
    yield
    _reset_caches()


def test_auth_required_and_project_owner_sees_created_project(auth_env: None) -> None:
    client = TestClient(create_app())

    unauthorized = client.get("/api/projects")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {
        "ok": False,
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Authentication required",
        },
    }

    register = client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert register.status_code == 200
    assert register.json()["data"]["email"] == "owner@example.com"

    initial_projects = client.get("/api/projects")
    assert initial_projects.status_code == 200
    assert initial_projects.json() == {"ok": True, "data": []}

    create_project = client.post("/api/projects", json={"title": "Hosted Project"})
    assert create_project.status_code == 200
    project_id = create_project.json()["data"]["projectId"]

    projects = client.get("/api/projects")
    assert projects.status_code == 200
    items = projects.json()["data"]
    assert len(items) == 1
    assert items[0]["projectId"] == project_id
    assert items[0]["title"] == "Hosted Project"
    assert items[0]["state"] == "ACTIVE"
    assert items[0]["deletedAt"] is None


def test_sqlite_auth_store_drops_legacy_study_group_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_auth.sqlite3"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE study_groups (group_id TEXT PRIMARY KEY);
            CREATE TABLE study_group_members (group_id TEXT, user_id TEXT);
            CREATE TABLE study_group_posts (post_id TEXT PRIMARY KEY, group_id TEXT);
            CREATE TABLE study_group_post_comments (comment_id TEXT PRIMARY KEY, post_id TEXT);
            CREATE TABLE study_group_join_requests (request_id TEXT PRIMARY KEY, group_id TEXT);
            """
        )
        conn.commit()
    finally:
        conn.close()

    SQLiteAuthStore(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        table_rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                'study_groups',
                'study_group_members',
                'study_group_posts',
                'study_group_post_comments',
                'study_group_join_requests',
                'friend_requests',
                'friendships'
              )
            ORDER BY name ASC
            """
        ).fetchall()
    finally:
        conn.close()

    table_names = [str(row[0]) for row in table_rows]
    assert table_names == ["friend_requests", "friendships"]


def test_sqlite_auth_snapshot_excludes_legacy_study_group_sections(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_auth.sqlite3"

    auth = SQLiteAuthStore(db_path)
    user = auth.create_user("snapshot@example.com", "password-123")
    auth.create_session(user.user_id)

    snapshot = auth.export_snapshot()

    assert snapshot["users"][0]["email"] == "snapshot@example.com"
    assert "friendRequests" in snapshot
    assert "friendships" in snapshot
    assert "studyGroups" not in snapshot
    assert "studyGroupMembers" not in snapshot
    assert "studyGroupPosts" not in snapshot
    assert "studyGroupPostComments" not in snapshot
    assert "studyGroupJoinRequests" not in snapshot


def test_sqlite_auth_store_hashes_session_tokens_at_rest(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_auth.sqlite3"

    auth = SQLiteAuthStore(db_path)
    user = auth.create_user("session@example.com", "password-123")
    session_token = auth.create_session(user.user_id)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT session_token FROM sessions WHERE user_id = ?",
            (user.user_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    stored_token = str(row[0])
    assert stored_token.startswith("sha256:")
    assert stored_token != session_token
    assert auth.get_user_by_session(session_token).user_id == user.user_id

    snapshot = auth.export_snapshot()
    assert snapshot["sessions"][0]["sessionToken"] == stored_token
    assert snapshot["sessions"][0]["sessionToken"] != session_token


def test_sqlite_auth_store_backfills_legacy_plaintext_session_tokens(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_auth.sqlite3"

    auth = SQLiteAuthStore(db_path)
    user = auth.create_user("legacy-session@example.com", "password-123")
    session_token = auth.create_session(user.user_id)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE sessions SET session_token = ? WHERE user_id = ?",
            (session_token, user.user_id),
        )
        conn.commit()
    finally:
        conn.close()

    reloaded = SQLiteAuthStore(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT session_token FROM sessions WHERE user_id = ?",
            (user.user_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert str(row[0]).startswith("sha256:")
    assert str(row[0]) != session_token
    assert reloaded.get_user_by_session(session_token).user_id == user.user_id


def test_sqlite_auth_store_delete_other_sessions_preserves_current_token(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_auth.sqlite3"

    auth = SQLiteAuthStore(db_path)
    user = auth.create_user("multi-session@example.com", "password-123")
    keep_token = auth.create_session(user.user_id)
    drop_token = auth.create_session(user.user_id)

    auth.delete_other_sessions_for_user(user.user_id, except_session_token=keep_token)

    assert auth.get_user_by_session(keep_token).user_id == user.user_id
    with pytest.raises(NotFound, match="session"):
        auth.get_user_by_session(drop_token)


def test_project_access_is_isolated_between_users(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    stranger_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Private Project"})
    project_id = created.json()["data"]["projectId"]

    stranger_client.post(
        "/api/auth/register",
        json={"email": "stranger@example.com", "password": "password123"},
    )

    projects = stranger_client.get("/api/projects")
    assert projects.status_code == 200
    assert projects.json() == {"ok": True, "data": []}

    forbidden = stranger_client.get(f"/api/projects/{project_id}/project-config")
    assert forbidden.status_code == 403
    assert forbidden.json() == {
        "ok": False,
        "error": {
            "code": "FORBIDDEN",
            "message": "Project access denied",
        },
    }


def test_project_material_source_binding_can_be_read_and_updated(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    initial = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert initial.status_code == 200
    initial_data = initial.json()["data"]
    assert initial_data["projectId"] == project_id
    assert initial_data["sourceKind"] == "SERVER_FS"
    assert initial_data["sourceRootLabel"] is None
    assert isinstance(initial_data["updatedAt"], str)

    updated = client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "SERVER_FS",
            "sourceRootLabel": "Course Videos",
        },
    )
    assert updated.status_code == 200
    assert updated.json() == {"ok": True, "data": None}

    fetched = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert fetched.status_code == 200
    fetched_data = fetched.json()["data"]
    assert fetched_data["projectId"] == project_id
    assert fetched_data["sourceKind"] == "SERVER_FS"
    assert fetched_data["sourceRootLabel"] == "Course Videos"
    assert isinstance(fetched_data["updatedAt"], str)
    assert fetched_data["updatedAt"] >= initial_data["updatedAt"]

    audit_events = client.get(f"/api/projects/{project_id}/audit-log-events")
    assert audit_events.status_code == 200
    assert audit_events.json()["data"][-1]["apiName"] == "set_project_material_source_binding"


def test_project_can_be_renamed(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Original Project"})
    project_id = created.json()["data"]["projectId"]

    renamed = client.patch(f"/api/projects/{project_id}", json={"title": "Renamed Project"})
    assert renamed.status_code == 200
    assert renamed.json() == {"ok": True, "data": None}

    projects = client.get("/api/projects")
    assert projects.status_code == 200
    items = projects.json()["data"]
    assert len(items) == 1
    assert items[0]["projectId"] == project_id
    assert items[0]["title"] == "Renamed Project"

    audit_events = client.get(f"/api/projects/{project_id}/audit-log-events")
    assert audit_events.status_code == 200
    assert audit_events.json()["data"][-1]["apiName"] == "edit_project"


def test_register_rejects_invalid_email(auth_env: None) -> None:
    client = TestClient(create_app())

    resp = client.post("/api/auth/register", json={"email": "not-an-email", "password": "password123"})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_INPUT"
    assert resp.json()["error"]["message"] == "Request validation failed"


def test_register_is_disabled_by_default_in_hosted_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.delenv("PLM_ALLOW_SIGNUP", raising=False)
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    assert resp.json()["error"]["message"] == "Sign-up is disabled in this deployment"


def test_register_requires_invite_for_non_bootstrap_email(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "owner@example.com")
    _reset_caches()

    client = TestClient(create_app())
    resp = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PRECONDITION"
    assert resp.json()["error"]["message"] == "invite code is required for registration"


def test_invited_user_does_not_become_super_admin(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "owner@example.com")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    invited_client = TestClient(app)

    owner_register = owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert owner_register.status_code == 200
    assert owner_register.json()["data"]["roles"] == ["super_admin"]
    owner_public_uid = owner_register.json()["data"]["publicUid"]

    invited_register = invited_client.post(
        "/api/auth/register",
        json={"email": "member@example.com", "password": "password123", "inviteCode": owner_public_uid},
    )

    assert invited_register.status_code == 200
    assert invited_register.json()["data"]["roles"] == []


def test_public_signup_can_disable_invite_requirement(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "owner@example.com")
    _reset_caches()

    client = TestClient(create_app())
    resp = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "member@example.com"
    assert resp.json()["data"]["emailVerificationRequired"] is False


def test_signup_human_check_blocks_missing_token(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    _enable_signup_human_check(monkeypatch)
    _reset_caches()

    client = TestClient(create_app())
    resp = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PRECONDITION"
    assert resp.json()["error"]["message"] == "human verification is required for registration"


def test_signup_human_check_verifies_token_when_enabled(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    _enable_signup_human_check(monkeypatch)
    _reset_caches()

    verified: dict[str, str | None] = {}

    def fake_verify_signup_human_check(token: str | None, *, remote_ip: str | None = None) -> None:
        verified["token"] = token
        verified["remote_ip"] = remote_ip

    monkeypatch.setattr("adapter.routers.auth.verify_signup_human_check", fake_verify_signup_human_check)

    client = TestClient(create_app())
    resp = client.post(
        "/api/auth/register",
        json={"email": "member@example.com", "password": "password123", "humanCheckToken": "altcha-token"},
    )

    assert resp.status_code == 200
    assert verified["token"] == "altcha-token"
    assert verified["remote_ip"] == "testclient"


def test_signup_human_check_challenge_endpoint_returns_altcha_payload(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    _enable_signup_human_check(monkeypatch)
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/auth/human-check/challenge")

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["parameters"]["algorithm"] == "SHA-256"
    assert payload["parameters"]["cost"] > 0
    assert payload["parameters"]["expiresAt"] is not None
    assert isinstance(payload["signature"], str)
    assert payload["signature"]


def test_signup_human_check_accepts_valid_altcha_payload(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_ALTCHA_COST", "10")
    _enable_signup_human_check(monkeypatch)
    _reset_caches()

    client = TestClient(create_app())
    challenge_resp = client.get("/api/auth/human-check/challenge")
    assert challenge_resp.status_code == 200

    challenge = Challenge.from_dict(challenge_resp.json()["data"])
    solution = solve_challenge(challenge, timeout=5)
    assert solution is not None
    token = __import__("altcha").Payload(challenge, solution).to_base64()

    resp = client.post(
        "/api/auth/register",
        json={"email": "member@example.com", "password": "password123", "humanCheckToken": token},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "member@example.com"


def test_email_verification_registration_requires_confirmation(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    _enable_email_verification(monkeypatch)
    _reset_caches()

    delivered: dict[str, object] = {}

    def fake_send_email_verification_email(*, to_email: str, verification_url: str, expires_minutes: int) -> None:
        delivered["to_email"] = to_email
        delivered["verification_url"] = verification_url
        delivered["expires_minutes"] = expires_minutes

    monkeypatch.setattr("adapter.routers.auth.send_email_verification_email", fake_send_email_verification_email)

    app = create_app()
    register_client = TestClient(app)
    login_client = TestClient(app)
    verify_client = TestClient(app)
    test_email = "verifymember@example.com"

    register = register_client.post("/api/auth/register", json={"email": test_email, "password": "password123"})
    assert register.status_code == 200
    assert register.json()["data"]["emailVerificationRequired"] is True
    assert register.json()["data"]["verificationEmailSent"] is True
    assert register_client.get("/api/auth/me").json() == {"ok": True, "data": None}
    assert delivered["to_email"] == test_email
    assert int(delivered["expires_minutes"]) >= 10

    blocked_login = login_client.post("/api/auth/login", json={"email": test_email, "password": "password123"})
    assert blocked_login.status_code == 401
    assert blocked_login.json()["error"]["message"] == "email verification is required before login"

    token = parse_qs(urlsplit(str(delivered["verification_url"])).query)["token"][0]
    confirm = verify_client.post("/api/auth/email-verification/confirm", json={"token": token})
    assert confirm.status_code == 200
    assert confirm.json()["data"]["email"] == test_email
    assert verify_client.get("/api/auth/me").json()["data"]["email"] == test_email

    login_after_confirm = TestClient(app).post("/api/auth/login", json={"email": test_email, "password": "password123"})
    assert login_after_confirm.status_code == 200


def test_email_verification_request_is_generic_for_unknown_email(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    _enable_email_verification(monkeypatch)
    _reset_caches()

    deliveries: list[str] = []

    def fake_send_email_verification_email(*, to_email: str, verification_url: str, expires_minutes: int) -> None:
        deliveries.append(to_email)

    monkeypatch.setattr("adapter.routers.auth.send_email_verification_email", fake_send_email_verification_email)

    client = TestClient(create_app())
    resp = client.post("/api/auth/email-verification/request", json={"email": "missing@example.com"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": None}
    assert deliveries == []


def test_password_reset_request_and_confirm_flow(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_password_reset(monkeypatch)
    _reset_caches()

    delivered: dict[str, object] = {}

    def fake_send_password_reset_email(*, to_email: str, reset_url: str, expires_minutes: int) -> None:
        delivered["to_email"] = to_email
        delivered["reset_url"] = reset_url
        delivered["expires_minutes"] = expires_minutes

    monkeypatch.setattr("adapter.routers.auth.send_password_reset_email", fake_send_password_reset_email)

    app = create_app()
    member_client = TestClient(app)
    recovery_client = TestClient(app)

    register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200
    assert member_client.get("/api/auth/me").json()["data"]["email"] == "member@example.com"

    request_reset = recovery_client.post("/api/auth/password-reset/request", json={"email": "member@example.com"})
    assert request_reset.status_code == 200
    assert request_reset.json() == {"ok": True, "data": None}
    assert delivered["to_email"] == "member@example.com"
    assert int(delivered["expires_minutes"]) >= 5

    token = parse_qs(urlsplit(str(delivered["reset_url"])).query)["token"][0]
    confirm_reset = recovery_client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "newPassword": "password456"},
    )
    assert confirm_reset.status_code == 200
    assert confirm_reset.json() == {"ok": True, "data": None}

    assert member_client.get("/api/auth/me").json() == {"ok": True, "data": None}

    old_login = TestClient(app).post("/api/auth/login", json={"email": "member@example.com", "password": "password123"})
    assert old_login.status_code == 401

    new_login = TestClient(app).post("/api/auth/login", json={"email": "member@example.com", "password": "password456"})
    assert new_login.status_code == 200


def test_password_reset_request_is_generic_for_unknown_email(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_password_reset(monkeypatch)
    _reset_caches()

    deliveries: list[str] = []

    def fake_send_password_reset_email(*, to_email: str, reset_url: str, expires_minutes: int) -> None:
        deliveries.append(to_email)

    monkeypatch.setattr("adapter.routers.auth.send_password_reset_email", fake_send_password_reset_email)

    client = TestClient(create_app())
    resp = client.post("/api/auth/password-reset/request", json={"email": "missing@example.com"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": None}
    assert deliveries == []


def test_login_rejects_invalid_email(auth_env: None) -> None:
    client = TestClient(create_app())

    resp = client.post("/api/auth/login", json={"email": "not-an-email", "password": "password123"})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_INPUT"
    assert resp.json()["error"]["message"] == "Request validation failed"


def test_hosted_mode_enables_auth_rate_limits_by_default(auth_env: None) -> None:
    assert get_auth_rate_limit_store().config.enabled is True


def test_signup_rate_limit_blocks_repeated_attempts(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_AUTH_SIGNUP_MAX_ATTEMPTS_PER_IP", "2")
    monkeypatch.setenv("PLM_AUTH_SIGNUP_MAX_ATTEMPTS_PER_EMAIL", "5")
    _reset_caches()

    client = TestClient(create_app())
    first = client.post("/api/auth/register", json={"email": "first@example.com", "password": "password123"})
    second = client.post("/api/auth/register", json={"email": "second@example.com", "password": "password123"})
    blocked = client.post("/api/auth/register", json={"email": "third@example.com", "password": "password123"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert blocked.json()["error"]["message"] == "Too many sign-up attempts. Try again later."
    assert int(blocked.headers["Retry-After"]) >= 1


def test_login_rate_limit_blocks_repeated_failures(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_AUTH_LOGIN_MAX_FAILURES_PER_IP", "10")
    monkeypatch.setenv("PLM_AUTH_LOGIN_MAX_FAILURES_PER_EMAIL", "2")
    _reset_caches()

    app = create_app()
    register_client = TestClient(app)
    login_client = TestClient(app)

    register = register_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    first = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})
    second = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})
    blocked = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})

    assert first.status_code == 401
    assert second.status_code == 401
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert blocked.json()["error"]["message"] == "Too many login attempts. Try again later."
    assert int(blocked.headers["Retry-After"]) >= 1


def test_successful_login_resets_email_failure_counter(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLM_AUTH_LOGIN_MAX_FAILURES_PER_IP", "10")
    monkeypatch.setenv("PLM_AUTH_LOGIN_MAX_FAILURES_PER_EMAIL", "2")
    _reset_caches()

    app = create_app()
    register_client = TestClient(app)
    login_client = TestClient(app)

    register = register_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    wrong_before_reset = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})
    good_after_reset = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "password123"})
    wrong_after_reset_one = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})
    wrong_after_reset_two = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})
    blocked = login_client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password"})

    assert wrong_before_reset.status_code == 401
    assert good_after_reset.status_code == 200
    assert wrong_after_reset_one.status_code == 401
    assert wrong_after_reset_two.status_code == 401
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
