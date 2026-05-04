from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
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
from adapter.errors import register_exception_handlers
from adapter.main import create_app
from backend.models.enums import MaterialSourceKind, RollUpStrategy, SessionMode
from backend.models.learning_task_node import LearningTaskContainer
from backend.models.recall_point import Anchor
from backend.models.rich_content import rich_text


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_commission_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


@pytest.fixture()
def hosted_membership_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_ENABLE_MANUAL_TEST_PAYMENT", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path / "runtime-data"))
    _reset_caches()
    yield
    _reset_caches()


def _register_member(client: TestClient, email: str) -> str:
    resp = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200
    return str(resp.json()["data"]["userId"])


def _activate_membership(client: TestClient) -> str:
    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    order_id = str(created.json()["data"]["order"]["orderId"])
    confirmed = client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["membership"]["isActive"] is True
    return order_id


def test_unknown_api_path_returns_error_envelope() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/not-found")
    assert resp.status_code == 404
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "Not found",
        },
    }


def test_unknown_exception_hides_internal_details_by_default() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("sensitive-path: C:/secret/file.txt")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "UNKNOWN",
            "message": "Internal server error",
        },
    }


def test_system_capabilities_reflect_hosted_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/system/capabilities")

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "data": {
            "appMode": "hosted",
            "asrEnabled": False,
            "serverMediaStreamEnabled": False,
            "browserLocalMediaEnabled": True,
            "baiduNetdiskEnabled": False,
            "authEnabled": True,
            "allowSignup": False,
            "signupInviteRequired": True,
            "passwordResetEnabled": False,
            "emailVerificationEnabled": False,
            "signupHumanCheckEnabled": False,
            "signupHumanCheckSiteKey": None,
            "llmConfigured": False,
            "storyGenerationConfigured": False,
            "llmSource": "none",
            "ready": True,
            "sqlBackend": "sqlite",
        },
    }


def test_system_capabilities_report_password_reset_when_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_PASSWORD_RESET", "true")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://example.com")
    monkeypatch.setenv("PLM_TRUSTED_HOSTS", "testserver,example.com")
    monkeypatch.setenv("PLM_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PLM_SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/system/capabilities")

    assert resp.status_code == 200
    assert resp.json()["data"]["passwordResetEnabled"] is True


