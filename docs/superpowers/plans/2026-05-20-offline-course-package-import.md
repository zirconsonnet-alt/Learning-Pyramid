# Offline Course Package Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LAN-based offline course package import flow where the desktop subtitle tool serves a selected video/subtitle package and the mobile app downloads it into an App-private local course library bound to an existing `{subjectId, scopedProjectId}`.

**Architecture:** Keep the online subject/project identity as the learning data backbone. Add a desktop-side package manifest and temporary token-gated HTTP server, then add a mobile-side local package store, download queue, and player source selection for verified local package files. Do not scan the phone file system, do not write public folders, and do not create a second local-only course system.

**Tech Stack:** Python stdlib `http.server`, `dataclasses`, `hashlib`, `pytest`; PySide6/Tk subtitle tool UI; Expo React Native SDK 55; `expo-file-system` modern `File`/`Directory`/`Paths`; `@noble/hashes` for streaming SHA-256; Jest and React Native Testing Library.

---

## Scope Check

The spec touches two subsystems, but they are one vertical feature: the mobile client cannot import a course package unless the desktop tool serves one. This plan keeps them in one implementation plan and makes each task independently testable.

## Confirmed Adjustment

The user confirmed the real course-package directory approach after Task 1 review. The desktop builder must materialize a package directory with `manifest.json`, `videos/`, `subtitles/`, and `covers/`; manifest file paths are package-internal paths that must exist under that directory. Task 2 and later must use the materialized package directory as `OfflineCoursePackageSession.root`, not the original input video directory.

## File Structure

Create:

- `tools/offline_course_package.py`: manifest model, validation, SHA-256, and real local course-package directory builder. Manifest file paths must point to files materialized under `videos/`, `subtitles/`, and `covers/`.
- `tools/offline_course_package_server.py`: token-gated temporary HTTP server with metadata, manifest, file list, and Range file download.
- `tests/test_offline_course_package.py`: package builder and manifest validation tests.
- `tests/test_offline_course_package_server.py`: token, expiry, manifest, and Range tests.
- `mobile/src/offlineCoursePackages/schema.ts`: zod schemas and TypeScript types for QR payloads, manifests, local packages, and download tasks.
- `mobile/src/offlineCoursePackages/storage.ts`: App-private directory path construction, manifest read/write, package listing, package deletion, and free-space check.
- `mobile/src/offlineCoursePackages/downloader.ts`: task queue state machine, metadata fetch, selected item download, SHA-256 verification, pause/resume/retry primitives.
- `mobile/src/offlineCoursePackages/source.ts`: local playback descriptor resolution from verified local package entries.
- `mobile/src/screens/OfflineCoursePackagesScreen.tsx`: project-scoped local course package management screen.
- `mobile/src/app/offline-packages/[subjectId]/[scopedProjectId].tsx`: Expo Router route for local package management.
- `mobile/__tests__/offline-course-package-schema.test.ts`
- `mobile/__tests__/offline-course-package-storage.test.ts`
- `mobile/__tests__/offline-course-package-downloader.test.ts`
- `mobile/__tests__/offline-course-package-screen.test.tsx`

Modify:

- `tools/subtitle_tool.py`: add “导入到手机” entry points after local subtitle generation and for selected local directory.
- `mobile/package.json` and `mobile/pnpm-lock.yaml`: install `expo-file-system` and `@noble/hashes`.
- `mobile/src/app/_layout.tsx`: register offline package route.
- `mobile/src/screens/ProjectSettingsScreen.tsx`: add project-scoped “离线课程包” entry.
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`: load verified local package playback descriptor and pass it to the workbench/player.
- `mobile/src/screens/LearningMediaPlayer.tsx`: support explicit local package playback descriptor.
- `mobile/src/api/media.ts`: include `LOCAL_COURSE_PACKAGE` in mobile-only playback descriptor union if the descriptor is passed through the existing player prop.
- `docs/current-change.md`, `docs/mobile-client.md`, `README.md`: update boundaries and usage.

---

### Task 1: Python Course Package Manifest Model

**Files:**
- Create: `tools/offline_course_package.py`
- Create: `tests/test_offline_course_package.py`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Update current work item**

Replace `docs/current-change.md` with:

```markdown
# 当前变更：离线课程包导入实现

## 当前用户要求

- 实现局域网离线课程包导入。
- 电脑端字幕工具提供视频、字幕和 manifest。
- 手机端下载到 App 私有课程库并绑定线上学科/项目。

## 根因判断

- 手机端离线学习需要完整课程素材包，不是单独字幕文件。
- 线上 `{subjectId, scopedProjectId}` 必须继续作为学习数据主干。

## 修改前判断

- 先实现纯 manifest 和临时服务，再接移动端下载与播放。
- 不扫描手机系统文件，不写公共目录，不做公网中继。

## 本次实际修改文件

- 待更新。

## 行为语义是否变化

- 待实现。

## 重构说明

- 待更新。

## 未修改内容

- 不改变 Web/Tauri 工作台学习语义。

## 影响范围

- 字幕工具、移动端本地课程库、移动端播放器、文档。

## 当前风险点和不确定项

- Expo-managed 大文件下载、空间检查和本地视频 URI 需要验证。

## 仍需用户确认的问题

- 无。

## 验证记录

- 待运行。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否
```

- [ ] **Step 2: Write failing manifest tests**

Create `tests/test_offline_course_package.py`:

```python
import hashlib
import json
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


def test_sha256_file_hashes_large_files_without_reading_manifest_state(tmp_path: Path) -> None:
    file_path = write_file(tmp_path / "large.mp4", b"a" * 1024 * 1024 + b"b")

    assert sha256_file(file_path) == hashlib.sha256(file_path.read_bytes()).hexdigest()
```

- [ ] **Step 3: Run failing tests**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.offline_course_package'`.

