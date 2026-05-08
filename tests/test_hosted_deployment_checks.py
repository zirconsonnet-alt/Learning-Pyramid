from __future__ import annotations

import importlib.util
from pathlib import Path

import backend.system.membership_payment_service as membership_payment_service
from backend.system.membership_payment_service import current_wechat_native_payment_config
from backend.system.hosted_deployment_checks import hosted_runtime_blockers, hosted_runtime_warnings, protected_storage_blockers


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_build_selfhost_bundle_module():
    module_path = REPO_ROOT / "tools" / "build_selfhost_bundle.py"
    spec = importlib.util.spec_from_file_location("build_selfhost_bundle", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_selfhost_compose_persists_legacy_app_data_project_root() -> None:
    compose_text = (REPO_ROOT / "docker-compose.selfhost.yml").read_text(encoding="utf-8")

    assert "- ./data/selfhost:/app/data" in compose_text


def test_selfhost_compose_declares_all_protected_data_roots() -> None:
    compose_text = (REPO_ROOT / "docker-compose.selfhost.yml").read_text(encoding="utf-8")

    assert "- ./data/selfhost:/data" in compose_text
    assert "- ./data/selfhost:/app/data" in compose_text


def test_selfhost_sync_preserves_old_frontend_chunks() -> None:
    sync_script = (REPO_ROOT / "tools" / "sync_selfhost_server.ps1").read_text(encoding="utf-8")

    assert "--filter 'P frontend/dist/assets/***'" in sync_script


def test_selfhost_bundle_normalizes_shell_scripts_to_lf(tmp_path: Path) -> None:
    module = _load_build_selfhost_bundle_module()
    script = tmp_path / "tools" / "post_deploy_selfhost.sh"
    script.parent.mkdir()
    script.write_bytes(b"#!/usr/bin/env bash\r\nset -euo pipefail\r\necho ok\r\n")

    module._normalize_bundle_shell_scripts(tmp_path)

    assert script.read_bytes() == b"#!/usr/bin/env bash\nset -euo pipefail\necho ok\n"


def test_selfhost_docker_context_includes_frontend_dist() -> None:
    dockerignore_lines = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    active_excludes = {
        line.strip()
        for line in dockerignore_lines
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("!")
    }

    assert "frontend/dist" not in active_excludes
    assert "frontend/dist/" not in active_excludes


def test_selfhost_sync_excludes_runtime_data_paths_from_delete() -> None:
    sync_script = (REPO_ROOT / "tools" / "sync_selfhost_server.ps1").read_text(encoding="utf-8")

    assert "--exclude 'data/'" in sync_script
    assert "--filter 'P data/***'" in sync_script
    assert "--filter 'P /data/***'" in sync_script


def test_shell_selfhost_sync_excludes_runtime_data_paths_from_delete() -> None:
    sync_script = (REPO_ROOT / "tools" / "sync_selfhost_server.sh").read_text(encoding="utf-8")

    assert "--exclude 'data/'" in sync_script
    assert "--filter 'P data/***'" in sync_script


def test_router_recovers_from_stale_dynamic_import_chunks() -> None:
    router_source = (REPO_ROOT / "frontend" / "src" / "router.tsx").read_text(encoding="utf-8")

    assert "Failed to fetch dynamically imported module" in router_source
    assert "window.location.reload()" in router_source


def test_local_mode_has_no_hosted_runtime_blockers(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.delenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", raising=False)

    assert hosted_runtime_blockers() == tuple()


def test_protected_storage_blockers_reject_missing_and_non_directory_paths(tmp_path) -> None:
    missing = tmp_path / "missing"
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("not a directory", encoding="utf-8")

    blockers = protected_storage_blockers((missing, file_path), data_expected=True)

    assert any("PROTECTED_PATH_MISSING" in item for item in blockers)
    assert any("PROTECTED_PATH_NOT_DIRECTORY" in item for item in blockers)


def test_protected_storage_blockers_reject_empty_expected_data_path(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    blockers = protected_storage_blockers((empty,), data_expected=True)

    assert blockers == (
        f"PROTECTED_PATH_EMPTY_UNEXPECTED: Protected data path is empty but data is expected: {empty}",
    )


def test_hosted_mode_requires_media_access_secret(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.delenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", raising=False)

    blockers = hosted_runtime_blockers()

    assert blockers == ("PLM_MEDIA_ACCESS_TOKEN_SECRET must be set to a non-placeholder secret in hosted mode.",)


def test_hosted_mode_warns_about_signup_and_example_postgres_password(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_REQUIRE_SIGNUP_INVITE", "false")
    monkeypatch.setenv("PLM_SECURE_COOKIES", "false")
    monkeypatch.setenv("PLM_SQL_BACKEND", "postgres")
    monkeypatch.setenv("PLM_POSTGRES_DSN", "postgresql://learningpyramid:learningpyramid@postgres:5432/learningpyramid")
    monkeypatch.setenv("PLM_POSTGRES_PASSWORD", "learningpyramid")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.delenv("PLM_PUBLIC_ORIGIN", raising=False)
    monkeypatch.delenv("PLM_TRUSTED_HOSTS", raising=False)

    warnings = hosted_runtime_warnings()

    assert (
        "PLM_ALLOW_SIGNUP=true enables hosted self-registration endpoints. Keep it disabled unless you intentionally want bootstrap, invite-based, or public registration."
        in warnings
    )
    assert (
        "Public sign-up should enable password recovery. Configure PLM_ENABLE_PASSWORD_RESET=true together with PLM_SMTP_* and PLM_PUBLIC_ORIGIN before opening registration."
        in warnings
    )
    assert (
        "Public sign-up without invite codes should enable email verification. Configure PLM_ENABLE_EMAIL_VERIFICATION=true together with PLM_SMTP_* and PLM_PUBLIC_ORIGIN before opening free registration."
        in warnings
    )
    assert (
        "Public sign-up without invite codes should enable human verification. Configure PLM_ENABLE_SIGNUP_HUMAN_CHECK=true together with PLM_ALTCHA_HMAC_SECRET before opening free registration."
        in warnings
    )
    assert "PLM_SECURE_COOKIES is disabled. Use this only for temporary plain-HTTP localhost testing." in warnings
    assert "PLM_PUBLIC_ORIGIN is empty. Set it to the external HTTPS origin before public deployment." in warnings
    assert "PLM_TRUSTED_HOSTS is empty. Set it to the externally reachable host list." in warnings
    assert "PostgreSQL credentials still look like example values. Update PLM_POSTGRES_PASSWORD and PLM_POSTGRES_DSN before deployment." in warnings


def test_hosted_mode_warns_about_partial_password_reset_config(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_PASSWORD_RESET", "true")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://example.com")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.delenv("PLM_SMTP_HOST", raising=False)
    monkeypatch.delenv("PLM_SMTP_FROM_EMAIL", raising=False)

    warnings = hosted_runtime_warnings()

    assert (
        "Password reset email is only partially configured. Complete PLM_SMTP_HOST, PLM_SMTP_FROM_EMAIL, PLM_PUBLIC_ORIGIN, and matching SMTP credentials or disable PLM_ENABLE_PASSWORD_RESET."
        in warnings
    )


def test_hosted_mode_warns_about_partial_email_verification_and_human_check_config(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("PLM_ENABLE_SIGNUP_HUMAN_CHECK", "true")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://example.com")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.delenv("PLM_SMTP_HOST", raising=False)
    monkeypatch.delenv("PLM_SMTP_FROM_EMAIL", raising=False)
    monkeypatch.delenv("PLM_ALTCHA_HMAC_SECRET", raising=False)

    warnings = hosted_runtime_warnings()

    assert (
        "Email verification is only partially configured. Complete PLM_SMTP_HOST, PLM_SMTP_FROM_EMAIL, PLM_PUBLIC_ORIGIN, and matching SMTP credentials or disable PLM_ENABLE_EMAIL_VERIFICATION."
        in warnings
    )
    assert (
        "Sign-up human verification is only partially configured. Complete PLM_ALTCHA_HMAC_SECRET or disable PLM_ENABLE_SIGNUP_HUMAN_CHECK."
        in warnings
    )


def test_hosted_mode_warns_about_partial_wechat_payment_config(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("PLM_WECHAT_PAY_APP_ID", "wx-test-app")
    monkeypatch.setenv("PLM_WECHAT_PAY_MCH_ID", "1900000109")
    monkeypatch.delenv("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH", raising=False)
    monkeypatch.delenv("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH", raising=False)

    warnings = hosted_runtime_warnings()

    assert "WeChat Native payment configuration is only partially filled. Complete every required PLM_WECHAT_PAY_* value or clear them all." in warnings


def test_hosted_mode_warns_when_wechat_payment_has_no_public_notify_origin(monkeypatch, tmp_path) -> None:
    private_key_path = tmp_path / "wechat-apiclient-key.pem"
    public_key_path = tmp_path / "wechatpay-public.pem"
    private_key_path.write_text("test-private-key")
    public_key_path.write_text("test-public-key")

    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.setenv("PLM_WECHAT_PAY_APP_ID", "wx-test-app")
    monkeypatch.setenv("PLM_WECHAT_PAY_MCH_ID", "1900000109")
    monkeypatch.setenv("PLM_WECHAT_PAY_CERT_SERIAL_NO", "SERIALNO1234567890")
    monkeypatch.setenv("PLM_WECHAT_PAY_API_V3_KEY", "0123456789ABCDEF0123456789ABCDEF")
    monkeypatch.setenv("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH", str(private_key_path))
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_ID", "PUB_KEY_ID_TEST")
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH", str(public_key_path))
    monkeypatch.delenv("PLM_PUBLIC_ORIGIN", raising=False)
    monkeypatch.delenv("PLM_WECHAT_PAY_NOTIFY_URL", raising=False)
    monkeypatch.delenv("PLM_WECHAT_PAY_REFUND_NOTIFY_URL", raising=False)

    warnings = hosted_runtime_warnings()

    assert "WeChat Native payment is enabled but neither PLM_PUBLIC_ORIGIN nor PLM_WECHAT_PAY_NOTIFY_URL is configured." in warnings
    assert "WeChat Native refunds need PLM_PUBLIC_ORIGIN, PLM_WECHAT_PAY_REFUND_NOTIFY_URL, or a usable PLM_WECHAT_PAY_NOTIFY_URL before production use." in warnings


def test_wechat_payment_config_accepts_legacy_appid_alias(monkeypatch, tmp_path) -> None:
    private_key_path = tmp_path / "wechat-apiclient-key.pem"
    public_key_path = tmp_path / "wechatpay-public.pem"
    private_key_path.write_text("test-private-key")
    public_key_path.write_text("test-public-key")

    monkeypatch.delenv("PLM_WECHAT_PAY_APP_ID", raising=False)
    monkeypatch.setenv("appid", "wx-legacy-appid")
    monkeypatch.setenv("PLM_WECHAT_PAY_MCH_ID", "1900000109")
    monkeypatch.setenv("PLM_WECHAT_PAY_CERT_SERIAL_NO", "SERIALNO1234567890")
    monkeypatch.setenv("PLM_WECHAT_PAY_API_V3_KEY", "0123456789ABCDEF0123456789ABCDEF")
    monkeypatch.setenv("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH", str(private_key_path))
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_ID", "PUB_KEY_ID_TEST")
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH", str(public_key_path))

    config = current_wechat_native_payment_config()

    assert config.app_id == "wx-legacy-appid"
    assert config.enabled is True


def test_wechat_payment_config_falls_back_to_repo_root_certs_when_container_paths_are_missing(monkeypatch, tmp_path) -> None:
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    private_key_path = certs_dir / "apiclient_key.pem"
    public_key_path = certs_dir / "wechatpay_public_key.pem"
    private_key_path.write_text("test-private-key")
    public_key_path.write_text("test-public-key")

    monkeypatch.setattr(membership_payment_service, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("PLM_WECHAT_PAY_APP_ID", "wx-test-app")
    monkeypatch.setenv("PLM_WECHAT_PAY_MCH_ID", "1900000109")
    monkeypatch.setenv("PLM_WECHAT_PAY_CERT_SERIAL_NO", "SERIALNO1234567890")
    monkeypatch.setenv("PLM_WECHAT_PAY_API_V3_KEY", "0123456789ABCDEF0123456789ABCDEF")
    monkeypatch.setenv("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH", "/app/certs/apiclient_key.pem")
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_ID", "PUB_KEY_ID_TEST")
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH", "/app/certs/wechatpay_public_key.pem")

    config = current_wechat_native_payment_config()

    assert config.private_key_pem_path == private_key_path.resolve()
    assert config.wechatpay_public_key_pem_path == public_key_path.resolve()
    assert config.enabled is True
