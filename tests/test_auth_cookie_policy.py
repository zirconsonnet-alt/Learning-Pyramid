from fastapi import Response

from adapter.auth import clear_auth_cookie, set_auth_cookie


def _set_cookie_header(response: Response) -> str:
    value = response.headers.get("set-cookie")
    assert value
    return value


def test_auth_cookie_defaults_to_lax_samesite(monkeypatch) -> None:
    monkeypatch.delenv("LEARNINGPYRAMID_AUTH_COOKIE_SAMESITE", raising=False)
    monkeypatch.setenv("LEARNINGPYRAMID_SECURE_COOKIES", "true")

    response = Response()
    set_auth_cookie(response, "session-token")

    header = _set_cookie_header(response)
    assert "plm_session=session-token" in header
    assert "SameSite=lax" in header
    assert "Secure" in header
    assert "HttpOnly" in header


def test_auth_cookie_can_use_none_samesite_for_cross_site_desktop(monkeypatch) -> None:
    monkeypatch.setenv("LEARNINGPYRAMID_AUTH_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("LEARNINGPYRAMID_SECURE_COOKIES", "true")

    response = Response()
    set_auth_cookie(response, "session-token")

    header = _set_cookie_header(response)
    assert "SameSite=none" in header
    assert "Secure" in header


def test_auth_cookie_invalid_samesite_falls_back_to_lax(monkeypatch) -> None:
    monkeypatch.setenv("LEARNINGPYRAMID_AUTH_COOKIE_SAMESITE", "invalid")
    monkeypatch.setenv("LEARNINGPYRAMID_SECURE_COOKIES", "true")

    response = Response()
    set_auth_cookie(response, "session-token")

    assert "SameSite=lax" in _set_cookie_header(response)


def test_auth_cookie_delete_uses_configured_samesite(monkeypatch) -> None:
    monkeypatch.setenv("LEARNINGPYRAMID_AUTH_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("LEARNINGPYRAMID_SECURE_COOKIES", "true")

    response = Response()
    clear_auth_cookie(response)

    header = _set_cookie_header(response)
    assert "plm_session=" in header
    assert "SameSite=none" in header
    assert "Secure" in header
