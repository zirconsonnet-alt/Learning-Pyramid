import argparse
import getpass
import hashlib
import http.cookiejar
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import secrets
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox, ttk
from typing import Callable
from urllib.parse import quote, urljoin, urlsplit
import urllib.request
from zipfile import ZipFile
import tkinter as tk

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT_TEXT = str(PROJECT_ROOT)
if PROJECT_ROOT_TEXT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_TEXT)

try:
    from PySide6.QtCore import QSettings, QTimer, Qt
    from PySide6.QtGui import QFont, QGuiApplication
    from PySide6.QtWidgets import (
        QApplication,
        QBoxLayout,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
    PYSIDE6_IMPORT_ERROR: Exception | None = None
except Exception as exc:
    class _PySide6TypeStub:
        def __getattr__(self, name):
            return self

        def __or__(self, other):
            return self

        def __ror__(self, other):
            return self

        def __call__(self, *args, **kwargs):
            return self

    _QT_STUB = _PySide6TypeStub()
    QSettings = QTimer = Qt = QFont = QGuiApplication = QApplication = QBoxLayout = QCheckBox = QComboBox = QFileDialog = QFrame = QGridLayout = QHBoxLayout = QLabel = QLineEdit = QMainWindow = QMessageBox = QPlainTextEdit = QProgressBar = QPushButton = QScrollArea = QSizePolicy = QSpinBox = QVBoxLayout = QWidget = _QT_STUB
    PYSIDE6_AVAILABLE = False
    PYSIDE6_IMPORT_ERROR = exc

try:
    from backend.system.version import APP_VERSION
except Exception:
    APP_VERSION = "0.0.0"

from tools.offline_course_package import build_course_package
from tools.offline_course_package_server import (
    OfflineCoursePackageSession,
    start_offline_course_package_server,
)


APP_TITLE = "LearningPyramid 字幕生成工具"
TOOL_ID = "subtitle-generator-windows-x64"
TOOL_EXE_BASENAME = "LearningPyramid-SubtitleTool"
DEFAULT_MODEL_FILE = "ggml-base.bin"
DEFAULT_UPDATE_BASE_URL = ""
BUILD_INFO_FILE = "build-info.json"
UPDATE_CONFIG_FILE = "update-config.json"
UPDATE_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm", ".wmv", ".flv")
BAIDU_NETDISK_VIDEO_EXTENSIONS = VIDEO_EXTENSIONS + (".ts", ".m2ts")
CUDA_BACKEND_NAMES = ("ggml-cuda.dll", "libggml-cuda.so", "libggml-cuda.dylib")
CUDA_DEVICE_COUNT_PATTERN = re.compile(r"found\s+(\d+)\s+CUDA devices", re.IGNORECASE)
DEFAULT_RECOGNITION_LANGUAGE = "zh"
RECOGNITION_LANGUAGE_LABELS = {
    "zh": "中文（推荐）",
    "auto": "自动检测",
    "en": "英文",
}
RECOGNITION_LANGUAGE_CODES = tuple(RECOGNITION_LANGUAGE_LABELS.keys())
DEFAULT_QT_WINDOW_WIDTH = 1140
DEFAULT_QT_WINDOW_HEIGHT = 780
MIN_QT_WINDOW_WIDTH = 960
MIN_QT_WINDOW_HEIGHT = 680
RIGHT_COLUMN_MIN_WIDTH = 360
RIGHT_COLUMN_MAX_WIDTH = 520
LAYOUT_BREAKPOINT_STACK = 1040
LAYOUT_BREAKPOINT_COMPACT = 1120
QT_UNBOUNDED_MAX_WIDTH = 16_777_215
SOURCE_MODE_UPDATE_MESSAGE = "源码运行模式，版本跟随当前工作区；在线更新仅在打包后的 EXE 中可用。"
SOURCE_MODE_LOCAL_LABEL = "本地目录"
SOURCE_MODE_PROJECT_BAIDU_LABEL = "项目网盘视频"


class CancelledError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    ffmpeg: Path
    whisper_cli: Path
    model: Path
    cuda_backend: Path | None = None


@dataclass(frozen=True)
class BatchOptions:
    input_dir: Path
    recursive: bool
    overwrite: bool
    threads: int
    enable_gpu: bool = False
    language: str = DEFAULT_RECOGNITION_LANGUAGE


@dataclass(frozen=True)
class ProjectBaiduBatchOptions:
    api_base_url: str
    email: str
    password: str
    subject_id: str
    scoped_project_id: str
    overwrite: bool
    threads: int
    enable_gpu: bool = False
    language: str = DEFAULT_RECOGNITION_LANGUAGE
    baidu_account_id: str | None = None
    baidu_import_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class MobilePackageOptions:
    input_dir: Path
    title: str
    subject_id: str
    scoped_project_id: str
    output_dir: Path | None = None


@dataclass
class BatchSummary:
    total: int
    generated: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UpdateConfig:
    base_url: str
    catalog_url: str
    tool_id: str = TOOL_ID


@dataclass(frozen=True)
class UpdateRelease:
    version: str
    display_name: str
    download_url: str
    published_at: str | None
    sha256: str | None
    size_bytes: int
    summary: str | None = None


@dataclass(frozen=True)
class InstalledBuildInfo:
    version: str
    published_at: str | None = None


class ProcessController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def attach(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._process = process

    def clear(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if self._process is process:
                self._process = None

    def terminate(self) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
        except Exception:
            return


def normalize_learningpyramid_api_base_url(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        raise ValueError("请填写 LearningPyramid API 地址。")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LearningPyramid API 地址必须以 http:// 或 https:// 开头。")
    if parsed.path.rstrip("/") == "/api" or parsed.path.rstrip("/").endswith("/api"):
        return raw
    return f"{raw}/api"


def _extract_api_error_message(payload: object, fallback: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
            if message:
                return message
        detail = payload.get("detail")
        if detail:
            return str(detail)
    return str(fallback or "请求 LearningPyramid API 失败")


def _api_join(api_base_url: str, path: str) -> str:
    return f"{api_base_url.rstrip('/')}/{str(path).lstrip('/')}"


def _project_api_suffix(subject_id: str, scoped_project_id: str, suffix: str) -> str:
    return (
        f"/subjects/{quote(str(subject_id), safe='')}"
        f"/projects/{quote(str(scoped_project_id), safe='')}"
        f"{suffix}"
    )


class LearningPyramidProjectClient:
    def __init__(self, api_base_url: str) -> None:
        self.api_base_url = normalize_learningpyramid_api_base_url(api_base_url)
        self.timeout_seconds = 60
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))

    def login(self, *, email: str, password: str) -> None:
        self._request_json(
            "POST",
            "/auth/login",
            body={"email": str(email).strip(), "password": str(password)},
        )

    def list_subjects(self):
        return self._request_json("GET", "/subjects")

    def list_subject_materials(self, subject_id: str):
        return self._request_json("GET", f"/subjects/{quote(str(subject_id), safe='')}/materials")

    def list_baidu_netdisk_accounts(self):
        return self._request_json("GET", "/profile/me/cloud-accounts/baidu-netdisk")

    def list_project_baidu_netdisk_files(
        self,
        subject_id: str,
        scoped_project_id: str,
        account_id: str,
        *,
        dir_path: str = "/",
        page: int = 1,
    ):
        query = (
            f"accountId={quote(str(account_id), safe='')}"
            f"&dirPath={quote(str(dir_path or '/'), safe='')}"
            f"&page={max(1, int(page))}&limit=200"
        )
        return self._request_json(
            "GET",
            f"{_project_api_suffix(subject_id, scoped_project_id, '/baidu-netdisk/files')}?{query}",
        )

    def list_instances(self, subject_id: str, scoped_project_id: str):
        return self._request_json("GET", _project_api_suffix(subject_id, scoped_project_id, "/instances"))

    def get_instance_subtitle_file(self, subject_id: str, scoped_project_id: str, instance_id: str):
        return self._request_json(
            "GET",
            _project_api_suffix(
                subject_id,
                scoped_project_id,
                f"/instances/{quote(str(instance_id), safe='')}/subtitle-file",
            ),
        )

    def get_instance_baidu_direct_playback_descriptor(self, subject_id: str, scoped_project_id: str, instance_id: str):
        return self._request_json(
            "GET",
            _project_api_suffix(
                subject_id,
                scoped_project_id,
                f"/media/instances/{quote(str(instance_id), safe='')}/baidu-direct-playback",
            ),
        )

    def upload_instance_subtitle_file(
        self,
        subject_id: str,
        scoped_project_id: str,
        instance_id: str,
        *,
        file_name: str,
        content: str,
    ):
        return self._request_json(
            "POST",
            _project_api_suffix(
                subject_id,
                scoped_project_id,
                f"/instances/{quote(str(instance_id), safe='')}/subtitle-file",
            ),
            body={"fileName": file_name, "content": content},
        )

    def import_learning_objects_from_baidu_netdisk(
        self,
        subject_id: str,
        scoped_project_id: str,
        account_id: str,
        *,
        items: list[dict[str, object]],
    ):
        return self._request_json(
            "POST",
            _project_api_suffix(subject_id, scoped_project_id, "/import-learning-objects-from-baidu-netdisk"),
            body={"accountId": account_id, "items": items},
        )

    def _request_json(self, method: str, path: str, *, body: object | None = None):
        payload_bytes: bytes | None = None
        headers = {
            "Accept": "application/json",
            "User-Agent": f"{TOOL_EXE_BASENAME}/{APP_VERSION}",
        }
        if body is not None:
            payload_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            _api_join(self.api_base_url, path),
            data=payload_bytes,
            headers=headers,
            method=method.upper(),
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            parsed_error: object = None
            try:
                parsed_error = json.loads(raw_error)
            except Exception:
                parsed_error = None
            raise RuntimeError(_extract_api_error_message(parsed_error, raw_error or str(exc))) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接 LearningPyramid API：{exc.reason}") from exc

        text = raw.decode("utf-8", errors="replace") if raw else ""
        try:
            payload = json.loads(text) if text else None
        except Exception as exc:
            raise RuntimeError("LearningPyramid API 返回了不可解析的响应。") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("LearningPyramid API 返回了无效响应。")
        if payload.get("ok") is not True:
            raise RuntimeError(_extract_api_error_message(payload, "LearningPyramid API 请求失败。"))
        return payload.get("data")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def default_threads() -> int:
    cpu_count = os.cpu_count() or 4
    return max(1, min(cpu_count, 8))


def default_mobile_package_output_dir(input_dir: Path) -> Path:
    resolved_input = input_dir.expanduser().resolve()
    return resolved_input.parent / f"{resolved_input.name}.learningpyramid-mobile-package"


def _validate_mobile_package_options(options: MobilePackageOptions) -> None:
    if not options.input_dir.exists() or not options.input_dir.is_dir():
        raise FileNotFoundError(f"课程目录不存在：{options.input_dir}")
    missing: list[str] = []
    if not str(options.title or "").strip():
        missing.append("--mobile-package-title")
    if not str(options.subject_id or "").strip():
        missing.append("--mobile-subject-id")
    if not str(options.scoped_project_id or "").strip():
        missing.append("--mobile-project-id")
    if missing:
        raise ValueError(f"手机导入模式缺少参数：{', '.join(missing)}")


def build_mobile_package_session(options: MobilePackageOptions) -> OfflineCoursePackageSession:
    _validate_mobile_package_options(options)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=2)
    package_root = options.output_dir or default_mobile_package_output_dir(options.input_dir)
    manifest = build_course_package(
        input_dir=options.input_dir.expanduser().resolve(),
        output_dir=package_root.expanduser().resolve(),
        title=options.title.strip(),
        subject_id=options.subject_id.strip(),
        scoped_project_id=options.scoped_project_id.strip(),
        package_id=f"mobile_{secrets.token_urlsafe(16)}",
        created_at=now.isoformat(),
    )
    return OfflineCoursePackageSession(
        root=package_root.expanduser().resolve(),
        manifest=manifest,
        token=secrets.token_urlsafe(32),
        expires_at_epoch=expires_at.timestamp(),
    )


def build_mobile_package_session_from_args(args: argparse.Namespace) -> OfflineCoursePackageSession:
    input_dir_text = str(getattr(args, "mobile_package_dir", "") or getattr(args, "input_dir", "") or "").strip()
    if not input_dir_text:
        raise SystemExit("请提供 --mobile-package-dir。")
    input_dir = Path(input_dir_text).expanduser().resolve()
    title = str(getattr(args, "mobile_package_title", "") or "").strip() or input_dir.name
    return build_mobile_package_session(
        MobilePackageOptions(
            input_dir=input_dir,
            title=title,
            subject_id=str(getattr(args, "mobile_subject_id", "") or "").strip(),
            scoped_project_id=str(getattr(args, "mobile_project_id", "") or "").strip(),
        )
    )


def format_mobile_package_connection_message(session: OfflineCoursePackageSession, base_url: str) -> str:
    expires_at = datetime.fromtimestamp(session.expires_at_epoch, timezone.utc).astimezone()
    return (
        "手机和电脑在局域网可互相访问时使用。\n\n"
        f"课程包：{session.root}\n"
        f"Metadata：{base_url}/metadata\n"
        f"Manifest：{base_url}/manifest\n"
        f"Token：{session.token}\n"
        f"过期时间：{expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )


def _wait_for_mobile_package_server_interrupt() -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return


def discover_runtime_paths(runtime_dir: Path | None = None) -> RuntimePaths:
    candidates: list[Path] = []
    configured_runtime = (os.getenv("LP_SUBTITLE_TOOL_RUNTIME_DIR") or "").strip()
    if runtime_dir is not None:
        candidates.append(runtime_dir.expanduser().resolve())
    if configured_runtime:
        candidates.append(Path(configured_runtime).expanduser().resolve())

    base_dir = executable_dir()
    candidates.extend(
        [
            (base_dir / "runtime").resolve(),
            (base_dir / "subtitle-tool-runtime").resolve(),
            (SCRIPT_DIR / "runtime").resolve(),
            (PROJECT_ROOT / "build" / "subtitle-tool" / "runtime").resolve(),
        ]
    )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        runtime = _try_make_runtime_paths(candidate)
        if runtime is not None:
            return runtime

    raise FileNotFoundError(
        "未找到内置运行时目录。请确认工具包中的 runtime 目录、ffmpeg.exe、whisper-cli.exe 和 ggml-base.bin 都在。"
    )


def _try_make_runtime_paths(root: Path) -> RuntimePaths | None:
    if not root.exists() or not root.is_dir():
        return None

    ffmpeg = _find_first_file(root, ("ffmpeg.exe", "ffmpeg"))
    whisper_cli = _find_first_file(root, ("whisper-cli.exe", "whisper-cli"))
    model = _find_first_file(root, (DEFAULT_MODEL_FILE,))
    if ffmpeg is None or whisper_cli is None or model is None:
        return None
    cuda_backend = _find_first_file(root, CUDA_BACKEND_NAMES)
    return RuntimePaths(root=root, ffmpeg=ffmpeg, whisper_cli=whisper_cli, model=model, cuda_backend=cuda_backend)


def _find_first_file(root: Path, names: tuple[str, ...]) -> Path | None:
    wanted = {name.lower() for name in names}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name.lower() in wanted:
            return path
    return None


def iter_video_files(root: Path, recursive: bool) -> list[Path]:
    iterator = root.rglob("*") if recursive else root.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def format_elapsed_short(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_bytes(size_bytes: int) -> str:
    value = max(0, float(size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{int(value)} B"


def _naturalize_version_tokens(text: str) -> tuple[tuple[int, object], ...]:
    tokens = re.findall(r"\d+|[a-z]+", text.lower())
    result: list[tuple[int, object]] = []
    for token in tokens:
        if token.isdigit():
            result.append((0, int(token)))
            continue
        order = {
            "dev": 0,
            "alpha": 1,
            "a": 1,
            "beta": 2,
            "b": 2,
            "rc": 3,
        }.get(token, 9)
        result.append((1, f"{order:02d}:{token}"))
    return tuple(result)


def version_sort_key(version: str) -> tuple[tuple[int, ...], int, tuple[tuple[int, object], ...]]:
    cleaned = version.strip().lower()
    main, separator, prerelease = cleaned.partition("-")
    main_parts = [int(part) for part in re.findall(r"\d+", main)]
    while len(main_parts) < 4:
        main_parts.append(0)
    return (tuple(main_parts), 1 if not separator else 0, _naturalize_version_tokens(prerelease))


def is_version_newer(candidate: str, current: str) -> bool:
    if not candidate.strip():
        return False
    return version_sort_key(candidate) > version_sort_key(current)


def load_installed_build_info() -> InstalledBuildInfo:
    payload: dict[str, object] = {}
    build_info_path = executable_dir() / BUILD_INFO_FILE
    if build_info_path.exists():
        try:
            loaded = json.loads(build_info_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}

    version = str(payload.get("version") or "").strip() or APP_VERSION
    published_at = str(payload.get("publishedAt") or "").strip() or None
    return InstalledBuildInfo(version=version, published_at=published_at)


def is_release_newer_than_installed(release: UpdateRelease, installed: InstalledBuildInfo) -> bool:
    if is_version_newer(release.version, installed.version):
        return True
    if release.version.strip() != installed.version.strip():
        return False
    if release.published_at and installed.published_at:
        return release.published_at > installed.published_at
    return False


def load_update_config() -> UpdateConfig:
    payload: dict[str, object] = {}
    config_path = executable_dir() / UPDATE_CONFIG_FILE
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}

    env_catalog_url = (os.getenv("LP_SUBTITLE_TOOL_UPDATE_CATALOG_URL") or "").strip()
    env_base_url = (os.getenv("LP_SUBTITLE_TOOL_UPDATE_BASE_URL") or "").strip()
    env_tool_id = (os.getenv("LP_SUBTITLE_TOOL_ID") or "").strip()

    base_url = str(payload.get("baseUrl") or "").strip() or DEFAULT_UPDATE_BASE_URL
    if env_base_url:
        base_url = env_base_url
    base_url = base_url.rstrip("/")

    catalog_url = str(payload.get("catalogUrl") or "").strip()
    if env_catalog_url:
        catalog_url = env_catalog_url
    if not catalog_url:
        if not base_url:
            return UpdateConfig(base_url="", catalog_url="", tool_id=str(payload.get("toolId") or "").strip() or TOOL_ID)
        catalog_url = urljoin(f"{base_url}/", "/api/system/public-downloads")

    tool_id = str(payload.get("toolId") or "").strip() or TOOL_ID
    if env_tool_id:
        tool_id = env_tool_id

    return UpdateConfig(base_url=base_url, catalog_url=catalog_url, tool_id=tool_id)


def fetch_latest_release(config: UpdateConfig) -> UpdateRelease | None:
    if not config.catalog_url:
        return None
    request = urllib.request.Request(
        config.catalog_url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{TOOL_EXE_BASENAME}/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload.get("data")
    if not isinstance(payload, dict):
        return None

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return None

    releases: list[UpdateRelease] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("id") or "").strip() != config.tool_id:
            continue

        version = str(raw.get("version") or "").strip()
        if not version:
            continue

        download_path = str(raw.get("downloadPath") or "").strip()
        asset_path = str(raw.get("assetPath") or "").strip().replace("\\", "/").lstrip("/")
        download_url = ""
        if download_path:
            download_url = urljoin(f"{config.base_url}/", download_path)
        elif asset_path:
            download_url = urljoin(f"{config.base_url}/", f"/downloads/{asset_path}")
        if not download_url:
            continue

        releases.append(
            UpdateRelease(
                version=version,
                display_name=str(raw.get("displayName") or APP_TITLE).strip() or APP_TITLE,
                download_url=download_url,
                published_at=str(raw.get("publishedAt") or "").strip() or None,
                sha256=str(raw.get("sha256") or "").strip() or None,
                size_bytes=max(0, int(raw.get("sizeBytes") or 0)),
                summary=str(raw.get("summary") or "").strip() or None,
            )
        )

    if not releases:
        return None

    return max(releases, key=lambda item: version_sort_key(item.version))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_release_zip(
    release: UpdateRelease,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    update_root = Path(tempfile.gettempdir()) / "LearningPyramidSubtitleTool" / "updates" / release.version
    if update_root.exists():
        shutil.rmtree(update_root, ignore_errors=True)
    update_root.mkdir(parents=True, exist_ok=True)

    zip_name = Path(urlsplit(release.download_url).path).name or f"{TOOL_EXE_BASENAME}-{release.version}.zip"
    zip_path = update_root / zip_name
    request = urllib.request.Request(
        release.download_url,
        headers={"User-Agent": f"{TOOL_EXE_BASENAME}/{APP_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response, zip_path.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        while True:
            chunk = response.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if on_progress is not None:
                on_progress(downloaded, total)

    if release.sha256:
        actual_sha256 = _sha256_file(zip_path)
        if actual_sha256.lower() != release.sha256.lower():
            raise RuntimeError("更新包校验失败，请稍后重试。")

    if on_progress is not None:
        on_progress(zip_path.stat().st_size, zip_path.stat().st_size)
    return zip_path


def extract_release_bundle(zip_path: Path) -> Path:
    extract_root = zip_path.parent / "bundle"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_root)

    direct_match = extract_root / f"{TOOL_EXE_BASENAME}.exe"
    if direct_match.exists():
        return extract_root

    for child in sorted(extract_root.iterdir()):
        if child.is_dir() and (child / f"{TOOL_EXE_BASENAME}.exe").exists():
            return child

    raise RuntimeError("更新包缺少可执行文件，无法完成安装。")


def whisper_output_file(prefix: Path, extension: str) -> Path:
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return prefix.parent / f"{prefix.name}{normalized_extension}"


def runtime_supports_cuda(runtime: RuntimePaths) -> bool:
    return runtime.cuda_backend is not None


def normalize_recognition_language(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in RECOGNITION_LANGUAGE_LABELS:
        return normalized
    return DEFAULT_RECOGNITION_LANGUAGE


def recognition_language_label(value: str | None) -> str:
    return RECOGNITION_LANGUAGE_LABELS[normalize_recognition_language(value)]


def recognition_language_code_from_label(value: str | None) -> str:
    normalized = str(value or "").strip()
    for code, label in RECOGNITION_LANGUAGE_LABELS.items():
        if normalized == label:
            return code
    return normalize_recognition_language(normalized)


def parse_cuda_device_count(output: str) -> int | None:
    match = CUDA_DEVICE_COUNT_PATTERN.search(output)
    if match is None:
        return None
    return max(0, int(match.group(1)))


def detect_cuda_device_count(runtime: RuntimePaths, *, timeout_seconds: float = 8.0) -> int | None:
    if not runtime_supports_cuda(runtime):
        return None

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [str(runtime.whisper_cli), "-h"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=creationflags,
            check=False,
        )
    except Exception:
        return None

    combined_output = f"{completed.stdout}\n{completed.stderr}"
    return parse_cuda_device_count(combined_output)


def format_runtime_acceleration_text(runtime: RuntimePaths) -> str:
    if runtime_supports_cuda(runtime):
        return "支持 GPU 模式（NVIDIA CUDA，可选）"
    return "仅支持 CPU 模式"


def format_selected_acceleration_text(enable_gpu: bool) -> str:
    if enable_gpu:
        return "GPU 模式（允许使用 NVIDIA CUDA）"
    return "CPU 模式"


def build_whisper_command(
    *,
    runtime: RuntimePaths,
    audio_path: Path,
    output_prefix: Path,
    threads: int,
    enable_gpu: bool,
    language: str,
) -> list[str]:
    if enable_gpu and not runtime_supports_cuda(runtime):
        raise RuntimeError("当前运行时未包含 CUDA backend，暂时不能启用 GPU 模式。")

    normalized_language = normalize_recognition_language(language)
    command = [
        str(runtime.whisper_cli),
        "-m",
        str(runtime.model),
        "-f",
        str(audio_path),
        "-t",
        str(max(1, threads)),
        "-l",
        normalized_language,
    ]
    if not enable_gpu:
        command.append("-ng")
    command.extend(
        [
            "-osrt",
            "-of",
            str(output_prefix),
        ]
    )
    return command


def create_windows_update_script(*, source_dir: Path, target_dir: Path) -> Path:
    script_dir = source_dir.parent
    script_path = script_dir / "apply-update.ps1"
    script_text = """param(
    [int]$WaitPid,
    [string]$SourceDir,
    [string]$TargetDir,
    [string]$ExeName
)

$ErrorActionPreference = "Stop"

for ($attempt = 0; $attempt -lt 240; $attempt++) {
    if (-not (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue)) {
        break
    }
    Start-Sleep -Milliseconds 500
}

if (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) {
    throw "Waiting for the running app to exit timed out."
}

& robocopy $SourceDir $TargetDir /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -ge 8) {
    throw "Robocopy failed while applying the update."
}

Start-Sleep -Milliseconds 400
Start-Process -FilePath (Join-Path $TargetDir $ExeName)
"""
    script_path.write_text(script_text, encoding="utf-8", newline="\n")
    return script_path


def run_batch(
    options: BatchOptions,
    runtime: RuntimePaths,
    *,
    log: Callable[[str], None],
    progress: Callable[[str], None],
    cancel_event: threading.Event,
    process_controller: ProcessController,
) -> BatchSummary:
    if not options.input_dir.exists() or not options.input_dir.is_dir():
        raise FileNotFoundError(f"目录不存在：{options.input_dir}")

    videos = iter_video_files(options.input_dir, recursive=options.recursive)
    if not videos:
        raise FileNotFoundError("当前目录下没有找到支持的视频文件。")

    summary = BatchSummary(total=len(videos))
    for index, video_path in enumerate(videos, start=1):
        if cancel_event.is_set():
            raise CancelledError("任务已取消。")

        subtitle_path = video_path.with_suffix(".srt")
        progress(index - 1, summary.total, video_path, "准备处理当前视频。")

        if subtitle_path.exists() and not options.overwrite:
            summary.skipped += 1
            log(f"[{index}/{summary.total}] 跳过 {video_path.name}，同名字幕已存在。")
            progress(index, summary.total, video_path, "已跳过，同名字幕已存在。")
            continue

        try:
            log(f"[{index}/{summary.total}] 正在处理 {video_path.name}")
            generate_subtitle_for_video(
                video_path=video_path,
                subtitle_path=subtitle_path,
                runtime=runtime,
                threads=options.threads,
                enable_gpu=options.enable_gpu,
                language=options.language,
                cancel_event=cancel_event,
                process_controller=process_controller,
                log=log,
                progress=lambda stage_progress, detail: progress((index - 1) + stage_progress, summary.total, video_path, detail),
            )
            summary.generated += 1
            log(f"[{index}/{summary.total}] 已生成 {subtitle_path.name}")
        except CancelledError:
            raise
        except Exception as exc:
            summary.failed += 1
            error_text = f"{video_path.name}: {exc}"
            summary.failures.append(error_text)
            log(f"[{index}/{summary.total}] 失败 {error_text}")

        progress(index, summary.total, video_path, "当前视频已处理完成。")

    return summary


def _display_name_from_instance(item: object) -> str:
    if isinstance(item, dict):
        for key in ("materialDisplayName", "materialId", "instanceId"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
    return "未命名视频"


def _instance_id_from_instance(item: object) -> str:
    if isinstance(item, dict):
        value = str(item.get("instanceId") or "").strip()
        if value:
            return value
    raise RuntimeError("项目实例缺少 instanceId。")


def _is_project_baidu_hls_instance(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    return str(item.get("mediaSourceKind") or "").strip() == "BAIDU_NETDISK" and str(item.get("playbackKind") or "").strip() == "HLS"


def _is_baidu_netdisk_video_item(item: dict[str, object]) -> bool:
    mime_type = str(item.get("mimeType") or "").strip().lower()
    if mime_type.startswith("video/"):
        return True
    name = str(item.get("name") or item.get("path") or "").strip().lower()
    return name.endswith(BAIDU_NETDISK_VIDEO_EXTENSIONS)


def _is_baidu_netdisk_importable_item(item: dict[str, object]) -> bool:
    return bool(item.get("isDir")) or _is_baidu_netdisk_video_item(item)


def normalize_baidu_remote_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        raise ValueError("百度网盘路径不能为空。")
    if not raw.startswith("/"):
        raw = f"/{raw}"
    normalized = PurePosixPath(raw).as_posix()
    return normalized if normalized.startswith("/") else f"/{normalized}"


def parse_baidu_import_paths_text(value: str) -> tuple[str, ...]:
    paths: list[str] = []
    seen: set[str] = set()
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        path = normalize_baidu_remote_path(line)
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return tuple(paths)


def _baidu_remote_parent_dir(remote_path: str) -> str:
    parent = PurePosixPath(normalize_baidu_remote_path(remote_path)).parent.as_posix()
    return parent if parent.startswith("/") else f"/{parent}"


def _resolve_single_baidu_account_id(client: object, configured_account_id: str | None) -> str:
    explicit = str(configured_account_id or "").strip()
    if explicit:
        return explicit
    accounts = client.list_baidu_netdisk_accounts()  # type: ignore[attr-defined]
    if not isinstance(accounts, list):
        raise RuntimeError("百度网盘账号响应无效。")
    enabled_accounts = [
        item for item in accounts
        if isinstance(item, dict) and str(item.get("accountId") or "").strip() and not item.get("disabledAt")
    ]
    if not enabled_accounts:
        raise RuntimeError("当前 LearningPyramid 账号还没有绑定百度网盘。")
    if len(enabled_accounts) > 1:
        raise RuntimeError("检测到多个百度网盘账号，请明确填写账号 ID。")
    return str(enabled_accounts[0]["accountId"]).strip()


def _resolve_baidu_import_item(
    client: object,
    *,
    subject_id: str,
    scoped_project_id: str,
    account_id: str,
    remote_path: str,
) -> dict[str, object]:
    normalized_path = normalize_baidu_remote_path(remote_path)
    if normalized_path == "/":
        raise ValueError("项目网盘模式不导入百度网盘根目录，请选择具体课程目录或视频文件。")
    parent_dir = _baidu_remote_parent_dir(normalized_path)
    page = 1
    while True:
        payload = client.list_project_baidu_netdisk_files(  # type: ignore[attr-defined]
            subject_id,
            scoped_project_id,
            account_id,
            dir_path=parent_dir,
            page=page,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("百度网盘目录响应无效。")
        items = payload.get("items")
        rows = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        for item in rows:
            if normalize_baidu_remote_path(str(item.get("path") or "")) != normalized_path:
                continue
            if not _is_baidu_netdisk_importable_item(item):
                raise RuntimeError(f"百度网盘路径不是目录或视频文件：{normalized_path}")
            file_id = str(item.get("fileId") or "").strip()
            if not file_id:
                raise RuntimeError(f"百度网盘路径缺少 fileId：{normalized_path}")
            resolved: dict[str, object] = {
                "fileId": file_id,
                "path": str(item.get("path") or "").strip(),
                "isDir": bool(item.get("isDir")),
            }
            name = str(item.get("name") or "").strip()
            if name:
                resolved["name"] = name
            for source_key, target_key in (
                ("sizeBytes", "sizeBytes"),
                ("mimeType", "mimeType"),
                ("durationMs", "durationMs"),
            ):
                value = item.get(source_key)
                if value is not None:
                    resolved[target_key] = value
            return resolved
        if not bool(payload.get("hasMore")):
            break
        page += 1
    raise RuntimeError(f"百度网盘路径不存在或当前项目无法访问：{normalized_path}")


def import_baidu_paths_into_project(
    *,
    client: object,
    options: ProjectBaiduBatchOptions,
    log: Callable[[str], None],
) -> None:
    paths = tuple(normalize_baidu_remote_path(item) for item in options.baidu_import_paths if str(item or "").strip())
    if not paths:
        return
    account_id = _resolve_single_baidu_account_id(client, options.baidu_account_id)
    items = [
        _resolve_baidu_import_item(
            client,
            subject_id=options.subject_id,
            scoped_project_id=options.scoped_project_id,
            account_id=account_id,
            remote_path=path,
        )
        for path in paths
    ]
    log(f"准备导入百度网盘路径：{', '.join(paths)}")
    client.import_learning_objects_from_baidu_netdisk(  # type: ignore[attr-defined]
        options.subject_id,
        options.scoped_project_id,
        account_id,
        items=items,
    )
    log("百度网盘视频已导入到当前项目。")


def subtitle_file_name_for_display_name(display_name: str, *, instance_id: str) -> str:
    normalized = str(display_name or "").replace("\\", "/").strip()
    filename = normalized.rsplit("/", 1)[-1] if normalized else ""
    stem = Path(filename).stem.strip()
    if not stem:
        stem = str(instance_id or "").strip() or "subtitle"
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(". ") or "subtitle"
    return f"{stem}.srt"


def run_project_baidu_batch(
    options: ProjectBaiduBatchOptions,
    runtime: RuntimePaths,
    *,
    client: object | None = None,
    log: Callable[[str], None],
    progress: Callable[[float, int, str, str], None],
    cancel_event: threading.Event,
    process_controller: ProcessController,
) -> BatchSummary:
    normalized_language = normalize_recognition_language(options.language)
    project_client = client
    if project_client is None:
        project_client = LearningPyramidProjectClient(options.api_base_url)
        project_client.login(email=options.email, password=options.password)  # type: ignore[attr-defined]

    import_baidu_paths_into_project(client=project_client, options=options, log=log)

    instances = project_client.list_instances(options.subject_id, options.scoped_project_id)  # type: ignore[attr-defined]
    if not isinstance(instances, list):
        raise RuntimeError("LearningPyramid 项目实例响应无效。")
    videos = [item for item in instances if _is_project_baidu_hls_instance(item)]
    if not videos:
        raise FileNotFoundError("当前项目中没有找到已导入的百度网盘视频实例。")

    summary = BatchSummary(total=len(videos))
    for index, item in enumerate(videos, start=1):
        if cancel_event.is_set():
            raise CancelledError("任务已取消。")

        instance_id = _instance_id_from_instance(item)
        display_name = _display_name_from_instance(item)
        subtitle_name = subtitle_file_name_for_display_name(display_name, instance_id=instance_id)
        progress(index - 1, summary.total, display_name, "准备处理当前网盘视频。")

        try:
            if not options.overwrite:
                existing = project_client.get_instance_subtitle_file(options.subject_id, options.scoped_project_id, instance_id)  # type: ignore[attr-defined]
                if isinstance(existing, dict) and existing.get("found") is True:
                    summary.skipped += 1
                    log(f"[{index}/{summary.total}] 跳过 {display_name}，实例字幕已存在。")
                    progress(index, summary.total, display_name, "已跳过，实例字幕已存在。")
                    continue

            log(f"[{index}/{summary.total}] 正在处理 {display_name}")
            descriptor = project_client.get_instance_baidu_direct_playback_descriptor(  # type: ignore[attr-defined]
                options.subject_id,
                options.scoped_project_id,
                instance_id,
            )
            if not isinstance(descriptor, dict):
                raise RuntimeError("百度网盘播放描述符响应无效。")
            playlist_text = str(descriptor.get("playlistText") or "").strip()
            if not playlist_text:
                raise RuntimeError("百度网盘播放描述符缺少 HLS playlist。")

            subtitle_content = generate_subtitle_for_baidu_hls(
                display_name=display_name,
                playlist_text=playlist_text,
                runtime=runtime,
                threads=options.threads,
                enable_gpu=options.enable_gpu,
                language=normalized_language,
                cancel_event=cancel_event,
                process_controller=process_controller,
                log=log,
                progress=lambda stage_progress, detail: progress((index - 1) + stage_progress, summary.total, display_name, detail),
            )
            project_client.upload_instance_subtitle_file(  # type: ignore[attr-defined]
                options.subject_id,
                options.scoped_project_id,
                instance_id,
                file_name=subtitle_name,
                content=subtitle_content,
            )
            summary.generated += 1
            log(f"[{index}/{summary.total}] 已生成 {subtitle_name}")
        except CancelledError:
            raise
        except Exception as exc:
            summary.failed += 1
            error_text = f"{display_name}: {exc}"
            summary.failures.append(error_text)
            log(f"[{index}/{summary.total}] 失败 {error_text}")

        progress(index, summary.total, display_name, "当前网盘视频已处理完成。")

    return summary


def _generate_subtitle_bytes_from_media_input(
    *,
    input_args: list[str],
    display_name: str,
    runtime: RuntimePaths,
    threads: int,
    enable_gpu: bool,
    language: str,
    cancel_event: threading.Event,
    process_controller: ProcessController,
    log: Callable[[str], None],
    progress: Callable[[str], None],
) -> bytes:
    safe_stem = subtitle_file_name_for_display_name(display_name, instance_id="subtitle").removesuffix(".srt")
    with tempfile.TemporaryDirectory(prefix="lp-subtitle-tool-") as tmpdir:
        tmp_root = Path(tmpdir)
        wav_path = tmp_root / f"{safe_stem}.wav"
        output_prefix = tmp_root / safe_stem

        log(f"  - 提取音频：{display_name}")
        progress(0.08, "正在提取音频...")
        _run_process(
            [
                str(runtime.ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                *input_args,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            cancel_event=cancel_event,
            process_controller=process_controller,
            on_heartbeat=lambda elapsed: progress(0.18, f"正在提取音频（已运行 {format_elapsed_short(elapsed)}）"),
        )

        acceleration_text = format_selected_acceleration_text(enable_gpu)
        language_text = recognition_language_label(language)
        log(f"  - 识别语音（{acceleration_text} / {language_text}）：{display_name}")
        progress(0.34, f"音频提取完成，正在识别语音（{acceleration_text} / {language_text}）...")
        _run_process(
            build_whisper_command(
                runtime=runtime,
                audio_path=wav_path,
                output_prefix=output_prefix,
                threads=threads,
                enable_gpu=enable_gpu,
                language=language,
            ),
            cancel_event=cancel_event,
            process_controller=process_controller,
            on_heartbeat=lambda elapsed: progress(0.72, f"正在识别语音（已运行 {format_elapsed_short(elapsed)}）"),
        )

        generated_srt = whisper_output_file(output_prefix, ".srt")
        if not generated_srt.exists():
            raise RuntimeError("whisper.cpp 没有产出 .srt 文件。")
        progress(0.92, "识别完成，正在整理字幕文件。")
        return generated_srt.read_bytes()


def generate_subtitle_for_video(
    *,
    video_path: Path,
    subtitle_path: Path,
    runtime: RuntimePaths,
    threads: int,
    enable_gpu: bool,
    language: str,
    cancel_event: threading.Event,
    process_controller: ProcessController,
    log: Callable[[str], None],
    progress: Callable[[str], None],
) -> None:
    srt_bytes = _generate_subtitle_bytes_from_media_input(
        input_args=["-i", str(video_path)],
        display_name=video_path.name,
        runtime=runtime,
        threads=threads,
        enable_gpu=enable_gpu,
        language=language,
        cancel_event=cancel_event,
        process_controller=process_controller,
        log=log,
        progress=progress,
    )
    subtitle_path.write_bytes(srt_bytes)
    progress(0.98, "字幕文件已写入到视频同目录。")


def generate_subtitle_for_baidu_hls(
    *,
    display_name: str,
    playlist_text: str,
    runtime: RuntimePaths,
    threads: int,
    enable_gpu: bool,
    language: str,
    cancel_event: threading.Event,
    process_controller: ProcessController,
    log: Callable[[str], None],
    progress: Callable[[str], None],
) -> str:
    normalized_playlist = str(playlist_text or "")
    if not normalized_playlist.lstrip().startswith("#EXTM3U"):
        raise RuntimeError("百度网盘播放列表不是有效 HLS playlist。")
    with tempfile.TemporaryDirectory(prefix="lp-subtitle-tool-baidu-") as tmpdir:
        playlist_path = Path(tmpdir) / "playlist.m3u8"
        playlist_path.write_text(normalized_playlist, encoding="utf-8", newline="\n")
        srt_bytes = _generate_subtitle_bytes_from_media_input(
            input_args=[
                "-protocol_whitelist",
                "file,http,https,tcp,tls,crypto",
                "-allowed_extensions",
                "ALL",
                "-i",
                str(playlist_path),
            ],
            display_name=display_name,
            runtime=runtime,
            threads=threads,
            enable_gpu=enable_gpu,
            language=language,
            cancel_event=cancel_event,
            process_controller=process_controller,
            log=log,
            progress=progress,
        )
    progress(0.98, "字幕已生成，正在上传到 LearningPyramid。")
    return srt_bytes.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _stream_process_output(stream, output_queue: "queue.Queue[str]") -> None:
    try:
        while True:
            line = stream.readline()
            if not line:
                break
            output_queue.put(line.rstrip())
    except Exception:
        return


def _run_process(
    command: list[str],
    *,
    cancel_event: threading.Event,
    process_controller: ProcessController,
    on_heartbeat: Callable[[], None] | None = None,
) -> None:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
    )
    output_queue: queue.Queue[str] = queue.Queue()
    recent_output: list[str] = []
    reader_thread: threading.Thread | None = None
    if process.stdout is not None:
        reader_thread = threading.Thread(target=_stream_process_output, args=(process.stdout, output_queue), daemon=True)
        reader_thread.start()

    process_controller.attach(process)
    started_at = time.monotonic()
    try:
        while True:
            if cancel_event.is_set():
                process_controller.terminate()
                raise CancelledError("任务已取消。")
            while True:
                try:
                    line = output_queue.get_nowait().strip()
                except queue.Empty:
                    break
                if not line:
                    continue
                recent_output.append(line)
                if len(recent_output) > 24:
                    recent_output = recent_output[-24:]
            if on_heartbeat is not None:
                on_heartbeat(time.monotonic() - started_at)
            if process.poll() is not None:
                break
            time.sleep(0.2)
    finally:
        process_controller.clear(process)
        if reader_thread is not None:
            reader_thread.join(timeout=1.0)
        while True:
            try:
                line = output_queue.get_nowait().strip()
            except queue.Empty:
                break
            if not line:
                continue
            recent_output.append(line)
            if len(recent_output) > 24:
                recent_output = recent_output[-24:]

    if process.returncode != 0:
        detail = "\n".join(recent_output).strip() or "子进程执行失败"
        raise RuntimeError(detail[:600])


def print_runtime_summary(runtime: RuntimePaths) -> str:
    acceleration = "cuda-optional" if runtime_supports_cuda(runtime) else "cpu-only"
    return f"ffmpeg={runtime.ffmpeg.name} | whisper={runtime.whisper_cli.name} | model={runtime.model.name} | acceleration={acceleration}"


def format_runtime_ready_text(runtime: RuntimePaths) -> str:
    return f"内置组件已就绪：{runtime.ffmpeg.name} / {runtime.whisper_cli.name} / {runtime.model.name} / {format_runtime_acceleration_text(runtime)}"


def configure_qt_display_scaling() -> None:
    if not PYSIDE6_AVAILABLE or QGuiApplication is None:
        return
    rounding_policy = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    if rounding_policy is None:
        return
    round_value = getattr(rounding_policy, "Round", None)
    if round_value is None:
        return
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(round_value)


if PYSIDE6_AVAILABLE:
    class ResponsiveMainWindow(QMainWindow):
        def __init__(self, resize_callback=None) -> None:
            super().__init__()
            self._resize_callback = resize_callback

        def resizeEvent(self, event) -> None:  # type: ignore[override]
            super().resizeEvent(event)
            if self._resize_callback is not None:
                self._resize_callback()


class QtSubtitleToolApp:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        if not PYSIDE6_AVAILABLE:
            raise RuntimeError(f"PySide6 不可用：{PYSIDE6_IMPORT_ERROR}")

        self.runtime_dir = runtime_dir
        configure_qt_display_scaling()
        self.app = QApplication.instance() or QApplication([APP_TITLE])
        self.settings = QSettings("LearningPyramid", "SubtitleTool")
        self.window = ResponsiveMainWindow(self._handle_window_resize)
        self.window.setWindowTitle(APP_TITLE)
        self.window.resize(DEFAULT_QT_WINDOW_WIDTH, DEFAULT_QT_WINDOW_HEIGHT)
        self.window.setMinimumSize(MIN_QT_WINDOW_WIDTH, MIN_QT_WINDOW_HEIGHT)
        self._configure_theme()
        self.can_self_update = is_frozen()

        self.installed_build = load_installed_build_info()
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.process_controller = ProcessController()
        self.worker_thread: threading.Thread | None = None
        self.update_thread: threading.Thread | None = None
        self.update_busy = False
        self.available_release: UpdateRelease | None = None
        self.staged_release: UpdateRelease | None = None
        self.staged_release_dir: Path | None = None
        self.task_started_at: float | None = None
        self.current_total = 0
        self.current_progress_units = 0.0
        self.generated_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.completed_count = 0
        self.current_file_path = ""
        self.current_detail = "请选择一个视频目录。"
        self._hero_layout_stacked: bool | None = None
        self._body_layout_compact: bool | None = None
        self.project_choices: list[dict[str, str]] = []
        self.baidu_dir_items: list[dict[str, object]] = []
        self.mobile_package_server = None

        self._build_ui()
        self._load_ui_state()
        self._apply_responsive_layout(force=True)
        self._refresh_selection_summary()
        self._reset_run_metrics()
        self._refresh_runtime_summary()
        self._refresh_update_controls()
        self.app.aboutToQuit.connect(self._save_ui_state)
        self.app.aboutToQuit.connect(self._stop_mobile_package_server)

        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._poll_events)
        self.poll_timer.start(120)
        if self.can_self_update:
            QTimer.singleShot(500, self._auto_check_updates)

    def _configure_theme(self) -> None:
        self.app.setStyle("Fusion")
        self.app.setFont(QFont("Microsoft YaHei UI", 10))
        self.app.setStyleSheet(
            """
            QMainWindow {
                background: #f6f2e8;
            }
            QWidget {
                color: #1f3042;
            }
            QWidget#appRoot {
                background: #f6f2e8;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QFrame[card="true"] {
                background: #ffffff;
                border: 1px solid #e7ddd0;
                border-radius: 22px;
            }
            QFrame[cardVariant="accent"] {
                background: #fff6d8;
                border: 1px solid #f1d18a;
            }
            QFrame[metric="true"] {
                background: #fbf8ef;
                border: 1px solid #eadfcf;
                border-radius: 18px;
            }
            QFrame[summary="true"] {
                background: #f1efe7;
                border: 1px solid #e0d9cd;
                border-radius: 15px;
            }
            QLabel[role="eyebrow"] {
                color: #b36a00;
                font-size: 9pt;
                font-weight: 700;
                letter-spacing: 0.08em;
            }
            QLabel[role="heroTitle"] {
                color: #10243a;
                font-size: 24pt;
                font-weight: 800;
            }
            QLabel[role="heroLead"] {
                color: #506579;
                font-size: 11pt;
            }
            QLabel[role="bodyMuted"] {
                color: #5f7282;
                font-size: 10pt;
            }
            QLabel[role="cardTitle"] {
                color: #10243a;
                font-size: 14pt;
                font-weight: 800;
            }
            QLabel[role="cardMuted"] {
                color: #6a7a89;
                font-size: 10pt;
            }
            QLabel[role="badge"] {
                background: #f1efe7;
                color: #38506a;
                border: 1px solid #e0d9cd;
                border-radius: 15px;
                padding: 8px 14px;
                font-size: 10pt;
                font-weight: 700;
            }
            QLabel[role="summaryText"] {
                color: #38506a;
                font-size: 10pt;
                font-weight: 700;
            }
            QLabel[role="metricValue"] {
                color: #10243a;
                font-size: 20pt;
                font-weight: 800;
            }
            QLabel[role="metricLabel"] {
                color: #7d6856;
                font-size: 9pt;
            }
            QLabel[role="progressLead"] {
                color: #10243a;
                font-size: 19pt;
                font-weight: 800;
            }
            QLabel[role="detailValue"] {
                color: #10243a;
                font-size: 10.5pt;
                font-weight: 700;
            }
            QPushButton {
                border-radius: 13px;
                padding: 10px 16px;
                border: 1px solid #d9cebd;
                background: #faf6ef;
                color: #1f3042;
                font-weight: 600;
            }
            QPushButton[variant="primary"] {
                background: #f3ad1d;
                color: #2f2410;
                border: 1px solid #d89915;
            }
            QPushButton:hover {
                background: #f4ede3;
            }
            QPushButton[variant="primary"]:hover {
                background: #e39f18;
            }
            QPushButton:disabled {
                background: #f1ece5;
                border-color: #e1d7ca;
                color: #a79d91;
            }
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
                background: #fffdf9;
                border: 1px solid #d9cebd;
                border-radius: 12px;
                padding: 8px 10px;
                selection-background-color: #f3ad1d;
            }
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                background: transparent;
            }
            QProgressBar {
                border: 1px solid #eadfcf;
                border-radius: 8px;
                background: #f1e7d7;
                text-align: center;
                min-height: 18px;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background: #f3ad1d;
            }
            QCheckBox {
                spacing: 8px;
                color: #1f3042;
                font-weight: 600;
            }
            """
        )

    def _make_button(self, text: str, *, variant: str, handler) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(handler)
        return button

    def _make_label(
        self,
        text: str = "",
        *,
        role: str | None = None,
        word_wrap: bool = False,
        alignment: Qt.AlignmentFlag | Qt.Alignment | None = None,
    ) -> QLabel:
        label = QLabel(text)
        if role is not None:
            label.setProperty("role", role)
        label.setWordWrap(word_wrap)
        if alignment is not None:
            label.setAlignment(alignment)
        return label

    def _make_card(
        self,
        *,
        margins: tuple[int, int, int, int] = (20, 20, 20, 20),
        spacing: int = 14,
        variant: str | None = None,
    ) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setProperty("card", True)
        if variant:
            card.setProperty("cardVariant", variant)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        return card, layout

    def _add_card_header(self, layout: QVBoxLayout, *, eyebrow: str, title: str, description: str | None = None) -> None:
        layout.addWidget(self._make_label(eyebrow, role="eyebrow"))
        layout.addWidget(self._make_label(title, role="cardTitle"))
        if description:
            layout.addWidget(self._make_label(description, role="cardMuted", word_wrap=True))

    def _make_metric_tile(self, title: str, value: str = "0") -> tuple[QFrame, QLabel]:
        tile = QFrame()
        tile.setProperty("metric", True)
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(14, 14, 14, 14)
        tile_layout.setSpacing(4)
        value_label = self._make_label(value, role="metricValue")
        title_label = self._make_label(title, role="metricLabel")
        tile_layout.addWidget(value_label)
        tile_layout.addWidget(title_label)
        return tile, value_label

    def _make_detail_block(self, title: str, initial_value: str) -> tuple[QWidget, QLabel]:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._make_label(title, role="metricLabel"))
        value_label = self._make_label(initial_value, role="detailValue", word_wrap=True)
        layout.addWidget(value_label)
        return block, value_label

    def _make_summary_surface(self, text: str = "") -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setProperty("summary", True)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)
        label = self._make_label(text, role="summaryText", word_wrap=True)
        layout.addWidget(label)
        return frame, label

    def _rebuild_grid(self, layout: QGridLayout, widgets: list[QWidget], *, columns: int) -> None:
        while layout.count():
            layout.takeAt(0)
        for column in range(4):
            layout.setColumnStretch(column, 0)
        for index, widget in enumerate(widgets):
            layout.addWidget(widget, index // columns, index % columns)
        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _read_setting_bool(self, key: str, default: bool) -> bool:
        value = self.settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _set_status_badge(self, text: str, tone: str) -> None:
        palette = {
            "idle": ("#f1efe7", "#637384", "#e0d9cd"),
            "running": ("#fff3d6", "#aa6a00", "#f0cf8e"),
            "success": ("#e6f5e9", "#227347", "#b7debf"),
            "warning": ("#fff0e0", "#b0681a", "#e8c294"),
            "error": ("#fdebea", "#b44747", "#f0bebd"),
        }
        background, foreground, border = palette.get(tone, palette["idle"])
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(
            f"background: {background}; color: {foreground}; border: 1px solid {border}; "
            "border-radius: 14px; padding: 7px 12px; font-size: 10pt; font-weight: 700;"
        )

    def _update_metric_values(self) -> None:
        remaining = max(0, self.current_total - self.completed_count)
        self.metric_total_value.setText(str(self.current_total))
        self.metric_completed_value.setText(str(self.completed_count))
        self.metric_generated_value.setText(str(self.generated_count))
        self.metric_skipped_value.setText(str(self.skipped_count))
        self.metric_failed_value.setText(str(self.failed_count))
        self.metric_remaining_value.setText(str(remaining))

    def _update_timing_labels(self) -> None:
        if self.task_started_at is None:
            self.elapsed_value_label.setText("00:00")
            self.eta_value_label.setText("待开始")
            return

        elapsed = max(0.0, time.monotonic() - self.task_started_at)
        self.elapsed_value_label.setText(format_elapsed_short(elapsed))
        if self.current_total <= 0 or self.current_progress_units <= 0:
            self.eta_value_label.setText("估算中")
            return

        ratio = min(0.9999, max(0.0001, self.current_progress_units / float(self.current_total)))
        remaining = max(0.0, elapsed * (1.0 / ratio - 1.0))
        self.eta_value_label.setText(format_elapsed_short(remaining))

    def _refresh_source_mode_controls(self) -> None:
        project_mode = self.source_mode_combo.currentText() == SOURCE_MODE_PROJECT_BAIDU_LABEL
        self.input_dir_edit.setEnabled(not project_mode)
        self.choose_directory_button.setEnabled(not project_mode)
        for widget in (
            self.api_base_url_edit,
            self.email_edit,
            self.password_edit,
            self.project_picker_combo,
            self.load_project_choices_button,
            self.subject_id_edit,
            self.project_id_edit,
            self.baidu_account_id_edit,
            self.baidu_current_dir_edit,
            self.baidu_items_combo,
            self.baidu_import_paths_edit,
            self.load_baidu_dir_button,
            self.baidu_parent_button,
            self.baidu_enter_button,
            self.baidu_add_path_button,
        ):
            widget.setEnabled(project_mode)

    def _refresh_selection_summary(self) -> None:
        self._refresh_source_mode_controls()
        language_text = recognition_language_label(recognition_language_code_from_label(self.language_combo.currentText()))
        acceleration_text = format_selected_acceleration_text(self.enable_gpu_checkbox.isChecked())
        source_text = "扫描项目中的百度网盘视频" if self.source_mode_combo.currentText() == SOURCE_MODE_PROJECT_BAIDU_LABEL else "递归扫描本地目录"
        overwrite_text = "覆盖已有字幕" if self.overwrite_checkbox.isChecked() else "跳过已有字幕"
        threads_text = f"{int(self.threads_spin.value())} 线程"
        parts = [language_text, acceleration_text, source_text, overwrite_text, threads_text]
        if self.source_mode_combo.currentText() == SOURCE_MODE_PROJECT_BAIDU_LABEL:
            import_count = len(parse_baidu_import_paths_text(self.baidu_import_paths_edit.toPlainText()))
            if import_count > 0:
                parts.append(f"先导入 {import_count} 个网盘路径")
        summary_text = " · ".join(parts)
        self.selection_summary_label.setText(summary_text)

    def _reset_run_metrics(self) -> None:
        self.task_started_at = None
        self.current_total = 0
        self.current_progress_units = 0.0
        self.generated_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.completed_count = 0
        self.current_file_path = ""
        self.current_detail = "请选择一个视频目录。"
        self.progress_bar.setValue(0)
        self.progress_label.setText("尚未开始")
        self.status_label.setText("")
        self.status_label.hide()
        self.current_file_value_label.setText("还没有开始处理")
        self.current_file_value_label.setToolTip("")
        self.current_step_value_label.setText("等待你点击开始生成")
        self._update_metric_values()
        self._update_timing_labels()
        self._set_status_badge("待开始", "idle")
        self._set_run_overview_active(False)

    def _record_log_counters(self, text: str) -> None:
        if re.match(r"^\[\d+/\d+\]\s+已生成\s+", text):
            self.generated_count += 1
        elif re.match(r"^\[\d+/\d+\]\s+跳过\s+", text):
            self.skipped_count += 1
        elif re.match(r"^\[\d+/\d+\]\s+失败\s+", text):
            self.failed_count += 1
        self._update_metric_values()

    def _load_ui_state(self) -> None:
        width = max(MIN_QT_WINDOW_WIDTH, int(self.settings.value("ui/width", DEFAULT_QT_WINDOW_WIDTH)))
        height = max(MIN_QT_WINDOW_HEIGHT, int(self.settings.value("ui/height", DEFAULT_QT_WINDOW_HEIGHT)))
        self.window.resize(width, height)
        self.source_mode_combo.setCurrentText(str(self.settings.value("form/sourceMode", SOURCE_MODE_LOCAL_LABEL)) or SOURCE_MODE_LOCAL_LABEL)
        self.input_dir_edit.setText(str(self.settings.value("form/inputDir", "")))
        self.api_base_url_edit.setText(str(self.settings.value("form/apiBaseUrl", "")))
        self.email_edit.setText(str(self.settings.value("form/email", "")))
        self.subject_id_edit.setText(str(self.settings.value("form/subjectId", "")))
        self.project_id_edit.setText(str(self.settings.value("form/projectId", "")))
        self.baidu_account_id_edit.setText(str(self.settings.value("form/baiduAccountId", "")))
        self.baidu_current_dir_edit.setText(str(self.settings.value("form/baiduCurrentDir", "/")) or "/")
        self.baidu_import_paths_edit.setPlainText(str(self.settings.value("form/baiduImportPaths", "")))
        self.overwrite_checkbox.setChecked(self._read_setting_bool("form/overwrite", False))
        self.threads_spin.setValue(max(1, min(16, int(self.settings.value("form/threads", default_threads())))))
        self.enable_gpu_checkbox.setChecked(self._read_setting_bool("form/gpu", False))
        saved_language = normalize_recognition_language(self.settings.value("form/language", DEFAULT_RECOGNITION_LANGUAGE))
        self.language_combo.setCurrentText(recognition_language_label(saved_language))
        self._set_log_visible(self._read_setting_bool("ui/logVisible", False))

    def _handle_window_resize(self) -> None:
        if not hasattr(self, "hero_row") or not hasattr(self, "body_layout"):
            return
        self._apply_responsive_layout()

    def _apply_responsive_layout(self, *, force: bool = False) -> None:
        stacked_hero = self.window.width() < LAYOUT_BREAKPOINT_STACK
        compact_body = self.window.width() < LAYOUT_BREAKPOINT_COMPACT

        if force or self._hero_layout_stacked != stacked_hero:
            self.hero_row.setDirection(
                QBoxLayout.Direction.TopToBottom if stacked_hero else QBoxLayout.Direction.LeftToRight
            )
            self.hero_row.setAlignment(
                self.update_button,
                (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                if stacked_hero
                else (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            )
            self._hero_layout_stacked = stacked_hero

        if force or self._body_layout_compact != compact_body:
            self.body_layout.setDirection(
                QBoxLayout.Direction.TopToBottom if compact_body else QBoxLayout.Direction.LeftToRight
            )
            self.body_layout.setStretch(0, 5 if compact_body else 7)
            self.body_layout.setStretch(1, 4 if compact_body else 4)
            self.left_layout.setContentsMargins(0, 0, 0 if compact_body else 6, 0)
            self.right_scroll.setMinimumWidth(0 if compact_body else RIGHT_COLUMN_MIN_WIDTH)
            self.right_scroll.setMaximumWidth(QT_UNBOUNDED_MAX_WIDTH if compact_body else RIGHT_COLUMN_MAX_WIDTH)
            self._rebuild_grid(self.details_grid, self.detail_blocks, columns=1 if compact_body else 2)
            self._rebuild_grid(self.metrics_grid, self.metric_tiles, columns=2)
            self._body_layout_compact = compact_body

    def _save_ui_state(self) -> None:
        self.settings.setValue("ui/width", self.window.width())
        self.settings.setValue("ui/height", self.window.height())
        self.settings.setValue("ui/logVisible", self.log_card.isVisible())
        self.settings.setValue("form/sourceMode", self.source_mode_combo.currentText())
        self.settings.setValue("form/inputDir", self.input_dir_edit.text().strip())
        self.settings.setValue("form/apiBaseUrl", self.api_base_url_edit.text().strip())
        self.settings.setValue("form/email", self.email_edit.text().strip())
        self.settings.setValue("form/subjectId", self.subject_id_edit.text().strip())
        self.settings.setValue("form/projectId", self.project_id_edit.text().strip())
        self.settings.setValue("form/baiduAccountId", self.baidu_account_id_edit.text().strip())
        self.settings.setValue("form/baiduCurrentDir", self.baidu_current_dir_edit.text().strip())
        self.settings.setValue("form/baiduImportPaths", self.baidu_import_paths_edit.toPlainText().strip())
        self.settings.setValue("form/overwrite", self.overwrite_checkbox.isChecked())
        self.settings.setValue("form/threads", self.threads_spin.value())
        self.settings.setValue("form/gpu", self.enable_gpu_checkbox.isChecked())
        self.settings.setValue("form/language", recognition_language_code_from_label(self.language_combo.currentText()))
        self.settings.sync()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        self.window.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(22, 22, 22, 22)
        shell.setSpacing(18)
        self.shell = shell

        hero_card, hero_layout = self._make_card(margins=(20, 18, 20, 18), spacing=10, variant="accent")
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(14)
        self.hero_row = hero_row

        hero_copy = QWidget()
        hero_copy_layout = QVBoxLayout(hero_copy)
        hero_copy_layout.setContentsMargins(0, 0, 0, 0)
        hero_copy_layout.setSpacing(6)
        hero_copy_layout.addWidget(self._make_label("OFFLINE SUBTITLE", role="eyebrow"))
        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(10)
        title_row_layout.addWidget(self._make_label(APP_TITLE, role="heroTitle"))
        self.version_label = self._make_label(f"{self.installed_build.version}", role="badge")
        title_row_layout.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row_layout.addStretch(1)
        hero_copy_layout.addWidget(title_row)
        hero_row.addWidget(hero_copy, 1)

        self.update_button = self._make_button("检查更新", variant="secondary", handler=self._handle_update_action)
        hero_row.addWidget(self.update_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        if not self.can_self_update:
            self.update_button.hide()
        hero_layout.addLayout(hero_row)
        selection_summary_frame, self.selection_summary_label = self._make_summary_surface("")
        hero_layout.addWidget(selection_summary_frame)
        shell.addWidget(hero_card)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(18)
        self.body_layout = body_layout
        shell.addWidget(body, 1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_container = QWidget()
        left_scroll.setWidget(left_container)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(16)
        self.left_layout = left_layout
        body_layout.addWidget(left_scroll, 7)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setMinimumWidth(RIGHT_COLUMN_MIN_WIDTH)
        right_scroll.setMaximumWidth(RIGHT_COLUMN_MAX_WIDTH)
        self.right_scroll = right_scroll
        body_layout.addWidget(right_scroll, 4)

        right_column = QWidget()
        self.right_column = right_column
        right_scroll.setWidget(right_column)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        workspace_card, workspace_layout = self._make_card()
        self._add_card_header(
            workspace_layout,
            eyebrow="工作区",
            title="选择来源",
        )
        directory_layout = QGridLayout()
        directory_layout.setHorizontalSpacing(12)
        directory_layout.setVerticalSpacing(10)
        directory_layout.addWidget(self._make_label("来源", role="metricLabel"), 0, 0)
        self.source_mode_combo = QComboBox()
        self.source_mode_combo.addItems([SOURCE_MODE_LOCAL_LABEL, SOURCE_MODE_PROJECT_BAIDU_LABEL])
        directory_layout.addWidget(self.source_mode_combo, 0, 1)
        directory_layout.addWidget(self._make_label("视频目录", role="metricLabel"), 1, 0)
        self.input_dir_edit = QLineEdit()
        self.input_dir_edit.setPlaceholderText("选择要批量生成字幕的视频目录")
        directory_layout.addWidget(self.input_dir_edit, 1, 1)
        self.choose_directory_button = self._make_button("选择目录", variant="secondary", handler=self._choose_directory)
        directory_layout.addWidget(self.choose_directory_button, 1, 2)
        directory_layout.addWidget(self._make_label("API 地址", role="metricLabel"), 2, 0)
        self.api_base_url_edit = QLineEdit()
        self.api_base_url_edit.setPlaceholderText("https://plm.xuebao.chat/api")
        directory_layout.addWidget(self.api_base_url_edit, 2, 1, 1, 2)
        directory_layout.addWidget(self._make_label("邮箱", role="metricLabel"), 3, 0)
        self.email_edit = QLineEdit()
        directory_layout.addWidget(self.email_edit, 3, 1, 1, 2)
        directory_layout.addWidget(self._make_label("密码", role="metricLabel"), 4, 0)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        directory_layout.addWidget(self.password_edit, 4, 1, 1, 2)
        directory_layout.addWidget(self._make_label("项目选择", role="metricLabel"), 5, 0)
        self.project_picker_combo = QComboBox()
        directory_layout.addWidget(self.project_picker_combo, 5, 1)
        self.load_project_choices_button = self._make_button("加载项目", variant="secondary", handler=self._load_project_choices)
        directory_layout.addWidget(self.load_project_choices_button, 5, 2)
        directory_layout.addWidget(self._make_label("学科 ID", role="metricLabel"), 6, 0)
        self.subject_id_edit = QLineEdit()
        self.subject_id_edit.setPlaceholderText("例如 subj_000001")
        directory_layout.addWidget(self.subject_id_edit, 6, 1, 1, 2)
        directory_layout.addWidget(self._make_label("项目 ID", role="metricLabel"), 7, 0)
        self.project_id_edit = QLineEdit()
        self.project_id_edit.setPlaceholderText("例如 proj_000001")
        directory_layout.addWidget(self.project_id_edit, 7, 1, 1, 2)
        directory_layout.addWidget(self._make_label("网盘账号", role="metricLabel"), 8, 0)
        self.baidu_account_id_edit = QLineEdit()
        self.baidu_account_id_edit.setPlaceholderText("可留空；只有一个已绑定账号时会自动使用")
        directory_layout.addWidget(self.baidu_account_id_edit, 8, 1, 1, 2)
        directory_layout.addWidget(self._make_label("当前目录", role="metricLabel"), 9, 0)
        self.baidu_current_dir_edit = QLineEdit()
        self.baidu_current_dir_edit.setPlaceholderText("/")
        directory_layout.addWidget(self.baidu_current_dir_edit, 9, 1)
        self.load_baidu_dir_button = self._make_button("读取目录", variant="secondary", handler=self._load_baidu_dir_items)
        directory_layout.addWidget(self.load_baidu_dir_button, 9, 2)
        directory_layout.addWidget(self._make_label("目录项目", role="metricLabel"), 10, 0)
        self.baidu_items_combo = QComboBox()
        directory_layout.addWidget(self.baidu_items_combo, 10, 1)
        baidu_item_actions = QWidget()
        baidu_item_actions_layout = QHBoxLayout(baidu_item_actions)
        baidu_item_actions_layout.setContentsMargins(0, 0, 0, 0)
        baidu_item_actions_layout.setSpacing(8)
        self.baidu_parent_button = self._make_button("上级", variant="secondary", handler=self._load_baidu_parent_dir)
        self.baidu_enter_button = self._make_button("进入", variant="secondary", handler=self._enter_selected_baidu_dir)
        self.baidu_add_path_button = self._make_button("添加", variant="secondary", handler=self._add_selected_baidu_import_path)
        baidu_item_actions_layout.addWidget(self.baidu_parent_button)
        baidu_item_actions_layout.addWidget(self.baidu_enter_button)
        baidu_item_actions_layout.addWidget(self.baidu_add_path_button)
        directory_layout.addWidget(baidu_item_actions, 10, 2)
        directory_layout.addWidget(self._make_label("导入路径", role="metricLabel"), 11, 0)
        self.baidu_import_paths_edit = QPlainTextEdit()
        self.baidu_import_paths_edit.setPlaceholderText("一行一个百度网盘目录或视频路径；会先导入当前项目再生成字幕")
        self.baidu_import_paths_edit.setMinimumHeight(76)
        self.baidu_import_paths_edit.setMaximumHeight(120)
        directory_layout.addWidget(self.baidu_import_paths_edit, 11, 1, 1, 2)
        directory_layout.setColumnStretch(1, 1)
        workspace_layout.addLayout(directory_layout)
        left_layout.addWidget(workspace_card)

        recognition_card, recognition_layout = self._make_card()
        self._add_card_header(
            recognition_layout,
            eyebrow="识别",
            title="识别偏好",
        )
        language_row = QWidget()
        language_row_layout = QGridLayout(language_row)
        language_row_layout.setContentsMargins(0, 0, 0, 0)
        language_row_layout.setHorizontalSpacing(12)
        language_row_layout.setVerticalSpacing(6)
        language_row_layout.addWidget(self._make_label("识别语言", role="metricLabel"), 0, 0)
        self.language_combo = QComboBox()
        self.language_combo.addItems(list(RECOGNITION_LANGUAGE_LABELS.values()))
        self.language_combo.setCurrentText(recognition_language_label(DEFAULT_RECOGNITION_LANGUAGE))
        self.language_combo.setMinimumWidth(180)
        language_row_layout.addWidget(self.language_combo, 0, 1)
        language_row_layout.addWidget(self._make_label("线程数", role="metricLabel"), 0, 2)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 16)
        self.threads_spin.setValue(default_threads())
        self.threads_spin.setMinimumWidth(92)
        language_row_layout.addWidget(self.threads_spin, 0, 3)
        language_row_layout.setColumnStretch(1, 1)
        recognition_layout.addWidget(language_row)
        gpu_row = QWidget()
        gpu_layout = QHBoxLayout(gpu_row)
        gpu_layout.setContentsMargins(0, 0, 0, 0)
        gpu_layout.setSpacing(18)
        self.enable_gpu_checkbox = QCheckBox("启用 GPU 模式")
        gpu_layout.addWidget(self.enable_gpu_checkbox)
        self.overwrite_checkbox = QCheckBox("覆盖已有 .srt")
        gpu_layout.addWidget(self.overwrite_checkbox)
        gpu_layout.addStretch(1)
        recognition_layout.addWidget(gpu_row)
        self.gpu_hint_label = self._make_label(
            "当前工具包未包含 CUDA backend，将继续使用 CPU 识别。",
            role="cardMuted",
            word_wrap=True,
        )
        recognition_layout.addWidget(self.gpu_hint_label)
        left_layout.addWidget(recognition_card)
        left_layout.addStretch(1)

        overview_card, overview_layout = self._make_card(spacing=12)
        overview_header = QWidget()
        overview_header_layout = QHBoxLayout(overview_header)
        overview_header_layout.setContentsMargins(0, 0, 0, 0)
        overview_header_layout.setSpacing(10)
        header_copy = QWidget()
        header_copy_layout = QVBoxLayout(header_copy)
        header_copy_layout.setContentsMargins(0, 0, 0, 0)
        header_copy_layout.setSpacing(4)
        header_copy_layout.addWidget(self._make_label("任务状态", role="eyebrow"))
        header_copy_layout.addWidget(self._make_label("本次生成", role="cardTitle"))
        overview_header_layout.addWidget(header_copy, 1)
        self.state_badge = self._make_label("待开始", role="badge")
        overview_header_layout.addWidget(self.state_badge, 0, Qt.AlignmentFlag.AlignTop)
        overview_layout.addWidget(overview_header)

        self.progress_label = self._make_label("尚未开始", role="progressLead")
        overview_layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        overview_layout.addWidget(self.progress_bar)
        self.status_label = self._make_label("", role="cardMuted", word_wrap=True)
        overview_layout.addWidget(self.status_label)

        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(12)
        details_grid.setVerticalSpacing(12)
        self.details_grid = details_grid
        current_file_block, self.current_file_value_label = self._make_detail_block("当前文件", "还没有开始处理")
        current_step_block, self.current_step_value_label = self._make_detail_block("最近步骤", "等待你点击开始生成")
        elapsed_block, self.elapsed_value_label = self._make_detail_block("已用时间", "00:00")
        eta_block, self.eta_value_label = self._make_detail_block("预计剩余", "待开始")
        self.timing_detail_blocks = [elapsed_block, eta_block]
        self.detail_blocks = [current_file_block, current_step_block, elapsed_block, eta_block]
        self._rebuild_grid(self.details_grid, self.detail_blocks, columns=2)
        overview_layout.addLayout(details_grid)
        right_layout.addWidget(overview_card)

        metrics_card, metrics_layout = self._make_card(spacing=12)
        self.metrics_card = metrics_card
        self._add_card_header(metrics_layout, eyebrow="任务计数", title="处理概览")
        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)
        self.metrics_grid = metrics_grid
        total_tile, self.metric_total_value = self._make_metric_tile("总视频")
        completed_tile, self.metric_completed_value = self._make_metric_tile("已完成")
        generated_tile, self.metric_generated_value = self._make_metric_tile("已生成")
        skipped_tile, self.metric_skipped_value = self._make_metric_tile("已跳过")
        failed_tile, self.metric_failed_value = self._make_metric_tile("失败数")
        remaining_tile, self.metric_remaining_value = self._make_metric_tile("剩余")
        self.metric_tiles = [total_tile, completed_tile, generated_tile, skipped_tile, failed_tile, remaining_tile]
        self._rebuild_grid(self.metrics_grid, self.metric_tiles, columns=2)
        metrics_layout.addLayout(metrics_grid)
        right_layout.addWidget(metrics_card)

        self.log_card, log_layout = self._make_card(spacing=12)
        self._add_card_header(
            log_layout,
            eyebrow="日志",
            title="处理日志",
        )
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(220)
        self.log_text.document().setMaximumBlockCount(800)
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(self.log_card)
        right_layout.addStretch(1)

        footer_card, footer_layout = self._make_card(margins=(16, 16, 16, 16), spacing=0)
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(12)
        footer_row.addStretch(1)
        self.log_toggle_button = self._make_button("查看日志", variant="secondary", handler=self._toggle_log_visibility)
        self.cancel_button = self._make_button("取消", variant="secondary", handler=self._cancel)
        self.cancel_button.setEnabled(False)
        self.mobile_import_button = self._make_button("导入到手机", variant="secondary", handler=self._start_mobile_import)
        self.start_button = self._make_button("开始生成", variant="primary", handler=self._start)
        footer_row.addWidget(self.log_toggle_button)
        footer_row.addWidget(self.cancel_button)
        footer_row.addWidget(self.mobile_import_button)
        footer_row.addWidget(self.start_button)
        footer_layout.addLayout(footer_row)
        shell.addWidget(footer_card)

        self.source_mode_combo.currentTextChanged.connect(self._refresh_selection_summary)
        self.input_dir_edit.textChanged.connect(self._refresh_selection_summary)
        self.overwrite_checkbox.toggled.connect(self._refresh_selection_summary)
        self.enable_gpu_checkbox.toggled.connect(self._refresh_selection_summary)
        self.language_combo.currentTextChanged.connect(self._refresh_selection_summary)
        self.threads_spin.valueChanged.connect(self._refresh_selection_summary)
        self.baidu_import_paths_edit.textChanged.connect(self._refresh_selection_summary)
        self.project_picker_combo.currentIndexChanged.connect(self._apply_selected_project_choice)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self.window, APP_TITLE, message)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self.window, APP_TITLE, message)

    def _ask_yes_no(self, message: str) -> bool:
        result = QMessageBox.question(
            self.window,
            APP_TITLE,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return result == QMessageBox.StandardButton.Yes

    def _set_advanced_visible(self, visible: bool) -> None:
        return

    def _toggle_advanced_visibility(self) -> None:
        return

    def _set_log_visible(self, visible: bool) -> None:
        self.log_card.setVisible(visible)
        self.log_toggle_button.setText("收起日志" if visible else "查看日志")

    def _toggle_log_visibility(self) -> None:
        self._set_log_visible(not self.log_card.isVisible())

    def _set_update_status(self, message: str) -> None:
        return

    def _set_run_overview_active(self, active: bool) -> None:
        self.metrics_card.setVisible(active)
        for widget in self.timing_detail_blocks:
            widget.setVisible(active)

    def _refresh_update_controls(self) -> None:
        if not self.can_self_update:
            self.update_button.setEnabled(False)
            return

        if self.update_busy:
            self.update_button.setEnabled(False)
            self.update_button.setText("更新中...")
            return

        self.update_button.setEnabled(True)
        if self.staged_release is not None and self.staged_release_dir is not None:
            self.update_button.setText(f"安装 {self.staged_release.version}")
            return
        if self.available_release is not None and is_release_newer_than_installed(self.available_release, self.installed_build):
            self.update_button.setText(f"更新到 {self.available_release.version}")
            return
        self.update_button.setText("检查更新")

    def _set_update_busy(self, busy: bool) -> None:
        self.update_busy = busy
        self._refresh_update_controls()

    def _auto_check_updates(self) -> None:
        self._check_for_updates(manual=False)

    def _check_for_updates(self, *, manual: bool) -> None:
        if not self.can_self_update:
            return
        if self.update_thread is not None and self.update_thread.is_alive():
            return
        self._set_update_busy(True)
        self._set_update_status("正在检查更新...")
        self.update_thread = threading.Thread(target=self._run_update_check, args=(manual,), daemon=True)
        self.update_thread.start()

    def _run_update_check(self, manual: bool) -> None:
        try:
            release = fetch_latest_release(load_update_config())
            if release is not None and is_release_newer_than_installed(release, self.installed_build):
                self.event_queue.put(("update_available", (release, manual)))
                return
            self.event_queue.put(("update_none", manual))
        except Exception as exc:
            self.event_queue.put(("update_error", (str(exc), manual)))

    def _handle_update_action(self) -> None:
        if not self.can_self_update:
            self._show_info(SOURCE_MODE_UPDATE_MESSAGE)
            return
        if self.update_busy:
            return
        if self.staged_release is not None and self.staged_release_dir is not None:
            self._install_staged_update()
            return
        if self.available_release is not None and is_release_newer_than_installed(self.available_release, self.installed_build):
            if self.worker_thread is not None and self.worker_thread.is_alive():
                self._show_info("请先等当前字幕任务完成，再安装更新。")
                return
            if not is_frozen():
                self._show_info("源码运行模式下不支持一键更新，请使用打包后的 EXE。")
                return
            detail = f"发现新版本 {self.available_release.version}"
            if self.available_release.size_bytes > 0:
                detail += f"（约 {format_bytes(self.available_release.size_bytes)}）"
            if not self._ask_yes_no(f"{detail}\n\n是否现在下载并准备安装？"):
                return
            self._start_download_update(self.available_release)
            return
        self._check_for_updates(manual=True)

    def _start_download_update(self, release: UpdateRelease) -> None:
        if self.update_thread is not None and self.update_thread.is_alive():
            return
        self._set_update_busy(True)
        self._set_update_status(f"正在下载 {release.version}...")
        self.update_thread = threading.Thread(target=self._run_download_update, args=(release,), daemon=True)
        self.update_thread.start()

    def _run_download_update(self, release: UpdateRelease) -> None:
        try:
            zip_path = download_release_zip(
                release,
                on_progress=lambda downloaded, total: self.event_queue.put(("update_download_progress", (release, downloaded, total))),
            )
            self.event_queue.put(("update_extracting", release.version))
            bundle_dir = extract_release_bundle(zip_path)
            self.event_queue.put(("update_staged", (release, str(bundle_dir))))
        except Exception as exc:
            self.event_queue.put(("update_error", (str(exc), True)))

    def _install_staged_update(self) -> None:
        if self.staged_release is None or self.staged_release_dir is None:
            return
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self._show_info("请先等当前字幕任务完成，再安装更新。")
            return
        if not is_frozen():
            self._show_info("源码运行模式下不支持一键更新，请使用打包后的 EXE。")
            return
        if not self.staged_release_dir.exists():
            self.staged_release = None
            self.staged_release_dir = None
            self._set_update_status("更新包已失效，请重新检查更新。")
            self._refresh_update_controls()
            return
        if not self._ask_yes_no(f"将安装 {self.staged_release.version}，程序会自动关闭并重新启动。\n\n是否继续？"):
            return

        script_path = create_windows_update_script(source_dir=self.staged_release_dir, target_dir=executable_dir())
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-WaitPid",
                str(os.getpid()),
                "-SourceDir",
                str(self.staged_release_dir),
                "-TargetDir",
                str(executable_dir()),
                "-ExeName",
                f"{TOOL_EXE_BASENAME}.exe",
            ],
            creationflags=creationflags,
        )
        QTimer.singleShot(120, self.window.close)

    def _choose_directory(self) -> None:
        initial_dir = self.input_dir_edit.text().strip() or str(executable_dir())
        selected = QFileDialog.getExistingDirectory(self.window, "选择要生成字幕的视频目录", initial_dir)
        if selected:
            self.input_dir_edit.setText(selected)

    def _make_project_client_from_form(self) -> LearningPyramidProjectClient:
        api_base_url = normalize_learningpyramid_api_base_url(self.api_base_url_edit.text().strip())
        email = self.email_edit.text().strip()
        password = self.password_edit.text()
        if not email:
            raise ValueError("请填写 LearningPyramid 登录邮箱。")
        if not password:
            raise ValueError("请填写 LearningPyramid 密码。")
        client = LearningPyramidProjectClient(api_base_url)
        client.login(email=email, password=password)
        return client

    def _current_project_ids_from_form(self) -> tuple[str, str]:
        subject_id = self.subject_id_edit.text().strip()
        scoped_project_id = self.project_id_edit.text().strip()
        if not subject_id:
            raise ValueError("请填写学科 ID。")
        if not scoped_project_id:
            raise ValueError("请填写项目 ID。")
        return subject_id, scoped_project_id

    def _current_baidu_account_id(self, client: object) -> str:
        account_id = _resolve_single_baidu_account_id(client, self.baidu_account_id_edit.text().strip() or None)
        if not self.baidu_account_id_edit.text().strip():
            self.baidu_account_id_edit.setText(account_id)
        return account_id

    def _load_project_choices(self) -> None:
        try:
            client = self._make_project_client_from_form()
            subjects = client.list_subjects()
            if not isinstance(subjects, list):
                raise RuntimeError("LearningPyramid 学科响应无效。")
            choices: list[dict[str, str]] = []
            for subject in subjects:
                if not isinstance(subject, dict):
                    continue
                subject_id = str(subject.get("subjectId") or "").strip()
                if not subject_id:
                    continue
                subject_title = str(subject.get("title") or subject_id).strip()
                materials = client.list_subject_materials(subject_id)
                if not isinstance(materials, list):
                    raise RuntimeError(f"LearningPyramid 项目响应无效：{subject_title}")
                for material in materials:
                    if not isinstance(material, dict):
                        continue
                    scoped_project_id = str(material.get("scopedProjectId") or "").strip()
                    if not scoped_project_id:
                        continue
                    material_title = str(material.get("title") or scoped_project_id).strip()
                    choices.append(
                        {
                            "subjectId": subject_id,
                            "scopedProjectId": scoped_project_id,
                            "label": f"{subject_title} / {material_title}",
                        }
                    )
            self.project_picker_combo.clear()
            self.project_choices = choices
            for choice in choices:
                self.project_picker_combo.addItem(choice["label"], choice)
            if choices:
                self.project_picker_combo.setCurrentIndex(0)
                self._apply_selected_project_choice()
            self._append_log(f"已加载 {len(choices)} 个项目。")
        except Exception as exc:
            self._show_error(str(exc))

    def _apply_selected_project_choice(self, *_args) -> None:
        choice = self.project_picker_combo.currentData()
        if not isinstance(choice, dict):
            return
        subject_id = str(choice.get("subjectId") or "").strip()
        scoped_project_id = str(choice.get("scopedProjectId") or "").strip()
        if subject_id:
            self.subject_id_edit.setText(subject_id)
        if scoped_project_id:
            self.project_id_edit.setText(scoped_project_id)

    def _load_baidu_dir_items(self) -> None:
        try:
            subject_id, scoped_project_id = self._current_project_ids_from_form()
            client = self._make_project_client_from_form()
            account_id = self._current_baidu_account_id(client)
            dir_path = normalize_baidu_remote_path(self.baidu_current_dir_edit.text().strip() or "/")
            payload = client.list_project_baidu_netdisk_files(
                subject_id,
                scoped_project_id,
                account_id,
                dir_path=dir_path,
                page=1,
            )
            if not isinstance(payload, dict):
                raise RuntimeError("百度网盘目录响应无效。")
            rows = payload.get("items")
            items = [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []
            items.sort(key=lambda item: (0 if bool(item.get("isDir")) else 1, str(item.get("name") or item.get("path") or "")))
            self.baidu_items_combo.clear()
            self.baidu_dir_items = items
            for item in items:
                name = str(item.get("name") or item.get("path") or "").strip() or "未命名"
                kind = "目录" if bool(item.get("isDir")) else ("视频" if _is_baidu_netdisk_video_item(item) else "文件")
                self.baidu_items_combo.addItem(f"[{kind}] {name}", item)
            self.baidu_current_dir_edit.setText(dir_path)
            self._append_log(f"已读取百度网盘目录：{dir_path}，{len(items)} 项。")
        except Exception as exc:
            self._show_error(str(exc))

    def _selected_baidu_item(self) -> dict[str, object] | None:
        item = self.baidu_items_combo.currentData()
        return item if isinstance(item, dict) else None

    def _load_baidu_parent_dir(self) -> None:
        current_dir = self.baidu_current_dir_edit.text().strip() or "/"
        parent = _baidu_remote_parent_dir(current_dir)
        self.baidu_current_dir_edit.setText(parent)
        self._load_baidu_dir_items()

    def _enter_selected_baidu_dir(self) -> None:
        item = self._selected_baidu_item()
        if item is None:
            return
        if not bool(item.get("isDir")):
            self._show_error("只能进入目录。")
            return
        self.baidu_current_dir_edit.setText(normalize_baidu_remote_path(str(item.get("path") or "")))
        self._load_baidu_dir_items()

    def _add_selected_baidu_import_path(self) -> None:
        item = self._selected_baidu_item()
        if item is None:
            return
        if not _is_baidu_netdisk_importable_item(item):
            self._show_error("只能添加目录或视频文件。")
            return
        selected_path = normalize_baidu_remote_path(str(item.get("path") or ""))
        current_paths = list(parse_baidu_import_paths_text(self.baidu_import_paths_edit.toPlainText()))
        if selected_path not in current_paths:
            current_paths.append(selected_path)
        self.baidu_import_paths_edit.setPlainText("\n".join(current_paths))
        self._refresh_selection_summary()

    def _sync_gpu_controls(self, runtime: RuntimePaths | None) -> None:
        if runtime is not None and runtime_supports_cuda(runtime):
            detected_devices = detect_cuda_device_count(runtime)
            if detected_devices is not None and detected_devices > 0:
                self.enable_gpu_checkbox.setEnabled(True)
                self.gpu_hint_label.setText(f"已检测到 {detected_devices} 个可用 NVIDIA GPU；勾选后会尝试使用 GPU 提高识别速度。")
                return

            self.enable_gpu_checkbox.setChecked(False)
            self.enable_gpu_checkbox.setEnabled(False)
            self.gpu_hint_label.setText("工具包已包含 CUDA backend，但当前电脑没有检测到可用的 NVIDIA GPU 或驱动，将继续使用 CPU 识别。")
            return

        self.enable_gpu_checkbox.setChecked(False)
        self.enable_gpu_checkbox.setEnabled(False)
        self.gpu_hint_label.setText("当前工具包未包含 CUDA backend，将继续使用 CPU 识别。")

    def _refresh_runtime_summary(self) -> None:
        try:
            runtime = discover_runtime_paths(self.runtime_dir)
        except Exception as exc:
            self._sync_gpu_controls(None)
            self._refresh_selection_summary()
            return
        self._sync_gpu_controls(runtime)
        self._refresh_selection_summary()

    def _stop_mobile_package_server(self) -> None:
        server = self.mobile_package_server
        if server is None:
            return
        self.mobile_package_server = None
        server.stop()

    def _start_mobile_import(self) -> None:
        if self.source_mode_combo.currentText() == SOURCE_MODE_PROJECT_BAIDU_LABEL:
            self._show_error("请先切换到本地目录模式，并选择本地视频目录。")
            return
        input_dir_text = self.input_dir_edit.text().strip()
        if not input_dir_text:
            self._show_error("请先选择一个视频目录。")
            return
        try:
            input_dir = Path(input_dir_text).expanduser().resolve()
            session = build_mobile_package_session(
                MobilePackageOptions(
                    input_dir=input_dir,
                    title=input_dir.name,
                    subject_id=self.subject_id_edit.text().strip(),
                    scoped_project_id=self.project_id_edit.text().strip(),
                )
            )
            self._stop_mobile_package_server()
            self.mobile_package_server = start_offline_course_package_server(session)
        except Exception as exc:
            self._show_error(str(exc))
            return
        assert self.mobile_package_server is not None
        message = format_mobile_package_connection_message(session, self.mobile_package_server.base_url)
        self._append_log("已启动手机导入临时服务。")
        self._append_log(message)
        self._show_info(message)

    def _start(self) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return

        try:
            runtime = discover_runtime_paths(self.runtime_dir)
        except Exception as exc:
            self._show_error(str(exc))
            return

        project_mode = self.source_mode_combo.currentText() == SOURCE_MODE_PROJECT_BAIDU_LABEL
        if project_mode:
            try:
                options: BatchOptions | ProjectBaiduBatchOptions = ProjectBaiduBatchOptions(
                    api_base_url=normalize_learningpyramid_api_base_url(self.api_base_url_edit.text().strip()),
                    email=self.email_edit.text().strip(),
                    password=self.password_edit.text(),
                    subject_id=self.subject_id_edit.text().strip(),
                    scoped_project_id=self.project_id_edit.text().strip(),
                    overwrite=self.overwrite_checkbox.isChecked(),
                    threads=max(1, int(self.threads_spin.value() or 1)),
                    enable_gpu=self.enable_gpu_checkbox.isChecked(),
                    language=recognition_language_code_from_label(self.language_combo.currentText()),
                    baidu_account_id=self.baidu_account_id_edit.text().strip() or None,
                    baidu_import_paths=parse_baidu_import_paths_text(self.baidu_import_paths_edit.toPlainText()),
                )
                _validate_project_baidu_options(options)
            except Exception as exc:
                self._show_error(str(exc))
                return
            task_label = f"{options.subject_id}/{options.scoped_project_id}"
            preparing_text = "准备扫描项目网盘视频..."
            status_text = (
                f"正在扫描项目中的百度网盘视频并准备逐个生成字幕"
                f"（{format_selected_acceleration_text(options.enable_gpu)} / {recognition_language_label(options.language)}）。"
            )
        else:
            input_dir_text = self.input_dir_edit.text().strip()
            if not input_dir_text:
                self._show_error("请先选择一个视频目录。")
                return
            input_dir = Path(input_dir_text).expanduser()
            options = BatchOptions(
                input_dir=input_dir,
                recursive=True,
                overwrite=self.overwrite_checkbox.isChecked(),
                threads=max(1, int(self.threads_spin.value() or 1)),
                enable_gpu=self.enable_gpu_checkbox.isChecked(),
                language=recognition_language_code_from_label(self.language_combo.currentText()),
            )
            task_label = str(options.input_dir)
            preparing_text = "准备扫描目录..."
            status_text = (
                f"正在扫描目录并准备逐个生成字幕（{format_selected_acceleration_text(options.enable_gpu)} / {recognition_language_label(options.language)}）。"
            )
        if options.enable_gpu and not runtime_supports_cuda(runtime):
            self._show_error("当前工具包未包含 CUDA backend，暂时不能启用 GPU 模式。")
            return

        self._append_log("")
        self._append_log(f"开始任务：{task_label}")
        self._append_log(print_runtime_summary(runtime))
        self._append_log(f"识别模式：{format_selected_acceleration_text(options.enable_gpu)}")
        self._append_log(f"识别语言：{recognition_language_label(options.language)}")

        self.cancel_event.clear()
        self.task_started_at = time.monotonic()
        self.current_total = 0
        self.current_progress_units = 0.0
        self.generated_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.completed_count = 0
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(preparing_text)
        self.status_label.setText(status_text)
        self.status_label.show()
        self.current_file_value_label.setText(preparing_text)
        self.current_file_value_label.setToolTip("")
        self.current_step_value_label.setText("准备任务队列")
        self._set_run_overview_active(True)
        self._update_metric_values()
        self._update_timing_labels()
        self._set_status_badge("进行中", "running")

        self.worker_thread = threading.Thread(target=self._run_worker, args=(options, runtime), daemon=True)
        self.worker_thread.start()

    def _run_worker(self, options: BatchOptions | ProjectBaiduBatchOptions, runtime: RuntimePaths) -> None:
        try:
            if isinstance(options, ProjectBaiduBatchOptions):
                summary = run_project_baidu_batch(
                    options,
                    runtime,
                    log=lambda text: self.event_queue.put(("log", text)),
                    progress=lambda done, total, video, detail: self.event_queue.put(("progress", (done, total, str(video), detail))),
                    cancel_event=self.cancel_event,
                    process_controller=self.process_controller,
                )
            else:
                summary = run_batch(
                    options,
                    runtime,
                    log=lambda text: self.event_queue.put(("log", text)),
                    progress=lambda done, total, video, detail: self.event_queue.put(("progress", (done, total, str(video), detail))),
                    cancel_event=self.cancel_event,
                    process_controller=self.process_controller,
                )
            self.event_queue.put(("done", summary))
        except CancelledError as exc:
            self.event_queue.put(("cancelled", str(exc)))
        except Exception as exc:
            self.event_queue.put(("error", str(exc)))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.process_controller.terminate()
        self.status_label.setText("正在尝试取消当前任务...")
        self.status_label.show()
        self.current_step_value_label.setText("正在取消当前任务")
        self._set_status_badge("取消中", "warning")

    def _poll_events(self) -> None:
        while True:
            try:
                event_name, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event_name == "log":
                text = str(payload)
                self._append_log(text)
                self._record_log_counters(text)
                continue

            if event_name == "progress":
                done, total, current, detail = payload
                total_count = max(1, int(total))
                progress_units = max(0.0, min(float(total_count), float(done)))
                self.current_total = total_count
                self.current_progress_units = progress_units
                self.completed_count = min(total_count, int(progress_units))
                self.current_file_path = str(current)
                self.current_detail = str(detail)
                self.progress_bar.setValue(max(0, min(100, int(progress_units / float(total_count) * 100.0))))
                visible_position = min(total_count, max(1, int(progress_units) + (0 if progress_units >= total_count else 1)))
                self.progress_label.setText(f"{visible_position}/{total_count} · {Path(str(current)).name}")
                self.status_label.setText(str(detail))
                self.status_label.show()
                self.current_file_value_label.setText(Path(str(current)).name)
                self.current_file_value_label.setToolTip(str(current))
                self.current_step_value_label.setText(str(detail))
                self._update_metric_values()
                self._update_timing_labels()
                continue

            if event_name == "update_available":
                release, manual = payload
                assert isinstance(release, UpdateRelease)
                self.available_release = release
                self._set_update_status(f"发现新版本 {release.version} · {format_bytes(release.size_bytes)}")
                self._set_update_busy(False)
                if manual:
                    self._append_log(f"发现可用更新：{release.version}")
                continue

            if event_name == "update_none":
                manual = bool(payload)
                if self.staged_release is None:
                    self.available_release = None
                    self._set_update_status(f"当前已是最新版 {self.installed_build.version}")
                self._set_update_busy(False)
                if manual:
                    self._append_log("当前已是最新版。")
                continue

            if event_name == "update_download_progress":
                release, downloaded, total = payload
                total_value = int(total or 0)
                downloaded_value = int(downloaded or 0)
                if total_value > 0:
                    percent = max(0, min(100, int(downloaded_value / total_value * 100)))
                    self._set_update_status(
                        f"正在下载 {release.version} · {percent}% · {format_bytes(downloaded_value)} / {format_bytes(total_value)}"
                    )
                else:
                    self._set_update_status(f"正在下载 {release.version} · {format_bytes(downloaded_value)}")
                continue

            if event_name == "update_extracting":
                self._set_update_status(f"正在解压更新包 {payload}...")
                continue

            if event_name == "update_staged":
                release, bundle_dir = payload
                assert isinstance(release, UpdateRelease)
                self.available_release = release
                self.staged_release = release
                self.staged_release_dir = Path(str(bundle_dir))
                self._set_update_status(f"更新已准备好：{release.version}，点击安装完成更新。")
                self._set_update_busy(False)
                if self._ask_yes_no(f"新版本 {release.version} 已下载完成。\n\n是否现在重启并安装？"):
                    self._install_staged_update()
                continue

            if event_name == "update_error":
                message, manual = payload
                self._set_update_status(f"更新失败：{message}")
                self._set_update_busy(False)
                if manual:
                    self._show_error(str(message))
                continue

            if event_name == "done":
                summary = payload
                assert isinstance(summary, BatchSummary)
                self.generated_count = summary.generated
                self.skipped_count = summary.skipped
                self.failed_count = summary.failed
                self.completed_count = summary.total
                self.current_total = summary.total
                self.current_progress_units = float(summary.total)
                self._update_metric_values()
                self._update_timing_labels()
                self._finish_work()
                self.status_label.setText(f"完成：生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。")
                self.status_label.show()
                self.current_step_value_label.setText("全部视频处理完成")
                self.progress_label.setText(f"{summary.total}/{summary.total} · 全部完成")
                self.progress_bar.setValue(100)
                self._set_status_badge("已完成", "success" if summary.failed == 0 else "warning")
                if summary.failures:
                    self._set_log_visible(True)
                    self._append_log("失败详情：")
                    for item in summary.failures:
                        self._append_log(item)
                self._show_info(f"处理完成。\n生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。")
                continue

            if event_name == "cancelled":
                self._finish_work()
                self.status_label.setText(str(payload))
                self.status_label.show()
                self.current_step_value_label.setText("任务已取消")
                self._set_status_badge("已取消", "warning")
                self._set_log_visible(True)
                self._append_log(str(payload))
                continue

            if event_name == "error":
                self._finish_work()
                self.status_label.setText(str(payload))
                self.status_label.show()
                self.current_step_value_label.setText("任务异常结束")
                self._set_status_badge("发生错误", "error")
                self._set_log_visible(True)
                self._append_log(str(payload))
                self._show_error(str(payload))

    def _finish_work(self) -> None:
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._update_timing_labels()

    def _append_log(self, text: str) -> None:
        self.log_text.appendPlainText(text)
        self.log_text.ensureCursorVisible()

    def run(self) -> int:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        return self.app.exec()


class SubtitleToolApp:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = runtime_dir
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("900x680")
        self.root.minsize(820, 640)
        self._configure_theme()
        self.can_self_update = is_frozen()
        self.installed_build = load_installed_build_info()

        self.input_dir_var = tk.StringVar()
        self.source_mode_var = tk.StringVar(value=SOURCE_MODE_LOCAL_LABEL)
        self.api_base_url_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.project_picker_var = tk.StringVar()
        self.subject_id_var = tk.StringVar()
        self.project_id_var = tk.StringVar()
        self.baidu_account_id_var = tk.StringVar()
        self.baidu_current_dir_var = tk.StringVar(value="/")
        self.runtime_var = tk.StringVar(value="正在检查内置运行时...")
        self.status_var = tk.StringVar(value="请选择一个视频目录。")
        self.progress_label_var = tk.StringVar(value="尚未开始")
        self.version_var = tk.StringVar(value=self.installed_build.version)
        self.update_status_var = tk.StringVar(value="自动检查更新中...")
        self.update_button_var = tk.StringVar(value="检查更新")
        self.advanced_toggle_var = tk.StringVar(value="高级设置")
        self.overwrite_var = tk.BooleanVar(value=False)
        self.threads_var = tk.IntVar(value=default_threads())
        self.enable_gpu_var = tk.BooleanVar(value=False)
        self.language_var = tk.StringVar(value=recognition_language_label(DEFAULT_RECOGNITION_LANGUAGE))
        self.gpu_hint_var = tk.StringVar(value="当前工具包未包含 CUDA backend，将继续使用 CPU 识别。")
        self.progress_value_var = tk.DoubleVar(value=0.0)
        self.log_toggle_var = tk.StringVar(value="查看日志")

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.process_controller = ProcessController()
        self.worker_thread: threading.Thread | None = None
        self.update_thread: threading.Thread | None = None
        self.update_busy = False
        self.available_release: UpdateRelease | None = None
        self.staged_release: UpdateRelease | None = None
        self.staged_release_dir: Path | None = None
        self.project_choices: list[dict[str, str]] = []
        self.baidu_dir_items: list[dict[str, object]] = []
        self.mobile_package_server = None

        self._build_ui()
        self._set_advanced_visible(False)
        self._set_log_visible(False)
        self._refresh_runtime_summary()
        self._refresh_update_controls()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(120, self._poll_events)
        if self.can_self_update:
            self.root.after(500, self._auto_check_updates)

    def _configure_theme(self) -> None:
        self.root.configure(bg="#eef3f8")
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background="#eef3f8", foreground="#16324b", font=("Segoe UI", 10))
        style.configure("App.TFrame", background="#eef3f8")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("HeroTitle.TLabel", background="#eef3f8", foreground="#10243a", font=("Segoe UI", 22, "bold"))
        style.configure("Body.TLabel", background="#eef3f8", foreground="#5b7087", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#10243a", font=("Segoe UI", 11, "bold"))
        style.configure("CardMuted.TLabel", background="#ffffff", foreground="#5f7288", font=("Segoe UI", 10))
        style.configure(
            "Badge.TLabel",
            background="#eaf2ff",
            foreground="#24507d",
            font=("Segoe UI", 9),
            padding=(10, 6),
            relief="solid",
            borderwidth=1,
        )
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 10))
        style.configure("Secondary.TButton", padding=(14, 10))
        style.configure("App.TCheckbutton", background="#ffffff", foreground="#16324b")
        style.configure("App.TSpinbox", arrowsize=14)
        style.configure("App.Horizontal.TProgressbar", thickness=10, troughcolor="#dbe6f2", background="#2f7ed1", bordercolor="#dbe6f2")

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        shell = ttk.Frame(self.root, style="App.TFrame", padding=20)
        shell.grid(sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=0)
        self.shell = shell

        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)
        title_row = ttk.Frame(header, style="App.TFrame")
        title_row.grid(row=0, column=0, sticky="w")
        ttk.Label(title_row, text=APP_TITLE, style="HeroTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(title_row, textvariable=self.version_var, style="Badge.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.update_button = ttk.Button(header, textvariable=self.update_button_var, style="Secondary.TButton", command=self._handle_update_action)
        self.update_button.grid(row=0, column=1, sticky="e")
        if not self.can_self_update:
            self.update_button.grid_remove()

        task_card = ttk.Frame(shell, style="Card.TFrame", padding=18)
        task_card.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        task_card.columnconfigure(0, weight=1)
        ttk.Label(task_card, text="开始生成", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(task_card, text="默认递归扫描并跳过已有字幕，选好目录就能直接开始。", style="CardMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 14)
        )

        directory_row = ttk.Frame(task_card, style="Card.TFrame")
        directory_row.grid(row=2, column=0, sticky="ew")
        directory_row.columnconfigure(1, weight=1)
        ttk.Label(directory_row, text="来源", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        self.source_mode_combobox = ttk.Combobox(
            directory_row,
            textvariable=self.source_mode_var,
            values=[SOURCE_MODE_LOCAL_LABEL, SOURCE_MODE_PROJECT_BAIDU_LABEL],
            state="readonly",
            width=16,
        )
        self.source_mode_combobox.grid(row=0, column=1, sticky="w", padx=(10, 10))
        ttk.Label(directory_row, text="视频目录", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.input_dir_entry = ttk.Entry(directory_row, textvariable=self.input_dir_var)
        self.input_dir_entry.grid(row=1, column=1, sticky="ew", padx=(10, 10), pady=(10, 0))
        self.choose_directory_button = ttk.Button(directory_row, text="选择目录", style="Secondary.TButton", command=self._choose_directory)
        self.choose_directory_button.grid(row=1, column=2, sticky="e", pady=(10, 0))
        ttk.Label(directory_row, text="API 地址", style="CardMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.api_base_url_entry = ttk.Entry(directory_row, textvariable=self.api_base_url_var)
        self.api_base_url_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Label(directory_row, text="邮箱", style="CardMuted.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.email_entry = ttk.Entry(directory_row, textvariable=self.email_var)
        self.email_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Label(directory_row, text="密码", style="CardMuted.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.password_entry = ttk.Entry(directory_row, textvariable=self.password_var, show="*")
        self.password_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Label(directory_row, text="项目选择", style="CardMuted.TLabel").grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.project_picker_combobox = ttk.Combobox(directory_row, textvariable=self.project_picker_var, state="readonly")
        self.project_picker_combobox.grid(row=5, column=1, sticky="ew", padx=(10, 10), pady=(10, 0))
        self.load_project_choices_button = ttk.Button(directory_row, text="加载项目", style="Secondary.TButton", command=self._load_project_choices)
        self.load_project_choices_button.grid(row=5, column=2, sticky="e", pady=(10, 0))
        ttk.Label(directory_row, text="学科 ID", style="CardMuted.TLabel").grid(row=6, column=0, sticky="w", pady=(10, 0))
        self.subject_id_entry = ttk.Entry(directory_row, textvariable=self.subject_id_var)
        self.subject_id_entry.grid(row=6, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Label(directory_row, text="项目 ID", style="CardMuted.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.project_id_entry = ttk.Entry(directory_row, textvariable=self.project_id_var)
        self.project_id_entry.grid(row=7, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Label(directory_row, text="网盘账号", style="CardMuted.TLabel").grid(row=8, column=0, sticky="w", pady=(10, 0))
        self.baidu_account_id_entry = ttk.Entry(directory_row, textvariable=self.baidu_account_id_var)
        self.baidu_account_id_entry.grid(row=8, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Label(directory_row, text="当前目录", style="CardMuted.TLabel").grid(row=9, column=0, sticky="w", pady=(10, 0))
        self.baidu_current_dir_entry = ttk.Entry(directory_row, textvariable=self.baidu_current_dir_var)
        self.baidu_current_dir_entry.grid(row=9, column=1, sticky="ew", padx=(10, 10), pady=(10, 0))
        self.load_baidu_dir_button = ttk.Button(directory_row, text="读取目录", style="Secondary.TButton", command=self._load_baidu_dir_items)
        self.load_baidu_dir_button.grid(row=9, column=2, sticky="e", pady=(10, 0))
        ttk.Label(directory_row, text="目录项目", style="CardMuted.TLabel").grid(row=10, column=0, sticky="w", pady=(10, 0))
        self.baidu_items_combobox = ttk.Combobox(directory_row, state="readonly")
        self.baidu_items_combobox.grid(row=10, column=1, sticky="ew", padx=(10, 10), pady=(10, 0))
        baidu_item_buttons = ttk.Frame(directory_row, style="Card.TFrame")
        baidu_item_buttons.grid(row=10, column=2, sticky="e", pady=(10, 0))
        self.baidu_parent_button = ttk.Button(baidu_item_buttons, text="上级", style="Secondary.TButton", command=self._load_baidu_parent_dir)
        self.baidu_parent_button.grid(row=0, column=0, sticky="e")
        self.baidu_enter_button = ttk.Button(baidu_item_buttons, text="进入", style="Secondary.TButton", command=self._enter_selected_baidu_dir)
        self.baidu_enter_button.grid(row=0, column=1, sticky="e", padx=(6, 0))
        self.baidu_add_path_button = ttk.Button(baidu_item_buttons, text="添加", style="Secondary.TButton", command=self._add_selected_baidu_import_path)
        self.baidu_add_path_button.grid(row=0, column=2, sticky="e", padx=(6, 0))
        ttk.Label(directory_row, text="导入路径", style="CardMuted.TLabel").grid(row=11, column=0, sticky="nw", pady=(10, 0))
        self.baidu_import_paths_text = tk.Text(directory_row, height=4, width=52)
        self.baidu_import_paths_text.grid(row=11, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=(10, 0))

        ttk.Label(task_card, textvariable=self.runtime_var, style="CardMuted.TLabel", wraplength=760).grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )

        progress_header = ttk.Frame(task_card, style="Card.TFrame")
        progress_header.grid(row=4, column=0, sticky="ew", pady=(18, 0))
        progress_header.columnconfigure(1, weight=1)
        ttk.Label(progress_header, text="当前进度", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(progress_header, textvariable=self.progress_label_var, style="CardMuted.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Progressbar(task_card, variable=self.progress_value_var, maximum=100, style="App.Horizontal.TProgressbar").grid(
            row=5, column=0, sticky="ew", pady=(12, 0)
        )
        ttk.Label(task_card, textvariable=self.status_var, style="CardMuted.TLabel", wraplength=760).grid(
            row=6, column=0, sticky="w", pady=(12, 0)
        )

        actions = ttk.Frame(task_card, style="Card.TFrame")
        actions.grid(row=7, column=0, sticky="ew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        toggles = ttk.Frame(actions, style="Card.TFrame")
        toggles.grid(row=0, column=0, sticky="w")
        self.advanced_toggle_button = ttk.Button(toggles, textvariable=self.advanced_toggle_var, style="Secondary.TButton", command=self._toggle_advanced_visibility)
        self.advanced_toggle_button.grid(row=0, column=0, sticky="w")
        self.log_toggle_button = ttk.Button(toggles, textvariable=self.log_toggle_var, style="Secondary.TButton", command=self._toggle_log_visibility)
        self.log_toggle_button.grid(row=0, column=1, sticky="w", padx=(10, 0))

        buttons = ttk.Frame(actions, style="Card.TFrame")
        buttons.grid(row=0, column=1, sticky="e")
        self.cancel_button = ttk.Button(buttons, text="取消", style="Secondary.TButton", command=self._cancel, state="disabled")
        self.cancel_button.grid(row=0, column=0)
        self.mobile_import_button = ttk.Button(buttons, text="导入到手机", style="Secondary.TButton", command=self._start_mobile_import)
        self.mobile_import_button.grid(row=0, column=1, padx=(10, 0))
        self.start_button = ttk.Button(buttons, text="开始生成", style="Primary.TButton", command=self._start)
        self.start_button.grid(row=0, column=2, padx=(10, 0))

        advanced_card = ttk.Frame(task_card, style="Card.TFrame")
        advanced_card.grid(row=8, column=0, sticky="ew", pady=(16, 0))
        advanced_card.columnconfigure(4, weight=1)
        ttk.Label(advanced_card, text="覆盖已有 .srt", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(advanced_card, variable=self.overwrite_var, style="App.TCheckbutton").grid(row=0, column=1, sticky="w", padx=(8, 18))
        ttk.Label(advanced_card, text="线程数", style="CardMuted.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(advanced_card, from_=1, to=16, textvariable=self.threads_var, width=8, style="App.TSpinbox").grid(row=0, column=3, sticky="w", padx=(8, 0))
        ttk.Label(advanced_card, text="启用 GPU 模式", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.gpu_checkbutton = ttk.Checkbutton(advanced_card, variable=self.enable_gpu_var, style="App.TCheckbutton")
        self.gpu_checkbutton.grid(row=1, column=1, sticky="w", padx=(8, 18), pady=(12, 0))
        ttk.Label(advanced_card, textvariable=self.gpu_hint_var, style="CardMuted.TLabel", wraplength=540).grid(
            row=1, column=2, columnspan=3, sticky="w", pady=(12, 0)
        )
        ttk.Label(advanced_card, text="识别语言", style="CardMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.language_combobox = ttk.Combobox(
            advanced_card,
            textvariable=self.language_var,
            values=list(RECOGNITION_LANGUAGE_LABELS.values()),
            state="readonly",
            width=14,
        )
        self.language_combobox.grid(row=2, column=1, sticky="w", padx=(8, 18), pady=(12, 0))
        ttk.Label(
            advanced_card,
            text="默认按中文识别，更适合中文课程；遇到双语素材时可切到自动检测。",
            style="CardMuted.TLabel",
            wraplength=540,
        ).grid(row=2, column=2, columnspan=3, sticky="w", pady=(12, 0))
        self.advanced_card = advanced_card
        self.project_picker_combobox.bind("<<ComboboxSelected>>", lambda _event: self._apply_selected_project_choice())
        self.source_mode_combobox.bind("<<ComboboxSelected>>", lambda _event: self._sync_source_mode_controls())
        self._sync_source_mode_controls()

        log_card = ttk.Frame(shell, style="Card.TFrame", padding=18)
        log_card.grid(row=2, column=0, sticky="nsew", pady=(16, 0))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)
        self.log_card = log_card

        log_header = ttk.Frame(log_card, style="Card.TFrame")
        log_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="处理日志", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(log_header, text="仅在排查问题时展开。", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.log_text = tk.Text(
            log_card,
            wrap="word",
            height=12,
            state="disabled",
            bg="#fbfdff",
            fg="#16324b",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8,
            font=("Consolas", 10),
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        scrollbar = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(14, 0))
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _set_advanced_visible(self, visible: bool) -> None:
        if visible:
            self.advanced_card.grid()
            self.advanced_toggle_var.set("收起设置")
            return
        self.advanced_card.grid_remove()
        self.advanced_toggle_var.set("高级设置")

    def _toggle_advanced_visibility(self) -> None:
        self._set_advanced_visible(not self.advanced_card.winfo_ismapped())

    def _set_log_visible(self, visible: bool) -> None:
        if visible:
            self.log_card.grid()
            self.shell.rowconfigure(2, weight=1)
            self.log_toggle_var.set("收起日志")
            return
        self.log_card.grid_remove()
        self.shell.rowconfigure(2, weight=0)
        self.log_toggle_var.set("查看日志")

    def _toggle_log_visibility(self) -> None:
        self._set_log_visible(not self.log_card.winfo_ismapped())

    def _set_update_status(self, message: str) -> None:
        return

    def _sync_source_mode_controls(self) -> None:
        project_mode = self.source_mode_var.get() == SOURCE_MODE_PROJECT_BAIDU_LABEL
        local_state = "disabled" if project_mode else "normal"
        project_state = "normal" if project_mode else "disabled"
        self.input_dir_entry.configure(state=local_state)
        self.choose_directory_button.configure(state=local_state)
        for widget in (
            self.api_base_url_entry,
            self.email_entry,
            self.password_entry,
            self.project_picker_combobox,
            self.load_project_choices_button,
            self.subject_id_entry,
            self.project_id_entry,
            self.baidu_account_id_entry,
            self.baidu_current_dir_entry,
            self.baidu_items_combobox,
            self.load_baidu_dir_button,
            self.baidu_parent_button,
            self.baidu_enter_button,
            self.baidu_add_path_button,
        ):
            widget.configure(state=project_state)
        self.baidu_import_paths_text.configure(state=project_state)

    def _refresh_update_controls(self) -> None:
        if not self.can_self_update:
            self.update_button.configure(state="disabled")
            return

        if self.update_busy:
            self.update_button.configure(state="disabled")
            self.update_button_var.set("更新中...")
            return

        self.update_button.configure(state="normal")
        if self.staged_release is not None and self.staged_release_dir is not None:
            self.update_button_var.set(f"安装 {self.staged_release.version}")
            return
        if self.available_release is not None and is_release_newer_than_installed(self.available_release, self.installed_build):
            self.update_button_var.set(f"更新到 {self.available_release.version}")
            return
        self.update_button_var.set("检查更新")

    def _set_update_busy(self, busy: bool) -> None:
        self.update_busy = busy
        self._refresh_update_controls()

    def _auto_check_updates(self) -> None:
        self._check_for_updates(manual=False)

    def _check_for_updates(self, *, manual: bool) -> None:
        if not self.can_self_update:
            return
        if self.update_thread is not None and self.update_thread.is_alive():
            return
        self._set_update_busy(True)
        self._set_update_status("正在检查更新...")
        self.update_thread = threading.Thread(target=self._run_update_check, args=(manual,), daemon=True)
        self.update_thread.start()

    def _run_update_check(self, manual: bool) -> None:
        try:
            release = fetch_latest_release(load_update_config())
            if release is not None and is_release_newer_than_installed(release, self.installed_build):
                self.event_queue.put(("update_available", (release, manual)))
                return
            self.event_queue.put(("update_none", manual))
        except Exception as exc:
            self.event_queue.put(("update_error", (str(exc), manual)))

    def _handle_update_action(self) -> None:
        if not self.can_self_update:
            messagebox.showinfo(APP_TITLE, SOURCE_MODE_UPDATE_MESSAGE)
            return
        if self.update_busy:
            return
        if self.staged_release is not None and self.staged_release_dir is not None:
            self._install_staged_update()
            return
        if self.available_release is not None and is_release_newer_than_installed(self.available_release, self.installed_build):
            if self.worker_thread is not None and self.worker_thread.is_alive():
                messagebox.showinfo(APP_TITLE, "请先等当前字幕任务完成，再安装更新。")
                return
            if not is_frozen():
                messagebox.showinfo(APP_TITLE, "源码运行模式下不支持一键更新，请使用打包后的 EXE。")
                return
            detail = f"发现新版本 {self.available_release.version}"
            if self.available_release.size_bytes > 0:
                detail += f"（约 {format_bytes(self.available_release.size_bytes)}）"
            if not messagebox.askyesno(APP_TITLE, f"{detail}\n\n是否现在下载并准备安装？"):
                return
            self._start_download_update(self.available_release)
            return
        self._check_for_updates(manual=True)

    def _start_download_update(self, release: UpdateRelease) -> None:
        if self.update_thread is not None and self.update_thread.is_alive():
            return
        self._set_update_busy(True)
        self._set_update_status(f"正在下载 {release.version}...")
        self.update_thread = threading.Thread(target=self._run_download_update, args=(release,), daemon=True)
        self.update_thread.start()

    def _run_download_update(self, release: UpdateRelease) -> None:
        try:
            zip_path = download_release_zip(
                release,
                on_progress=lambda downloaded, total: self.event_queue.put(("update_download_progress", (release, downloaded, total))),
            )
            self.event_queue.put(("update_extracting", release.version))
            bundle_dir = extract_release_bundle(zip_path)
            self.event_queue.put(("update_staged", (release, str(bundle_dir))))
        except Exception as exc:
            self.event_queue.put(("update_error", (str(exc), True)))

    def _install_staged_update(self) -> None:
        if self.staged_release is None or self.staged_release_dir is None:
            return
        if self.worker_thread is not None and self.worker_thread.is_alive():
            messagebox.showinfo(APP_TITLE, "请先等当前字幕任务完成，再安装更新。")
            return
        if not is_frozen():
            messagebox.showinfo(APP_TITLE, "源码运行模式下不支持一键更新，请使用打包后的 EXE。")
            return
        if not self.staged_release_dir.exists():
            self.staged_release = None
            self.staged_release_dir = None
            self._set_update_status("更新包已失效，请重新检查更新。")
            self._refresh_update_controls()
            return

        if not messagebox.askyesno(
            APP_TITLE,
            f"将安装 {self.staged_release.version}，程序会自动关闭并重新启动。\n\n是否继续？",
        ):
            return

        script_path = create_windows_update_script(source_dir=self.staged_release_dir, target_dir=executable_dir())
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-WaitPid",
                str(os.getpid()),
                "-SourceDir",
                str(self.staged_release_dir),
                "-TargetDir",
                str(executable_dir()),
                "-ExeName",
                f"{TOOL_EXE_BASENAME}.exe",
            ],
            creationflags=creationflags,
        )
        self.root.after(120, self._close)

    def _close(self) -> None:
        self._stop_mobile_package_server()
        self.root.destroy()

    def _choose_directory(self) -> None:
        initial_dir = self.input_dir_var.get().strip() or str(executable_dir())
        selected = filedialog.askdirectory(initialdir=initial_dir, title="选择要生成字幕的视频目录")
        if selected:
            self.input_dir_var.set(selected)

    def _make_project_client_from_form(self) -> LearningPyramidProjectClient:
        api_base_url = normalize_learningpyramid_api_base_url(self.api_base_url_var.get().strip())
        email = self.email_var.get().strip()
        password = self.password_var.get()
        if not email:
            raise ValueError("请填写 LearningPyramid 登录邮箱。")
        if not password:
            raise ValueError("请填写 LearningPyramid 密码。")
        client = LearningPyramidProjectClient(api_base_url)
        client.login(email=email, password=password)
        return client

    def _current_project_ids_from_form(self) -> tuple[str, str]:
        subject_id = self.subject_id_var.get().strip()
        scoped_project_id = self.project_id_var.get().strip()
        if not subject_id:
            raise ValueError("请填写学科 ID。")
        if not scoped_project_id:
            raise ValueError("请填写项目 ID。")
        return subject_id, scoped_project_id

    def _current_baidu_account_id(self, client: object) -> str:
        account_id = _resolve_single_baidu_account_id(client, self.baidu_account_id_var.get().strip() or None)
        if not self.baidu_account_id_var.get().strip():
            self.baidu_account_id_var.set(account_id)
        return account_id

    def _load_project_choices(self) -> None:
        try:
            client = self._make_project_client_from_form()
            subjects = client.list_subjects()
            if not isinstance(subjects, list):
                raise RuntimeError("LearningPyramid 学科响应无效。")
            choices: list[dict[str, str]] = []
            labels: list[str] = []
            for subject in subjects:
                if not isinstance(subject, dict):
                    continue
                subject_id = str(subject.get("subjectId") or "").strip()
                if not subject_id:
                    continue
                subject_title = str(subject.get("title") or subject_id).strip()
                materials = client.list_subject_materials(subject_id)
                if not isinstance(materials, list):
                    raise RuntimeError(f"LearningPyramid 项目响应无效：{subject_title}")
                for material in materials:
                    if not isinstance(material, dict):
                        continue
                    scoped_project_id = str(material.get("scopedProjectId") or "").strip()
                    if not scoped_project_id:
                        continue
                    material_title = str(material.get("title") or scoped_project_id).strip()
                    label = f"{subject_title} / {material_title}"
                    choices.append({"subjectId": subject_id, "scopedProjectId": scoped_project_id, "label": label})
                    labels.append(label)
            self.project_choices = choices
            self.project_picker_combobox.configure(values=labels)
            if labels:
                self.project_picker_combobox.current(0)
                self._apply_selected_project_choice()
            else:
                self.project_picker_var.set("")
            self._append_log(f"已加载 {len(choices)} 个项目。")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _apply_selected_project_choice(self) -> None:
        index = self.project_picker_combobox.current()
        if index < 0 or index >= len(self.project_choices):
            return
        choice = self.project_choices[index]
        self.subject_id_var.set(choice["subjectId"])
        self.project_id_var.set(choice["scopedProjectId"])

    def _load_baidu_dir_items(self) -> None:
        try:
            subject_id, scoped_project_id = self._current_project_ids_from_form()
            client = self._make_project_client_from_form()
            account_id = self._current_baidu_account_id(client)
            dir_path = normalize_baidu_remote_path(self.baidu_current_dir_var.get().strip() or "/")
            payload = client.list_project_baidu_netdisk_files(
                subject_id,
                scoped_project_id,
                account_id,
                dir_path=dir_path,
                page=1,
            )
            if not isinstance(payload, dict):
                raise RuntimeError("百度网盘目录响应无效。")
            rows = payload.get("items")
            items = [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []
            items.sort(key=lambda item: (0 if bool(item.get("isDir")) else 1, str(item.get("name") or item.get("path") or "")))
            self.baidu_dir_items = items
            labels: list[str] = []
            for item in items:
                name = str(item.get("name") or item.get("path") or "").strip() or "未命名"
                kind = "目录" if bool(item.get("isDir")) else ("视频" if _is_baidu_netdisk_video_item(item) else "文件")
                labels.append(f"[{kind}] {name}")
            self.baidu_items_combobox.configure(values=labels)
            if labels:
                self.baidu_items_combobox.current(0)
            else:
                self.baidu_items_combobox.set("")
            self.baidu_current_dir_var.set(dir_path)
            self._append_log(f"已读取百度网盘目录：{dir_path}，{len(items)} 项。")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _selected_baidu_item(self) -> dict[str, object] | None:
        index = self.baidu_items_combobox.current()
        if index < 0 or index >= len(self.baidu_dir_items):
            return None
        return self.baidu_dir_items[index]

    def _load_baidu_parent_dir(self) -> None:
        current_dir = self.baidu_current_dir_var.get().strip() or "/"
        self.baidu_current_dir_var.set(_baidu_remote_parent_dir(current_dir))
        self._load_baidu_dir_items()

    def _enter_selected_baidu_dir(self) -> None:
        item = self._selected_baidu_item()
        if item is None:
            return
        if not bool(item.get("isDir")):
            messagebox.showerror(APP_TITLE, "只能进入目录。")
            return
        self.baidu_current_dir_var.set(normalize_baidu_remote_path(str(item.get("path") or "")))
        self._load_baidu_dir_items()

    def _read_baidu_import_paths_text(self) -> str:
        return self.baidu_import_paths_text.get("1.0", "end").strip()

    def _set_baidu_import_paths_text(self, paths: list[str]) -> None:
        self.baidu_import_paths_text.delete("1.0", "end")
        self.baidu_import_paths_text.insert("1.0", "\n".join(paths))

    def _add_selected_baidu_import_path(self) -> None:
        item = self._selected_baidu_item()
        if item is None:
            return
        if not _is_baidu_netdisk_importable_item(item):
            messagebox.showerror(APP_TITLE, "只能添加目录或视频文件。")
            return
        selected_path = normalize_baidu_remote_path(str(item.get("path") or ""))
        current_paths = list(parse_baidu_import_paths_text(self._read_baidu_import_paths_text()))
        if selected_path not in current_paths:
            current_paths.append(selected_path)
        self._set_baidu_import_paths_text(current_paths)

    def _stop_mobile_package_server(self) -> None:
        server = self.mobile_package_server
        if server is None:
            return
        self.mobile_package_server = None
        server.stop()

    def _start_mobile_import(self) -> None:
        if self.source_mode_var.get() == SOURCE_MODE_PROJECT_BAIDU_LABEL:
            messagebox.showerror(APP_TITLE, "请先切换到本地目录模式，并选择本地视频目录。")
            return
        input_dir_text = self.input_dir_var.get().strip()
        if not input_dir_text:
            messagebox.showerror(APP_TITLE, "请先选择一个视频目录。")
            return
        try:
            input_dir = Path(input_dir_text).expanduser().resolve()
            session = build_mobile_package_session(
                MobilePackageOptions(
                    input_dir=input_dir,
                    title=input_dir.name,
                    subject_id=self.subject_id_var.get().strip(),
                    scoped_project_id=self.project_id_var.get().strip(),
                )
            )
            self._stop_mobile_package_server()
            self.mobile_package_server = start_offline_course_package_server(session)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        assert self.mobile_package_server is not None
        message = format_mobile_package_connection_message(session, self.mobile_package_server.base_url)
        self._append_log("已启动手机导入临时服务。")
        self._append_log(message)
        messagebox.showinfo(APP_TITLE, message)

    def _sync_gpu_controls(self, runtime: RuntimePaths | None) -> None:
        if runtime is not None and runtime_supports_cuda(runtime):
            detected_devices = detect_cuda_device_count(runtime)
            if detected_devices is not None and detected_devices > 0:
                self.gpu_checkbutton.configure(state="normal")
                self.gpu_hint_var.set(f"已检测到 {detected_devices} 个可用 NVIDIA GPU；勾选后会尝试使用 GPU 提高识别速度。")
                return

            self.enable_gpu_var.set(False)
            self.gpu_checkbutton.configure(state="disabled")
            self.gpu_hint_var.set("工具包已包含 CUDA backend，但当前电脑没有检测到可用的 NVIDIA GPU 或驱动，将继续使用 CPU 识别。")
            return

        self.enable_gpu_var.set(False)
        self.gpu_checkbutton.configure(state="disabled")
        self.gpu_hint_var.set("当前工具包未包含 CUDA backend，将继续使用 CPU 识别。")

    def _refresh_runtime_summary(self) -> None:
        try:
            runtime = discover_runtime_paths(self.runtime_dir)
        except Exception as exc:
            self.runtime_var.set(f"未检测到内置运行时：{exc}")
            self._sync_gpu_controls(None)
            return
        self._sync_gpu_controls(runtime)
        self.runtime_var.set(f"{format_runtime_ready_text(runtime)} | 默认线程 {default_threads()}")

    def _start(self) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return

        try:
            runtime = discover_runtime_paths(self.runtime_dir)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        project_mode = self.source_mode_var.get() == SOURCE_MODE_PROJECT_BAIDU_LABEL
        if project_mode:
            try:
                options: BatchOptions | ProjectBaiduBatchOptions = ProjectBaiduBatchOptions(
                    api_base_url=normalize_learningpyramid_api_base_url(self.api_base_url_var.get().strip()),
                    email=self.email_var.get().strip(),
                    password=self.password_var.get(),
                    subject_id=self.subject_id_var.get().strip(),
                    scoped_project_id=self.project_id_var.get().strip(),
                    overwrite=bool(self.overwrite_var.get()),
                    threads=max(1, int(self.threads_var.get() or 1)),
                    enable_gpu=bool(self.enable_gpu_var.get()),
                    language=recognition_language_code_from_label(self.language_var.get()),
                    baidu_account_id=self.baidu_account_id_var.get().strip() or None,
                    baidu_import_paths=parse_baidu_import_paths_text(self._read_baidu_import_paths_text()),
                )
                _validate_project_baidu_options(options)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, str(exc))
                return
            task_label = f"{options.subject_id}/{options.scoped_project_id}"
            preparing_text = "准备扫描项目网盘视频..."
            status_text = (
                f"正在扫描项目中的百度网盘视频并准备逐个生成字幕"
                f"（{format_selected_acceleration_text(options.enable_gpu)} / {recognition_language_label(options.language)}）。"
            )
        else:
            input_dir_text = self.input_dir_var.get().strip()
            if not input_dir_text:
                messagebox.showerror(APP_TITLE, "请先选择一个视频目录。")
                return
            input_dir = Path(input_dir_text).expanduser()
            options = BatchOptions(
                input_dir=input_dir,
                recursive=True,
                overwrite=bool(self.overwrite_var.get()),
                threads=max(1, int(self.threads_var.get() or 1)),
                enable_gpu=bool(self.enable_gpu_var.get()),
                language=recognition_language_code_from_label(self.language_var.get()),
            )
            task_label = str(options.input_dir)
            preparing_text = "准备扫描目录..."
            status_text = (
                f"正在扫描目录并准备逐个生成字幕（{format_selected_acceleration_text(options.enable_gpu)} / {recognition_language_label(options.language)}）。"
            )
        if options.enable_gpu and not runtime_supports_cuda(runtime):
            messagebox.showerror(APP_TITLE, "当前工具包未包含 CUDA backend，暂时不能启用 GPU 模式。")
            return
        self._append_log("")
        self._append_log(f"开始任务：{task_label}")
        self._append_log(print_runtime_summary(runtime))
        self._append_log(f"识别模式：{format_selected_acceleration_text(options.enable_gpu)}")
        self._append_log(f"识别语言：{recognition_language_label(options.language)}")

        self.cancel_event.clear()
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress_value_var.set(0.0)
        self.progress_label_var.set(preparing_text)
        self.status_var.set(status_text)

        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(options, runtime),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_worker(self, options: BatchOptions | ProjectBaiduBatchOptions, runtime: RuntimePaths) -> None:
        try:
            if isinstance(options, ProjectBaiduBatchOptions):
                summary = run_project_baidu_batch(
                    options,
                    runtime,
                    log=lambda text: self.event_queue.put(("log", text)),
                    progress=lambda done, total, video, detail: self.event_queue.put(("progress", (done, total, str(video), detail))),
                    cancel_event=self.cancel_event,
                    process_controller=self.process_controller,
                )
            else:
                summary = run_batch(
                    options,
                    runtime,
                    log=lambda text: self.event_queue.put(("log", text)),
                    progress=lambda done, total, video, detail: self.event_queue.put(("progress", (done, total, str(video), detail))),
                    cancel_event=self.cancel_event,
                    process_controller=self.process_controller,
                )
            self.event_queue.put(("done", summary))
        except CancelledError as exc:
            self.event_queue.put(("cancelled", str(exc)))
        except Exception as exc:
            self.event_queue.put(("error", str(exc)))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.process_controller.terminate()
        self.status_var.set("正在尝试取消当前任务...")

    def _poll_events(self) -> None:
        while True:
            try:
                event_name, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event_name == "log":
                self._append_log(str(payload))
                continue

            if event_name == "progress":
                done, total, current, detail = payload
                total_count = max(1, int(total))
                progress_units = max(0.0, min(float(total_count), float(done)))
                self.progress_value_var.set(max(0.0, min(100.0, progress_units / float(total_count) * 100.0)))
                completed_count = min(total_count, max(1, int(progress_units) + (0 if progress_units >= total_count else 1)))
                self.progress_label_var.set(f"{completed_count}/{total_count} · {Path(str(current)).name}")
                self.status_var.set(str(detail))
                continue

            if event_name == "update_available":
                release, manual = payload
                assert isinstance(release, UpdateRelease)
                self.available_release = release
                self._set_update_status(f"发现新版本 {release.version} · {format_bytes(release.size_bytes)}")
                self._set_update_busy(False)
                if manual:
                    self._append_log(f"发现可用更新：{release.version}")
                continue

            if event_name == "update_none":
                manual = bool(payload)
                if self.staged_release is None:
                    self.available_release = None
                    self._set_update_status(f"当前已是最新版 {self.installed_build.version}")
                self._set_update_busy(False)
                if manual:
                    self._append_log("当前已是最新版。")
                continue

            if event_name == "update_download_progress":
                release, downloaded, total = payload
                total_value = int(total or 0)
                downloaded_value = int(downloaded or 0)
                if total_value > 0:
                    percent = max(0, min(100, int(downloaded_value / total_value * 100)))
                    self._set_update_status(
                        f"正在下载 {release.version} · {percent}% · {format_bytes(downloaded_value)} / {format_bytes(total_value)}"
                    )
                else:
                    self._set_update_status(f"正在下载 {release.version} · {format_bytes(downloaded_value)}")
                continue

            if event_name == "update_extracting":
                self._set_update_status(f"正在解压更新包 {payload}...")
                continue

            if event_name == "update_staged":
                release, bundle_dir = payload
                assert isinstance(release, UpdateRelease)
                self.available_release = release
                self.staged_release = release
                self.staged_release_dir = Path(str(bundle_dir))
                self._set_update_status(f"更新已准备好：{release.version}，点击安装完成更新。")
                self._set_update_busy(False)
                if messagebox.askyesno(APP_TITLE, f"新版本 {release.version} 已下载完成。\n\n是否现在重启并安装？"):
                    self._install_staged_update()
                continue

            if event_name == "update_error":
                message, manual = payload
                self._set_update_status(f"更新失败：{message}")
                self._set_update_busy(False)
                if manual:
                    messagebox.showerror(APP_TITLE, str(message))
                continue

            if event_name == "done":
                summary = payload
                assert isinstance(summary, BatchSummary)
                self._finish_work()
                self.status_var.set(
                    f"完成：生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。"
                )
                if summary.failures:
                    self._set_log_visible(True)
                    self._append_log("失败详情：")
                    for item in summary.failures:
                        self._append_log(item)
                messagebox.showinfo(
                    APP_TITLE,
                    f"处理完成。\n生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。",
                )
                continue

            if event_name == "cancelled":
                self._finish_work()
                self.status_var.set(str(payload))
                self._set_log_visible(True)
                self._append_log(str(payload))
                continue

            if event_name == "error":
                self._finish_work()
                self.status_var.set(str(payload))
                self._set_log_visible(True)
                self._append_log(str(payload))
                messagebox.showerror(APP_TITLE, str(payload))

        self.root.after(120, self._poll_events)

    def _finish_work(self) -> None:
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def run(self) -> int:
        self.root.mainloop()
        return 0


def run_cli(args: argparse.Namespace) -> int:
    if _mobile_package_cli_requested(args):
        session = build_mobile_package_session_from_args(args)
        server = start_offline_course_package_server(session)
        try:
            print(format_mobile_package_connection_message(session, server.base_url))
            _wait_for_mobile_package_server_interrupt()
        finally:
            server.stop()
        return 0

    runtime = discover_runtime_paths(Path(args.runtime_dir).expanduser().resolve() if args.runtime_dir else None)
    if _project_baidu_cli_requested(args):
        password = str(args.lp_password or os.getenv("LP_SUBTITLE_TOOL_PASSWORD") or "")
        if not password:
            password = getpass.getpass("LearningPyramid 密码: ")
        options = ProjectBaiduBatchOptions(
            api_base_url=normalize_learningpyramid_api_base_url(args.lp_api_base_url),
            email=str(args.lp_email or "").strip(),
            password=password,
            subject_id=str(args.lp_subject_id or "").strip(),
            scoped_project_id=str(args.lp_project_id or "").strip(),
            overwrite=bool(args.overwrite),
            threads=max(1, int(args.threads or 1)),
            enable_gpu=bool(args.gpu),
            language=normalize_recognition_language(args.language),
            baidu_account_id=str(args.lp_baidu_account_id or "").strip() or None,
            baidu_import_paths=parse_baidu_import_paths_text("\n".join(args.lp_baidu_import_path or [])),
        )
        try:
            _validate_project_baidu_options(options)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        cancel_event = threading.Event()
        process_controller = ProcessController()
        summary = run_project_baidu_batch(
            options,
            runtime,
            log=lambda text: print(text),
            progress=lambda done, total, video, detail: print(f"进度 {done:.2f}/{total}: {video} | {detail}"),
            cancel_event=cancel_event,
            process_controller=process_controller,
        )
        print(f"完成：生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。")
        return 0 if summary.failed == 0 else 2

    if not args.input_dir:
        raise SystemExit("请提供 --input-dir，或使用 --lp-api-base-url/--lp-subject-id/--lp-project-id 运行项目网盘模式。")
    options = BatchOptions(
        input_dir=Path(args.input_dir).expanduser().resolve(),
        recursive=not bool(args.non_recursive),
        overwrite=bool(args.overwrite),
        threads=max(1, int(args.threads or 1)),
        enable_gpu=bool(args.gpu),
        language=normalize_recognition_language(args.language),
    )
    cancel_event = threading.Event()
    process_controller = ProcessController()
    summary = run_batch(
        options,
        runtime,
        log=lambda text: print(text),
        progress=lambda done, total, video, detail: print(f"进度 {done:.2f}/{total}: {video} | {detail}"),
        cancel_event=cancel_event,
        process_controller=process_controller,
    )
    print(f"完成：生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。")
    return 0 if summary.failed == 0 else 2


def _project_baidu_cli_requested(args: argparse.Namespace) -> bool:
    return any(
        bool(str(getattr(args, name, "") or "").strip())
        for name in ("lp_api_base_url", "lp_email", "lp_subject_id", "lp_project_id", "lp_baidu_account_id")
    ) or bool(
        [
            item for item in getattr(args, "lp_baidu_import_path", [])
            if str(item or "").strip()
        ]
    )


def _mobile_package_cli_requested(args: argparse.Namespace) -> bool:
    return any(
        bool(str(getattr(args, name, "") or "").strip())
        for name in ("mobile_package_dir", "mobile_package_title", "mobile_subject_id", "mobile_project_id")
    )


def _validate_project_baidu_options(options: ProjectBaiduBatchOptions) -> None:
    missing: list[str] = []
    if not str(options.api_base_url or "").strip():
        missing.append("--lp-api-base-url")
    if not str(options.email or "").strip():
        missing.append("--lp-email")
    if not str(options.password or "").strip():
        missing.append("--lp-password")
    if not str(options.subject_id or "").strip():
        missing.append("--lp-subject-id")
    if not str(options.scoped_project_id or "").strip():
        missing.append("--lp-project-id")
    if missing:
        raise ValueError(f"项目网盘模式缺少参数：{', '.join(missing)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate same-directory SRT subtitles for a video folder.")
    parser.add_argument("--input-dir", help="Run in headless mode for the given video directory.")
    parser.add_argument("--runtime-dir", help="Optional runtime directory containing ffmpeg, whisper-cli and the model.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .srt files.")
    parser.add_argument("--non-recursive", action="store_true", help="Only process the selected directory, not subdirectories.")
    parser.add_argument("--threads", type=int, default=default_threads(), help="whisper.cpp worker thread count.")
    parser.add_argument("--gpu", action="store_true", help="Allow whisper.cpp to use the bundled CUDA backend when available.")
    parser.add_argument(
        "--language",
        choices=RECOGNITION_LANGUAGE_CODES,
        default=DEFAULT_RECOGNITION_LANGUAGE,
        help="Recognition language: zh, auto, or en.",
    )
    parser.add_argument("--lp-api-base-url", help="LearningPyramid API base URL, for example https://plm.xuebao.chat/api.")
    parser.add_argument("--lp-email", help="LearningPyramid login email for project Baidu Netdisk subtitle generation.")
    parser.add_argument("--lp-password", help="LearningPyramid password. If omitted, LP_SUBTITLE_TOOL_PASSWORD or an interactive prompt is used.")
    parser.add_argument("--lp-subject-id", help="Subject id from the LearningPyramid project URL.")
    parser.add_argument("--lp-project-id", help="Scoped project id from the LearningPyramid project URL.")
    parser.add_argument("--lp-baidu-account-id", help="Optional Baidu Netdisk cloud account id. Omit it when the user has exactly one bound account.")
    parser.add_argument(
        "--lp-baidu-import-path",
        action="append",
        default=[],
        help="Baidu Netdisk file or directory path to import into the selected project before subtitle generation. Repeat for multiple paths.",
    )
    parser.add_argument("--mobile-package-dir", help="Build and serve a mobile offline course package from a local video directory.")
    parser.add_argument("--mobile-package-title", help="Display title for the mobile offline course package.")
    parser.add_argument("--mobile-subject-id", help="Subject id to bind the mobile offline package to.")
    parser.add_argument("--mobile-project-id", help="Scoped project id to bind the mobile offline package to.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.input_dir or _project_baidu_cli_requested(args) or _mobile_package_cli_requested(args):
        return run_cli(args)
    runtime_dir = Path(args.runtime_dir).expanduser().resolve() if args.runtime_dir else None
    app = QtSubtitleToolApp(runtime_dir=runtime_dir) if PYSIDE6_AVAILABLE else SubtitleToolApp(runtime_dir=runtime_dir)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
