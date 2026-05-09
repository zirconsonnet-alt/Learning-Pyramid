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

from backend.system.version import (
    APP_ID,
    APP_NAME,
    APP_PACKAGE_NAME,
    APP_VERSION,
    LAUNCHER_EXE_BASENAME,
    STOP_EXE_BASENAME,
)


def _standalone_bundle_name() -> str:
    return f"{APP_PACKAGE_NAME}-{APP_VERSION}-windows-standalone"


def _installer_bundle_name() -> str:
    return f"{APP_PACKAGE_NAME}-{APP_VERSION}-windows-installer"


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=str(cwd), check=True)


def _standalone_bundle_dir(output_root: Path) -> Path:
    return output_root / _standalone_bundle_name()


def _standalone_bundle_zip(output_root: Path) -> Path:
    return output_root / f"{_standalone_bundle_name()}.zip"


def _installer_bundle_dir(output_root: Path) -> Path:
    return output_root / _installer_bundle_name()


def _installer_bundle_zip(output_root: Path) -> Path:
    return output_root / f"{_installer_bundle_name()}.zip"


def _locate_iscc() -> Path | None:
    env_path = os.getenv("ISCC_EXE", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        if candidate.exists():
            return candidate

    candidates = (
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _ensure_standalone_bundle(
    *,
    output_root: Path,
    build_frontend: bool,
    bootstrap_packaging_venv: bool,
    refresh_packaging_venv: bool,
    pyinstaller_python: str | None,
    rebuild_standalone: bool,
) -> tuple[Path, Path]:
    bundle_dir = _standalone_bundle_dir(output_root)
    bundle_zip = _standalone_bundle_zip(output_root)
    should_rebuild = rebuild_standalone or build_frontend or bootstrap_packaging_venv or refresh_packaging_venv or bool(pyinstaller_python)
    if not should_rebuild and bundle_dir.exists() and bundle_zip.exists():
        return bundle_dir, bundle_zip

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "build_windows_standalone.py"),
        "--output-dir",
        str(output_root),
    ]
    if build_frontend:
        cmd.append("--build-frontend")
    if bootstrap_packaging_venv:
        cmd.append("--bootstrap-packaging-venv")
    if refresh_packaging_venv:
        cmd.append("--refresh-packaging-venv")
    if pyinstaller_python:
        cmd.extend(["--pyinstaller-python", pyinstaller_python])
    _run(cmd, cwd=PROJECT_ROOT)
    return bundle_dir, bundle_zip


def _write_batch_launcher(path: Path, ps1_name: str) -> None:
    content = f"""@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0{ps1_name}" %*
"""
    path.write_text(content, encoding="utf-8", newline="\r\n")