def test_system_capabilities_report_signup_protection_flags(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_ENABLE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("PLM_ENABLE_SIGNUP_HUMAN_CHECK", "true")
    monkeypatch.setenv("PLM_TURNSTILE_SITE_KEY", "turnstile-site-key")
    monkeypatch.setenv("PLM_TURNSTILE_SECRET_KEY", "turnstile-secret-key")
    monkeypatch.setenv("PLM_TURNSTILE_EXPECTED_HOSTNAME", "example.com")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://example.com")
    monkeypatch.setenv("PLM_TRUSTED_HOSTS", "testserver,example.com")
    monkeypatch.setenv("PLM_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PLM_SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/system/capabilities")

    assert resp.status_code == 200
    assert resp.json()["data"]["signupInviteRequired"] is False
    assert resp.json()["data"]["emailVerificationEnabled"] is True
    assert resp.json()["data"]["signupHumanCheckEnabled"] is True
    assert resp.json()["data"]["signupHumanCheckSiteKey"] == "turnstile-site-key"


def test_public_download_catalog_and_assets_are_public(monkeypatch, tmp_path: Path) -> None:
    download_root = tmp_path / "public-downloads"
    download_root.mkdir(parents=True)
    asset_path = download_root / "LearningPyramid-subtitle-tool-0.1.0-beta.3-windows-x64.zip"
    asset_path.write_bytes(b"zip-bytes")
    (download_root / "catalog.json").write_text(
        json.dumps(
            {
                "generatedAt": "2026-03-29T08:00:00Z",
                "items": [
                    {
                        "id": "subtitle-generator-windows-x64",
                        "displayName": "LearningPyramid 字幕生成工具",
                        "version": "0.1.0-beta.3",
                        "platform": "windows-x64",
                        "summary": "离线字幕生成工具",
                        "assetPath": asset_path.name,
                        "publishedAt": "2026-03-29T08:00:00Z",
                        "sha256": "abc123",
                        "recommended": True,
                        "includedComponents": ["ffmpeg", "whisper.cpp", "ggml-base.bin"],
                        "requirements": ["Windows 10/11 x64"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_PUBLIC_DOWNLOADS_DIR", str(download_root))
    _reset_caches()

    client = TestClient(create_app())
    catalog_resp = client.get("/api/system/public-downloads")

    assert catalog_resp.status_code == 200
    assert catalog_resp.json() == {
        "ok": True,
        "data": {
            "generatedAt": "2026-03-29T08:00:00Z",
            "items": [
                {
                    "id": "subtitle-generator-windows-x64",
                    "displayName": "LearningPyramid 字幕生成工具",
                    "version": "0.1.0-beta.3",
                    "platform": "windows-x64",
                    "summary": "离线字幕生成工具",
                    "fileName": asset_path.name,
                    "assetPath": asset_path.name,
                    "downloadPath": f"/downloads/{asset_path.name}",
                    "publishedAt": "2026-03-29T08:00:00Z",
                    "sha256": "abc123",
                    "sizeBytes": len(b"zip-bytes"),
                    "recommended": True,
                    "includedComponents": ["ffmpeg", "whisper.cpp", "ggml-base.bin"],
                    "requirements": ["Windows 10/11 x64"],
                }
            ],
        },
    }

    file_resp = client.get(f"/downloads/{asset_path.name}")
    assert file_resp.status_code == 200
    assert file_resp.content == b"zip-bytes"

    blocked_resp = client.get("/downloads/../secret.txt")
    assert blocked_resp.status_code == 404
    _reset_caches()


def test_public_health_endpoint_does_not_require_auth_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    with patch("adapter.main.get_auth_store", side_effect=AssertionError("auth store should not be used for /api/health/live")):
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/api/health/live")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["data"]["status"] == "ok"
    _reset_caches()


def test_global_llm_settings_endpoint_updates_runtime_capabilities(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())

    before = client.get("/api/system/capabilities")
    assert before.status_code == 200
    assert before.json()["data"]["llmConfigured"] is False

    updated = client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["llmConfigured"] is True
    assert updated.json()["data"]["llmSource"] == "global"
    assert updated.json()["data"]["promptAssemblyMode"] == "system"
    assert updated.json()["data"]["savedApiKeyPreview"] == "sk-l...5678"

    listed = client.get("/api/system/global-llm-settings")
    assert listed.status_code == 200
    assert listed.json()["data"]["savedApiKeyConfigured"] is True
    assert listed.json()["data"]["promptAssemblyMode"] == "system"

    after = client.get("/api/system/capabilities")
    assert after.status_code == 200
    assert after.json()["data"]["llmConfigured"] is True
    assert after.json()["data"]["llmSource"] == "global"
    _reset_caches()


def test_system_llm_ask_endpoint_uses_saved_global_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    saved = client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )
    assert saved.status_code == 200

    captured: dict[str, object] = {}

    def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["api_key"] = api_key
        captured["timeout_sec"] = timeout_sec
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "你好，我已经准备好了。",
                    }
                }
            ]
        }

    with patch("backend.system.api.SystemAPI._http_post_json", side_effect=fake_post_json):
        resp = client.post(
            "/api/system/llm/ask",
            json={
                "prompt": "简单介绍一下你自己",
                "systemPrompt": "你是一个简洁的助手",
                "temperature": 0.2,
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": {"content": "你好，我已经准备好了。"}}
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["api_key"] == "sk-local-12345678"
    assert captured["timeout_sec"] == 60.0
    assert captured["payload"] == {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "你是一个简洁的助手"},
            {"role": "user", "content": "简单介绍一下你自己"},
        ],
        "temperature": 0.2,
    }
    _reset_caches()


def test_member_can_read_and_update_personal_llm_settings(hosted_membership_env: None) -> None:
    client = TestClient(create_app())
    _register_member(client, "active-member@example.com")
    _activate_membership(client)

    before = client.get("/api/profile/me/llm-settings")
    assert before.status_code == 200

    updated = client.put(
        "/api/profile/me/llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-member-12345678",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["llmConfigured"] is True
    assert updated.json()["data"]["llmSource"] == "user"


def test_non_member_is_blocked_from_personal_llm_settings(hosted_membership_env: None) -> None:
    client = TestClient(create_app())
    _register_member(client, "non-member@example.com")

    listed = client.get("/api/profile/me/llm-settings")
    assert listed.status_code == 400
    assert listed.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "This feature requires active membership.",
        },
    }

    updated = client.put(
        "/api/profile/me/llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-member-12345678",
        },
    )
    assert updated.status_code == 400
    assert updated.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "This feature requires active membership.",
        },
    }


