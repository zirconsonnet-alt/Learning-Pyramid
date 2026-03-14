from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def isoformat_from_unix_seconds(value: float | int) -> str:
    timestamp = max(0.0, float(value))
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()


def isoformat_from_unix_nanoseconds(value: float | int) -> str:
    timestamp = max(0.0, float(value)) / 1_000_000_000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()


def collect_media_file_stat_details(file_path: Path) -> dict[str, Any]:
    try:
        stat = file_path.stat()
    except Exception:
        return {}
    return {
        "sizeBytes": int(stat.st_size),
        "modifiedAt": isoformat_from_unix_nanoseconds(int(stat.st_mtime_ns)),
    }


def resolve_media_tool_path(name: str) -> str | None:
    resolved = shutil.which(str(name).strip())
    return None if not resolved else str(Path(resolved).resolve())
