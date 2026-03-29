from __future__ import annotations

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

WHISPER_CPP_VERSION = "v1.8.4"
WHISPER_CPP_SOURCE_URL = f"https://github.com/ggml-org/whisper.cpp/archive/refs/tags/{WHISPER_CPP_VERSION}.zip"
WHISPER_MODEL_FILE = "ggml-base.bin"
WHISPER_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin?download=true"
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

DEFAULT_EXCLUDED_MODULES = (
    "IPython",
    "PIL",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
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
    _run([str(python_path), "-m", "pip", "install", "pyinstaller==6.8.0"], cwd=PROJECT_ROOT)
    return python_path


def _require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required command not found in PATH: {name}")


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


def _locate_whisper_cli(source_dir: Path, build_root: Path) -> tuple[Path, list[Path]]:
    _require_command("cmake")
    whisper_build_dir = build_root / "whispercpp-build"
    if whisper_build_dir.exists():
        shutil.rmtree(whisper_build_dir)

    _run(["cmake", "-S", str(source_dir), "-B", str(whisper_build_dir), "-DWHISPER_SDL2=OFF"], cwd=PROJECT_ROOT)
    _run(["cmake", "--build", str(whisper_build_dir), "--config", "Release", "--target", "whisper-cli"], cwd=PROJECT_ROOT)

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


def _write_bundle_readme(bundle_dir: Path) -> None:
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

说明：
- 工具完全在本机离线运行，不会把视频上传到公网
- 生成的字幕文件可被 LearningPyramid 直接识别为播放器字幕和 AI 补充上下文
"""
    (bundle_dir / "README.txt").write_text(text, encoding="utf-8", newline="\n")


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


def _upsert_catalog_item(output_root: Path, *, zip_path: Path, sha256: str) -> None:
    catalog_path = output_root / "catalog.json"
    published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

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
        "summary": "离线扫描视频目录，用内置 ffmpeg + whisper.cpp 生成同目录同名 .srt 字幕。",
        "assetPath": zip_path.name,
        "publishedAt": published_at,
        "sha256": sha256,
        "sizeBytes": int(zip_path.stat().st_size),
        "recommended": True,
        "includedComponents": [
            "ffmpeg release essentials for Windows",
            f"whisper.cpp {WHISPER_CPP_VERSION}",
            "ggml-base multilingual model",
        ],
        "requirements": [
            "Windows 10/11 x64",
            "首次转写时请为模型推理预留约 400 MB 内存",
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
    args = parser.parse_args()

    pyinstaller_python = _resolve_pyinstaller_python(
        pyinstaller_python=args.pyinstaller_python,
        bootstrap_packaging_venv=bool(args.bootstrap_packaging_venv),
        refresh_packaging_venv=bool(args.refresh_packaging_venv),
        packaging_venv_dir=Path(args.packaging_venv_dir).resolve(),
    )

    output_root = Path(args.output_dir).resolve()
    cache_root = Path(args.cache_dir).resolve()
    bundle_dir = output_root / _bundle_name()
    zip_path = output_root / f"{_bundle_name()}.zip"
    build_root = PROJECT_ROOT / "build" / "subtitle-tool"

    archives_dir = cache_root / "archives"
    extract_dir = cache_root / "extract"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if build_root.exists():
        shutil.rmtree(build_root)
    output_root.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)

    whisper_source_zip = _download(WHISPER_CPP_SOURCE_URL, archives_dir / f"whisper.cpp-{WHISPER_CPP_VERSION}.zip")
    whisper_source_dir = _extract_zip(whisper_source_zip, extract_dir / f"whispercpp-{WHISPER_CPP_VERSION}", refresh=bool(args.refresh_vendor_cache))

    ffmpeg_zip = _download(FFMPEG_ZIP_URL, archives_dir / "ffmpeg-release-essentials.zip")
    ffmpeg_extract_dir = _extract_zip(ffmpeg_zip, extract_dir / "ffmpeg-release-essentials", refresh=bool(args.refresh_vendor_cache))
    ffmpeg_exe = _find_first(ffmpeg_extract_dir, ("ffmpeg.exe",))
    if ffmpeg_exe is None:
        raise SystemExit("Failed to locate ffmpeg.exe inside the downloaded FFmpeg package")

    model_path = _download(WHISPER_MODEL_URL, cache_root / "models" / WHISPER_MODEL_FILE)
    whisper_cli, whisper_dlls = _locate_whisper_cli(whisper_source_dir, build_root)

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

    _write_bundle_readme(bundle_dir)

    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)
    zip_sha256 = _sha256(zip_path)
    _upsert_catalog_item(output_root, zip_path=zip_path, sha256=zip_sha256)

    print(f"Subtitle tool bundle directory: {bundle_dir}")
    print(f"Subtitle tool zip: {zip_path}")
    print(f"Subtitle tool sha256: {zip_sha256}")
    print(f"PyInstaller python: {pyinstaller_python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