def test_system_llm_ask_endpoint_can_concat_system_prompt_into_user_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    saved = client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
            "promptAssemblyMode": "user_concat",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["promptAssemblyMode"] == "user_concat"

    captured: dict[str, object] = {}

    def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
        captured["payload"] = payload
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    with patch("backend.system.api.SystemAPI._http_post_json", side_effect=fake_post_json):
        resp = client.post(
            "/api/system/llm/ask",
            json={
                "prompt": "简单介绍一下你自己",
                "systemPrompt": "你是一个简洁的助手",
            },
        )

    assert resp.status_code == 200
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert messages == [
        {
            "role": "user",
            "content": (
                "以下内容是系统规则与上下文，请把它们和用户问题一起视为本次输入，严格依据这些信息回答。\n"
                "[系统信息]\n"
                "你是一个简洁的助手\n"
                "[用户问题]\n"
                "简单介绍一下你自己"
            ),
        }
    ]
    _reset_caches()


def test_system_llm_ask_endpoint_requires_configured_service(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.delenv("PLM_NATIVE_LLM_QA_BASE_URL", raising=False)
    monkeypatch.delenv("PLM_NATIVE_LLM_QA_MODEL", raising=False)
    monkeypatch.delenv("PLM_NATIVE_LLM_QA_API_KEY", raising=False)
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.post("/api/system/llm/ask", json={"prompt": "hello"})

    assert resp.status_code == 400
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "LLM service is not configured",
        },
    }
    _reset_caches()


def test_project_llm_ask_endpoint_includes_recall_point_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "LLM Context Project",
        project_root=str(tmp_path / "project-context"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    instance_id = api.add_instance(project_id, "manual/clip-1")
    api.add_learning_object_leaf(project_id, parent_id=None, instance_id=instance_id, title="Clip 1")
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[
            (
                rich_text("What is spaced repetition?"),
                rich_text("It is reviewing information over time."),
                Anchor(instance_id=instance_id, position="t=1200"),
            )
        ],
        title="Lesson 1",
    )
    recall_point = api.list_recall_points_by_learning_task_node(project_id, entry_node_id)[0]

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )

    captured: dict[str, object] = {}

    def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["api_key"] = api_key
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "根据当前复述点内容，这是一个关于间隔复习的问题。",
                    }
                }
            ]
        }

    with patch("backend.system.api.SystemAPI._http_post_json", side_effect=fake_post_json):
        resp = client.post(
            f"/api/projects/{project_id}/llm/ask",
            json={
                "prompt": "请用一句话总结这条复述点",
                "recallPointId": str(recall_point.recall_point_id),
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": {"content": "根据当前复述点内容，这是一个关于间隔复习的问题。"}}
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["api_key"] == "sk-local-12345678"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    joined = "\n".join(str(item.get("content", "")) for item in messages if isinstance(item, dict))
    assert "Project title: LLM Context Project" in joined
    assert "Context target: recall point" in joined
    assert "What is spaced repetition?" in joined
    assert "It is reviewing information over time." in joined
    assert "不要回答“未提供当前节点内容/主题/关键词”" in joined
    assert "请用一句话总结这条复述点" in joined
    _reset_caches()


def test_project_llm_ask_endpoint_can_concat_context_into_user_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "LLM Concat Project",
        project_root=str(tmp_path / "project-context-user-concat"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    instance_id = api.add_instance(project_id, "manual/clip-2")
    api.add_learning_object_leaf(project_id, parent_id=None, instance_id=instance_id, title="Clip 2")
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[
            (
                rich_text("事件的和含义"),
                rich_text("A和B至少发生一个"),
                Anchor(instance_id=instance_id, position="t=2200"),
            )
        ],
        title="1.2事件关系运算",
    )

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
            "promptAssemblyMode": "user_concat",
        },
    )

    captured: dict[str, object] = {}

    def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
        captured["payload"] = payload
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    with patch("backend.system.api.SystemAPI._http_post_json", side_effect=fake_post_json):
        resp = client.post(
            f"/api/projects/{project_id}/llm/ask",
            json={
                "prompt": "请基于当前节点内容出 3 道题",
                "learningTaskNodeId": str(entry_node_id),
            },
        )

    assert resp.status_code == 200
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    joined = str(messages[0]["content"])
    assert "以下内容是系统规则与上下文" in joined
    assert "[系统信息]" in joined
    assert "[项目上下文]" in joined
    assert "Project Context" in joined
    assert "Context target: learning task node" in joined
    assert "事件的和含义" in joined
    assert "A和B至少发生一个" in joined
    assert "请基于当前节点内容出 3 道题" in joined
    _reset_caches()


