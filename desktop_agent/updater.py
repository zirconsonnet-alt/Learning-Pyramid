from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode, urljoin

import requests

from backend.system.versioning import compare_versions


def _default_install_dir() -> Path:
    local_appdata = str(os.getenv("LOCALAPPDATA") or "").strip()
    if local_appdata:
        return Path(local_appdata).expanduser().resolve() / "Programs" / "LearningPyramidDesktopAgent"
    return Path.home().resolve() / "LearningPyramidDesktopAgent"


@dataclass(frozen=True, slots=True)
class DesktopAgentUpdateCheckResult:
    available: bool
    update_available: bool
    current_version: str
    latest_version: str | None = None
    download_url: str | None = None
    published_at: str | None = None
    asset_name: str | None = None
    asset_kind: str | None = None
    sha256: str | None = None
    integrity_mode: str | None = None
    signature_status: str | None = None
    signature_subject: str | None = None
    silent_install_supported: bool = False
    silent_install_strategy: str | None = None
    release_notes: str | None = None


@dataclass(frozen=True, slots=True)
class DesktopAgentPreparedUpdate:
    current_version: str
    latest_version: str
    download_url: str
    asset_name: str
    asset_kind: str
    asset_path: Path
    sha256: str
    integrity_mode: str
    signature_status: str | None = None
    signature_subject: str | None = None
    silent_install_supported: bool = False
    silent_install_strategy: str | None = None


@dataclass(frozen=True, slots=True)
class DesktopAgentSilentInstallPlan:
    command: tuple[str, ...]
    helper_script_path: Path
    rollback_script_path: Path
    state_path: Path
    backup_dir: Path
    log_path: Path
    relaunch_exe_path: Path


