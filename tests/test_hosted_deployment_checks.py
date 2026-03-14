from __future__ import annotations

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
