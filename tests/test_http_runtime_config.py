from __future__ import annotations

from backend.system.http_runtime_config import current_http_runtime_config


def test_local_http_runtime_config_defaults_to_dev_origins(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.delenv("PLM_PUBLIC_ORIGIN", raising=False)
    monkeypatch.delenv("PLM_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("PLM_TRUSTED_HOSTS", raising=False)

    cfg = current_http_runtime_config()

    assert cfg.allowed_origins == ("http://localhost:5173", "http://localhost:3000")
    assert cfg.trusted_hosts == tuple()


def test_hosted_http_runtime_config_derives_origin_and_trusted_host(monkeypatch) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_PUBLIC_ORIGIN", "https://learn.example.com/path/ignored")
    monkeypatch.delenv("PLM_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("PLM_TRUSTED_HOSTS", raising=False)

    cfg = current_http_runtime_config()

    assert cfg.public_origin == "https://learn.example.com"
    assert cfg.allowed_origins == ("https://learn.example.com",)
    assert cfg.trusted_hosts == ("learn.example.com",)


def test_http_runtime_config_prefers_explicit_allowed_origins_and_trusted_hosts(monkeypatch) -> None:
    monkeypatch.setenv("PLM_ALLOWED_ORIGINS", "https://a.example.com, https://b.example.com")
    monkeypatch.setenv("PLM_TRUSTED_HOSTS", "a.example.com,b.example.com")
    monkeypatch.setenv("PLM_PROXY_HEADERS", "false")
    monkeypatch.setenv("PLM_FORWARDED_ALLOW_IPS", "*")

    cfg = current_http_runtime_config()

    assert cfg.allowed_origins == ("https://a.example.com", "https://b.example.com")
    assert cfg.trusted_hosts == ("a.example.com", "b.example.com")
    assert cfg.proxy_headers_enabled is False
    assert cfg.forwarded_allow_ips == "*"