- [ ] **Step 4: Implement manifest module**

Create `tools/offline_course_package.py`:

Python files in this repository must not add the annotations future import. Use this content:

```python
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
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tools/offline_course_package.py tests/test_offline_course_package.py docs/current-change.md
git commit -m "feat: add offline course package manifest"
```

---

### Task 2: Desktop Temporary Package Server

**Files:**
- Create: `tools/offline_course_package_server.py`
- Create: `tests/test_offline_course_package_server.py`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write failing server tests**

Create `tests/test_offline_course_package_server.py`:

```python
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tools.offline_course_package import build_course_package
from tools.offline_course_package_server import OfflineCoursePackageSession, start_offline_course_package_server


def write_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def read_url(url: str, token: str, headers: dict[str, str] | None = None) -> tuple[int, bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", **(headers or {})})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read(), dict(response.headers.items())


@pytest.fixture()
def package_root(tmp_path: Path):
    input_dir = tmp_path / "course"
    output_dir = tmp_path / "course-package"
    write_file(input_dir / "01.mp4", b"0123456789")
    write_file(input_dir / "01.srt", b"subtitle")
    manifest = build_course_package(
        input_dir=input_dir,
        output_dir=output_dir,
        title="课程",
        subject_id="subj_1",
        scoped_project_id="proj_1",
        package_id="pkg_1",
        created_at="2026-05-20T12:00:00Z",
    )
    return output_dir, manifest


def test_serves_metadata_manifest_and_range_download(package_root) -> None:
    root, manifest = package_root
    session = OfflineCoursePackageSession(root=root, manifest=manifest, token="secret", expires_at_epoch=4102444800)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        base_url = server.base_url
        status, metadata_raw, _headers = read_url(f"{base_url}/metadata", "secret")
        assert status == 200
        metadata = json.loads(metadata_raw.decode("utf-8"))
        assert metadata["title"] == "课程"
        assert metadata["totalBytes"] > 0

        status, manifest_raw, _headers = read_url(f"{base_url}/manifest", "secret")
        assert status == 200
        assert json.loads(manifest_raw.decode("utf-8"))["packageId"] == "pkg_1"

        status, chunk, headers = read_url(f"{base_url}/files/videos/01.mp4", "secret", {"Range": "bytes=2-5"})
        assert status == 206
        assert chunk == b"2345"
        assert headers["Content-Range"] == "bytes 2-5/10"
    finally:
        server.stop()


def test_rejects_missing_token(package_root) -> None:
    root, manifest = package_root
    session = OfflineCoursePackageSession(root=root, manifest=manifest, token="secret", expires_at_epoch=4102444800)
    server = start_offline_course_package_server(session, host="127.0.0.1", port=0)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{server.base_url}/metadata", timeout=5)
        assert exc.value.code == 401
    finally:
        server.stop()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
python -m pytest tests/test_offline_course_package_server.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.offline_course_package_server'`.

- [ ] **Step 3: Implement token-gated server**

Create `tools/offline_course_package_server.py`:

```python
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


@dataclass(frozen=True)
class OfflineCoursePackageSession:
    root: Path
    manifest: dict[str, Any]
    token: str
    expires_at_epoch: float


class RunningOfflineCoursePackageServer:
    def __init__(self, httpd: ThreadingHTTPServer, thread: threading.Thread) -> None:
        self._httpd = httpd
        self._thread = thread
        host, port = httpd.server_address
        self.base_url = f"http://{host}:{port}"

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def _total_bytes(manifest: dict[str, Any]) -> int:
    total = 0
    for item in manifest.get("items", []):
        if not isinstance(item, dict):
            continue
        for key in ("video", "subtitle", "cover"):
            entry = item.get(key)
            if isinstance(entry, dict) and isinstance(entry.get("sizeBytes"), int):
                total += int(entry["sizeBytes"])
    return total


def _paths_from_manifest(manifest: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for item in manifest.get("items", []):
        if not isinstance(item, dict):
            continue
        for key in ("video", "subtitle", "cover"):
            entry = item.get(key)
            if isinstance(entry, dict):
                path = str(entry.get("path") or "").replace("\\", "/").lstrip("/")
                if path:
                    paths.add(path)
    return paths


def start_offline_course_package_server(
    session: OfflineCoursePackageSession,
    *,
    host: str = "0.0.0.0",
    port: int = 0,
) -> RunningOfflineCoursePackageServer:
    allowed_paths = _paths_from_manifest(session.manifest)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            if time.time() > session.expires_at_epoch:
                self._send_json(HTTPStatus.GONE, {"error": "session expired"})
                return
            if self.headers.get("Authorization") != f"Bearer {session.token}":
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return

            path = urlsplit(self.path).path
            if path == "/metadata":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "packageId": session.manifest["packageId"],
                        "title": session.manifest["title"],
                        "subjectId": session.manifest["subjectId"],
                        "scopedProjectId": session.manifest["scopedProjectId"],
                        "totalBytes": _total_bytes(session.manifest),
                        "itemCount": len(session.manifest.get("items", [])),
                    },
                )
                return
            if path == "/manifest":
                self._send_json(HTTPStatus.OK, session.manifest)
                return
            if path.startswith("/files/"):
                relative = unquote(path.removeprefix("/files/")).replace("\\", "/").lstrip("/")
                if relative not in allowed_paths or ".." in Path(relative).parts:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "file not found"})
                    return
                self._send_file(session.root / relative)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            if not path.exists() or not path.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "file not found"})
                return
            size = path.stat().st_size
            start = 0
            end = size - 1
            status = HTTPStatus.OK
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                raw_start, _, raw_end = range_header.removeprefix("bytes=").partition("-")
                start = max(0, int(raw_start or "0"))
                end = min(size - 1, int(raw_end or str(size - 1)))
                status = HTTPStatus.PARTIAL_CONTENT
            length = max(0, end - start + 1)
            self.send_response(status.value)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(length))
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    self.wfile.write(chunk)

    httpd = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return RunningOfflineCoursePackageServer(httpd, thread)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py tests/test_offline_course_package_server.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tools/offline_course_package_server.py tests/test_offline_course_package_server.py docs/current-change.md
git commit -m "feat: serve offline course packages over lan"
```

