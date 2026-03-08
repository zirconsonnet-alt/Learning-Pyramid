from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system.version import APP_NAME, APP_PACKAGE_NAME, APP_VERSION, LAUNCHER_EXE_BASENAME, SERVER_EXE_BASENAME, STOP_EXE_BASENAME


DEFAULT_PACKAGING_VENV = PROJECT_ROOT / "build" / "packaging-venv"
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
    "tkinter",
    "torch",
    "torchaudio",
    "torchvision",
    "traitlets",
)


def _bundle_name() -> str:
    return f"{APP_PACKAGE_NAME}-{APP_VERSION}-windows-standalone"


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=str(cwd), check=True)


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
            "-r",
            str(PROJECT_ROOT / "requirements.txt"),
            "pyinstaller==6.8.0",
        ],
        cwd=PROJECT_ROOT,
    )
    return python_path


def _ensure_frontend_dist(*, build_frontend: bool) -> None:
    dist_index = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if build_frontend:
        _run(["pnpm", "build"], cwd=PROJECT_ROOT / "frontend")
    if not dist_index.exists():
        raise SystemExit("frontend/dist is missing. Run `pnpm -C frontend build` first.")


def _build_executable(
    *,
    name: str,
    script: Path,
    release_dir: Path,
    build_root: Path,
    pyinstaller_python: Path,
    excluded_modules: tuple[str, ...],
    add_data: list[tuple[Path, str]] | None = None,
) -> None:
    cmd = [
        str(pyinstaller_python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(release_dir),
        "--workpath",
        str(build_root / f"work-{name}"),
        "--specpath",
        str(build_root / f"spec-{name}"),
        str(script),
    ]
    for module_name in excluded_modules:
        cmd.extend(["--exclude-module", module_name])
    for src, dst in add_data or []:
        cmd.extend(["--add-data", f"{src}{';'}{dst}"])
    _run(cmd, cwd=PROJECT_ROOT)


def _write_readme(dst: Path) -> None:
    text = f"""# {APP_NAME} {APP_VERSION} standalone

Start:
  Double-click `{LAUNCHER_EXE_BASENAME}.exe`

Stop:
  Double-click `{STOP_EXE_BASENAME}.exe`

Notes:
- No Python installation is required for this bundle.
- Local Whisper is still external. Install it separately if you want ASR.
- User data is stored in the normal {APP_NAME} app-data directory, not next to this bundle.
"""
    (dst / "START-HERE.txt").write_text(text, encoding="utf-8", newline="\n")


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-frontend", action="store_true")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "release"))
    parser.add_argument("--pyinstaller-python")
    parser.add_argument("--bootstrap-packaging-venv", action="store_true")
    parser.add_argument("--refresh-packaging-venv", action="store_true")
    parser.add_argument("--packaging-venv-dir", default=str(DEFAULT_PACKAGING_VENV))
    args = parser.parse_args()

    _ensure_frontend_dist(build_frontend=args.build_frontend)
    pyinstaller_python = _resolve_pyinstaller_python(
        pyinstaller_python=args.pyinstaller_python,
        bootstrap_packaging_venv=args.bootstrap_packaging_venv,
        refresh_packaging_venv=args.refresh_packaging_venv,
        packaging_venv_dir=Path(args.packaging_venv_dir).resolve(),
    )

    output_root = Path(args.output_dir).resolve()
    bundle_dir = output_root / _bundle_name()
    zip_path = output_root / f"{_bundle_name()}.zip"
    build_root = PROJECT_ROOT / "build" / "standalone"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if build_root.exists():
        shutil.rmtree(build_root)
    output_root.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)

    _build_executable(
        name=LAUNCHER_EXE_BASENAME,
        script=PROJECT_ROOT / "tools" / "launch_plm.py",
        release_dir=bundle_dir,
        build_root=build_root,
        pyinstaller_python=pyinstaller_python,
        excluded_modules=DEFAULT_EXCLUDED_MODULES,
    )
    _build_executable(
        name=STOP_EXE_BASENAME,
        script=PROJECT_ROOT / "tools" / "stop_plm.py",
        release_dir=bundle_dir,
        build_root=build_root,
        pyinstaller_python=pyinstaller_python,
        excluded_modules=DEFAULT_EXCLUDED_MODULES,
    )
    _build_executable(
        name=SERVER_EXE_BASENAME,
        script=PROJECT_ROOT / "tools" / "run_server.py",
        release_dir=bundle_dir,
        build_root=build_root,
        pyinstaller_python=pyinstaller_python,
        excluded_modules=DEFAULT_EXCLUDED_MODULES,
        add_data=[
            (PROJECT_ROOT / "frontend" / "dist", "frontend/dist"),
            (PROJECT_ROOT / "tools" / "local_whisper_service.py", "tools"),
        ],
    )

    shutil.copy2(PROJECT_ROOT / "README.md", bundle_dir / "README.md")
    _write_readme(bundle_dir)

    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)

    print(f"Standalone bundle directory: {bundle_dir}")
    print(f"Standalone bundle zip: {zip_path}")
    print(f"PyInstaller python: {pyinstaller_python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