def test_project_llm_task_context_includes_recall_points_and_availability_note(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "Task Context Project",
        project_root=str(tmp_path / "project-task-context"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    instance_id = api.add_instance(project_id, "manual/clip-1")
    api.add_learning_object_leaf(project_id, parent_id=None, instance_id=instance_id, title="Clip 1")
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[
            (
                rich_text("概率论是研究什么的学科"),
                rich_text("随机现象的统计规律"),
                Anchor(instance_id=instance_id, position="t=1000"),
            ),
            (
                rich_text("随机试验的3个特点"),
                rich_text("可重复性，可预知性，不确定性"),
                Anchor(instance_id=instance_id, position="t=2000"),
            ),
        ],
        title="1.1随机事件",
    )

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )

    captured: dict[str, object] = {}

    def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "ok",
                    }
                }
            ]
        }

    with patch("backend.system.api.SystemAPI._http_post_json", side_effect=fake_post_json):
        resp = client.post(
            f"/api/projects/{project_id}/llm/ask",
            json={
                "prompt": "请总结当前任务节点的内容",
                "learningTaskNodeId": str(entry_node_id),
            },
        )

    assert resp.status_code == 200
    payload = captured["payload"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    joined = "\n".join(str(item.get("content", "")) for item in messages if isinstance(item, dict))
    assert "Context target: learning task node" in joined
    assert "Active recall points included: 2 / 2" in joined
    assert "do not claim the current node content is missing" in joined
    assert "Do not ask the user to provide the topic, keywords, or summary again." in joined
    assert "不要回答“未提供当前节点内容/主题/关键词”" in joined
    assert "概率论是研究什么的学科" in joined
    assert "随机试验的3个特点" in joined
    _reset_caches()


def test_project_llm_ask_endpoint_rejects_multiple_context_targets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    project_id = get_api().create_project(
        "Context Validation Project",
        project_root=str(tmp_path / "project-context-2"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )

    resp = client.post(
        f"/api/projects/{project_id}/llm/ask",
        json={
            "prompt": "hello",
            "recallPointId": "rp1",
            "learningTaskNodeId": "ltn1",
        },
    )

    assert resp.status_code == 400
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "Only one of recallPointId, learningTaskNodeId, learningObjectNodeId may be provided",
        },
    }
    _reset_caches()