---

### Task 3: Subtitle Tool Entry Point

**Files:**
- Modify: `tools/subtitle_tool.py`
- Test: `tests/test_offline_course_package.py`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Add a headless package command test**

Append to `tests/test_offline_course_package.py`:

```python
from tools.subtitle_tool import build_parser


def test_subtitle_tool_parser_accepts_mobile_package_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--mobile-package-dir",
            "C:/course",
            "--mobile-package-title",
            "默认网课材料",
            "--mobile-subject-id",
            "subj_1",
            "--mobile-project-id",
            "proj_1",
        ]
    )

    assert args.mobile_package_dir == "C:/course"
    assert args.mobile_package_title == "默认网课材料"
    assert args.mobile_subject_id == "subj_1"
    assert args.mobile_project_id == "proj_1"
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py::test_subtitle_tool_parser_accepts_mobile_package_args -q
```

Expected: FAIL because parser does not know the mobile package arguments.

- [ ] **Step 3: Add parser arguments and package helper**

Modify `tools/subtitle_tool.py`:

```python
import secrets
from datetime import datetime, timedelta, timezone
```

Add imports near other project imports:

```python
from tools.offline_course_package import build_course_package
from tools.offline_course_package_server import OfflineCoursePackageSession, start_offline_course_package_server
```

Add parser arguments in `build_parser()`:

```python
    parser.add_argument("--mobile-package-dir", help="Build a mobile offline course package from a local video directory.")
    parser.add_argument("--mobile-package-title", help="Display title for the mobile offline course package.")
    parser.add_argument("--mobile-subject-id", help="Subject id to bind the mobile offline package to.")
    parser.add_argument("--mobile-project-id", help="Scoped project id to bind the mobile offline package to.")
```

Add a helper near `run_cli`:

```python
def _mobile_package_cli_requested(args: argparse.Namespace) -> bool:
    return bool(str(getattr(args, "mobile_package_dir", "") or "").strip())


def build_mobile_package_session_from_args(args: argparse.Namespace) -> OfflineCoursePackageSession:
    input_dir = Path(str(args.mobile_package_dir)).expanduser().resolve()
    package_dir = input_dir.parent / f"{input_dir.name}.learningpyramid-mobile-package"
    title = str(args.mobile_package_title or input_dir.name).strip() or input_dir.name
    subject_id = str(args.mobile_subject_id or "").strip()
    scoped_project_id = str(args.mobile_project_id or "").strip()
    if not subject_id:
        raise SystemExit("请提供 --mobile-subject-id。")
    if not scoped_project_id:
        raise SystemExit("请提供 --mobile-project-id。")
    now = datetime.now(timezone.utc)
    manifest = build_course_package(
        input_dir=input_dir,
        output_dir=package_dir,
        title=title,
        subject_id=subject_id,
        scoped_project_id=scoped_project_id,
        package_id=f"pkg_{now.strftime('%Y%m%d_%H%M%S')}",
        created_at=now.isoformat().replace("+00:00", "Z"),
    )
    return OfflineCoursePackageSession(
        root=package_dir,
        manifest=manifest,
        token=secrets.token_urlsafe(24),
        expires_at_epoch=(now + timedelta(minutes=10)).timestamp(),
    )
```

At the top of `run_cli`, before project Baidu mode:

```python
    if _mobile_package_cli_requested(args):
        session = build_mobile_package_session_from_args(args)
        server = start_offline_course_package_server(session)
        print(json.dumps({"url": server.base_url, "token": session.token}, ensure_ascii=False))
        print("按 Ctrl+C 停止手机导入服务。")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
        return 0
```

- [ ] **Step 4: Run parser test**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py::test_subtitle_tool_parser_accepts_mobile_package_args -q
```

Expected: PASS.

- [ ] **Step 5: Add UI buttons without changing generation flow**

In both `QtSubtitleToolApp._build_ui()` and `SubtitleToolApp._build_ui()`, add a secondary button labeled `导入到手机` next to the existing `开始生成` button. The handler must:

```python
def _start_mobile_package_server_from_form(self) -> None:
    input_dir_text = self.input_dir_var.get().strip()
    if not input_dir_text:
        messagebox.showerror(APP_TITLE, "请先选择一个视频目录。")
        return
    subject_id = self.subject_id_var.get().strip()
    scoped_project_id = self.project_id_var.get().strip()
    if not subject_id or not scoped_project_id:
        messagebox.showerror(APP_TITLE, "请先填写目标学科 ID 和项目 ID。")
        return
    args = argparse.Namespace(
        mobile_package_dir=input_dir_text,
        mobile_package_title=Path(input_dir_text).name,
        mobile_subject_id=subject_id,
        mobile_project_id=scoped_project_id,
    )
    session = build_mobile_package_session_from_args(args)
    server = start_offline_course_package_server(session)
    self._append_log(f"手机导入服务已启动：{server.base_url}")
    self._append_log(f"Token：{session.token}")
    messagebox.showinfo(APP_TITLE, f"手机导入服务已启动。\n\n地址：{server.base_url}\nToken：{session.token}")
```

Store the returned server on `self.mobile_package_server` and stop an existing server before starting a new one.

- [ ] **Step 6: Run Python tests**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py tests/test_offline_course_package_server.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add tools/subtitle_tool.py tests/test_offline_course_package.py docs/current-change.md
git commit -m "feat: expose mobile package import from subtitle tool"
```

