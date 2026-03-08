from __future__ import annotations

import atexit
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from functools import lru_cache
from pathlib import Path

from backend.models.errors import ExternalServiceError, PreconditionFailure
from backend.system.runtime_env import resource_root


BUILTIN_WHISPER_BASE_URL = "builtin://whisper"
_RUNTIME_LOCK = threading.Lock()
_RUNTIME_PROCESS: subprocess.Popen[str] | None = None
_RUNTIME_URL: str | None = None


def is_builtin_whisper_base_url(base_url: str | None) -> bool:
    text = (base_url or "").strip().lower()
    return text in {"", BUILTIN_WHISPER_BASE_URL, "local://whisper", "whisper://local"}


@lru_cache(maxsize=1)
def find_local_whisper_python() -> Path | None:
    candidates: list[Path] = []
    for key in ("PLM3_WHISPER_PYTHON", "WHISPER_PYTHON"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            candidates.append(Path(raw))

    if importlib.util.find_spec("whisper") is not None:
        candidates.append(Path(sys.executable))

    venv_python = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    home = Path.home()
    candidates.extend(
        [
            home / "whisper" / ".venv" / venv_python,
            Path.cwd() / "whisper" / ".venv" / venv_python,
        ]
    )

    if os.name == "nt":
        for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            candidates.append(Path(f"{drive}:/whisper/.venv/Scripts/python.exe"))
    else:
        candidates.extend(
            [
                Path("/opt/whisper/.venv/bin/python"),
                Path("/usr/local/whisper/.venv/bin/python"),
            ]
        )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if _python_supports_whisper(candidate):
            return candidate
    return None


def can_auto_use_local_whisper() -> bool:
    return find_local_whisper_python() is not None


def ensure_local_whisper_runtime() -> str:
    global _RUNTIME_PROCESS, _RUNTIME_URL
    with _RUNTIME_LOCK:
        if _RUNTIME_URL and _runtime_health_ok(_RUNTIME_URL):
            return _RUNTIME_URL

        if _RUNTIME_PROCESS is not None and _RUNTIME_PROCESS.poll() is not None:
            _RUNTIME_PROCESS = None
            _RUNTIME_URL = None

        python_exe = find_local_whisper_python()
        if python_exe is None:
            raise PreconditionFailure(
                "Local Whisper not found. Install it under H:\\whisper or set PLM3_WHISPER_PYTHON."
            )

        script_path = resource_root() / "tools" / "local_whisper_service.py"
        if not script_path.exists():
            raise ExternalServiceError(f"Local Whisper runtime script missing: {script_path}")

        port = _find_free_port()
        url = f"http://127.0.0.1:{port}"
        proc = subprocess.Popen(
            [str(python_exe), str(script_path), "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(script_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        deadline = time.time() + 60.0
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if _runtime_health_ok(url):
                _RUNTIME_PROCESS = proc
                _RUNTIME_URL = url
                return url
            time.sleep(0.5)

        try:
            proc.terminate()
        except Exception:
            pass
        raise ExternalServiceError("Failed to start local Whisper runtime")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _runtime_health_ok(url: str) -> bool:
    req = urllib.request.Request(f"{url}/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return False
    return bool(isinstance(payload, dict) and payload.get("ok"))


@lru_cache(maxsize=None)
def _python_supports_whisper(candidate: Path) -> bool:
    if not candidate.exists() or not candidate.is_file():
        return False
    try:
        proc = subprocess.run(
            [str(candidate), "-c", "import whisper; print('ok')"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return False
    return proc.returncode == 0 and "ok" in proc.stdout


def _stop_runtime() -> None:
    global _RUNTIME_PROCESS, _RUNTIME_URL
    with _RUNTIME_LOCK:
        proc = _RUNTIME_PROCESS
        _RUNTIME_PROCESS = None
        _RUNTIME_URL = None
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


atexit.register(_stop_runtime)