def test_project_llm_chat_completions_endpoint_enforces_non_empty_messages(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    project_id = get_api().create_project(
        "Raw Chat Project",
        project_root=str(tmp_path / "project-raw-chat"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )

    empty_resp = client.post(
        f"/api/projects/{project_id}/llm/chat-completions",
        json={"messages": []},
    )
    assert empty_resp.status_code == 400
    assert empty_resp.json()["error"]["code"] == "INVALID_INPUT"
    assert any(error["loc"][-1] == "messages" for error in empty_resp.json()["error"]["details"])

    captured: dict[str, object] = {}

    def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["api_key"] = api_key
        captured["timeout_sec"] = timeout_sec
        return {"id": "chatcmpl_local", "choices": []}

    with patch("backend.system.api.SystemAPI._http_post_json", side_effect=fake_post_json):
        ok_resp = client.post(
            f"/api/projects/{project_id}/llm/chat-completions",
            json={
                "messages": [{"role": "user", "content": "hello"}],
                "parallelToolCalls": False,
            },
        )

    assert ok_resp.status_code == 200
    assert ok_resp.json() == {"ok": True, "data": {"id": "chatcmpl_local", "choices": []}}
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["api_key"] == "sk-local-12345678"
    assert captured["timeout_sec"] == 90.0
    assert captured["payload"] == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello"}],
        "parallel_tool_calls": False,
    }
    _reset_caches()


def test_project_llm_debug_endpoint_returns_latest_non_stream_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "Debug Project",
        project_root=str(tmp_path / "project-debug"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    instance_id = api.add_instance(project_id, "manual/clip-1")
    api.add_learning_object_leaf(project_id, parent_id=None, instance_id=instance_id, title="Clip 1")
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[(rich_text("事件的和含义"), rich_text("A和B至少发生一个"), Anchor(instance_id=instance_id, position="t=1000"))],
        title="1.2事件关系运算",
    )

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )

    with patch(
        "backend.system.api.SystemAPI._http_post_json",
        return_value={"choices": [{"message": {"role": "assistant", "content": "这是一次测试回答。"}}]},
    ):
        ask_resp = client.post(
            f"/api/projects/{project_id}/llm/ask",
            json={
                "prompt": "请总结当前节点",
                "learningTaskNodeId": str(entry_node_id),
            },
        )

    assert ask_resp.status_code == 200
    debug_resp = client.get(f"/api/projects/{project_id}/llm/debug/latest")
    assert debug_resp.status_code == 200
    payload = debug_resp.json()["data"]
    assert payload["projectId"] == str(project_id)
    assert payload["contextTargetKind"] == "task"
    assert payload["contextTargetId"] == str(entry_node_id)
    assert payload["stream"] is False
    assert payload["resolvedModelName"] == "gpt-4o-mini"
    assert payload["responseContent"] == "这是一次测试回答。"
    assert payload["errorMessage"] is None
    joined = "\n".join(item["content"] for item in payload["messages"])
    assert "Project Context" in joined
    assert "1.2事件关系运算" in joined
    assert "请总结当前节点" in joined
    _reset_caches()


