from __future__ import annotations

import os
import sys
from pathlib import Path


def load_packaged_default_server_url() -> str:
    candidates = []
    executable = Path(sys.executable).resolve()
    candidates.append(executable.with_name("server-default.txt"))
    candidates.append(Path(__file__).resolve().parent.parent / "server-default.txt")
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                text = candidate.read_text(encoding="utf-8").strip()
                if text:
                    return text.rstrip("/")
        except Exception:
            continue
    return ""


def current_default_server_url() -> str:
    env_value = str(os.getenv("PLM_PUBLIC_ORIGIN") or os.getenv("PLM_DESKTOP_AGENT_DEFAULT_SERVER_URL") or "").strip()
    if env_value:
        return env_value.rstrip("/")
    packaged = load_packaged_default_server_url()
    if packaged:
        return packaged.rstrip("/")
    return "http://127.0.0.1:8000"
