import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system.version import APP_VERSION


TOOL_ID = "subtitle-generator-windows-x64"
TOOL_LABEL = "LearningPyramid 字幕生成工具"
TOOL_EXE_BASENAME = "LearningPyramid-SubtitleTool"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "public-downloads"
DEFAULT_PACKAGING_VENV = PROJECT_ROOT / "build" / "packaging-venv"
DEFAULT_UPDATE_BASE_URL = ""
VISUAL_STUDIO_GENERATOR = "Visual Studio 17 2022"

WHISPER_CPP_VERSION = "v1.8.4"
WHISPER_CPP_SOURCE_URL = f"https://github.com/ggml-org/whisper.cpp/archive/refs/tags/{WHISPER_CPP_VERSION}.zip"
WHISPER_CUDA_PREBUILT_VERSION = "11.8.0"
WHISPER_CUDA_PREBUILT_ARCHIVE = f"whisper-cublas-{WHISPER_CUDA_PREBUILT_VERSION}-bin-x64.zip"
WHISPER_CUDA_PREBUILT_URL = (
    f"https://github.com/ggml-org/whisper.cpp/releases/download/{WHISPER_CPP_VERSION}/{WHISPER_CUDA_PREBUILT_ARCHIVE}"
)
PYSIDE6_VERSION = "6.8.2.1"
WHISPER_MODEL_FILE = "ggml-base.bin"
WHISPER_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin?download=true"
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

DEFAULT_EXCLUDED_MODULES = (
    "IPython",
    "PIL",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "_pytest",
    "jedi",
    "jupyter",
    "jupyter_client",
    "jupyter_core",
    "jupyterlab",
    "matplotlib",
    "notebook",
    "numpy",
    "pandas",
    "pygame",
    "pygments",
    "pytest",
    "scipy",
    "sklearn",
    "torch",
    "torchaudio",
    "torchvision",
    "traitlets",
)


def _bundle_name() -> str:
    return f"LearningPyramid-subtitle-tool-{APP_VERSION}-windows-x64"


def _utc_timestamp_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=str(cwd), check=True)


def _download(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination

    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination


def _reuse_cached_file(*candidates: Path) -> Path | None:
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def _extract_zip(archive_path: Path, destination: Path, *, refresh: bool) -> Path:
    if refresh and destination.exists():
        shutil.rmtree(destination)
    if destination.exists():
        children = [path for path in destination.iterdir()]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return destination

    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path, "r") as zf:
        zf.extractall(destination)

    children = [path for path in destination.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return destination


def _replace_text_once(path: Path, before: str, after: str) -> None:
    text = path.read_text(encoding="utf-8")
    if after in text:
        return
    if before not in text:
        raise SystemExit(f"Failed to patch expected text in {path}")
    path.write_text(text.replace(before, after, 1), encoding="utf-8", newline="\n")


def _patch_whisper_cpp_for_mingw(source_dir: Path) -> None:
    if os.name != "nt":
        return
    if not shutil.which("mingw32-make"):
        return

    cpu_source = source_dir / "ggml" / "src" / "ggml-cpu" / "ggml-cpu.c"
    _replace_text_once(
        cpu_source,
        "#if _WIN32_WINNT >= 0x0602",
        "#if _WIN32_WINNT >= 0x0602 && !defined(__MINGW32__)",
    )


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _resolve_pyinstaller_python(
    *,
    pyinstaller_python: str | None,
    bootstrap_packaging_venv: bool,
    refresh_packaging_venv: bool,
    packaging_venv_dir: Path,
) -> Path:
    if pyinstaller_python:
        python_path = Path(pyinstaller_python).expanduser().resolve()
        if not python_path.exists():
            raise SystemExit(f"PyInstaller python is missing: {python_path}")
        return python_path

    if not bootstrap_packaging_venv:
        return Path(sys.executable).resolve()

    if refresh_packaging_venv and packaging_venv_dir.exists():
        shutil.rmtree(packaging_venv_dir)

    python_path = _venv_python_path(packaging_venv_dir)
    if not python_path.exists():
        _run([sys.executable, "-m", "venv", str(packaging_venv_dir)], cwd=PROJECT_ROOT)

    _run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], cwd=PROJECT_ROOT)
    _run(
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "pyinstaller==6.8.0",
            f"PySide6=={PYSIDE6_VERSION}",
        ],
        cwd=PROJECT_ROOT,
    )
    return python_path


def _require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required command not found in PATH: {name}")