def test_project_llm_stream_endpoint_returns_sse_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    project_id = get_api().create_project(
        "Stream Project",
        project_root=str(tmp_path / "project-stream"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )

    with patch("backend.system.api.SystemAPI.request_project_llm_text_stream", return_value=iter(["你好", "，世界"])) as mocked_stream:
        resp = client.post(
            f"/api/projects/{project_id}/llm/ask/stream",
            json={
                "prompt": "打个招呼",
                "learningTaskNodeId": "ltn_stream_1",
            },
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: start" in resp.text
    assert 'event: delta\ndata: {"content": "你好"}' in resp.text
    assert 'event: delta\ndata: {"content": "，世界"}' in resp.text
    assert "event: done" in resp.text
    mocked_stream.assert_called_once()
    kwargs = mocked_stream.call_args.kwargs
    assert str(kwargs["project_id"]) == str(project_id)
    assert str(kwargs["learning_task_node_id"]) == "ltn_stream_1"
    assert kwargs["user_prompt"] == "打个招呼"
    _reset_caches()


def test_non_member_hosted_llm_endpoints_are_blocked_before_llm_work(hosted_membership_env: None, tmp_path: Path) -> None:
    client = TestClient(create_app())
    _register_member(client, "blocked-ai@example.com")

    project_resp = client.post(
        "/api/projects",
        json={"title": "Blocked AI Project", "projectRoot": str(tmp_path / "blocked-ai-project"), "initialSourceKind": "MANUAL"},
    )
    assert project_resp.status_code == 200
    project_id = str(project_resp.json()["data"]["projectId"])

    system_resp = client.post("/api/system/llm/ask", json={"prompt": "hello"})
    assert system_resp.status_code == 400
    assert system_resp.json()["error"]["message"] == "This feature requires active membership."

    project_resp = client.post(f"/api/projects/{project_id}/llm/ask", json={"prompt": "hello"})
    assert project_resp.status_code == 400
    assert project_resp.json()["error"]["message"] == "This feature requires active membership."

    raw_resp = client.post(
        f"/api/projects/{project_id}/llm/chat-completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert raw_resp.status_code == 400
    assert raw_resp.json()["error"]["message"] == "This feature requires active membership."

    stream_resp = client.post(f"/api/projects/{project_id}/llm/ask/stream", json={"prompt": "hello"})
    assert stream_resp.status_code == 200
    assert 'event: error\ndata: {"code": "PRECONDITION", "message": "This feature requires active membership."}' in stream_resp.text


def test_member_hosted_llm_endpoints_continue_to_work(hosted_membership_env: None, tmp_path: Path) -> None:
    client = TestClient(create_app())
    _register_member(client, "working-ai@example.com")
    _activate_membership(client)
    client.put(
        "/api/profile/me/llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-member-12345678",
        },
    )

    project_resp = client.post(
        "/api/projects",
        json={"title": "Working AI Project", "projectRoot": str(tmp_path / "working-ai-project"), "initialSourceKind": "MANUAL"},
    )
    assert project_resp.status_code == 200
    project_id = str(project_resp.json()["data"]["projectId"])

    with patch(
        "backend.system.api.SystemAPI._http_post_json",
        return_value={"choices": [{"message": {"role": "assistant", "content": "会员可用"}}]},
    ):
        system_resp = client.post("/api/system/llm/ask", json={"prompt": "hello"})
        assert system_resp.status_code == 200
        assert system_resp.json()["data"]["content"] == "会员可用"

        project_ask = client.post(f"/api/projects/{project_id}/llm/ask", json={"prompt": "hello"})
        assert project_ask.status_code == 200
        assert project_ask.json()["data"]["content"] == "会员可用"

        raw_resp = client.post(
            f"/api/projects/{project_id}/llm/chat-completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert raw_resp.status_code == 200


def test_non_member_is_blocked_from_pomodoro_tts_preview(hosted_membership_env: None) -> None:
    client = TestClient(create_app())
    _register_member(client, "blocked-pomodoro@example.com")

    resp = client.post("/api/system/pomodoro/tts-preview", json={"text": "10 秒后开始专注"})
    assert resp.status_code == 400
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "This feature requires active membership.",
        },
    }


def test_non_member_can_still_use_project_and_review_endpoints(hosted_membership_env: None, tmp_path: Path) -> None:
    client = TestClient(create_app())
    _register_member(client, "non-member-regression@example.com")

    project_resp = client.post(
        "/api/projects",
        json={
            "title": "Ungated Workflow Project",
            "projectRoot": str(tmp_path / "ungated-project"),
            "initialSourceKind": "MANUAL",
            "initialProjectType": "LOOSE_POINTS",
        },
    )
    assert project_resp.status_code == 200
    project_id = str(project_resp.json()["data"]["projectId"])

    listed_projects = client.get("/api/projects")
    assert listed_projects.status_code == 200
    assert any(str(item["projectId"]) == project_id for item in listed_projects.json()["data"])

    submitted = client.post(
        f"/api/projects/{project_id}/learning-tasks",
        json={
            "title": "Review remains available",
            "items": [
                {
                    "question": [{"kind": "TEXT", "text": "什么是学习金字塔？"}],
                    "answer": [{"kind": "TEXT", "text": "一种帮助组织学习过程的结构化方法。"}],
                    "references": [],
                }
            ],
        },
    )
    assert submitted.status_code == 200, submitted.json()

    recall_points = client.get(f"/api/projects/{project_id}/recall-points")
    assert recall_points.status_code == 200
    assert len(recall_points.json()["data"]) == 1


def test_project_llm_debug_endpoint_returns_latest_stream_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "Stream Debug Project",
        project_root=str(tmp_path / "project-stream-debug"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    instance_id = api.add_instance(project_id, "manual/clip-1")
    object_node_id = api.add_learning_object_leaf(project_id, parent_id=None, instance_id=instance_id, title="1.2事件关系运算.mp4")

    client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-local-12345678",
        },
    )

    with patch("backend.system.api.SystemAPI._http_post_json_stream_text_chunks", return_value=iter(["你好", "，世界"])):
        stream_resp = client.post(
            f"/api/projects/{project_id}/llm/ask/stream",
            json={
                "prompt": "打个招呼",
                "learningObjectNodeId": str(object_node_id),
            },
        )

    assert stream_resp.status_code == 200
    debug_resp = client.get(f"/api/projects/{project_id}/llm/debug/latest")
    assert debug_resp.status_code == 200
    payload = debug_resp.json()["data"]
    assert payload["contextTargetKind"] == "object"
    assert payload["contextTargetId"] == str(object_node_id)
    assert payload["stream"] is True
    assert payload["responseContent"] == "你好，世界"
    assert payload["errorMessage"] is None
    joined = "\n".join(item["content"] for item in payload["messages"])
    assert "打个招呼" in joined
    _reset_caches()


