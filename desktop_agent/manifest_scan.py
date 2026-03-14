from __future__ import annotations

from pathlib import Path

from desktop_agent.local_diagnostics import collect_media_file_stat_details
from desktop_agent.path_safety import iter_safe_media_files, resolve_agent_root


VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".mpg",
    ".mpeg",
    ".wmv",
}


def scan_media_manifest(root_dir: str | Path) -> list[dict[str, str | int]]:
    root = resolve_agent_root(root_dir)

    items: list[dict[str, str | int]] = []
    for path in iter_safe_media_files(root, video_extensions=VIDEO_EXTENSIONS):
        rel = path.relative_to(root).as_posix()
        stat_details = collect_media_file_stat_details(path)
        items.append(
            {
                "relativePath": rel,
                "displayName": path.stem or path.name,
                "mediaKind": "video",
                "sizeBytes": int(stat_details.get("sizeBytes", 0)),
                "modifiedAt": str(stat_details.get("modifiedAt") or ""),
            }
        )
    return items