---

### Task 4: Mobile Manifest Schema and Dependencies

**Files:**
- Modify: `mobile/package.json`
- Modify: `mobile/pnpm-lock.yaml`
- Create: `mobile/src/offlineCoursePackages/schema.ts`
- Create: `mobile/__tests__/offline-course-package-schema.test.ts`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Install dependencies**

Run:

```powershell
pnpm --dir mobile exec expo install expo-file-system
pnpm --dir mobile add @noble/hashes
```

Expected: `mobile/package.json` includes `expo-file-system` and `@noble/hashes`.

- [ ] **Step 2: Write schema tests**

Create `mobile/__tests__/offline-course-package-schema.test.ts`:

```ts
import { OfflineCoursePackageQrPayloadSchema, CoursePackageManifestSchema } from "../src/offlineCoursePackages/schema"

describe("offline course package schema", () => {
  it("accepts a token-gated LAN QR payload", () => {
    const payload = OfflineCoursePackageQrPayloadSchema.parse({
      kind: "learningpyramid.offlineCoursePackage",
      version: 1,
      url: "http://192.168.1.8:23456/session/abc",
      token: "secret",
      expiresAt: "2026-05-20T12:10:00Z",
    })

    expect(payload.token).toBe("secret")
  })

  it("requires project identity and file hashes in manifests", () => {
    const manifest = CoursePackageManifestSchema.parse({
      manifestVersion: 1,
      packageId: "pkg_1",
      title: "默认网课材料",
      createdAt: "2026-05-20T12:00:00Z",
      subjectId: "subj_1",
      scopedProjectId: "proj_1",
      source: { tool: "LearningPyramid-SubtitleTool", version: "local" },
      items: [
        {
          itemId: "lesson_01",
          title: "第一讲",
          order: 1,
          learningObjectKey: "lesson_01",
          video: {
            path: "videos/01.mp4",
            sizeBytes: 10,
            sha256: "0".repeat(64),
          },
        },
      ],
    })

    expect(manifest.items[0].video.path).toBe("videos/01.mp4")
  })
})
```

- [ ] **Step 3: Run failing test**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-schema.test.ts
```

Expected: FAIL because `src/offlineCoursePackages/schema.ts` does not exist.

- [ ] **Step 4: Implement schema**

Create `mobile/src/offlineCoursePackages/schema.ts`:

```ts
import { z } from "zod"

const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/)

export const OfflineCoursePackageQrPayloadSchema = z.object({
  kind: z.literal("learningpyramid.offlineCoursePackage"),
  version: z.literal(1),
  url: z.string().url(),
  token: z.string().min(1),
  expiresAt: z.string().min(1),
})

export const CoursePackageFileSchema = z.object({
  path: z.string().min(1),
  sizeBytes: z.number().int().nonnegative(),
  sha256: Sha256Schema,
})

export const CoursePackageSubtitleFileSchema = CoursePackageFileSchema.extend({
  language: z.string().min(1),
})

export const CoursePackageItemSchema = z.object({
  itemId: z.string().min(1),
  title: z.string().min(1),
  order: z.number().int().nonnegative(),
  learningObjectKey: z.string().min(1),
  video: CoursePackageFileSchema,
  subtitle: CoursePackageSubtitleFileSchema.optional(),
  cover: CoursePackageFileSchema.optional(),
})

export const CoursePackageManifestSchema = z.object({
  manifestVersion: z.literal(1),
  packageId: z.string().min(1),
  title: z.string().min(1),
  createdAt: z.string().min(1),
  subjectId: z.string().min(1),
  scopedProjectId: z.string().min(1),
  source: z.object({
    tool: z.string().min(1),
    version: z.string().min(1),
  }),
  items: z.array(CoursePackageItemSchema).min(1),
})

export const LocalCoursePackageStatusSchema = z.enum(["downloading", "completed", "failed", "paused"])

export const LocalCoursePackageSchema = z.object({
  packageId: z.string().min(1),
  subjectId: z.string().min(1),
  scopedProjectId: z.string().min(1),
  title: z.string().min(1),
  rootUri: z.string().min(1),
  status: LocalCoursePackageStatusSchema,
  manifest: CoursePackageManifestSchema,
})

export const DownloadTaskStatusSchema = z.enum(["queued", "downloading", "paused", "verifying", "completed", "failed"])

export const DownloadTaskSchema = z.object({
  id: z.string().min(1),
  packageId: z.string().min(1),
  relativePath: z.string().min(1),
  remoteUrl: z.string().url(),
  tempUri: z.string().min(1),
  finalUri: z.string().min(1),
  expectedSizeBytes: z.number().int().nonnegative(),
  expectedSha256: Sha256Schema,
  downloadedBytes: z.number().int().nonnegative(),
  status: DownloadTaskStatusSchema,
  lastError: z.string().nullable(),
})

export type OfflineCoursePackageQrPayload = z.infer<typeof OfflineCoursePackageQrPayloadSchema>
export type CoursePackageManifest = z.infer<typeof CoursePackageManifestSchema>
export type CoursePackageItem = z.infer<typeof CoursePackageItemSchema>
export type LocalCoursePackage = z.infer<typeof LocalCoursePackageSchema>
export type DownloadTask = z.infer<typeof DownloadTaskSchema>
```

- [ ] **Step 5: Run tests**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-schema.test.ts
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add mobile/package.json mobile/pnpm-lock.yaml mobile/src/offlineCoursePackages/schema.ts mobile/__tests__/offline-course-package-schema.test.ts docs/current-change.md
git commit -m "feat: add mobile offline package schema"
```

---

### Task 5: Mobile Local Package Storage