def test_learning_task_node_patch_endpoint_updates_container_title(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "Node Rename Project",
        project_root=str(tmp_path / "project-node-rename"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )

    session = api.sys.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        api.sys.learning_task_node_repo.add(
            session,
            LearningTaskContainer(
                project_id=project_id,
                node_id="agg_node_1",
                parent_id=None,
                children=tuple(),
                title="聚合节点@L1",
            ),
        )
        api.sys.commit(session)
    except Exception:
        if session.state == "OPEN":
            api.sys.rollback(session)
        raise

    resp = client.patch(
        f"/api/projects/{project_id}/learning-task-nodes/agg_node_1",
        json={"title": "第一章总览"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": None}
    detail = client.get(f"/api/projects/{project_id}/learning-task-nodes/agg_node_1")
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "第一章总览"
    _reset_caches()


def test_learning_task_node_list_includes_entry_target_layer_for_object_mirrors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "Object Mirror Task Tree Project",
        project_root=str(tmp_path / "project-object-mirror-task-tree"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    root_node_id = api.add_learning_object_container(project_id, parent_id=None, children=tuple(), title="课程")
    chapter_node_id = api.add_learning_object_container(project_id, parent_id=root_node_id, children=tuple(), title="第一章")
    lesson_a = api.add_instance(project_id, "course/chapter-1/lesson-a.mp4")
    lesson_b = api.add_instance(project_id, "course/chapter-1/lesson-b.mp4")
    api.add_learning_object_leaf(project_id, parent_id=chapter_node_id, instance_id=lesson_a, title="1.1")
    api.add_learning_object_leaf(project_id, parent_id=chapter_node_id, instance_id=lesson_b, title="1.2")

    api.set_project_roll_up_strategy(project_id, RollUpStrategy.LEARNING_OBJECT_ISOMORPHIC)
    api.submit_learning_task(
        project_id,
        items=[
            (rich_text("Q1"), rich_text("A1"), Anchor(lesson_a, position="t=1000")),
            (rich_text("Q2"), rich_text("A2"), Anchor(lesson_b, position="t=2000")),
        ],
        title="第一章学习",
    )

    resp = client.get(f"/api/projects/{project_id}/learning-task-nodes")
    assert resp.status_code == 200
    mirror = next(
        item
        for item in resp.json()["data"]
        if item.get("nodeOrigin") == "OBJECT_MIRROR" and item.get("boundLearningObjectNodeId") == str(chapter_node_id)
    )
    assert mirror["title"] == "第一章"
    assert mirror["targetLayerIndex"] == 1
    _reset_caches()


def test_learning_task_node_list_includes_display_children_for_object_mirrors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    api = get_api()
    project_id = api.create_project(
        "Object Mirror Task Tree Children Project",
        project_root=str(tmp_path / "project-object-mirror-task-tree-children"),
        initial_source_kind=MaterialSourceKind.MANUAL,
    )
    root_node_id = api.add_learning_object_container(project_id, parent_id=None, children=tuple(), title="课程")
    chapter_node_id = api.add_learning_object_container(project_id, parent_id=root_node_id, children=tuple(), title="第一章")
    lesson_a = api.add_instance(project_id, "course/chapter-1/lesson-a.mp4")
    lesson_b = api.add_instance(project_id, "course/chapter-1/lesson-b.mp4")
    api.add_learning_object_leaf(project_id, parent_id=chapter_node_id, instance_id=lesson_a, title="1.1")
    api.add_learning_object_leaf(project_id, parent_id=chapter_node_id, instance_id=lesson_b, title="1.2")

    api.set_project_roll_up_strategy(project_id, RollUpStrategy.LEARNING_OBJECT_ISOMORPHIC)
    entry_node_id = api.submit_learning_task(
        project_id,
        items=[
            (rich_text("Q1"), rich_text("A1"), Anchor(lesson_a, position="t=1000")),
            (rich_text("Q2"), rich_text("A2"), Anchor(lesson_b, position="t=2000")),
        ],
        title="第一章学习",
    )

    resp = client.get(f"/api/projects/{project_id}/learning-task-nodes")
    assert resp.status_code == 200
    mirror = next(
        item
        for item in resp.json()["data"]
        if item.get("nodeOrigin") == "OBJECT_MIRROR" and item.get("boundLearningObjectNodeId") == str(chapter_node_id)
    )
    assert mirror["targetLayerIndex"] == 1
    assert mirror["children"] == []
    assert mirror["displayChildNodeIds"] == [str(entry_node_id)]
    _reset_caches()


def test_hosted_mode_disables_api_docs_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    assert client.get("/api/openapi.json").status_code == 404
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/redoc").status_code == 404


def test_hosted_mode_can_enable_api_docs_explicitly(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_API_DOCS", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    openapi = client.get("/api/openapi.json")
    docs = client.get("/api/docs")
    redoc = client.get("/api/redoc")

    assert openapi.status_code == 200
    assert openapi.json()["openapi"].startswith("3.")
    assert docs.status_code == 200
    assert "Swagger UI" in docs.text
    assert redoc.status_code == 200
    assert "ReDoc" in redoc.text


def test_health_endpoint_reports_runtime_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/health")

    body = resp.json()
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"]
    assert body["ok"] is True
    assert body["data"]["sqlBackend"] == "sqlite"
    assert body["data"]["store"]["ok"] is True
    assert body["data"]["auth"]["ok"] is True


def test_system_runtime_requires_auth_when_auth_enabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "runtime-auth@example.com")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    anon_client = TestClient(create_app())
    anon_resp = anon_client.get("/api/system/runtime")
    assert anon_resp.status_code == 401
    assert anon_resp.json()["error"]["message"] == "Authentication required"

    auth_client = TestClient(create_app())
    register_resp = auth_client.post("/api/auth/register", json={"email": "runtime-auth@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    authed_resp = auth_client.get("/api/system/runtime")
    assert authed_resp.status_code == 200
    assert authed_resp.json()["ok"] is True


def test_hosted_mode_blocks_asr_and_server_media_routes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "tester@example.com")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    register_resp = client.post(
        "/api/auth/register",
        json={"email": "tester@example.com", "password": "password123"},
    )
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Hosted Feature Flags"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    asr_resp = client.post(
        f"/api/projects/{project_id}/asr",
        json={
            "recallPointId": "rp1",
            "centerMs": 1000,
            "preMs": 30000,
            "postMs": 30000,
        },
    )
    instance_asr_resp = client.post(
        f"/api/projects/{project_id}/instances/i1/asr",
        json={
            "startMs": 0,
            "endMs": 60000,
        },
    )
    instance_asr_audio_resp = client.post(
        f"/api/projects/{project_id}/instances/i1/asr/audio",
        data={
            "startMs": "0",
            "endMs": "60000",
        },
        files={"file": ("clip.wav", b"wav", "audio/wav")},
    )
    media_resp = client.get(f"/api/projects/{project_id}/media/instances/i1")

    assert asr_resp.status_code == 400
    assert asr_resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "ASR is disabled in this deployment",
        },
    }
    assert instance_asr_resp.status_code == 400
    assert instance_asr_resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "ASR is disabled in this deployment",
        },
    }
    assert instance_asr_audio_resp.status_code == 400
    assert instance_asr_audio_resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "ASR is disabled in this deployment",
        },
    }
    assert media_resp.status_code == 400
    assert media_resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "Server-side media streaming is disabled in this deployment",
        },
    }
    _reset_caches()
