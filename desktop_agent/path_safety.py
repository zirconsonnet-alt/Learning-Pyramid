from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath


def resolve_agent_root(root_dir: str | Path) -> Path:
    root = Path(root_dir).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"root_dir not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"root_dir is not a directory: {root}")
    if root.is_symlink():
        raise RuntimeError(f"root_dir must not be a symlink: {root}")
    return root.resolve()


def normalize_agent_relative_path(relative_path: str) -> tuple[str, ...]:
    raw = str(relative_path or "").replace("\\", "/").strip().strip("/")
    if not raw:
        raise ValueError("relative_path must be non-empty")
    path = PurePosixPath(raw)
    if path.is_absolute():
        raise ValueError("relative_path must be relative")
    parts = path.parts
    if parts and ":" in parts[0]:
        raise ValueError("relative_path must not include a drive prefix")
    normalized_parts: list[str] = []
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("relative_path must not contain '..'")
        normalized_parts.append(part)
    if not normalized_parts:
        raise ValueError("relative_path must be non-empty")
    return tuple(normalized_parts)


def resolve_agent_media_path(root_dir: str | Path, relative_path: str) -> Path:
    root = resolve_agent_root(root_dir)
    parts = normalize_agent_relative_path(relative_path)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"symlink path is not supported: {current}")
    if current.suffix.lower() == ".lnk":
        raise RuntimeError(f"shortcut path is not supported: {current}")
    candidate = current.resolve()
    candidate.relative_to(root)
    if not candidate.exists():
        raise FileNotFoundError(f"media file not found: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"media path is not a file: {candidate}")
    return candidate


def iter_safe_media_files(root_dir: str | Path, *, video_extensions: set[str]) -> tuple[Path, ...]:
    root = resolve_agent_root(root_dir)
    items: list[Path] = []

    def _is_hidden(entry: os.DirEntry[str]) -> bool:
        if entry.name.startswith("."):
            return True
        try:
            attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        except OSError:
            return False
        hidden_flag = int(getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0))
        return bool(hidden_flag and attrs & hidden_flag)

    def _walk(current_dir: Path) -> None:
        with os.scandir(current_dir) as entries:
            ordered = sorted(entries, key=lambda item: item.name.casefold())
        for entry in ordered:
            if _is_hidden(entry):
                continue
            path = Path(entry.path)
            if entry.is_symlink():
                continue
            if path.suffix.lower() == ".lnk":
                continue
            if entry.is_dir(follow_symlinks=False):
                _walk(path)
                continue
            if entry.is_file(follow_symlinks=False) and path.suffix.lower() in video_extensions:
                items.append(path)

    _walk(root)
    return tuple(items)