def _write_install_script(path: Path, payload_zip_name: str) -> None:
    content = f"""param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\\{APP_ID}"),
    [switch]$DesktopShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

function New-Shortcut {{
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory,
        [string]$Arguments = ""
    )
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Arguments = $Arguments
    $shortcut.IconLocation = $TargetPath
    $shortcut.Save()
}}

$payloadZip = Join-Path $PSScriptRoot "payload\\{payload_zip_name}"
if (-not (Test-Path $payloadZip)) {{
    throw "Installer payload missing: $payloadZip"
}}

$tempRoot = Join-Path $env:TEMP ("learning-pyramid-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {{
    Expand-Archive -Path $payloadZip -DestinationPath $tempRoot -Force
    $bundleDir = Get-ChildItem -Path $tempRoot -Directory | Select-Object -First 1
    if ($null -eq $bundleDir) {{
        throw "Failed to locate extracted {APP_NAME} bundle."
    }}

    if (Test-Path $InstallDir) {{
        $stopExe = Join-Path $InstallDir "{STOP_EXE_BASENAME}.exe"
        if (Test-Path $stopExe) {{
            & $stopExe | Out-Null
            Start-Sleep -Milliseconds 500
        }}
        Remove-Item -Path $InstallDir -Recurse -Force
    }}

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Copy-Item -Path (Join-Path $bundleDir.FullName "*") -Destination $InstallDir -Recurse -Force

    $uninstallPs = Join-Path $InstallDir "Uninstall-LearningPyramid.ps1"
    @'
param([switch]$RemoveData)

$ErrorActionPreference = "Stop"
$installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dataDir = Join-Path $env:LOCALAPPDATA "{APP_ID}"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\{APP_ID}"
$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "{APP_ID}.lnk"
$stopExe = Join-Path $installDir "{STOP_EXE_BASENAME}.exe"

if (Test-Path $stopExe) {{
    & $stopExe | Out-Null
    Start-Sleep -Milliseconds 500
}}
if (Test-Path $startMenuDir) {{
    Remove-Item -Path $startMenuDir -Recurse -Force
}}
if (Test-Path $desktopLink) {{
    Remove-Item -Path $desktopLink -Force
}}
if (Test-Path $installDir) {{
    Remove-Item -Path $installDir -Recurse -Force
}}
if ($RemoveData -and (Test-Path $dataDir)) {{
    Remove-Item -Path $dataDir -Recurse -Force
}}
Write-Host "{APP_NAME} removed."
'@ | Set-Content -Path $uninstallPs -Encoding UTF8

    @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-LearningPyramid.ps1" %*
'@ | Set-Content -Path (Join-Path $InstallDir "Uninstall-LearningPyramid.bat") -Encoding ASCII
    Copy-Item -Path $uninstallPs -Destination (Join-Path $InstallDir "Uninstall-PLM3.ps1") -Force
    Copy-Item -Path (Join-Path $InstallDir "Uninstall-LearningPyramid.bat") -Destination (Join-Path $InstallDir "Uninstall-PLM3.bat") -Force

    $metadata = [ordered]@{{
        app = "{APP_NAME}"
        version = "{APP_VERSION}"
        installDir = $InstallDir
        installedAt = (Get-Date).ToString("o")
    }} | ConvertTo-Json
    Set-Content -Path (Join-Path $InstallDir "install-metadata.json") -Value $metadata -Encoding UTF8

    $startMenuDir = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\{APP_ID}"
    New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null
    New-Shortcut -ShortcutPath (Join-Path $startMenuDir "{APP_ID}.lnk") -TargetPath (Join-Path $InstallDir "{LAUNCHER_EXE_BASENAME}.exe") -WorkingDirectory $InstallDir
    New-Shortcut -ShortcutPath (Join-Path $startMenuDir "Uninstall {APP_ID}.lnk") -TargetPath "powershell.exe" -WorkingDirectory $InstallDir -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$uninstallPs`""

    if ($DesktopShortcut) {{
        $desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "{APP_ID}.lnk"
        New-Shortcut -ShortcutPath $desktopLink -TargetPath (Join-Path $InstallDir "{LAUNCHER_EXE_BASENAME}.exe") -WorkingDirectory $InstallDir
    }}

    if (-not $NoLaunch) {{
        Start-Process -FilePath (Join-Path $InstallDir "{LAUNCHER_EXE_BASENAME}.exe") -WorkingDirectory $InstallDir
    }}

    Write-Host "{APP_NAME} installed to $InstallDir"
}} finally {{
    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}}
"""
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_readme(path: Path) -> None:
    content = f"""# {APP_NAME} {APP_VERSION} installer

Run `Install-LearningPyramid.bat` to install {APP_NAME} into `%LOCALAPPDATA%\\Programs\\{APP_ID}`.

Options:
- `Install-LearningPyramid.bat -DesktopShortcut`
- `Install-LearningPyramid.bat -NoLaunch`

Uninstall:
- Start menu: `{APP_ID} > Uninstall {APP_ID}`
- Or run `%LOCALAPPDATA%\\Programs\\{APP_ID}\\Uninstall-LearningPyramid.bat`

Notes:
- App binaries live under `%LOCALAPPDATA%\\Programs\\{APP_ID}`
- User data stays under `%LOCALAPPDATA%\\{APP_ID}`
- The default uninstall keeps user data unless you pass `-RemoveData`
"""
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_inno_script(path: Path, standalone_dir: Path) -> None:
    source_dir = standalone_dir.resolve()
    content = f"""#define MyAppName "{APP_NAME}"
#define MyAppVersion "{APP_VERSION}"
#define MyAppSource "{source_dir}"

[Setup]
AppId={APP_ID}-{APP_VERSION}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
DefaultDirName={{localappdata}}\\Programs\\{APP_ID}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={path.parent}
OutputBaseFilename={APP_PACKAGE_NAME}-{APP_VERSION}-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "{{#MyAppSource}}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{autoprograms}}\\{APP_ID}"; Filename: "{{app}}\\{LAUNCHER_EXE_BASENAME}.exe"
Name: "{{autoprograms}}\\Uninstall {APP_ID}"; Filename: "{{uninstallexe}}"

[Run]
Filename: "{{app}}\\{LAUNCHER_EXE_BASENAME}.exe"; Description: "Launch {APP_NAME}"; Flags: nowait postinstall skipifsilent
"""
    path.write_text(content, encoding="utf-8", newline="\n")


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "release"))
    parser.add_argument("--build-frontend", action="store_true")
    parser.add_argument("--bootstrap-packaging-venv", action="store_true")
    parser.add_argument("--refresh-packaging-venv", action="store_true")
    parser.add_argument("--pyinstaller-python")
    parser.add_argument("--rebuild-standalone", action="store_true")
    parser.add_argument("--skip-inno", action="store_true")
    args = parser.parse_args()

    output_root = Path(args.output_dir).resolve()
    standalone_dir, standalone_zip = _ensure_standalone_bundle(
        output_root=output_root,
        build_frontend=args.build_frontend,
        bootstrap_packaging_venv=args.bootstrap_packaging_venv,
        refresh_packaging_venv=args.refresh_packaging_venv,
        pyinstaller_python=args.pyinstaller_python,
        rebuild_standalone=args.rebuild_standalone,
    )

    installer_dir = _installer_bundle_dir(output_root)
    installer_zip = _installer_bundle_zip(output_root)
    payload_dir = installer_dir / "payload"

    if installer_dir.exists():
        shutil.rmtree(installer_dir)
    installer_dir.mkdir(parents=True, exist_ok=True)
    payload_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(standalone_zip, payload_dir / standalone_zip.name)
    _write_install_script(installer_dir / "Install-LearningPyramid.ps1", standalone_zip.name)
    _write_batch_launcher(installer_dir / "Install-LearningPyramid.bat", "Install-LearningPyramid.ps1")
    shutil.copy2(installer_dir / "Install-LearningPyramid.ps1", installer_dir / "Install-PLM3.ps1")
    shutil.copy2(installer_dir / "Install-LearningPyramid.bat", installer_dir / "Install-PLM3.bat")
    _write_readme(installer_dir / "README.txt")

    inno_script_path = installer_dir / "LearningPyramid.iss"
    _write_inno_script(inno_script_path, standalone_dir)

    installer_exe_path = None
    if not args.skip_inno:
        iscc_path = _locate_iscc()
        if iscc_path is not None:
            _run([str(iscc_path), str(inno_script_path)], cwd=installer_dir)
            installer_exe_path = installer_dir / f"{APP_PACKAGE_NAME}-{APP_VERSION}-Setup.exe"

    if installer_zip.exists():
        installer_zip.unlink()
    _create_zip(installer_dir, installer_zip)

    print(f"Installer bundle directory: {installer_dir}")
    print(f"Installer bundle zip: {installer_zip}")
    if installer_exe_path is not None and installer_exe_path.exists():
        print(f"Inno Setup installer: {installer_exe_path}")
    else:
        print("Inno Setup installer: skipped (ISCC.exe not found or --skip-inno)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
