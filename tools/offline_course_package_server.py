import json
import mimetypes
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from tools.offline_course_package import validate_course_package_manifest

FILE_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class OfflineCoursePackageSession:
    root: Path
    manifest: dict[str, Any]
    token: str
    expires_at_epoch: float


@dataclass(frozen=True)
class OfflineCoursePackageServer:
    base_url: str
    _httpd: ThreadingHTTPServer
    _thread: threading.Thread

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def _iter_manifest_file_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in manifest["items"]:
        for key in ("video", "subtitle", "cover"):
            entry = item.get(key)
            if entry is not None:
                entries.append(entry)
    return entries


def _total_bytes(manifest: dict[str, Any]) -> int:
    return sum(entry["sizeBytes"] for entry in _iter_manifest_file_entries(manifest))


def _paths_from_manifest(manifest: dict[str, Any]) -> set[str]:
    return {entry["path"] for entry in _iter_manifest_file_entries(manifest)}


def _safe_file_path(root: Path, relative: str) -> Path | None:
    if "\\" in relative or relative.startswith("/"):
        return None
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    root_resolved = root.resolve()
    file_path = (root_resolved / relative).resolve()
    try:
        file_path.relative_to(root_resolved)
    except ValueError:
        return None
    if not file_path.is_file():
        return None
    return file_path


def _validate_declared_files_exist(root: Path, declared_paths: set[str]) -> None:
    missing = [path for path in sorted(declared_paths) if _safe_file_path(root, path) is None]
    if missing:
        raise FileNotFoundError(f"课程包缺少 manifest 声明文件：{missing[0]}")


def _parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    if not range_header.startswith("bytes="):
        raise ValueError("range unit must be bytes")
    spec = range_header[len("bytes=") :].strip()
    if "," in spec or "-" not in spec:
        raise ValueError("single range required")
    start_text, end_text = spec.split("-", 1)
    if not start_text and not end_text:
        raise ValueError("empty range")
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
    else:
        suffix_size = int(end_text)
        if suffix_size <= 0:
            raise ValueError("invalid suffix range")
        start = max(file_size - suffix_size, 0)
        end = file_size - 1
    if start < 0 or end < start or start >= file_size:
        raise ValueError("unsatisfiable range")
    return start, min(end, file_size - 1)


def start_offline_course_package_server(
    session: OfflineCoursePackageSession,
    host: str = "0.0.0.0",
    port: int = 0,
) -> OfflineCoursePackageServer:
    validate_course_package_manifest(session.manifest)
    root = session.root
    declared_paths = _paths_from_manifest(session.manifest)
    _validate_declared_files_exist(root, declared_paths)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.headers.get("Authorization") != f"Bearer {session.token}":
                self.send_error(HTTPStatus.UNAUTHORIZED)
                return
            if time.time() >= session.expires_at_epoch:
                self.send_error(HTTPStatus.GONE)
                return

            path = urlsplit(self.path).path
            if path == "/metadata":
                self._send_json(
                    {
                        "packageId": session.manifest["packageId"],
                        "title": session.manifest["title"],
                        "subjectId": session.manifest["subjectId"],
                        "scopedProjectId": session.manifest["scopedProjectId"],
                        "totalBytes": _total_bytes(session.manifest),
                        "itemCount": len(session.manifest["items"]),
                    }
                )
                return
            if path == "/manifest":
                self._send_json(session.manifest)
                return
            if path.startswith("/files/"):
                self._send_file(unquote(path[len("/files/") :]))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def _send_json(self, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, relative_path: str) -> None:
            if relative_path not in declared_paths:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            file_path = _safe_file_path(root, relative_path)
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            file_size = file_path.stat().st_size
            range_header = self.headers.get("Range")
            if range_header:
                try:
                    start, end = _parse_range_header(range_header, file_size)
                except (ValueError, OverflowError):
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers()
                    return
                self._send_file_bytes(file_path, file_size, start, end)
                return

            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.end_headers()
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        def _send_file_bytes(self, file_path: Path, file_size: int, start: int, end: int) -> None:
            content_length = end - start + 1
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_length))
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            with file_path.open("rb") as handle:
                handle.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = handle.read(min(FILE_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    self.wfile.write(chunk)

        def log_message(self, format: str, *args: Any) -> None:
            return

    httpd = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    actual_host = "127.0.0.1" if host == "0.0.0.0" else host
    base_url = f"http://{actual_host}:{httpd.server_port}"
    return OfflineCoursePackageServer(base_url=base_url, _httpd=httpd, _thread=thread)
