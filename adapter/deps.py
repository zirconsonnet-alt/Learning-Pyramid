from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from backend.system.api import SystemAPI
from backend.system.app_paths import resolve_store_path
from backend.system.inmemory_system import InMemorySystem


@lru_cache(maxsize=1)
def get_api() -> SystemAPI:
    project_root = Path(__file__).resolve().parent.parent
    persist_path = resolve_store_path(legacy_root=project_root)
    sys = InMemorySystem(persist_path=persist_path)
    return SystemAPI(sys)