**Files:**
- Create: `mobile/src/offlineCoursePackages/storage.ts`
- Create: `mobile/__tests__/offline-course-package-storage.test.ts`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write storage tests with mocked file-system**

Create `mobile/__tests__/offline-course-package-storage.test.ts`:

```ts
jest.mock("expo-file-system", () => {
  class MockDirectory {
    uri: string
    constructor(...parts: Array<{ uri?: string } | string>) {
      this.uri = parts.map((part) => (typeof part === "string" ? part : part.uri ?? "")).join("/")
    }
    create = jest.fn()
    delete = jest.fn()
  }
  class MockFile {
    uri: string
    static writes: Record<string, string> = {}
    constructor(...parts: Array<{ uri?: string } | string>) {
      this.uri = parts.map((part) => (typeof part === "string" ? part : part.uri ?? "")).join("/")
    }
    create = jest.fn()
    write = jest.fn((content: string) => {
      MockFile.writes[this.uri] = content
    })
    text = jest.fn(async () => MockFile.writes[this.uri] ?? "")
    delete = jest.fn()
  }
  return {
    Directory: MockDirectory,
    File: MockFile,
    Paths: { document: { uri: "file://document" }, availableDiskSpace: 1024 * 1024 * 1024 },
  }
})

import { buildCoursePackageRoot, hasEnoughSpace, writeLocalManifest } from "../src/offlineCoursePackages/storage"
import type { CoursePackageManifest } from "../src/offlineCoursePackages/schema"

const manifest: CoursePackageManifest = {
  manifestVersion: 1,
  packageId: "pkg_1",
  title: "课程",
  createdAt: "2026-05-20T12:00:00Z",
  subjectId: "subj_1",
  scopedProjectId: "proj_1",
  source: { tool: "tool", version: "local" },
  items: [
    {
      itemId: "lesson_1",
      title: "第一讲",
      order: 1,
      learningObjectKey: "lesson_1",
      video: { path: "videos/01.mp4", sizeBytes: 10, sha256: "0".repeat(64) },
    },
  ],
}

describe("offline package storage", () => {
  it("builds project-scoped app-private package paths", () => {
    expect(buildCoursePackageRoot("subj_1", "proj_1", "pkg_1").uri).toContain(
      "courses/subject_subj_1/project_proj_1/package_pkg_1",
    )
  })

  it("writes manifest under the package root", async () => {
    const file = await writeLocalManifest(manifest)

    expect(file.uri).toContain("manifest.json")
  })

  it("checks free disk space with a safety margin", () => {
    expect(hasEnoughSpace(1024, 512)).toBe(true)
    expect(hasEnoughSpace(1024, 2048)).toBe(false)
  })
})
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-storage.test.ts
```

Expected: FAIL because storage module does not exist.

- [ ] **Step 3: Implement storage module**

Create `mobile/src/offlineCoursePackages/storage.ts`:

```ts
import { Directory, File, Paths } from "expo-file-system"

import type { CoursePackageManifest } from "./schema"

const SAFETY_MARGIN_BYTES = 256 * 1024 * 1024

function safeSegment(value: string) {
  return value.replace(/[^A-Za-z0-9._-]+/g, "_")
}

export function buildCoursePackageRoot(subjectId: string, scopedProjectId: string, packageId: string) {
  return new Directory(
    Paths.document,
    "courses",
    `subject_${safeSegment(subjectId)}`,
    `project_${safeSegment(scopedProjectId)}`,
    `package_${safeSegment(packageId)}`,
  )
}

export function buildCoursePackageFile(root: Directory, relativePath: string) {
  const cleanParts = relativePath.split("/").filter((part) => part && part !== "." && part !== "..")
  return new File(root, ...cleanParts)
}

export function hasEnoughSpace(availableBytes: number, requiredBytes: number) {
  return availableBytes >= requiredBytes + SAFETY_MARGIN_BYTES
}

export function totalSelectedBytes(manifest: CoursePackageManifest, itemIds: string[]) {
  const selected = new Set(itemIds)
  return manifest.items
    .filter((item) => selected.has(item.itemId))
    .reduce((sum, item) => sum + item.video.sizeBytes + (item.subtitle?.sizeBytes ?? 0) + (item.cover?.sizeBytes ?? 0), 0)
}

export function getAvailableDiskSpaceBytes() {
  const value = Number(Paths.availableDiskSpace)
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error("无法读取手机剩余空间。")
  }
  return value
}

export async function writeLocalManifest(manifest: CoursePackageManifest) {
  const root = buildCoursePackageRoot(manifest.subjectId, manifest.scopedProjectId, manifest.packageId)
  root.create({ idempotent: true, intermediates: true })
  const file = new File(root, "manifest.json")
  file.create({ overwrite: true, intermediates: true })
  file.write(JSON.stringify(manifest, null, 2))
  return file
}

export function deleteLocalPackage(manifest: CoursePackageManifest) {
  const root = buildCoursePackageRoot(manifest.subjectId, manifest.scopedProjectId, manifest.packageId)
  root.delete()
}
```

- [ ] **Step 4: Run tests**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-storage.test.ts
pnpm --dir mobile typecheck
```

Expected: PASS. If TypeScript reports that `Paths.availableDiskSpace` does not exist in the installed Expo SDK 55 types, stop and report the API gap; do not switch to deprecated FileSystem methods without confirmation.

- [ ] **Step 5: Commit**

```powershell
git add mobile/src/offlineCoursePackages/storage.ts mobile/__tests__/offline-course-package-storage.test.ts docs/current-change.md
git commit -m "feat: add mobile offline package storage"
```

---

### Task 6: Mobile Download Queue and Verification

**Files:**
- Create: `mobile/src/offlineCoursePackages/downloader.ts`
- Create: `mobile/__tests__/offline-course-package-downloader.test.ts`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write downloader tests**

Create `mobile/__tests__/offline-course-package-downloader.test.ts`:

```ts
jest.mock("@noble/hashes/sha256", () => ({
  sha256: {
    create: () => {
      const chunks: number[] = []
      return {
        update: (bytes: Uint8Array) => {
          chunks.push(...Array.from(bytes))
          return undefined
        },
        digest: () => new Uint8Array(32).fill(chunks.length === 3 ? 0 : 1),
      }
    },
  },
}))

