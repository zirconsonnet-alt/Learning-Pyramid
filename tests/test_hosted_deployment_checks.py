from __future__ import annotations

import backend.system.membership_payment_service as membership_payment_service
from backend.system.membership_payment_service import current_wechat_native_payment_config
from backend.system.hosted_deployment_checks import hosted_runtime_blockers, hosted_runtime_warnings


def test_local_mode_has_no_hosted_runtime_blockers(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.delenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", raising=False)

    assert hosted_runtime_blockers() == tuple()


def test_hosted_mode_requires_media_access_secret(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.delenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", raising=False)

    blockers = hosted_runtime_blockers()

    assert blockers == ("PLM_MEDIA_ACCESS_TOKEN_SECRET must be set to a non-placeholder secret in hosted mode.",)


def test_hosted_mode_warns_about_signup_and_example_postgres_password(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_SECURE_COOKIES", "false")
    monkeypatch.setenv("PLM_SQL_BACKEND", "postgres")
    monkeypatch.setenv("PLM_POSTGRES_DSN", "postgresql://learningpyramid:learningpyramid@postgres:5432/learningpyramid")
    monkeypatch.setenv("PLM_POSTGRES_PASSWORD", "learningpyramid")
    monkeypatch.setenv("PLM_MEDIA_ACCESS_TOKEN_SECRET", "real-secret")
    monkeypatch.delenv("PLM_PUBLIC_ORIGIN", raising=False)
    monkeypatch.delenv("PLM_TRUSTED_HOSTS", raising=False)

    warnings = hosted_runtime_warnings()

    assert "PLM_ALLOW_SIGNUP=true leaves the hosted deployment open for self-registration." in warnings
    assert "PLM_SECURE_COOKIES is disabled. Use this only for temporary plain-HTTP localhost testing." in warnings
    assert "PLM_PUBLIC_ORIGIN is empty. Set it to the external HTTPS origin before public deployment." in warnings
    assert "PLM_TRUSTED_HOSTS is empty. Set it to the externally reachable host list." in warnings
    assert "PostgreSQL credentials still look like example values. Update PLM_POSTGRES_PASSWORD and PLM_POSTGRES_DSN before deployment." in warnings


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
