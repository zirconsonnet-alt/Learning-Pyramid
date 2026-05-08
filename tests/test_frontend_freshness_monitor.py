from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN = REPO_ROOT / "frontend" / "src" / "main.tsx"
FRESHNESS_MONITOR = REPO_ROOT / "frontend" / "src" / "ui" / "runtime" / "frontendFreshness.ts"


def test_main_installs_frontend_freshness_monitor() -> None:
    source = MAIN.read_text(encoding="utf-8")

    assert 'import { installFrontendFreshnessMonitor } from "@/ui/runtime/frontendFreshness"' in source
    assert "installFrontendFreshnessMonitor()" in source


def test_frontend_freshness_monitor_checks_latest_index_bundle_and_reload_once() -> None:
    source = FRESHNESS_MONITOR.read_text(encoding="utf-8")

    assert 'const FRONTEND_ENTRY_ASSET_RE = /\\/assets\\/(index-[A-Za-z0-9_-]+\\.js)(?:[?#][^"\']*)?/' in source
    assert 'cache: "no-store"' in source
    assert 'credentials: "same-origin"' in source
    assert 'url.searchParams.set("__lp_freshness"' in source
    assert 'window.location.reload()' in source
    assert 'window.addEventListener("focus", handleWindowFocus)' in source
    assert 'window.addEventListener("pageshow", handlePageShow)' in source
    assert 'document.addEventListener("visibilitychange", handleVisibilityChange)' in source
    assert 'window.history.pushState = function pushState' in source
    assert 'window.history.replaceState = function replaceState' in source
    assert 'sessionStorage.getItem(RELOAD_MARKER)' in source
    assert 'sessionStorage.setItem(RELOAD_MARKER, reloadMarker)' in source