import { buildDownloadTasks, bytesToHex, markTaskFailed, markTaskPaused } from "../src/offlineCoursePackages/downloader"
import type { CoursePackageManifest } from "../src/offlineCoursePackages/schema"

const manifest: CoursePackageManifest = {
  manifestVersion: 1,
  packageId: "pkg_1",
  title: "课程",
  createdAt: "2026-05-20T12:00:00Z",
  subjectId: "subj_1",
  scopedProjectId: "proj_1",
  source: { tool: "tool", version: "local" },
  items: [
    {
      itemId: "lesson_1",
      title: "第一讲",
      order: 1,
      learningObjectKey: "lesson_1",
      video: { path: "videos/01.mp4", sizeBytes: 3, sha256: "0".repeat(64) },
      subtitle: { path: "subtitles/01.srt", language: "zh-CN", sizeBytes: 2, sha256: "1".repeat(64) },
    },
  ],
}

describe("offline package downloader", () => {
  it("builds one file task per selected manifest file", () => {
    const tasks = buildDownloadTasks({
      manifest,
      selectedItemIds: ["lesson_1"],
      baseUrl: "http://127.0.0.1:1234",
      token: "secret",
      packageRootUri: "file://root",
    })

    expect(tasks.map((task) => task.relativePath)).toEqual(["videos/01.mp4", "subtitles/01.srt"])
    expect(tasks[0].remoteUrl).toBe("http://127.0.0.1:1234/files/videos/01.mp4")
  })

  it("keeps task transitions explicit", () => {
    const task = buildDownloadTasks({
      manifest,
      selectedItemIds: ["lesson_1"],
      baseUrl: "http://127.0.0.1:1234",
      token: "secret",
      packageRootUri: "file://root",
    })[0]

    expect(markTaskPaused(task).status).toBe("paused")
    expect(markTaskFailed(task, "hash mismatch").lastError).toBe("hash mismatch")
  })

  it("converts bytes to lowercase hex", () => {
    expect(bytesToHex(new Uint8Array([0, 10, 255]))).toBe("000aff")
  })
})
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-downloader.test.ts
```

Expected: FAIL because downloader module does not exist.

- [ ] **Step 3: Implement downloader state helpers**

Create `mobile/src/offlineCoursePackages/downloader.ts`:

```ts
import type { CoursePackageFileSchema, CoursePackageManifest, DownloadTask } from "./schema"
import type { z } from "zod"

type CoursePackageFile = z.infer<typeof CoursePackageFileSchema>

function taskForFile(input: {
  baseUrl: string
  entry: CoursePackageFile
  packageId: string
  packageRootUri: string
  token: string
}): DownloadTask {
  const cleanPath = input.entry.path.replace(/^\/+/, "")
  return {
    id: `${input.packageId}:${cleanPath}`,
    packageId: input.packageId,
    relativePath: cleanPath,
    remoteUrl: `${input.baseUrl.replace(/\/$/, "")}/files/${encodeURI(cleanPath)}`,
    tempUri: `${input.packageRootUri}/download-state/${cleanPath}.part`,
    finalUri: `${input.packageRootUri}/${cleanPath}`,
    expectedSizeBytes: input.entry.sizeBytes,
    expectedSha256: input.entry.sha256,
    downloadedBytes: 0,
    status: "queued",
    lastError: null,
  }
}

export function buildDownloadTasks(input: {
  baseUrl: string
  manifest: CoursePackageManifest
  packageRootUri: string
  selectedItemIds: string[]
  token: string
}): DownloadTask[] {
  const selected = new Set(input.selectedItemIds)
  return input.manifest.items
    .filter((item) => selected.has(item.itemId))
    .flatMap((item) => [item.video, item.subtitle, item.cover].filter((entry): entry is CoursePackageFile => Boolean(entry)))
    .map((entry) =>
      taskForFile({
        baseUrl: input.baseUrl,
        entry,
        packageId: input.manifest.packageId,
        packageRootUri: input.packageRootUri,
        token: input.token,
      }),
    )
}

export function markTaskPaused(task: DownloadTask): DownloadTask {
  return { ...task, status: "paused" }
}

export function markTaskFailed(task: DownloadTask, error: string): DownloadTask {
  return { ...task, status: "failed", lastError: error }
}

export function bytesToHex(bytes: Uint8Array) {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
}
```

This task intentionally stops at pure state helpers. Do not add network/file writes until Task 7.

- [ ] **Step 4: Run tests**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-downloader.test.ts
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add mobile/src/offlineCoursePackages/downloader.ts mobile/__tests__/offline-course-package-downloader.test.ts docs/current-change.md
git commit -m "feat: add offline package download tasks"
```

---

### Task 7: Mobile Local Package UI and Route

**Files:**
- Create: `mobile/src/screens/OfflineCoursePackagesScreen.tsx`
- Create: `mobile/src/app/offline-packages/[subjectId]/[scopedProjectId].tsx`
- Create: `mobile/__tests__/offline-course-package-screen.test.tsx`
- Modify: `mobile/src/app/_layout.tsx`
- Modify: `mobile/src/screens/ProjectSettingsScreen.tsx`
- Modify: `mobile/__tests__/root-layout.test.tsx`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write route and screen tests**

