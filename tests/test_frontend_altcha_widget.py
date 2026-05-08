from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTH_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "auth" / "AuthPage.tsx"
ALTCHA_WIDGET = REPO_ROOT / "frontend" / "src" / "views" / "auth" / "AltchaWidget.tsx"
TURNSTILE_WIDGET = REPO_ROOT / "frontend" / "src" / "views" / "auth" / "TurnstileWidget.tsx"
SYSTEM_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "system.ts"
AUTH_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "auth.ts"


def test_auth_page_uses_altcha_not_turnstile_for_signup_human_check() -> None:
    auth_source = AUTH_PAGE.read_text(encoding="utf-8")
    system_source = SYSTEM_API.read_text(encoding="utf-8")
    auth_api_source = AUTH_API.read_text(encoding="utf-8")

    assert not TURNSTILE_WIDGET.exists()
    assert ALTCHA_WIDGET.exists()
    assert "AltchaWidget" in auth_source
    assert "Turnstile" not in auth_source
    assert "signupHumanCheckProvider" in system_source
    assert "signupHumanCheckChallengeUrl" in system_source
    assert "signupHumanCheckSiteKey" not in system_source
    assert "getSignupHumanCheckChallenge" in auth_api_source
    assert "humanCheckToken" in auth_api_source


def test_altcha_widget_imports_local_altcha_package_and_emits_verified_payload() -> None:
    source = ALTCHA_WIDGET.read_text(encoding="utf-8")

    assert 'import "altcha"' in source
    assert "<altcha-widget" in source
    assert "challengeUrl" in source
    assert 'name="altcha"' in source
    assert 'addEventListener("verified"' in source
    assert "onTokenChange" in source
