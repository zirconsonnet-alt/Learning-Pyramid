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

from backend.system.version import APP_VERSION
from tools.build_windows_standalone import DEFAULT_EXCLUDED_MODULES, _resolve_pyinstaller_python


AGENT_EXE_BASENAME = "LearningPyramidDesktopAgent"
AGENT_EXCLUDED_MODULES = tuple(
    module_name for module_name in DEFAULT_EXCLUDED_MODULES if module_name not in {"PIL", "tkinter", "PySide6"}
)


def _ensure_agent_ui_runtime(pyinstaller_python: Path, *, install_missing: bool) -> None:
    command = [
        str(pyinstaller_python),
        "-c",
        "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PySide6') else 1)",
    ]
    result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
    if result.returncode == 0:
        return
    if not install_missing:
        raise SystemExit("PySide6 is required to build the desktop agent UI. Install it into the PyInstaller python, or rerun with --bootstrap-packaging-venv.")
    _run([str(pyinstaller_python), "-m", "pip", "install", "PySide6==6.8.2.1"], cwd=PROJECT_ROOT)


def _bundle_name() -> str:
    return f"LearningPyramidDesktopAgent-{APP_VERSION}-windows-standalone"


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=str(cwd), check=True)


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def _default_server_url() -> str:
    return str(os.getenv("PLM_DESKTOP_AGENT_DEFAULT_SERVER_URL") or os.getenv("PLM_PUBLIC_ORIGIN") or "").strip().rstrip("/")


def _write_readme(dst: Path) -> None:
    default_server_url = _default_server_url()
    server_hint = default_server_url or "<this hosted server>"
    text = f"""# LearningPyramid Desktop Agent {APP_VERSION}

Quick start:
  1. Double-click {AGENT_EXE_BASENAME}.exe
  2. Click "登录并接入"
  3. Log into your LearningPyramid account
  4. Select a project and logical root
  5. Choose the local folder once
  6. Click "保存并启动连接器"

CLI:
  {AGENT_EXE_BASENAME}.exe ui
  {AGENT_EXE_BASENAME}.exe tray
  {AGENT_EXE_BASENAME}.exe run
  {AGENT_EXE_BASENAME}.exe pair --server-url https://your-host --pairing-code ABCD-EFGH --project-id proj_xxx --root-dir C:\\Videos

Optional:
  {AGENT_EXE_BASENAME}.exe sync

Notes:
- Launching the exe without arguments opens the setup window.
- After one successful onboarding, later launches can start the saved connector without logging in again.
- Default server: {server_hint}
- The agent stores its config under APPDATA\\LearningPyramidDesktopAgent.
- Runtime logs are written to APPDATA\\LearningPyramidDesktopAgent\\logs\\desktop-agent.log.
- Keep the tray app running while remote devices are watching videos.
- Account login is the primary onboarding path; setup codes remain optional.
"""
    (dst / "START-HERE.txt").write_text(text, encoding="utf-8", newline="\n")


def _write_server_default(dst: Path) -> None:
    default_server_url = _default_server_url()
    if not default_server_url:
        return
    (dst / "server-default.txt").write_text(default_server_url + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "release"))
    parser.add_argument("--pyinstaller-python")
    parser.add_argument("--bootstrap-packaging-venv", action="store_true")
    parser.add_argument("--refresh-packaging-venv", action="store_true")
    parser.add_argument("--packaging-venv-dir", default=str(PROJECT_ROOT / "build" / "packaging-venv"))
    args = parser.parse_args()

    pyinstaller_python = _resolve_pyinstaller_python(
        pyinstaller_python=args.pyinstaller_python,
        bootstrap_packaging_venv=args.bootstrap_packaging_venv,
        refresh_packaging_venv=args.refresh_packaging_venv,
        packaging_venv_dir=Path(args.packaging_venv_dir).resolve(),
    )
    _ensure_agent_ui_runtime(
        pyinstaller_python,
        install_missing=bool(args.bootstrap_packaging_venv or args.refresh_packaging_venv),
    )

    output_root = Path(args.output_dir).resolve()
    bundle_dir = output_root / _bundle_name()
    zip_path = output_root / f"{_bundle_name()}.zip"
    build_root = PROJECT_ROOT / "build" / "desktop-agent"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if build_root.exists():
        shutil.rmtree(build_root)
    output_root.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(pyinstaller_python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--name",
        AGENT_EXE_BASENAME,
        "--distpath",
        str(bundle_dir),
        "--workpath",
        str(build_root / "work"),
        "--specpath",
        str(build_root / "spec"),
        str(PROJECT_ROOT / "desktop_agent" / "main.py"),
    ]
    for module_name in AGENT_EXCLUDED_MODULES:
        cmd.extend(["--exclude-module", module_name])
    _run(cmd, cwd=PROJECT_ROOT)

    shutil.copy2(PROJECT_ROOT / "README.md", bundle_dir / "README.md")
    _write_readme(bundle_dir)
    _write_server_default(bundle_dir)

    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)

    print(f"Desktop agent bundle directory: {bundle_dir}")
    print(f"Desktop agent bundle zip: {zip_path}")
    print(f"PyInstaller python: {pyinstaller_python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
