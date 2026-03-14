from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system.version import APP_VERSION
from tools.build_windows_desktop_agent import AGENT_EXE_BASENAME


AGENT_APP_ID = "LearningPyramidDesktopAgent"


def _standalone_bundle_name() -> str:
    return f"{AGENT_APP_ID}-{APP_VERSION}-windows-standalone"


def _installer_bundle_name() -> str:
    return f"{AGENT_APP_ID}-{APP_VERSION}-windows-installer"


def _release_manifest_name() -> str:
    return f"{AGENT_APP_ID}-{APP_VERSION}-release.json"


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


def _release_manifest_path(output_root: Path) -> Path:
    return output_root / _release_manifest_name()


def _sha256_text(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_thumbprint(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(ch for ch in str(value).strip() if ch.isalnum()).upper()
    return normalized or None


def _load_release_notes(path_value: str | None) -> str | None:
    normalized = str(path_value or "").strip()
    if not normalized:
        return None
    path = Path(normalized).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"release notes file not found: {path}")
    content = path.read_text(encoding="utf-8").strip()
    return content or None


def _locate_iscc() -> Path | None:
    env_path = os.getenv("ISCC_EXE", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        if candidate.exists():
            return candidate
    for candidate in (
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ):
        if candidate.exists():
            return candidate
    return None


def _locate_signtool(explicit_path: str | None = None) -> Path | None:
    for raw in (
        explicit_path,
        os.getenv("PLM_DESKTOP_AGENT_SIGNTOOL_EXE", "").strip(),
    ):
        normalized = str(raw or "").strip()
        if not normalized:
            continue
        candidate = Path(normalized).expanduser().resolve()
        if candidate.exists():
            return candidate
    which_candidate = shutil.which("signtool.exe") or shutil.which("signtool")
    if which_candidate:
        return Path(which_candidate).resolve()
    return None


def _ensure_standalone_bundle(
    *,
    output_root: Path,
    bootstrap_packaging_venv: bool,
    refresh_packaging_venv: bool,
    pyinstaller_python: str | None,
    rebuild_standalone: bool,
) -> tuple[Path, Path]:
    bundle_dir = _standalone_bundle_dir(output_root)
    bundle_zip = _standalone_bundle_zip(output_root)
    should_rebuild = rebuild_standalone or bootstrap_packaging_venv or refresh_packaging_venv or bool(pyinstaller_python)
    if not should_rebuild and bundle_dir.exists() and bundle_zip.exists():
        return bundle_dir, bundle_zip
    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "build_windows_desktop_agent.py"),
        "--output-dir",
        str(output_root),
    ]
    if bootstrap_packaging_venv:
        command.append("--bootstrap-packaging-venv")
    if refresh_packaging_venv:
        command.append("--refresh-packaging-venv")
    if pyinstaller_python:
        command.extend(["--pyinstaller-python", pyinstaller_python])
    _run(command, cwd=PROJECT_ROOT)
    return bundle_dir, bundle_zip


def _write_batch_launcher(path: Path, ps1_name: str) -> None:
    path.write_text(
        f"""@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0{ps1_name}" %*
""",
        encoding="utf-8",
        newline="\r\n",
    )


def _write_install_script(path: Path, payload_zip_name: str) -> None:
    path.write_text(
        f"""param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\\{AGENT_APP_ID}"),
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

$tempRoot = Join-Path $env:TEMP ("learning-pyramid-desktop-agent-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {{
    Expand-Archive -Path $payloadZip -DestinationPath $tempRoot -Force
    $bundleDir = Get-ChildItem -Path $tempRoot -Directory | Select-Object -First 1
    if ($null -eq $bundleDir) {{
        throw "Failed to locate extracted desktop agent bundle."
    }}

    if (Test-Path $InstallDir) {{
        Remove-Item -Path $InstallDir -Recurse -Force
    }}

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Copy-Item -Path (Join-Path $bundleDir.FullName "*") -Destination $InstallDir -Recurse -Force

    $uninstallPs = Join-Path $InstallDir "Uninstall-LearningPyramidDesktopAgent.ps1"
    @'
param([switch]$RemoveData)

$ErrorActionPreference = "Stop"
$installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dataDir = Join-Path $env:APPDATA "{AGENT_APP_ID}"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\{AGENT_APP_ID}"
$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "{AGENT_APP_ID}.lnk"

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
Write-Host "LearningPyramid Desktop Agent removed."
'@ | Set-Content -Path $uninstallPs -Encoding UTF8

    @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-LearningPyramidDesktopAgent.ps1" %*
'@ | Set-Content -Path (Join-Path $InstallDir "Uninstall-LearningPyramidDesktopAgent.bat") -Encoding ASCII

    $startMenuDir = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\{AGENT_APP_ID}"
    New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null
    New-Shortcut -ShortcutPath (Join-Path $startMenuDir "{AGENT_APP_ID}.lnk") -TargetPath (Join-Path $InstallDir "{AGENT_EXE_BASENAME}.exe") -WorkingDirectory $InstallDir
    New-Shortcut -ShortcutPath (Join-Path $startMenuDir "Uninstall {AGENT_APP_ID}.lnk") -TargetPath "powershell.exe" -WorkingDirectory $InstallDir -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$uninstallPs`""

    if ($DesktopShortcut) {{
        $desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "{AGENT_APP_ID}.lnk"
        New-Shortcut -ShortcutPath $desktopLink -TargetPath (Join-Path $InstallDir "{AGENT_EXE_BASENAME}.exe") -WorkingDirectory $InstallDir
    }}

    if (-not $NoLaunch) {{
        Start-Process -FilePath (Join-Path $InstallDir "{AGENT_EXE_BASENAME}.exe") -WorkingDirectory $InstallDir
    }}

    Write-Host "LearningPyramid Desktop Agent installed to $InstallDir"
}} finally {{
    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}}
""",
        encoding="utf-8",
        newline="\n",
    )


