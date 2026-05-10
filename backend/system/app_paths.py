import os
from pathlib import Path

from backend.system.version import APP_ID

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
    override = os.getenv("LEARNINGPYRAMID_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _platform_data_dir_name(APP_DIR_NAME)


def default_store_db_path() -> Path:
    return default_data_dir() / "learningpyramid_store.sqlite3"


def default_auth_db_path() -> Path:
    return default_data_dir() / "learningpyramid_auth.sqlite3"


def default_membership_db_path() -> Path:
    return default_data_dir() / "learningpyramid_membership.sqlite3"


def runtime_dir() -> Path:
    return default_data_dir() / "runtime"


def logs_dir() -> Path:
    return default_data_dir() / "logs"


def resolve_auth_db_path() -> Path:
    raw = os.getenv("LEARNINGPYRAMID_AUTH_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return default_auth_db_path()


def resolve_membership_db_path() -> Path:
    raw = os.getenv("LEARNINGPYRAMID_MEMBERSHIP_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return default_membership_db_path()


def resolve_store_db_path() -> Path:
    raw = os.getenv("LEARNINGPYRAMID_STORE_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return default_store_db_path()
