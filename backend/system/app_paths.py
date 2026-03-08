from __future__ import annotations

import os
import shutil
from pathlib import Path

from backend.system.version import APP_ID, LEGACY_APP_IDS

APP_DIR_NAME = APP_ID


def _platform_data_dir_name(app_dir_name: str) -> Path:
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA", "").strip()
        if base:
            return Path(base) / app_dir_name
        return Path.home() / "AppData" / "Local" / app_dir_name

    xdg = os.getenv("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / app_dir_name.lower()

    if os.sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_dir_name

    return Path.home() / ".local" / "share" / app_dir_name.lower()


def default_data_dir() -> Path:
    override = os.getenv("PLM_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _platform_data_dir_name(APP_DIR_NAME)


def legacy_data_dirs() -> tuple[Path, ...]:
    return tuple(_platform_data_dir_name(app_id) for app_id in LEGACY_APP_IDS if app_id != APP_DIR_NAME)


def default_store_path() -> Path:
    return default_data_dir() / "plm_store.json"


def runtime_dir() -> Path:
    return default_data_dir() / "runtime"


def logs_dir() -> Path:
    return default_data_dir() / "logs"


def resolve_store_path(*, legacy_root: Path | None = None) -> Path:
    raw = os.getenv("PLM_STORE_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()

    target = default_store_path()
    legacy = None if legacy_root is None else legacy_root / ".plm_store.json"
    if target.exists():
        return target

    if not os.getenv("PLM_DATA_DIR", "").strip():
        for legacy_dir in legacy_data_dirs():
            legacy_store = legacy_dir / "plm_store.json"
            if legacy_store.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_store, target)
                return target

    if legacy is None or not legacy.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, target)
    return target