Create `mobile/__tests__/offline-course-package-screen.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react-native"

import { OfflineCoursePackagesScreen } from "../src/screens/OfflineCoursePackagesScreen"

describe("OfflineCoursePackagesScreen", () => {
  it("shows local package management actions without claiming system file access", () => {
    const connectComputer = jest.fn()
    const screen = render(
      <OfflineCoursePackagesScreen
        connectComputer={connectComputer}
        packages={[]}
        projectTitle="默认网课材料"
      />,
    )

    expect(screen.getByText("离线课程包")).toBeTruthy()
    expect(screen.getByText("默认网课材料")).toBeTruthy()
    expect(screen.getByText("连接电脑")).toBeTruthy()
    expect(screen.queryByText("扫描手机文件")).toBeNull()
    fireEvent.press(screen.getByText("连接电脑"))
    expect(connectComputer).toHaveBeenCalled()
  })
})
```

Append to `mobile/__tests__/root-layout.test.tsx`:

```tsx
  it("registers offline package management as a project-scoped route", () => {
    const screen = render(<RootLayout />)

    expect(screen.getByText("screen:offline-packages/[subjectId]/[scopedProjectId]")).toBeTruthy()
  })
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-screen.test.tsx __tests__/root-layout.test.tsx
```

Expected: FAIL because the screen and route do not exist.

- [ ] **Step 3: Implement screen**

Create `mobile/src/screens/OfflineCoursePackagesScreen.tsx`:

```tsx
import { StyleSheet, Text, View } from "react-native"

import { AppButton } from "../components/AppButton"
import { EmptyState } from "../components/EmptyState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"
import type { LocalCoursePackage } from "../offlineCoursePackages/schema"

export function OfflineCoursePackagesScreen({
  connectComputer,
  packages,
  projectTitle,
}: {
  connectComputer: () => void
  packages: LocalCoursePackage[]
  projectTitle?: string | null
}) {
  return (
    <Screen>
      <View style={styles.header}>
        <Text maxFontSizeMultiplier={1.1} style={styles.title}>离线课程包</Text>
        <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{projectTitle ?? "当前项目"}</Text>
      </View>
      <AppButton label="连接电脑" onPress={connectComputer} />
      {packages.length === 0 ? <EmptyState title="暂无离线课程包" /> : null}
      <View style={styles.list}>
        {packages.map((item) => (
          <View key={item.packageId} style={styles.row}>
            <Text maxFontSizeMultiplier={1.1} style={styles.rowTitle}>{item.title}</Text>
            <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{item.status}</Text>
          </View>
        ))}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: ui.spacing.xs },
  list: { gap: 0 },
  meta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  row: { borderBottomColor: ui.colors.borderSoft, borderBottomWidth: 1, gap: ui.spacing.xs, paddingVertical: ui.spacing.lg },
  rowTitle: { color: ui.colors.text, fontSize: ui.type.body, fontWeight: "700" },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
```

- [ ] **Step 4: Implement route and registration**

Create `mobile/src/app/offline-packages/[subjectId]/[scopedProjectId].tsx`:

```tsx
import { useLocalSearchParams } from "expo-router"

import { firstRouteParam } from "../../../routing/params"
import { OfflineCoursePackagesScreen } from "../../../screens/OfflineCoursePackagesScreen"

export default function OfflinePackagesRoute() {
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""

  return (
    <OfflineCoursePackagesScreen
      connectComputer={() => {
        throw new Error(`扫码连接电脑尚未接入：${subjectId}/${scopedProjectId}`)
      }}
      packages={[]}
      projectTitle={scopedProjectId}
    />
  )
}
```

Modify `mobile/src/app/_layout.tsx` inside `<Stack>`:

```tsx
            <Stack.Screen name="offline-packages/[subjectId]/[scopedProjectId]" options={{ title: "离线课程包" }} />
```

Modify `mobile/src/screens/ProjectSettingsScreen.tsx` props:

```tsx
export function ProjectSettingsScreen({
  openOfflinePackages,
  projectTitle,
}: {
  openOfflinePackages?: () => void
  projectTitle?: string | null
}) {
```

Add inside the screen before the `EmptyState`:

```tsx
      {openOfflinePackages ? <AppButton label="离线课程包" onPress={openOfflinePackages} variant="secondary" /> : null}
```

Import `AppButton`.

- [ ] **Step 5: Run tests**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/offline-course-package-screen.test.tsx __tests__/root-layout.test.tsx
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add mobile/src/screens/OfflineCoursePackagesScreen.tsx mobile/src/app/offline-packages mobile/src/app/_layout.tsx mobile/src/screens/ProjectSettingsScreen.tsx mobile/__tests__/offline-course-package-screen.test.tsx mobile/__tests__/root-layout.test.tsx docs/current-change.md
git commit -m "feat: add offline package management route"
```

---

### Task 8: Local Package Playback Source

**Files:**
- Create: `mobile/src/offlineCoursePackages/source.ts`
- Modify: `mobile/src/api/media.ts`
- Modify: `mobile/src/screens/LearningMediaPlayer.tsx`
- Modify: `mobile/__tests__/learning-object-detail.test.tsx`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write local playback source tests**

Append to `mobile/__tests__/learning-object-detail.test.tsx`:

```tsx
import { getLocalPackagePlaybackDescriptor } from "../src/offlineCoursePackages/source"

describe("local package playback source", () => {
  it("resolves a verified local package item into a local playback descriptor", () => {
    const descriptor = getLocalPackagePlaybackDescriptor({
      instanceId: "inst_1",
      item: {
        itemId: "lesson_1",
        title: "第一讲",
        order: 1,
        learningObjectKey: "inst_1",
        video: { path: "videos/01.mp4", sizeBytes: 10, sha256: "0".repeat(64) },
      },
      packageRootUri: "file://document/courses/pkg_1",
    })

    expect(descriptor.sourceKind).toBe("LOCAL_COURSE_PACKAGE")
    expect(descriptor.url).toBe("file://document/courses/pkg_1/videos/01.mp4")
  })
})
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/learning-object-detail.test.tsx
```

Expected: FAIL because source module does not exist.

- [ ] **Step 3: Implement local source module and descriptor union**

Create `mobile/src/offlineCoursePackages/source.ts`:

```ts
import type { PlaybackDescriptor } from "../api/media"
import type { CoursePackageItem } from "./schema"