def _write_readme(path: Path) -> None:
    path.write_text(
        f"""# LearningPyramid Desktop Agent {APP_VERSION} installer

Run `Install-LearningPyramidDesktopAgent.bat` to install the desktop agent into `%LOCALAPPDATA%\\Programs\\{AGENT_APP_ID}`.

After install:
- Open the desktop agent
- Click `登录并接入`
- Log into your LearningPyramid account
- Select a project and local folder once
- Click `保存并启动连接器`
- Later launches can start the saved connector directly without re-entering your password

Options:
- `Install-LearningPyramidDesktopAgent.bat -DesktopShortcut`
- `Install-LearningPyramidDesktopAgent.bat -NoLaunch`

Uninstall:
- Start menu: `{AGENT_APP_ID} > Uninstall {AGENT_APP_ID}`
- Or run `%LOCALAPPDATA%\\Programs\\{AGENT_APP_ID}\\Uninstall-LearningPyramidDesktopAgent.bat`
""",
        encoding="utf-8",
        newline="\n",
    )


def _write_inno_script(path: Path, standalone_dir: Path) -> None:
    source_dir = standalone_dir.resolve()
    path.write_text(
        f"""#define MyAppName "LearningPyramid Desktop Agent"
#define MyAppVersion "{APP_VERSION}"
#define MyAppSource "{source_dir}"

[Setup]
AppId={AGENT_APP_ID}-{APP_VERSION}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
DefaultDirName={{localappdata}}\\Programs\\{AGENT_APP_ID}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={path.parent}
OutputBaseFilename={AGENT_APP_ID}-{APP_VERSION}-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "{{#MyAppSource}}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{autoprograms}}\\{AGENT_APP_ID}"; Filename: "{{app}}\\{AGENT_EXE_BASENAME}.exe"

[Run]
Filename: "{{app}}\\{AGENT_EXE_BASENAME}.exe"; Description: "Launch LearningPyramid Desktop Agent"; Flags: nowait postinstall skipifsilent
""",
        encoding="utf-8",
        newline="\n",
    )


def _sign_windows_binary(
    path: Path,
    *,
    signtool_exe: Path,
    cert_sha1: str,
    timestamp_url: str | None,
) -> dict[str, str | None]:
    thumbprint = _normalize_thumbprint(cert_sha1)
    if thumbprint is None:
        raise ValueError("signing certificate thumbprint is required")
    command = [
        str(signtool_exe),
        "sign",
        "/fd",
        "SHA256",
        "/sha1",
        thumbprint,
    ]
    if str(timestamp_url or "").strip():
        command.extend(
            [
                "/tr",
                str(timestamp_url).strip(),
                "/td",
                "SHA256",
            ]
        )
    command.append(str(path))
    _run(command, cwd=path.parent)
    return {
        "status": "SIGNED",
        "subject": None,
        "issuer": None,
        "thumbprint": thumbprint,
        "signedAt": _utc_now_text(),
        "source": "signtool",
    }


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def _signature_payload_for_asset(
    *,
    kind: str,
    installer_signature: dict[str, str | None] | None,
) -> dict[str, str | None]:
    if kind == "installer_exe":
        return dict(
            installer_signature
            or {
                "status": "UNSIGNED",
                "subject": None,
                "issuer": None,
                "thumbprint": None,
                "signedAt": None,
                "source": "generated",
            }
        )
    return {
        "status": "UNSUPPORTED",
        "subject": None,
        "issuer": None,
        "thumbprint": None,
        "signedAt": None,
        "source": "generated",
    }


def _silent_install_payload(kind: str) -> dict[str, str | bool]:
    if kind == "installer_exe":
        return {"supported": True, "strategy": "inno_exe", "relaunch": True}
    if kind == "installer_zip":
        return {"supported": True, "strategy": "powershell_zip", "relaunch": True}
    return {"supported": False, "strategy": "unsupported", "relaunch": False}


