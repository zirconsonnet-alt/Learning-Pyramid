import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

try:
    import websocket
except Exception:  # pragma: no cover - environment guard
    websocket = None


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "frontend"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _find_chrome() -> str | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _wait_for(predicate, timeout: float = 20.0, interval: float = 0.1):
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:  # pragma: no cover - diagnostics path
            last_error = exc
        time.sleep(interval)
    if last_error:
        raise AssertionError(f"condition was not met before timeout: {last_error}") from last_error
    raise AssertionError("condition was not met before timeout")


def _json_response(path: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(path)
    endpoint = parsed.path
    now = "2026-05-09T00:00:00Z"

    if endpoint == "/api/system/capabilities":
        return {
            "ok": True,
            "data": {
                "appMode": "hosted",
                "asrEnabled": False,
                "serverMediaStreamEnabled": False,
                "browserLocalMediaEnabled": True,
                "baiduNetdiskEnabled": False,
                "authEnabled": False,
                "allowSignup": False,
                "signupInviteRequired": False,
                "passwordResetEnabled": False,
                "emailVerificationEnabled": False,
                "signupHumanCheckEnabled": False,
                "signupHumanCheckProvider": None,
                "signupHumanCheckChallengeUrl": None,
                "llmConfigured": False,
                "storyGenerationConfigured": False,
                "llmSource": "none",
            },
        }

    if endpoint == "/api/system/data-safety":
        return {
            "ok": True,
            "data": {
                "state": "ok",
                "checkedAt": now,
                "environment": "runtime-navigation-test",
                "releaseBlocked": False,
                "protectedClasses": [],
                "latestVerifiedBackup": None,
                "findings": [],
            },
        }

    if endpoint == "/api/subjects":
        return {
            "ok": True,
            "data": [
                {
                    "subjectId": "subj_runtime_navigation",
                    "title": "运行时导航测试学科",
                    "state": "ACTIVE",
                    "createdAt": now,
                    "deletedAt": None,
                }
            ],
        }

    if endpoint == "/api/projects":
        return {
            "ok": True,
            "data": [
                {
                    "projectId": "proj_runtime_navigation",
                    "title": "运行时导航测试项目",
                    "state": "ACTIVE",
                    "createdAt": now,
                    "deletedAt": None,
                }
            ],
        }

    if endpoint == "/api/subjects/subj_runtime_navigation/materials":
        return {
            "ok": True,
            "data": [
                {
                    "subjectId": "subj_runtime_navigation",
                    "materialId": "mat_runtime_navigation",
                    "materialType": "COURSE",
                    "title": "运行时导航测试项目",
                    "createdAt": now,
                    "projectId": "proj_runtime_navigation",
                }
            ],
        }

    if endpoint == "/api/projects/proj_runtime_navigation/audit-log-events":
        return {"ok": True, "data": []}

    if endpoint == "/api/membership/me":
        return {
            "ok": True,
            "data": {
                "userId": "runtime-navigation-user",
                "currentStatus": "active",
                "currentStartsAt": now,
                "currentEndsAt": "2099-12-31T23:59:59Z",
                "isActive": True,
                "isFirstOrderEligible": False,
                "baseMonthlyPriceCent": 1900,
                "firstOrderPriceCent": 100,
                "renewalPriceCent": 1900,
                "currentPriceCent": 1900,
                "supportedPaymentProviders": [],
            },
        }

    return {"ok": True, "data": []}


class _MockApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._send(_json_response(self.path))

    def do_POST(self) -> None:
        self._send({"ok": True, "data": None})

    def do_PATCH(self) -> None:
        self._send({"ok": True, "data": None})

    def do_DELETE(self) -> None:
        self._send({"ok": True, "data": None})

    def _send(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


class _CdpPage:
    def __init__(self, ws_url: str):
        if websocket is None:  # pragma: no cover - guarded by skip
            raise RuntimeError("websocket-client is not installed")
        self._ws = websocket.create_connection(ws_url, timeout=10)
        self._next_id = 0

    def close(self) -> None:
        self._ws.close()

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        message_id = self._next_id
        self._ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise AssertionError(f"CDP {method} failed: {message['error']}")
            return message.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if "exceptionDetails" in result:
            raise AssertionError(f"browser evaluation failed: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")


def _read_json(url: str, timeout: float = 5.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _start_mock_api(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), _MockApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _start_vite(api_port: int, vite_port: int) -> subprocess.Popen[str]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        pytest.skip("npm is not available")
    env = os.environ.copy()
    env["PLM_BACKEND_HOST"] = "127.0.0.1"
    env["PLM_BACKEND_PORT"] = str(api_port)
    env["BROWSER"] = "none"
    process = subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(vite_port), "--strictPort"],
        cwd=FRONTEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def ready() -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{vite_port}/projects", timeout=1) as response:
                return response.status == 200
        except Exception:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(f"Vite dev server exited early:\n{output[-2000:]}")
            return False

    _wait_for(ready, timeout=30.0)
    return process


def _open_chrome_page(chrome_path: str, cdp_port: int, target_url: str):
    profile_dir = tempfile.TemporaryDirectory(prefix="lp-chrome-profile-", ignore_cleanup_errors=True)
    process = subprocess.Popen(
        [
            chrome_path,
            "--headless=new",
            f"--remote-debugging-port={cdp_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir.name}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-gpu",
            "--window-size=1365,768",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        _wait_for(lambda: _read_json(f"http://127.0.0.1:{cdp_port}/json/version"), timeout=20.0)
        request = urllib.request.Request(
            f"http://127.0.0.1:{cdp_port}/json/new?{urllib.parse.quote(target_url, safe='')}",
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            page_info = json.loads(response.read().decode("utf-8"))
        page = _CdpPage(page_info["webSocketDebuggerUrl"])
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        profile_dir.cleanup()
        raise
    return process, profile_dir, page


@pytest.mark.skipif(websocket is None, reason="websocket-client is required for Chrome DevTools Protocol checks")
def test_pomodoro_shortcut_changes_url_and_rendered_route_together() -> None:
    chrome_path = _find_chrome()
    if not chrome_path:
        pytest.skip("Chrome or Chromium is required for runtime SPA navigation checks")

    api_port = _free_port()
    vite_port = _free_port()
    cdp_port = _free_port()
    api = _start_mock_api(api_port)
    vite: subprocess.Popen[str] | None = None
    chrome: subprocess.Popen[str] | None = None
    chrome_profile: tempfile.TemporaryDirectory[str] | None = None
    page: _CdpPage | None = None

    try:
        vite = _start_vite(api_port, vite_port)
        chrome, chrome_profile, page = _open_chrome_page(chrome_path, cdp_port, f"http://127.0.0.1:{vite_port}/projects")
        page.call("Page.enable")
        page.call("Runtime.enable")

        _wait_for(lambda: page.evaluate("document.readyState") == "complete", timeout=15.0)
        _wait_for(lambda: page.evaluate("location.pathname") == "/projects", timeout=15.0)
        _wait_for(lambda: "所有学科" in str(page.evaluate("document.body.innerText")), timeout=15.0)

        clicked_text = page.evaluate(
            """
            (() => {
              const links = Array.from(document.querySelectorAll('a[href="/pomodoro"]'));
              const link = links.find((item) => (item.textContent || '').trim()) || links[0];
              if (!link) return null;
              const text = (link.textContent || '').trim();
              link.click();
              return text;
            })()
            """,
        )

        assert clicked_text, "expected a visible Pomodoro shortcut link in the app header"
        _wait_for(lambda: page.evaluate("location.pathname") == "/pomodoro", timeout=15.0)

        def rendered_pomodoro_page() -> bool:
            body_text = str(page.evaluate("document.body.innerText"))
            return "番茄钟" in body_text and "所有学科" not in body_text

        _wait_for(rendered_pomodoro_page, timeout=15.0)
    finally:
        if page:
            page.close()
        if chrome:
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()
        if chrome_profile:
            chrome_profile.cleanup()
        if vite:
            vite.terminate()
            try:
                vite.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite.kill()
        api.shutdown()
        api.server_close()
