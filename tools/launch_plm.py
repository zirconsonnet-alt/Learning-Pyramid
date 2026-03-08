from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system.runtime_env import executable_dir, is_frozen, resource_root
from backend.system.app_paths import logs_dir, runtime_dir
from backend.system.version import APP_NAME, LEGACY_APP_IDS, SERVER_EXE_BASENAME


def _runtime_meta_path(host: str, port: int) -> Path:
    safe_host = host.replace(":", "_")
    return runtime_dir() / f"server-{safe_host}-{port}.json"


def _health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/api/health"


def _app_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/"


def _is_server_healthy(host: str, port: int, timeout_sec: float = 2.0) -> bool:
    req = urllib.request.Request(_health_url(host, port), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return False
    data = payload.get("data")
    return bool(isinstance(data, dict) and data.get("app") == APP_NAME)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_pid(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return
    try:
        os.kill(pid, 15)
    except OSError:
        return


def _read_process_command_line(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            return None
        return proc.stdout.strip() or None

    cmdline_path = Path(f"/proc/{pid}/cmdline")
    if not cmdline_path.exists():
        return None
    try:
        raw = cmdline_path.read_bytes()
    except Exception:
        return None
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip() or None


def _is_expected_runtime_process(pid: int, runtime_token: str) -> bool:
    cmdline = _read_process_command_line(pid)
    if not cmdline:
        return False
    text = cmdline.lower()
    server_markers = ["run_server.py", SERVER_EXE_BASENAME.lower(), "plm-server"]
    server_markers.extend(app_id.lower() for app_id in LEGACY_APP_IDS)
    return runtime_token.lower() in text and any(marker in text for marker in server_markers)


def _frontend_dist_exists() -> bool:
    if is_frozen():
        return _server_executable_path().exists()
    return (resource_root() / "frontend" / "dist" / "index.html").exists()


def _read_runtime_meta(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_runtime_meta(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _server_executable_path() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return executable_dir() / f"{SERVER_EXE_BASENAME}{suffix}"


def _server_command(host: str, port: int, runtime_token: str) -> list[str]:
    if is_frozen():
        return [
            str(_server_executable_path()),
            "--host",
            host,
            "--port",
            str(port),
            "--runtime-token",
            runtime_token,
            "--runtime-mode",
            "release",
        ]
    return [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "run_server.py"),
        "--host",
        host,
        "--port",
        str(port),
        "--runtime-token",
        runtime_token,
        "--runtime-mode",
        "release",
    ]


def _start_server(host: str, port: int, runtime_token: str) -> tuple[int, Path]:
    logs_dir().mkdir(parents=True, exist_ok=True)
    log_path = logs_dir() / "server.log"
    log_file = open(log_path, "a", encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        proc = subprocess.Popen(
            _server_command(host, port, runtime_token),
            cwd=str(executable_dir() if is_frozen() else PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            text=True,
            creationflags=creationflags,
        )
    finally:
        log_file.close()
    return proc.pid, log_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if not _frontend_dist_exists():
        if is_frozen():
            print(f"{APP_NAME} server binary is missing. Expected {_server_executable_path()}", file=sys.stderr)
        else:
            print(f"{APP_NAME} frontend build is missing. Expected frontend/dist/index.html.", file=sys.stderr)
            print("Build it first with: pnpm -C frontend install && pnpm -C frontend build", file=sys.stderr)
        return 1

    meta_path = _runtime_meta_path(args.host, args.port)
    if _is_server_healthy(args.host, args.port):
        if not args.no_browser:
            webbrowser.open(_app_url(args.host, args.port))
        print(f"{APP_NAME} is already running at {_app_url(args.host, args.port)}")
        return 0

    meta = _read_runtime_meta(meta_path)
    if meta is not None:
        pid = int(meta.get("pid", 0) or 0)
        runtime_token = str(meta.get("runtimeToken", "") or "")
        if pid > 0 and _pid_alive(pid) and runtime_token and _is_expected_runtime_process(pid, runtime_token):
            _terminate_pid(pid)
            time.sleep(1.0)
        else:
            meta_path.unlink(missing_ok=True)

    runtime_token = secrets.token_hex(16)
    pid, log_path = _start_server(args.host, args.port, runtime_token)
    deadline = time.time() + float(args.timeout)
    while time.time() < deadline:
        if _is_server_healthy(args.host, args.port):
            _write_runtime_meta(
                meta_path,
                {
                    "pid": pid,
                    "host": args.host,
                    "port": args.port,
                    "url": _app_url(args.host, args.port),
                    "logPath": str(log_path),
                    "runtimeToken": runtime_token,
                },
            )
            if not args.no_browser:
                webbrowser.open(_app_url(args.host, args.port))
            print(f"{APP_NAME} started at {_app_url(args.host, args.port)}")
            return 0
        time.sleep(0.5)

    print(f"{APP_NAME} failed to start. Check log: {log_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