def _write_release_manifest(
    *,
    output_root: Path,
    standalone_zip: Path,
    installer_zip: Path,
    installer_exe_path: Path | None,
    release_notes: str | None,
    installer_signature: dict[str, str | None] | None,
) -> Path:
    manifest_assets: dict[str, dict[str, object]] = {}
    asset_specs: list[tuple[str, Path]] = [
        ("standalone_zip", standalone_zip),
        ("installer_zip", installer_zip),
    ]
    if installer_exe_path is not None and installer_exe_path.exists():
        asset_specs.append(("installer_exe", installer_exe_path))
    generated_at = _utc_now_text()
    for kind, path in asset_specs:
        manifest_assets[path.name] = {
            "kind": kind,
            "sizeBytes": int(path.stat().st_size),
            "sha256": _sha256_text(path),
            "publishedAt": generated_at,
            "integrityMode": "sha256",
            "signature": _signature_payload_for_asset(kind=kind, installer_signature=installer_signature),
            "silentInstall": _silent_install_payload(kind),
        }
    payload = {
        "version": APP_VERSION,
        "generatedAt": generated_at,
        "releaseNotes": release_notes,
        "assets": manifest_assets,
    }
    manifest_path = _release_manifest_path(output_root)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "release"))
    parser.add_argument("--bootstrap-packaging-venv", action="store_true")
    parser.add_argument("--refresh-packaging-venv", action="store_true")
    parser.add_argument("--pyinstaller-python")
    parser.add_argument("--rebuild-standalone", action="store_true")
    parser.add_argument("--skip-inno", action="store_true")
    parser.add_argument("--release-notes-file", default=os.getenv("PLM_DESKTOP_AGENT_RELEASE_NOTES_FILE", ""))
    parser.add_argument("--signtool-exe", default=os.getenv("PLM_DESKTOP_AGENT_SIGNTOOL_EXE", ""))
    parser.add_argument("--sign-cert-sha1", default=os.getenv("PLM_DESKTOP_AGENT_SIGN_CERT_SHA1", ""))
    parser.add_argument("--sign-timestamp-url", default=os.getenv("PLM_DESKTOP_AGENT_SIGN_TIMESTAMP_URL", ""))
    args = parser.parse_args()

    output_root = Path(args.output_dir).resolve()
    standalone_dir, standalone_zip = _ensure_standalone_bundle(
        output_root=output_root,
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
    _write_install_script(installer_dir / "Install-LearningPyramidDesktopAgent.ps1", standalone_zip.name)
    _write_batch_launcher(
        installer_dir / "Install-LearningPyramidDesktopAgent.bat",
        "Install-LearningPyramidDesktopAgent.ps1",
    )
    _write_readme(installer_dir / "README.txt")

    inno_script_path = installer_dir / "LearningPyramidDesktopAgent.iss"
    _write_inno_script(inno_script_path, standalone_dir)

    installer_exe_path: Path | None = None
    if not args.skip_inno:
        iscc_path = _locate_iscc()
        if iscc_path is not None:
            _run([str(iscc_path), str(inno_script_path)], cwd=installer_dir)
            installer_exe_path = installer_dir / f"{AGENT_APP_ID}-{APP_VERSION}-Setup.exe"
            if installer_exe_path.exists():
                shutil.copy2(installer_exe_path, output_root / installer_exe_path.name)

    installer_signature: dict[str, str | None] | None = None
    if installer_exe_path is not None and installer_exe_path.exists():
        thumbprint = _normalize_thumbprint(args.sign_cert_sha1)
        if thumbprint:
            signtool_exe = _locate_signtool(args.signtool_exe)
            if signtool_exe is None:
                raise RuntimeError("signtool.exe is required when signing is configured")
            installer_signature = _sign_windows_binary(
                installer_exe_path,
                signtool_exe=signtool_exe,
                cert_sha1=thumbprint,
                timestamp_url=str(args.sign_timestamp_url or "").strip() or None,
            )

    if installer_zip.exists():
        installer_zip.unlink()
    _create_zip(installer_dir, installer_zip)

    release_manifest = _write_release_manifest(
        output_root=output_root,
        standalone_zip=standalone_zip,
        installer_zip=installer_zip,
        installer_exe_path=installer_exe_path,
        release_notes=_load_release_notes(args.release_notes_file),
        installer_signature=installer_signature,
    )

    print(f"Desktop agent installer bundle directory: {installer_dir}")
    print(f"Desktop agent installer bundle zip: {installer_zip}")
    if installer_exe_path is not None and installer_exe_path.exists():
        print(f"Desktop agent Inno Setup installer: {installer_exe_path}")
    else:
        print("Desktop agent Inno Setup installer: skipped (ISCC.exe not found or --skip-inno)")
    print(f"Desktop agent release manifest: {release_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
