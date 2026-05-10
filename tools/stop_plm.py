import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system.app_paths import runtime_dir
from backend.system.version import APP_NAME, SERVER_EXE_BASENAME


def _runtime_meta_path(host: str, port: int) -> Path:
    safe_host = host.replace(":", "_")
    return runtime_dir() / f"server-{safe_host}-{port}.json"


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
    server_markers = ["run_server.py", SERVER_EXE_BASENAME.lower()]
    return runtime_token.lower() in text and any(marker in text for marker in server_markers)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    meta_path = _runtime_meta_path(args.host, args.port)
    if not meta_path.exists():
        print(f"No {APP_NAME} runtime metadata found.")
        return 0

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta_path.unlink(missing_ok=True)
        print("Removed invalid runtime metadata.")
        return 0

    pid = int(meta.get("pid", 0) or 0)
    runtime_token = str(meta.get("runtimeToken", "") or "")
    if pid > 0 and runtime_token and _is_expected_runtime_process(pid, runtime_token):
        _terminate_pid(pid)
        meta_path.unlink(missing_ok=True)
        print(f"{APP_NAME} stopped.")
    elif pid > 0:
        meta_path.unlink(missing_ok=True)
        print(f"Runtime metadata existed, but PID/token did not match a known {APP_NAME} runtime. Removed stale metadata.")
    else:
        meta_path.unlink(missing_ok=True)
        print(f"{APP_NAME} runtime was not running. Removed stale metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
