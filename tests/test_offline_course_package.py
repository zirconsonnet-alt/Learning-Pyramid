import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.offline_course_package import (
    CoursePackageError,
    build_course_package,
    build_course_package_manifest,
    sha256_file,
    validate_course_package_manifest,
)


def write_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_builds_manifest_from_local_videos_and_sidecar_subtitles(tmp_path: Path) -> None:
    root = tmp_path / "course"
    video = write_file(root / "01.mp4", b"video-01")
    subtitle = write_file(root / "01.srt", b"1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    cover = write_file(root / "01.jpg", b"cover-01")

    manifest = build_course_package_manifest(
        input_dir=root,
        title="默认网课材料",
        subject_id="subj_1",
        scoped_project_id="proj_1",
        package_id="pkg_test",
        created_at="2026-05-20T12:00:00Z",
    )

    assert manifest["manifestVersion"] == 1
    assert manifest["subjectId"] == "subj_1"
    assert manifest["scopedProjectId"] == "proj_1"
    assert manifest["source"] == {"tool": "LearningPyramid-SubtitleTool", "version": "local"}
    assert manifest["items"][0]["video"]["path"] == "videos/01.mp4"
    assert manifest["items"][0]["subtitle"]["path"] == "subtitles/01.srt"
    assert manifest["items"][0]["cover"]["path"] == "covers/01.jpg"
    assert manifest["items"][0]["video"]["sha256"] == hashlib.sha256(video.read_bytes()).hexdigest()
    assert manifest["items"][0]["subtitle"]["sha256"] == hashlib.sha256(subtitle.read_bytes()).hexdigest()
    assert manifest["items"][0]["cover"]["sha256"] == hashlib.sha256(cover.read_bytes()).hexdigest()


def test_validate_manifest_rejects_missing_project_identity() -> None:
    manifest = {
        "manifestVersion": 1,
        "packageId": "pkg_1",
        "title": "课程",
        "createdAt": "2026-05-20T12:00:00Z",
        "items": [],
    }

    with pytest.raises(CoursePackageError, match="subjectId"):
        validate_course_package_manifest(manifest)


def test_validate_manifest_rejects_missing_source_metadata() -> None:
    manifest = {
        "manifestVersion": 1,
        "packageId": "pkg_1",
        "title": "课程",
        "createdAt": "2026-05-20T12:00:00Z",
        "subjectId": "subj_1",
        "scopedProjectId": "proj_1",
        "items": [
            {
                "itemId": "01",
                "title": "01",
                "order": 1,
                "learningObjectKey": "01",
                "video": {
                    "path": "videos/01.mp4",
                    "sizeBytes": 8,
                    "sha256": "0" * 64,
                },
            }
        ],
    }

    with pytest.raises(CoursePackageError, match="source"):
        validate_course_package_manifest(manifest)


@pytest.mark.parametrize("source", [{"tool": "", "version": "local"}, {"tool": "tool", "version": ""}])
def test_validate_manifest_rejects_incomplete_source_metadata(source: dict[str, str]) -> None:
    manifest = {
        "manifestVersion": 1,
        "packageId": "pkg_1",
        "title": "课程",
        "createdAt": "2026-05-20T12:00:00Z",
        "subjectId": "subj_1",
        "scopedProjectId": "proj_1",
        "source": source,
        "items": [
            {
                "itemId": "01",
                "title": "01",
                "order": 1,
                "learningObjectKey": "01",
                "video": {
                    "path": "videos/01.mp4",
                    "sizeBytes": 8,
                    "sha256": "0" * 64,
                },
            }
        ],
    }

    with pytest.raises(CoursePackageError, match="manifest.source"):
        validate_course_package_manifest(manifest)


@pytest.mark.parametrize(
    "path",
    [
        "../01.mp4",
        "/tmp/01.mp4",
        "C:/tmp/01.mp4",
        "videos",
        "videos/../secret.mp4",
        "videos//01.mp4",
        "subtitles/01.mp4",
        r"videos\01.mp4",
    ],
)
def test_validate_manifest_rejects_file_paths_outside_package(path: str) -> None:
    manifest = {
        "manifestVersion": 1,
        "packageId": "pkg_1",
        "title": "课程",
        "createdAt": "2026-05-20T12:00:00Z",
        "subjectId": "subj_1",
        "scopedProjectId": "proj_1",
        "source": {"tool": "tool", "version": "local"},
        "items": [
            {
                "itemId": "01",
                "title": "01",
                "order": 1,
                "learningObjectKey": "01",
                "video": {
                    "path": path,
                    "sizeBytes": 8,
                    "sha256": "0" * 64,
                },
            }
        ],
    }

    with pytest.raises(CoursePackageError, match="path"):
        validate_course_package_manifest(manifest)


def test_builds_unique_package_paths_for_duplicate_video_names(tmp_path: Path) -> None:
    root = tmp_path / "course"
    first = write_file(root / "chapter-a" / "01.mp4", b"video-a")
    second = write_file(root / "chapter-b" / "01.mp4", b"video-b")

    manifest = build_course_package_manifest(
        input_dir=root,
        title="默认网课材料",
        subject_id="subj_1",
        scoped_project_id="proj_1",
        package_id="pkg_test",
        created_at="2026-05-20T12:00:00Z",
    )

    paths = [item["video"]["path"] for item in manifest["items"]]
    hashes = {item["video"]["path"]: item["video"]["sha256"] for item in manifest["items"]}

    assert paths == ["videos/01.mp4", "videos/01_2.mp4"]
    assert hashes["videos/01.mp4"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert hashes["videos/01_2.mp4"] == hashlib.sha256(second.read_bytes()).hexdigest()


def test_builds_materialized_course_package_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "course-package"
    video = write_file(input_dir / "chapter-a" / "01.mp4", b"video-a")
    subtitle = write_file(input_dir / "chapter-a" / "01.srt", b"subtitle-a")
    cover = write_file(input_dir / "chapter-a" / "01.jpg", b"cover-a")

    manifest = build_course_package(
        input_dir=input_dir,
        output_dir=output_dir,
        title="默认网课材料",
        subject_id="subj_1",
        scoped_project_id="proj_1",
        package_id="pkg_test",
        created_at="2026-05-20T12:00:00Z",
    )

    item = manifest["items"][0]
    saved_manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert saved_manifest == manifest
    assert (output_dir / item["video"]["path"]).read_bytes() == video.read_bytes()
    assert (output_dir / item["subtitle"]["path"]).read_bytes() == subtitle.read_bytes()
    assert (output_dir / item["cover"]["path"]).read_bytes() == cover.read_bytes()


def test_build_course_package_rejects_non_empty_output_dir(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "course-package"
    write_file(input_dir / "01.mp4", b"video")
    write_file(output_dir / "existing.txt", b"existing")

    with pytest.raises(CoursePackageError, match="输出目录必须为空"):
        build_course_package(
            input_dir=input_dir,
            output_dir=output_dir,
            title="默认网课材料",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            package_id="pkg_test",
            created_at="2026-05-20T12:00:00Z",
        )


def test_build_course_package_rejects_output_dir_inside_input_dir(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    write_file(input_dir / "01.mp4", b"video")

    with pytest.raises(CoursePackageError, match="输出目录不能位于输入课程目录内"):
        build_course_package(
            input_dir=input_dir,
            output_dir=input_dir / ".learningpyramid-mobile-package",
            title="默认网课材料",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            package_id="pkg_test",
            created_at="2026-05-20T12:00:00Z",
        )


def test_validate_manifest_rejects_duplicate_file_paths() -> None:
    manifest = {
        "manifestVersion": 1,
        "packageId": "pkg_1",
        "title": "课程",
        "createdAt": "2026-05-20T12:00:00Z",
        "subjectId": "subj_1",
        "scopedProjectId": "proj_1",
        "source": {"tool": "tool", "version": "local"},
        "items": [
            {
                "itemId": "01",
                "title": "01",
                "order": 1,
                "learningObjectKey": "01",
                "video": {"path": "videos/01.mp4", "sizeBytes": 8, "sha256": "0" * 64},
            },
            {
                "itemId": "02",
                "title": "02",
                "order": 2,
                "learningObjectKey": "02",
                "video": {"path": "videos/01.mp4", "sizeBytes": 8, "sha256": "1" * 64},
            },
        ],
    }

    with pytest.raises(CoursePackageError, match="重复文件路径"):
        validate_course_package_manifest(manifest)


def test_build_course_package_rejects_symlink_video_outside_input_dir(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    outside_video = write_file(tmp_path / "outside.mp4", b"outside")
    input_dir.mkdir()
    symlink_path = input_dir / "01.mp4"
    try:
        symlink_path.symlink_to(outside_video)
    except (NotImplementedError, OSError) as exc:
        if os.name == "nt":
            pytest.skip(f"当前 Windows 环境不允许创建 symlink：{exc}")
        raise

    with pytest.raises(CoursePackageError, match="符号链接"):
        build_course_package_manifest(
            input_dir=input_dir,
            title="默认网课材料",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            package_id="pkg_test",
            created_at="2026-05-20T12:00:00Z",
        )


def test_sha256_file_hashes_large_files_without_reading_manifest_state(tmp_path: Path) -> None:
    file_path = write_file(tmp_path / "large.mp4", b"a" * 1024 * 1024 + b"b")

    assert sha256_file(file_path) == hashlib.sha256(file_path.read_bytes()).hexdigest()
