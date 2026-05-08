from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TURNSTILE_WIDGET = REPO_ROOT / "frontend" / "src" / "views" / "auth" / "TurnstileWidget.tsx"


def test_turnstile_loader_waits_for_cloudflare_ready_and_can_retry_after_script_failure() -> None:
    source = TURNSTILE_WIDGET.read_text(encoding="utf-8")

    assert "ready?: (callback: () => void) => void" in source
    assert "window.turnstile.ready" in source or "turnstile.ready" in source
    assert "TURNSTILE_SCRIPT_TIMEOUT_MS" in source
    assert "data-plm-turnstile-loaded" in source
    assert "script.remove()" in source
    assert "retryTurnstile" in source