class DesktopAgentUpdater:
    def __init__(
        self,
        *,
        request_get: Callable[..., requests.Response] = requests.get,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.request_get = request_get
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def check_for_updates(self, *, server_url: str, current_version: str) -> DesktopAgentUpdateCheckResult:
        normalized_server_url = str(server_url).strip().rstrip("/")
        normalized_current_version = str(current_version).strip()
        query = urlencode({"currentVersion": normalized_current_version})
        response = self.request_get(
            f"{normalized_server_url}/api/system/desktop-agent-release?{query}",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = dict(response.json()["data"])
        latest = payload.get("latest")
        if not payload.get("available") or not isinstance(latest, dict):
            return DesktopAgentUpdateCheckResult(
                available=False,
                update_available=False,
                current_version=normalized_current_version,
            )
        preferred_asset = latest.get("preferredAsset") or {}
        download_path = str(preferred_asset.get("downloadPath") or "").strip()
        download_url = urljoin(f"{normalized_server_url}/", download_path.lstrip("/")) if download_path else None
        latest_version = str(latest.get("version") or "").strip() or None
        if latest_version is None:
            return DesktopAgentUpdateCheckResult(
                available=False,
                update_available=False,
                current_version=normalized_current_version,
            )
        update_available = bool(payload.get("updateAvailable"))
        if not update_available:
            try:
                update_available = compare_versions(normalized_current_version, latest_version) < 0
            except ValueError:
                update_available = True
        signature = preferred_asset.get("signature") or {}
        silent_install = preferred_asset.get("silentInstall") or {}
        return DesktopAgentUpdateCheckResult(
            available=True,
            update_available=update_available,
            current_version=normalized_current_version,
            latest_version=latest_version,
            download_url=download_url,
            published_at=None if latest.get("publishedAt") is None else str(latest.get("publishedAt")),
            asset_name=None if preferred_asset.get("name") is None else str(preferred_asset.get("name")),
            asset_kind=None if preferred_asset.get("kind") is None else str(preferred_asset.get("kind")),
            sha256=None if preferred_asset.get("sha256") is None else str(preferred_asset.get("sha256")).lower(),
            integrity_mode=None if preferred_asset.get("integrityMode") is None else str(preferred_asset.get("integrityMode")),
            signature_status=None if signature.get("status") is None else str(signature.get("status")).upper(),
            signature_subject=None if signature.get("subject") is None else str(signature.get("subject")),
            silent_install_supported=bool(silent_install.get("supported")),
            silent_install_strategy=None if silent_install.get("strategy") is None else str(silent_install.get("strategy")),
            release_notes=None if latest.get("releaseNotes") is None else str(latest.get("releaseNotes")),
        )

    def prepare_update(
        self,
        *,
        server_url: str,
        current_version: str,
        target_dir: str | Path,
        require_signed: bool = False,
    ) -> DesktopAgentPreparedUpdate:
        result = self.check_for_updates(server_url=server_url, current_version=current_version)
        if not result.available or not result.update_available:
            raise RuntimeError("desktop agent update is not available")
        if not result.download_url or not result.asset_name or not result.asset_kind:
            raise RuntimeError("desktop agent release is missing a downloadable asset")
        if not result.sha256:
            raise RuntimeError("desktop agent release is missing sha256 integrity metadata")
        if require_signed and str(result.signature_status or "").upper() != "SIGNED":
            raise RuntimeError("desktop agent release is not signed")

        staging_dir = Path(target_dir).expanduser().resolve()
        staging_dir.mkdir(parents=True, exist_ok=True)
        destination = staging_dir / result.asset_name
        partial_path = destination.with_suffix(destination.suffix + ".partial")
        if partial_path.exists():
            partial_path.unlink()

        response = self.request_get(result.download_url, timeout=max(30.0, self.timeout_seconds * 6), stream=True)
        response.raise_for_status()
        digest = hashlib.sha256()
        with partial_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                digest.update(chunk)
        actual_sha256 = digest.hexdigest().lower()
        expected_sha256 = result.sha256.lower()
        if actual_sha256 != expected_sha256:
            partial_path.unlink(missing_ok=True)
            raise RuntimeError("desktop agent update sha256 mismatch")
        if destination.exists():
            destination.unlink()
        partial_path.rename(destination)
        return DesktopAgentPreparedUpdate(
            current_version=result.current_version,
            latest_version=str(result.latest_version),
            download_url=str(result.download_url),
            asset_name=str(result.asset_name),
            asset_kind=str(result.asset_kind),
            asset_path=destination,
            sha256=expected_sha256,
            integrity_mode=str(result.integrity_mode or "sha256"),
            signature_status=result.signature_status,
            signature_subject=result.signature_subject,
            silent_install_supported=bool(result.silent_install_supported),
            silent_install_strategy=result.silent_install_strategy,
        )

    @staticmethod
    def _helper_script_text(
        *,
        install_dir: Path,
        relaunch_exe_path: Path,
        state_path: Path,
        backup_dir: Path,
        rollback_script_path: Path,
    ) -> str:
        install_dir_text = str(install_dir)
        relaunch_exe_path_text = str(relaunch_exe_path)
        state_path_text = str(state_path)
        backup_dir_text = str(backup_dir)
        rollback_script_path_text = str(rollback_script_path)
        return textwrap.dedent(
            f"""
            param(
                [int]$WaitPid,
                [string]$AssetPath,
                [string]$AssetKind,
                [string]$LogPath,
                [string]$CurrentVersion,
                [string]$TargetVersion,
                [switch]$Relaunch
            )

            $ErrorActionPreference = "Stop"

            function Ensure-ParentDirectory {{
                param([string]$PathValue)
                $dir = Split-Path -Parent $PathValue
                if ($dir -and -not (Test-Path $dir)) {{
                    New-Item -ItemType Directory -Path $dir -Force | Out-Null
                }}
            }}

            function Write-UpdateLog {{
                param([string]$Message)
                Ensure-ParentDirectory -PathValue $LogPath
                Add-Content -Path $LogPath -Value ("[{0}] {1}" -f (Get-Date -Format o), $Message)
            }}

            function Set-UpdateState {{
                param(
                    [string]$Status,
                    [string]$Message,
                    [string]$InstalledVersion
                )
                Ensure-ParentDirectory -PathValue "{state_path_text}"
                $payload = @{{
                    status = $Status
                    message = $Message
                    current_version = $CurrentVersion
                    target_version = $TargetVersion
                    installed_version = $InstalledVersion
                    updated_at = (Get-Date -Format o)
                    log_path = $LogPath
                    backup_dir = "{backup_dir_text}"
                    rollback_script_path = "{rollback_script_path_text}"
                    asset_path = $AssetPath
                    asset_kind = $AssetKind
                    relaunch_exe_path = "{relaunch_exe_path_text}"
                }}
                $payload | ConvertTo-Json -Depth 4 | Set-Content -Path "{state_path_text}" -Encoding UTF8
            }}

            function Restore-Backup {{
                param([bool]$LaunchAfterRestore)
                if (-not (Test-Path "{backup_dir_text}")) {{
                    Set-UpdateState -Status "FAILED" -Message "Update failed and no backup was available." -InstalledVersion $CurrentVersion
                    return $false
                }}
                Write-UpdateLog "restoring previous install from backup"
                if (Test-Path "{install_dir_text}") {{
                    Remove-Item -Path "{install_dir_text}" -Recurse -Force
                }}
                New-Item -ItemType Directory -Path "{install_dir_text}" -Force | Out-Null
                Copy-Item -Path (Join-Path "{backup_dir_text}" "*") -Destination "{install_dir_text}" -Recurse -Force
                Set-UpdateState -Status "ROLLED_BACK" -Message ("Rolled back to " + $CurrentVersion) -InstalledVersion $CurrentVersion
                if ($LaunchAfterRestore -and (Test-Path "{relaunch_exe_path_text}")) {{
                    Write-UpdateLog "relaunching rolled back desktop agent"
                    Start-Process -FilePath "{relaunch_exe_path_text}" -WorkingDirectory "{install_dir_text}"
                }}
                return $true
            }}

            Write-UpdateLog ("waiting for process " + $WaitPid + " to exit")
            while ($WaitPid -gt 0 -and (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue)) {{
                Start-Sleep -Seconds 1
            }}

            if (-not (Test-Path $AssetPath)) {{
                throw "Update asset missing: $AssetPath"
            }}

            Set-UpdateState -Status "INSTALLING" -Message ("Installing " + $TargetVersion) -InstalledVersion $CurrentVersion
            if (Test-Path "{backup_dir_text}") {{
                Remove-Item -Path "{backup_dir_text}" -Recurse -Force
            }}
            if (Test-Path "{install_dir_text}") {{
                New-Item -ItemType Directory -Path "{backup_dir_text}" -Force | Out-Null
                Copy-Item -Path (Join-Path "{install_dir_text}" "*") -Destination "{backup_dir_text}" -Recurse -Force
                Write-UpdateLog "backed up previous install"
            }}

            try {{
                if ($AssetKind -eq "installer_exe") {{
                    Write-UpdateLog "running Inno Setup silent installer"
                    $proc = Start-Process -FilePath $AssetPath -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-") -PassThru -Wait
                    if ($proc.ExitCode -ne 0) {{
                        throw "Installer exited with code $($proc.ExitCode)"
                    }}
                }} elseif ($AssetKind -eq "installer_zip") {{
                    Write-UpdateLog "running ZIP installer payload"
                    $extractRoot = Join-Path $env:TEMP ("learningpyramid-desktop-agent-update-" + [guid]::NewGuid().ToString("N"))
                    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
                    try {{
                        Expand-Archive -Path $AssetPath -DestinationPath $extractRoot -Force
                        $bundleDir = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
                        if ($null -eq $bundleDir) {{
                            throw "Failed to locate extracted installer bundle."
                        }}
                        $installScript = Join-Path $bundleDir.FullName "Install-LearningPyramidDesktopAgent.ps1"
                        if (-not (Test-Path $installScript)) {{
                            throw "Installer script missing: $installScript"
                        }}
                        & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript -NoLaunch
                    }} finally {{
                        Remove-Item -Path $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
                    }}
                }} else {{
                    throw "Silent update is not supported for asset kind: $AssetKind"
                }}

                if (-not (Test-Path "{relaunch_exe_path_text}")) {{
                    throw "Installed desktop agent executable is missing after update."
                }}
                Write-UpdateLog "running post-install healthcheck"
                $health = Start-Process -FilePath "{relaunch_exe_path_text}" -ArgumentList @("healthcheck") -PassThru -Wait -WindowStyle Hidden
                if ($health.ExitCode -ne 0) {{
                    throw "Installed desktop agent healthcheck failed with code $($health.ExitCode)"
                }}

                Set-UpdateState -Status "SUCCEEDED" -Message ("Installed " + $TargetVersion) -InstalledVersion $TargetVersion
                if ($Relaunch -and (Test-Path "{relaunch_exe_path_text}")) {{
                    Write-UpdateLog "relaunching updated desktop agent"
                    Start-Process -FilePath "{relaunch_exe_path_text}" -WorkingDirectory "{install_dir_text}"
                }}
            }} catch {{
                $message = $_.Exception.Message
                Write-UpdateLog ("update failed: " + $message)
                if (-not (Restore-Backup -LaunchAfterRestore $Relaunch.IsPresent)) {{
                    Set-UpdateState -Status "FAILED" -Message $message -InstalledVersion $CurrentVersion
                }}
                throw
            }}
            """
        ).strip() + "\n"

    @staticmethod
    def _rollback_script_text(
        *,
        install_dir: Path,
        relaunch_exe_path: Path,
        state_path: Path,
        backup_dir: Path,
        rollback_script_path: Path,
        current_version: str,
        target_version: str,
    ) -> str:
        install_dir_text = str(install_dir)
        relaunch_exe_path_text = str(relaunch_exe_path)
        state_path_text = str(state_path)
        backup_dir_text = str(backup_dir)
        rollback_script_path_text = str(rollback_script_path)
        current_version_text = str(current_version)
        target_version_text = str(target_version)
        return textwrap.dedent(
            f"""
            param(
                [int]$WaitPid,
                [switch]$Relaunch
            )

            $ErrorActionPreference = "Stop"

            while ($WaitPid -gt 0 -and (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue)) {{
                Start-Sleep -Seconds 1
            }}

            if (-not (Test-Path "{backup_dir_text}")) {{
                throw "Rollback backup missing: {backup_dir_text}"
            }}

            if (Test-Path "{install_dir_text}") {{
                Remove-Item -Path "{install_dir_text}" -Recurse -Force
            }}
            New-Item -ItemType Directory -Path "{install_dir_text}" -Force | Out-Null
            Copy-Item -Path (Join-Path "{backup_dir_text}" "*") -Destination "{install_dir_text}" -Recurse -Force

            $payload = @{{
                status = "ROLLED_BACK"
                message = "Manual rollback to {current_version_text}"
                current_version = "{current_version_text}"
                target_version = "{target_version_text}"
                installed_version = "{current_version_text}"
                updated_at = (Get-Date -Format o)
                log_path = $null
                backup_dir = "{backup_dir_text}"
                rollback_script_path = "{rollback_script_path_text}"
                asset_path = $null
                asset_kind = $null
                relaunch_exe_path = "{relaunch_exe_path_text}"
            }}
            $payload | ConvertTo-Json -Depth 4 | Set-Content -Path "{state_path_text}" -Encoding UTF8

            if ($Relaunch -and (Test-Path "{relaunch_exe_path_text}")) {{
                Start-Process -FilePath "{relaunch_exe_path_text}" -WorkingDirectory "{install_dir_text}"
            }}
            """
        ).strip() + "\n"

    def build_silent_install_plan(
        self,
        prepared: DesktopAgentPreparedUpdate,
        *,
        current_pid: int,
        helper_dir: str | Path,
        relaunch: bool = True,
        install_dir: str | Path | None = None,
    ) -> DesktopAgentSilentInstallPlan:
        if not prepared.silent_install_supported:
            raise RuntimeError("desktop agent release does not support silent install")
        helper_root = Path(helper_dir).expanduser().resolve()
        helper_root.mkdir(parents=True, exist_ok=True)
        helper_script_path = helper_root / "apply-desktop-agent-update.ps1"
        rollback_script_path = helper_root / "rollback-desktop-agent-update.ps1"
        state_path = helper_root / "update-state.json"
        log_path = helper_root / "apply-desktop-agent-update.log"
        backup_dir = helper_root / "backup-current"
        resolved_install_dir = Path(install_dir).expanduser().resolve() if install_dir is not None else _default_install_dir()
        relaunch_exe_path = resolved_install_dir / "LearningPyramidDesktopAgent.exe"
        helper_script_path.write_text(
            self._helper_script_text(
                install_dir=resolved_install_dir,
                relaunch_exe_path=relaunch_exe_path,
                state_path=state_path,
                backup_dir=backup_dir,
                rollback_script_path=rollback_script_path,
            ),
            encoding="utf-8",
        )
        rollback_script_path.write_text(
            self._rollback_script_text(
                install_dir=resolved_install_dir,
                relaunch_exe_path=relaunch_exe_path,
                state_path=state_path,
                backup_dir=backup_dir,
                rollback_script_path=rollback_script_path,
                current_version=prepared.current_version,
                target_version=prepared.latest_version,
            ),
            encoding="utf-8",
        )
        command = (
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper_script_path),
            "-WaitPid",
            str(max(0, int(current_pid))),
            "-AssetPath",
            str(prepared.asset_path),
            "-AssetKind",
            prepared.asset_kind,
            "-LogPath",
            str(log_path),
            "-CurrentVersion",
            prepared.current_version,
            "-TargetVersion",
            prepared.latest_version,
            *(() if not relaunch else ("-Relaunch",)),
        )
        return DesktopAgentSilentInstallPlan(
            command=command,
            helper_script_path=helper_script_path,
            rollback_script_path=rollback_script_path,
            state_path=state_path,
            backup_dir=backup_dir,
            log_path=log_path,
            relaunch_exe_path=relaunch_exe_path,
        )

    @staticmethod
    def cleanup_update_staging(path: str | Path) -> None:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            return
        target.unlink(missing_ok=True)


def default_update_staging_dir(base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir).expanduser().resolve() if base_dir is not None else Path(tempfile.gettempdir()).resolve()
    return root / "LearningPyramidDesktopAgent" / "updates"
