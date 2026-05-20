import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm", ".wmv", ".flv")
SUBTITLE_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa")
COVER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
PACKAGE_FILE_DIRS = {
    "video": "videos",
    "subtitle": "subtitles",
    "cover": "covers",
}


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


def _validate_package_file_path(path: str, expected_dir: str, label: str) -> None:
    if "\\" in path:
        raise CoursePackageError(f"{label} path 必须使用包内相对路径。")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise CoursePackageError(f"{label} path 必须使用包内相对路径。")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise CoursePackageError(f"{label} path 必须使用包内相对路径。")
    if len(parts) < 2:
        raise CoursePackageError(f"{label} path 必须包含文件名。")
    if parts[0] != expected_dir:
        raise CoursePackageError(f"{label} path 必须位于 {expected_dir}/。")


def _ensure_regular_file_inside_root(input_dir: Path, path: Path) -> None:
    if path.is_symlink():
        raise CoursePackageError(f"不支持导入符号链接文件：{path}")
    root = input_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CoursePackageError(f"文件不在课程目录内：{path}") from exc


def _copy_package_file(source: Path, package_root: Path, relative_path: str) -> None:
    destination = package_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _ensure_output_dir_outside_input(input_dir: Path, output_dir: Path) -> None:
    input_root = input_dir.resolve()
    output_root = output_dir.resolve()
    try:
        output_root.relative_to(input_root)
    except ValueError:
        return
    raise CoursePackageError("课程包输出目录不能位于输入课程目录内。")


def iter_video_files(input_dir: Path) -> list[Path]:
    videos = sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    for video in videos:
        _ensure_regular_file_inside_root(input_dir, video)
    return videos


def _build_manifest_and_files(
    *,
    input_dir: Path,
    title: str,
    subject_id: str,
    scoped_project_id: str,
    package_id: str,
    created_at: str,
) -> tuple[dict[str, Any], list[tuple[Path, str]]]:
    videos = iter_video_files(input_dir)
    if not videos:
        raise CoursePackageError("未找到可导入的视频文件。")

    files: list[tuple[Path, str]] = []
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

        video_relative_path = f"videos/{item_id}{video.suffix.lower()}"
        item: dict[str, Any] = {
            "itemId": item_id,
            "title": video.stem,
            "order": index,
            "learningObjectKey": item_id,
            "video": _file_entry(video, video_relative_path),
        }
        files.append((video, video_relative_path))

        subtitle = _find_sidecar(video, SUBTITLE_EXTENSIONS)
        if subtitle is not None:
            _ensure_regular_file_inside_root(input_dir, subtitle)
            subtitle_relative_path = f"subtitles/{item_id}{subtitle.suffix.lower()}"
            item["subtitle"] = {
                **_file_entry(subtitle, subtitle_relative_path),
                "language": "zh-CN",
            }
            files.append((subtitle, subtitle_relative_path))
        cover = _find_sidecar(video, COVER_EXTENSIONS)
        if cover is not None:
            _ensure_regular_file_inside_root(input_dir, cover)
            cover_relative_path = f"covers/{item_id}{cover.suffix.lower()}"
            item["cover"] = _file_entry(cover, cover_relative_path)
            files.append((cover, cover_relative_path))
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
    return manifest, files


def build_course_package_manifest(
    *,
    input_dir: Path,
    title: str,
    subject_id: str,
    scoped_project_id: str,
    package_id: str,
    created_at: str,
) -> dict[str, Any]:
    manifest, _files = _build_manifest_and_files(
        input_dir=input_dir,
        title=title,
        subject_id=subject_id,
        scoped_project_id=scoped_project_id,
        package_id=package_id,
        created_at=created_at,
    )
    return manifest


def build_course_package(
    *,
    input_dir: Path,
    output_dir: Path,
    title: str,
    subject_id: str,
    scoped_project_id: str,
    package_id: str,
    created_at: str,
) -> dict[str, Any]:
    _ensure_output_dir_outside_input(input_dir, output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise CoursePackageError("课程包输出路径必须是目录。")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CoursePackageError("课程包输出目录必须为空。")

    manifest, files = _build_manifest_and_files(
        input_dir=input_dir,
        title=title,
        subject_id=subject_id,
        scoped_project_id=scoped_project_id,
        package_id=package_id,
        created_at=created_at,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for source, relative_path in files:
        _copy_package_file(source, output_dir, relative_path)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate_course_package_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("manifestVersion") != 1:
        raise CoursePackageError("manifestVersion 必须为 1。")
    for key in ("packageId", "title", "createdAt", "subjectId", "scopedProjectId"):
        if not str(manifest.get(key) or "").strip():
            raise CoursePackageError(f"manifest 缺少 {key}。")
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise CoursePackageError("manifest 缺少 source。")
    for key in ("tool", "version"):
        if not str(source.get(key) or "").strip():
            raise CoursePackageError(f"manifest.source 缺少 {key}。")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise CoursePackageError("manifest 必须包含至少一个视频条目。")
    seen_paths: set[str] = set()
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
            path = str(entry.get("path") or "").strip()
            if not path:
                raise CoursePackageError(f"items[{index}].{file_key} 缺少 path。")
            _validate_package_file_path(
                path,
                PACKAGE_FILE_DIRS[file_key],
                f"items[{index}].{file_key}",
            )
            if path in seen_paths:
                raise CoursePackageError(f"manifest 包含重复文件路径：{path}")
            seen_paths.add(path)
            if not isinstance(entry.get("sizeBytes"), int) or entry["sizeBytes"] < 0:
                raise CoursePackageError(f"items[{index}].{file_key} 缺少 sizeBytes。")
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256") or "")):
                raise CoursePackageError(f"items[{index}].{file_key} 缺少 sha256。")