def _python_can_import(python_path: Path, module_name: str) -> bool:
    result = subprocess.run(
        [str(python_path), "-c", f"import {module_name}"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _cmake_generator_args() -> list[str]:
    if os.name != "nt":
        return []

    if shutil.which("ninja"):
        return ["-G", "Ninja"]
    if shutil.which("mingw32-make") and shutil.which("g++"):
        return ["-G", "MinGW Makefiles"]
    return []


def _find_vswhere() -> Path | None:
    if os.name != "nt":
        return None
    program_files_x86 = os.environ.get("ProgramFiles(x86)") or ""
    if not program_files_x86:
        return None
    candidate = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if candidate.exists():
        return candidate
    return None


def _find_visual_studio_installation() -> Path | None:
    vswhere = _find_vswhere()
    if vswhere is None:
        return None

    result = subprocess.run(
        [
            str(vswhere),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.Component.MSBuild",
            "-property",
            "installationPath",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    installation = result.stdout.strip()
    if not installation:
        return None
    path = Path(installation)
    if not path.exists():
        return None
    return path


def _can_attempt_cuda_build() -> tuple[bool, str | None]:
    if os.name != "nt":
        return False, "CUDA backend currently only targets Windows packaging in this script."
    if shutil.which("nvcc") is None:
        return False, "nvcc not found in PATH."
    if _find_visual_studio_installation() is None:
        return False, "Visual Studio Build Tools were not detected."
    return True, None


def _load_prebuilt_cuda_runtime(
    *,
    cache_root: Path,
    extract_root: Path,
    refresh_vendor_cache: bool,
) -> tuple[Path, list[Path]]:
    archives_dir = cache_root / "archives"
    archive_path = _reuse_cached_file(archives_dir / WHISPER_CUDA_PREBUILT_ARCHIVE)
    if archive_path is None:
        archive_path = _download(WHISPER_CUDA_PREBUILT_URL, archives_dir / WHISPER_CUDA_PREBUILT_ARCHIVE)

    extracted_root = _extract_zip(
        archive_path,
        extract_root / f"whispercpp-cuda-prebuilt-{WHISPER_CUDA_PREBUILT_VERSION}",
        refresh=refresh_vendor_cache,
    )
    whisper_cli = _find_first(extracted_root, ("whisper-cli.exe",))
    if whisper_cli is None:
        raise SystemExit("Failed to locate whisper-cli.exe inside the official whisper.cpp CUDA package")
    dlls = sorted(whisper_cli.parent.glob("*.dll"))
    return whisper_cli, dlls


def _find_cuda_eula() -> Path | None:
    candidates: list[Path] = []
    for env_name in ("CUDA_PATH", "CUDA_PATH_V11_8", "CUDA_PATH_V12_4", "CUDA_PATH_V12_5"):
        value = (os.environ.get(env_name) or "").strip()
        if value:
            candidates.append(Path(value) / "EULA.txt")

    nvcc_path = shutil.which("nvcc")
    if nvcc_path:
        try:
            candidates.append(Path(nvcc_path).resolve().parents[1] / "EULA.txt")
        except Exception:
            pass

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _build_gui_executable(
    *,
    pyinstaller_python: Path,
    release_dir: Path,
    build_root: Path,
) -> None:
    cmd = [
        str(pyinstaller_python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        TOOL_EXE_BASENAME,
        "--distpath",
        str(release_dir),
        "--workpath",
        str(build_root / "work-pyinstaller"),
        "--specpath",
        str(build_root / "spec-pyinstaller"),
        str(PROJECT_ROOT / "tools" / "subtitle_tool.py"),
    ]
    for module_name in DEFAULT_EXCLUDED_MODULES:
        cmd.extend(["--exclude-module", module_name])
    _run(cmd, cwd=PROJECT_ROOT)


def _build_whisper_runtime(
    source_dir: Path,
    build_root: Path,
    *,
    build_dir_name: str,
    generator_args: list[str],
    extra_cmake_args: list[str] | None = None,
) -> tuple[Path, list[Path]]:
    _require_command("cmake")
    whisper_build_dir = build_root / build_dir_name
    if whisper_build_dir.exists():
        shutil.rmtree(whisper_build_dir)

    configure_cmd = [
        "cmake",
        "-S",
        str(source_dir),
        "-B",
        str(whisper_build_dir),
        "-DWHISPER_SDL2=OFF",
        *generator_args,
    ]
    if extra_cmake_args:
        configure_cmd.extend(extra_cmake_args)
    _run(configure_cmd, cwd=PROJECT_ROOT)
    _run(
        [
            "cmake",
            "--build",
            str(whisper_build_dir),
            "--config",
            "Release",
            "--target",
            "whisper-cli",
            "--parallel",
        ],
        cwd=PROJECT_ROOT,
    )

    cli_candidates = [
        whisper_build_dir / "bin" / "Release" / "whisper-cli.exe",
        whisper_build_dir / "bin" / "whisper-cli.exe",
        whisper_build_dir / "Release" / "whisper-cli.exe",
    ]
    whisper_cli = next((path for path in cli_candidates if path.exists()), None)
    if whisper_cli is None:
        raise SystemExit("Failed to locate whisper-cli.exe after building whisper.cpp")

    dlls = sorted(whisper_cli.parent.glob("*.dll"))
    return whisper_cli, dlls


def _resolve_whisper_runtime(
    *,
    source_dir: Path,
    build_root: Path,
    cache_root: Path,
    extract_root: Path,
    backend_mode: str,
    refresh_vendor_cache: bool,
) -> tuple[Path, list[Path], bool]:
    normalized_mode = backend_mode.strip().lower()
    if normalized_mode not in {"auto", "cpu", "cuda"}:
        raise SystemExit(f"Unsupported whisper backend mode: {backend_mode}")

    prebuilt_cuda_error: Exception | None = None
    if normalized_mode in {"auto", "cuda"}:
        try:
            whisper_cli, dlls = _load_prebuilt_cuda_runtime(
                cache_root=cache_root,
                extract_root=extract_root,
                refresh_vendor_cache=refresh_vendor_cache,
            )
            print(f"Using official whisper.cpp CUDA runtime asset: {WHISPER_CUDA_PREBUILT_ARCHIVE}")
            return whisper_cli, dlls, True
        except Exception as exc:
            prebuilt_cuda_error = exc
            if normalized_mode == "cuda":
                print(f"Warning: failed to use official CUDA runtime asset, will try local CUDA build. Detail: {exc}")
            else:
                print(f"Info: official CUDA runtime asset unavailable, falling back to local build or CPU runtime. Detail: {exc}")

    can_attempt_cuda, cuda_reason = _can_attempt_cuda_build()
    if normalized_mode in {"auto", "cuda"}:
        if can_attempt_cuda:
            try:
                whisper_cli, dlls = _build_whisper_runtime(
                    source_dir,
                    build_root,
                    build_dir_name="whispercpp-cuda-build",
                    generator_args=["-G", VISUAL_STUDIO_GENERATOR, "-A", "x64"],
                    extra_cmake_args=[
                        "-DGGML_CUDA=ON",
                    ],
                )
                return whisper_cli, dlls, True
            except subprocess.CalledProcessError as exc:
                if normalized_mode == "cuda":
                    detail = f"Failed to obtain CUDA runtime. official_asset={prebuilt_cuda_error!s}; local_build={exc!s}"
                    raise SystemExit(detail) from exc
                print(f"Warning: CUDA build failed, falling back to CPU-only runtime. Detail: {exc}")
        elif normalized_mode == "cuda":
            raise SystemExit(f"CUDA backend requested but unavailable: official_asset={prebuilt_cuda_error!s}; local_build={cuda_reason}")
        elif cuda_reason:
            print(f"Info: skipping CUDA runtime build, reason: {cuda_reason}")

    whisper_cli, dlls = _build_whisper_runtime(
        source_dir,
        build_root,
        build_dir_name="whispercpp-build",
        generator_args=_cmake_generator_args(),
    )
    return whisper_cli, dlls, False


def _copy_if_exists(src: Path | None, dst: Path) -> None:
    if src is None or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _find_first(root: Path, patterns: tuple[str, ...]) -> Path | None:
    for pattern in patterns:
        matches = sorted(root.rglob(pattern))
        if matches:
            return matches[0]
    return None


def _write_bundle_readme(bundle_dir: Path, *, supports_cuda: bool) -> None:
    gpu_lines = ""
    if supports_cuda:
        gpu_lines = (
            f"- 已内置 whisper.cpp 官方 CUDA {WHISPER_CUDA_PREBUILT_VERSION} Windows x64 runtime\n"
            "- 若机器装有支持 CUDA 的 NVIDIA 显卡，可在“高级设置”里手动启用 GPU 模式\n"
        )
    text = f"""# {TOOL_LABEL}

双击：
  {TOOL_EXE_BASENAME}.exe

功能：
- 选择一个视频目录，批量生成同目录同名 `.srt`
- 默认递归处理子目录
- 默认跳过已存在字幕，必要时可勾选覆盖

内置组件：
- ffmpeg（Windows release essentials）
- whisper.cpp {WHISPER_CPP_VERSION}
- {WHISPER_MODEL_FILE} 默认多语言模型
{gpu_lines}

说明：
- 工具完全在本机离线运行，不会把视频上传到公网
- 工具会直接把字幕生成到视频同目录，无需手动移动文件
- 回到 LearningPyramid 重新打开视频后，会按同目录同名规则直接读取这些字幕
"""
    (bundle_dir / "README.txt").write_text(text, encoding="utf-8", newline="\n")


def _write_update_config(bundle_dir: Path, *, update_base_url: str) -> None:
    base_url = update_base_url.strip().rstrip("/")
    payload = {
        "baseUrl": base_url,
        "catalogUrl": f"{base_url}/api/system/public-downloads",
        "toolId": TOOL_ID,
    }
    (bundle_dir / "update-config.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def _write_build_info(bundle_dir: Path, *, published_at: str) -> None:
    payload = {
        "toolId": TOOL_ID,
        "version": APP_VERSION,
        "publishedAt": published_at,
    }
    (bundle_dir / "build-info.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upsert_catalog_item(output_root: Path, *, zip_path: Path, sha256: str, published_at: str, supports_cuda: bool) -> None:
    catalog_path = output_root / "catalog.json"

    catalog: dict[str, object]
    if catalog_path.exists():
        try:
            loaded = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        catalog = loaded if isinstance(loaded, dict) else {}
    else:
        catalog = {}

    items_raw = catalog.get("items")
    items = [item for item in items_raw if isinstance(item, dict)] if isinstance(items_raw, list) else []
    new_item = {
        "id": TOOL_ID,
        "displayName": TOOL_LABEL,
        "version": APP_VERSION,
        "platform": "windows-x64",
        "summary": (
            "离线扫描视频目录，用内置 ffmpeg + whisper.cpp 生成同目录同名 .srt 字幕，支持可选 NVIDIA CUDA GPU 加速。"
            if supports_cuda
            else "离线扫描视频目录，用内置 ffmpeg + whisper.cpp 生成同目录同名 .srt 字幕。"
        ),
        "assetPath": zip_path.name,
        "publishedAt": published_at,
        "sha256": sha256,
        "sizeBytes": int(zip_path.stat().st_size),
        "recommended": True,
        "includedComponents": [
            "ffmpeg release essentials for Windows",
            f"whisper.cpp {WHISPER_CPP_VERSION}",
            "ggml-base multilingual model",
            *(
                [
                    f"official whisper.cpp CUDA {WHISPER_CUDA_PREBUILT_VERSION} Windows x64 runtime",
                ]
                if supports_cuda
                else []
            ),
        ],
        "requirements": [
            "Windows 10/11 x64",
            "首次转写时请为模型推理预留约 400 MB 内存",
            *(
                [
                    "启用 GPU 模式时需要已安装驱动的 NVIDIA CUDA 显卡",
                ]
                if supports_cuda
                else []
            ),
        ],
    }

    filtered_items = [item for item in items if str(item.get("id") or "").strip() != TOOL_ID]
    filtered_items.append(new_item)
    catalog["generatedAt"] = published_at
    catalog["items"] = filtered_items
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--cache-dir", default=str(PROJECT_ROOT / "build" / "subtitle-tool" / "vendor-cache"))
    parser.add_argument("--pyinstaller-python")
    parser.add_argument("--bootstrap-packaging-venv", action="store_true")
    parser.add_argument("--refresh-packaging-venv", action="store_true")
    parser.add_argument("--packaging-venv-dir", default=str(DEFAULT_PACKAGING_VENV))
    parser.add_argument("--refresh-vendor-cache", action="store_true")
    parser.add_argument("--update-base-url", default=DEFAULT_UPDATE_BASE_URL)
    parser.add_argument("--whisper-backend", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()

    pyinstaller_python = _resolve_pyinstaller_python(
        pyinstaller_python=args.pyinstaller_python,
        bootstrap_packaging_venv=bool(args.bootstrap_packaging_venv),
        refresh_packaging_venv=bool(args.refresh_packaging_venv),
        packaging_venv_dir=Path(args.packaging_venv_dir).resolve(),
    )
    if not _python_can_import(pyinstaller_python, "PySide6"):
        raise SystemExit(
            "PySide6 is not installed in the selected packaging python. "
            "Use --bootstrap-packaging-venv or install PySide6 manually before building."
        )

    output_root = Path(args.output_dir).resolve()
    cache_root = Path(args.cache_dir).resolve()
    bundle_dir = output_root / _bundle_name()
    zip_path = output_root / f"{_bundle_name()}.zip"
    build_root = PROJECT_ROOT / "build" / "subtitle-tool" / "work"
    published_at = _utc_timestamp_text()

    archives_dir = cache_root / "archives"
    extract_dir = cache_root / "extract"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if build_root.exists():
        shutil.rmtree(build_root)
    output_root.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)

    canonical_whisper_zip = archives_dir / f"whisper.cpp-{WHISPER_CPP_VERSION}.zip"
    whisper_source_zip = _reuse_cached_file(
        canonical_whisper_zip,
        archives_dir / f"whisper.cpp-{WHISPER_CPP_VERSION.removeprefix('v')}.zip",
    )
    if whisper_source_zip is None:
        whisper_source_zip = _download(WHISPER_CPP_SOURCE_URL, canonical_whisper_zip)
    whisper_source_dir = _extract_zip(whisper_source_zip, extract_dir / f"whispercpp-{WHISPER_CPP_VERSION}", refresh=bool(args.refresh_vendor_cache))
    _patch_whisper_cpp_for_mingw(whisper_source_dir)

    canonical_ffmpeg_zip = archives_dir / "ffmpeg-release-essentials.zip"
    ffmpeg_zip = _reuse_cached_file(
        canonical_ffmpeg_zip,
        archives_dir / "ffmpeg-8.1-essentials_build.zip",
    )
    if ffmpeg_zip is None:
        ffmpeg_zip = _download(FFMPEG_ZIP_URL, canonical_ffmpeg_zip)
    ffmpeg_extract_dir = _extract_zip(ffmpeg_zip, extract_dir / "ffmpeg-release-essentials", refresh=bool(args.refresh_vendor_cache))
    ffmpeg_exe = _find_first(ffmpeg_extract_dir, ("ffmpeg.exe",))
    if ffmpeg_exe is None:
        raise SystemExit("Failed to locate ffmpeg.exe inside the downloaded FFmpeg package")

    canonical_model_path = cache_root / "models" / WHISPER_MODEL_FILE
    model_path = _reuse_cached_file(
        canonical_model_path,
        archives_dir / WHISPER_MODEL_FILE,
    )
    if model_path is None:
        model_path = _download(WHISPER_MODEL_URL, canonical_model_path)
    whisper_cli, whisper_dlls, supports_cuda = _resolve_whisper_runtime(
        source_dir=whisper_source_dir,
        build_root=build_root,
        cache_root=cache_root,
        extract_root=extract_dir,
        backend_mode=str(args.whisper_backend),
        refresh_vendor_cache=bool(args.refresh_vendor_cache),
    )

    _build_gui_executable(
        pyinstaller_python=pyinstaller_python,
        release_dir=bundle_dir,
        build_root=build_root,
    )

    runtime_dir = bundle_dir / "runtime"
    _copy_if_exists(ffmpeg_exe, runtime_dir / "ffmpeg" / ffmpeg_exe.name)
    _copy_if_exists(model_path, runtime_dir / "models" / model_path.name)
    _copy_if_exists(whisper_cli, runtime_dir / "whispercpp" / whisper_cli.name)
    for dll in whisper_dlls:
        _copy_if_exists(dll, runtime_dir / "whispercpp" / dll.name)

    _copy_if_exists(whisper_source_dir / "LICENSE", bundle_dir / "licenses" / "LICENSE-whisper.cpp.txt")
    ffmpeg_license = _find_first(ffmpeg_extract_dir, ("LICENSE*", "COPYING*", "README*.txt"))
    _copy_if_exists(ffmpeg_license, bundle_dir / "licenses" / "LICENSE-ffmpeg.txt")
    if supports_cuda:
        _copy_if_exists(_find_cuda_eula(), bundle_dir / "licenses" / "LICENSE-nvidia-cuda.txt")

    _write_bundle_readme(bundle_dir, supports_cuda=supports_cuda)
    _write_update_config(bundle_dir, update_base_url=str(args.update_base_url))
    _write_build_info(bundle_dir, published_at=published_at)

    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)
    zip_sha256 = _sha256(zip_path)
    _upsert_catalog_item(output_root, zip_path=zip_path, sha256=zip_sha256, published_at=published_at, supports_cuda=supports_cuda)

    print(f"Subtitle tool bundle directory: {bundle_dir}")
    print(f"Subtitle tool zip: {zip_path}")
    print(f"Subtitle tool sha256: {zip_sha256}")
    print(f"PyInstaller python: {pyinstaller_python}")
    print(f"Whisper backend: {'cuda' if supports_cuda else 'cpu'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