export function getLocalPackagePlaybackDescriptor({
  instanceId,
  item,
  packageRootUri,
}: {
  instanceId: string
  item: CoursePackageItem
  packageRootUri: string
}): PlaybackDescriptor {
  return {
    instanceId,
    sourceKind: "LOCAL_COURSE_PACKAGE",
    playbackKind: "FILE",
    url: `${packageRootUri.replace(/\/$/, "")}/${item.video.path}`,
    mimeType: "video/mp4",
    durationMs: null,
    supportsFrameGrab: false,
    supportsServerAsr: false,
  }
}
```

Modify `mobile/src/api/media.ts`:

```ts
  sourceKind: z.enum(["SERVER_FS", "BROWSER_LOCAL", "NATIVE_LOCAL", "MANUAL", "BAIDU_NETDISK", "LOCAL_COURSE_PACKAGE"]),
```

- [ ] **Step 4: Update player URL resolution**

Modify `mobile/src/screens/LearningMediaPlayer.tsx`:

```tsx
  const sourceUri =
    descriptor.sourceKind === "LOCAL_COURSE_PACKAGE"
      ? descriptor.url
      : resolveApiResourceUrl(apiBaseUrl, descriptor.url)
```

Then change the `VideoSource`:

```tsx
    uri: sourceUri,
```

Add to `getUnsupportedPlaybackMessage`:

```tsx
  if (descriptor.sourceKind === "LOCAL_COURSE_PACKAGE" && !descriptor.url.startsWith("file://")) {
    return "本地课程包文件地址无效"
  }
```

- [ ] **Step 5: Run tests**

Run:

```powershell
pnpm --dir mobile test -- --runTestsByPath __tests__/learning-object-detail.test.tsx
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add mobile/src/offlineCoursePackages/source.ts mobile/src/api/media.ts mobile/src/screens/LearningMediaPlayer.tsx mobile/__tests__/learning-object-detail.test.tsx docs/current-change.md
git commit -m "feat: support local course package playback"
```

---

### Task 9: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/mobile-client.md`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Update `docs/mobile-client.md` boundaries**

Replace the old mobile boundary statements with:

```markdown
- 移动端不扫描手机系统文件，也不写手机公共目录。
- 移动端允许通过电脑端配对导入 App 托管的离线课程包。
- 离线课程包必须绑定线上学科和 scoped project。
- 手机本地播放只使用 App 私有课程库内已校验文件。
- 删除本地课程包只删除手机本地素材，不删除线上学习记录。
```

- [ ] **Step 2: Update README Public Subtitle Tool section**

Add under `## Public Subtitle Tool`:

```markdown
字幕工具支持为本地课程目录生成手机离线课程包。手机端通过“离线课程包”入口扫码连接电脑端临时局域网服务，主动下载视频、字幕和 manifest 到 App 私有课程库。该能力不扫描手机系统文件，不写公共目录，不做公网中继，课程包必须绑定线上学科和 scoped project。
```

- [ ] **Step 3: Update `docs/current-change.md` final state**

Set the validation section to:

```markdown
## 验证记录

- 已运行：`python -m pytest tests/test_offline_course_package.py tests/test_offline_course_package_server.py -q`
- 已运行：`pnpm --dir mobile test`
- 已运行：`pnpm --dir mobile typecheck`
- 已运行：`git diff --check -- README.md docs/mobile-client.md docs/current-change.md tools/offline_course_package.py tools/offline_course_package_server.py tools/subtitle_tool.py tests/test_offline_course_package.py tests/test_offline_course_package_server.py mobile`
- 未运行：Android/iOS 真机大文件导入 smoke。
```

- [ ] **Step 4: Run full verification**

Run:

```powershell
python -m pytest tests/test_offline_course_package.py tests/test_offline_course_package_server.py -q
pnpm --dir mobile test
pnpm --dir mobile typecheck
git diff --check -- README.md docs/mobile-client.md docs/current-change.md tools/offline_course_package.py tools/offline_course_package_server.py tools/subtitle_tool.py tests/test_offline_course_package.py tests/test_offline_course_package_server.py mobile
```

Expected:

- Python tests pass.
- Mobile Jest passes.
- Mobile typecheck passes.
- `git diff --check` exits 0. LF/CRLF warnings are acceptable if exit code is 0.

- [ ] **Step 5: Commit docs and verification notes**

```powershell
git add README.md docs/mobile-client.md docs/current-change.md
git commit -m "docs: document offline course package import"
```

---

## Self-Review

Spec coverage:

- Desktop manifest: Task 1.
- Desktop temporary LAN service and token-gated Range downloads: Task 2.
- Subtitle tool entry point: Task 3.
- Mobile App-private package schema and storage: Tasks 4 and 5.
- Space check: Task 5.
- Download queue, pause, retry state: Task 6.
- Mobile management UI: Task 7.
- Local playback descriptor: Task 8.
- Documentation and verification: Task 9.

Known implementation gate:

- If Expo SDK 55 installed types do not expose `Paths.availableDiskSpace` or the modern `File`/`Directory` APIs needed here, stop and confirm whether to use a development build or add a native module. Do not replace the design with deprecated APIs silently.

No placeholder implementation slots:

- The plan contains no placeholder implementation slots.
- Each task has explicit file paths, commands, expected outputs, and commit boundaries.
