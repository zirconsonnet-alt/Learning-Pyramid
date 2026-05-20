import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tools.offline_course_package import build_course_package
from tools.offline_course_package_server import (
    OfflineCoursePackageSession,
    start_offline_course_package_server,
)


def write_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def build_session(tmp_path: Path, *, expires_at_epoch: float | None = None) -> OfflineCoursePackageSession:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "course-package"
    write_file(input_dir / "01.mp4", b"0123456789")
    write_file(input_dir / "01.srt", b"subtitle")
    manifest = build_course_package(
        input_dir=input_dir,
        output_dir=output_dir,
        title="默认网课材料",
        subject_id="subj_1",
        scoped_project_id="proj_1",
        package_id="pkg_test",
        created_at="2026-05-20T12:00:00Z",
    )
    return OfflineCoursePackageSession(
        root=output_dir,
        manifest=manifest,
        token="token-1",
        expires_at_epoch=expires_at_epoch if expires_at_epoch is not None else time.time() + 60,
    )


def request(server, path: str, *, token: str | None = "token-1", headers: dict[str, str] | None = None):
    request_headers = dict(headers or {})
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"
    return urlopen(Request(f"{server.base_url}{path}", headers=request_headers), timeout=5)


def read_json(response) -> dict:
    return json.loads(response.read().decode("utf-8"))


def assert_http_error(status: int, func) -> None:
    try:
        func()
    except HTTPError as exc:
        assert exc.code == status
    else:
        raise AssertionError(f"expected HTTP {status}")


def test_serves_metadata_manifest_and_range_download(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        with request(server, "/metadata") as response:
            metadata = read_json(response)

        assert response.status == 200
        assert metadata["title"] == "默认网课材料"
        assert metadata["packageId"] == "pkg_test"
        assert metadata["subjectId"] == "subj_1"
        assert metadata["scopedProjectId"] == "proj_1"
        assert metadata["totalBytes"] > 0
        assert metadata["itemCount"] == 1

        with request(server, "/manifest") as response:
            manifest = read_json(response)

        assert response.status == 200
        assert manifest["packageId"] == "pkg_test"

        with request(server, "/files/videos/01.mp4", headers={"Range": "bytes=2-5"}) as response:
            body = response.read()

        assert response.status == 206
        assert body == b"2345"
        assert response.headers["Content-Range"] == "bytes 2-5/10"
    finally:
        server.stop()


def test_serves_full_file_download_without_range(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        with request(server, "/files/videos/01.mp4") as response:
            body = response.read()

        assert response.status == 200
        assert body == b"0123456789"
        assert response.headers["Content-Length"] == "10"
    finally:
        server.stop()


def test_rejects_missing_token(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        assert_http_error(401, lambda: request(server, "/metadata", token=None))
    finally:
        server.stop()


def test_rejects_expired_session(tmp_path: Path) -> None:
    session = build_session(tmp_path, expires_at_epoch=time.time() - 1)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        assert_http_error(410, lambda: request(server, "/metadata"))
    finally:
        server.stop()


def test_rejects_file_not_declared_in_manifest(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    write_file(session.root / "videos" / "secret.mp4", b"secret")
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        assert_http_error(404, lambda: request(server, "/files/videos/secret.mp4"))
    finally:
        server.stop()


def test_rejects_path_traversal(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        assert_http_error(404, lambda: request(server, "/files/%2e%2e/manifest.json"))
    finally:
        server.stop()


@pytest.mark.parametrize(
    "range_header",
    ["bytes=99-100", "bytes=abc-def", "items=0-1", "bytes=-0", "bytes=0-1,2-3"],
)
def test_rejects_invalid_range(tmp_path: Path, range_header: str) -> None:
    session = build_session(tmp_path)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        assert_http_error(
            416,
            lambda: request(server, "/files/videos/01.mp4", headers={"Range": range_header}),
        )
    finally:
        server.stop()


def test_rejects_session_when_declared_file_is_missing(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    (session.root / "videos" / "01.mp4").unlink()

    with pytest.raises(FileNotFoundError, match="manifest 声明文件"):
        start_offline_course_package_server(session, host="127.0.0.1", port=0)
