from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return source_root()


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return source_root()
