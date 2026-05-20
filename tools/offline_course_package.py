import hashlib
import re
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm", ".wmv", ".flv")
SUBTITLE_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa")
COVER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


class CoursePackageError(ValueError):
    pass


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def safe_id_from_stem(stem: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return safe or "item"


def _file_entry(path: Path, relative_path: str) -> dict[str, Any]:
    return {
        "path": relative_path.replace("\\", "/"),
        "sizeBytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _find_sidecar(path: Path, extensions: tuple[str, ...]) -> Path | None:
    for extension in extensions:
        candidate = path.with_suffix(extension)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def iter_video_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def build_course_package_manifest(
    *,
    input_dir: Path,
    title: str,
    subject_id: str,
    scoped_project_id: str,
    package_id: str,
    created_at: str,
) -> dict[str, Any]:
    videos = iter_video_files(input_dir)
    if not videos:
        raise CoursePackageError("未找到可导入的视频文件。")

    items: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, video in enumerate(videos, start=1):
        base_id = safe_id_from_stem(video.stem)
        item_id = base_id
        suffix = 2
        while item_id in used_ids:
            item_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(item_id)

        item: dict[str, Any] = {
            "itemId": item_id,
            "title": video.stem,
            "order": index,
            "learningObjectKey": item_id,
            "video": _file_entry(video, f"videos/{video.name}"),
        }
        subtitle = _find_sidecar(video, SUBTITLE_EXTENSIONS)
        if subtitle is not None:
            item["subtitle"] = {
                **_file_entry(subtitle, f"subtitles/{subtitle.name}"),
                "language": "zh-CN",
            }
        cover = _find_sidecar(video, COVER_EXTENSIONS)
        if cover is not None:
            item["cover"] = _file_entry(cover, f"covers/{cover.name}")
        items.append(item)

    manifest = {
        "manifestVersion": 1,
        "packageId": package_id,
        "title": title,
        "createdAt": created_at,
        "subjectId": subject_id,
        "scopedProjectId": scoped_project_id,
        "source": {"tool": "LearningPyramid-SubtitleTool", "version": "local"},
        "items": items,
    }
    validate_course_package_manifest(manifest)
    return manifest


def validate_course_package_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("manifestVersion") != 1:
        raise CoursePackageError("manifestVersion 必须为 1。")
    for key in ("packageId", "title", "createdAt", "subjectId", "scopedProjectId"):
        if not str(manifest.get(key) or "").strip():
            raise CoursePackageError(f"manifest 缺少 {key}。")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise CoursePackageError("manifest 必须包含至少一个视频条目。")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CoursePackageError(f"items[{index}] 必须是对象。")
        if not isinstance(item.get("video"), dict):
            raise CoursePackageError(f"items[{index}] 缺少 video。")
        for file_key in ("video", "subtitle", "cover"):
            entry = item.get(file_key)
            if entry is None:
                continue
            if not isinstance(entry, dict):
                raise CoursePackageError(f"items[{index}].{file_key} 必须是对象。")
            if not str(entry.get("path") or "").strip():
                raise CoursePackageError(f"items[{index}].{file_key} 缺少 path。")
            if not isinstance(entry.get("sizeBytes"), int) or entry["sizeBytes"] < 0:
                raise CoursePackageError(f"items[{index}].{file_key} 缺少 sizeBytes。")
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256") or "")):
                raise CoursePackageError(f"items[{index}].{file_key} 缺少 sha256。")
