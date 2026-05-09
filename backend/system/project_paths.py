import os
import re
from pathlib import Path

from backend.system.runtime_env import executable_dir, is_frozen, source_root

_INVALID_PATH_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_SEPARATOR_RE = re.compile(r"[\s\-]+")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def default_projects_root() -> Path:
    override = os.getenv("PLM_PROJECTS_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    base = executable_dir() if is_frozen() else source_root()
    return base / "data"


def sanitize_project_dir_name(title: str) -> str:
    name = _INVALID_PATH_CHARS_RE.sub("-", title.strip())
    name = _SEPARATOR_RE.sub("-", name)
    name = name.strip(" .-")
    if not name:
        name = "project"
    if name.upper() in _WINDOWS_RESERVED_NAMES:
        name = f"{name}-project"
    return name


def allocate_project_root(title: str, *, projects_root: Path | None = None) -> tuple[Path, Path]:
    base_root = (projects_root or default_projects_root()).expanduser().resolve()
    base_root.mkdir(parents=True, exist_ok=True)

    stem = sanitize_project_dir_name(title)
    candidate = base_root / stem
    suffix = 2
    while candidate.exists():
        candidate = base_root / f"{stem}-{suffix}"
        suffix += 1

    learning_root = candidate / "learning_objects"
    learning_root.mkdir(parents=True, exist_ok=False)
    return candidate, learning_root
