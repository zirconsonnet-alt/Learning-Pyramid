import hashlib
from pathlib import Path

import pytest

from tools.offline_course_package import (
    CoursePackageError,
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


def test_sha256_file_hashes_large_files_without_reading_manifest_state(tmp_path: Path) -> None:
    file_path = write_file(tmp_path / "large.mp4", b"a" * 1024 * 1024 + b"b")

    assert sha256_file(file_path) == hashlib.sha256(file_path.read_bytes()).hexdigest()
