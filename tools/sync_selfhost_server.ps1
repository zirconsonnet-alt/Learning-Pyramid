param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [string]$ServerUser = "root",
    [string]$RemoteRoot = "/opt/learningpyramid",
    [int]$SshPort = 22,
    [string]$SshKeyPath = "",
    [switch]$SkipBuild,
    [switch]$AllowDirtyWorktree,
    [switch]$PromptOnDirtyWorktree,
    [switch]$DisableSshKey
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-SshKeyPath {
    param([string]$ConfiguredPath)
    $candidates = @()
    if ($ConfiguredPath) {
        $candidates += $ConfiguredPath
    }
    $candidates += (Join-Path $HOME ".ssh\learningpyramid_selfhost_ed25519")
    foreach ($candidate in $candidates) {
        if (-not $candidate) {
            continue
        }
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

function Test-SshKeyAvailableWithoutPrompt {
    param([string]$KeyPath)
    if (-not $KeyPath -or -not (Test-Path $KeyPath)) {
        return $false
    }

    & ssh-keygen -y -P '""' -f $KeyPath *> $null
    if ($LASTEXITCODE -eq 0) {
        return $true
    }

    $pubPath = "${KeyPath}.pub"
    $sshAdd = Get-Command ssh-add -ErrorAction SilentlyContinue
    if ($sshAdd -and (Test-Path $pubPath)) {
        $expectedPublicKey = (Get-Content -Raw $pubPath).Trim()
        if ($expectedPublicKey) {
            $agentKeys = @(& ssh-add -L 2>$null)
            if ($LASTEXITCODE -eq 0 -and $agentKeys -contains $expectedPublicKey) {
                return $true
            }
        }
    }

    return $false
}

function Test-SshKeyAcceptedByServer {
    param(
        [string]$KeyPath,
        [string]$ServerHost,
        [string]$ServerUser,
        [int]$SshPort
    )
    if (-not $KeyPath -or -not (Test-Path $KeyPath)) {
        return $false
    }

    $testArgs = @(
        "-o", "BatchMode=yes",
        "-o", "PreferredAuthentications=publickey",
        "-o", "PubkeyAuthentication=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=10",
        "-i", $KeyPath,
        "-p", "$SshPort",
        "${ServerUser}@${ServerHost}",
        "printf 'ssh-key-ok\n'"
    )
    & ssh @testArgs *> $null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-InstallProjectSshKey {
    param(
        [string]$RepoRoot,
        [string]$ServerHost,
        [string]$ServerUser,
        [int]$SshPort,
        [string]$SshKeyPath,
        [switch]$ReplaceExistingKey,
        [switch]$NoKeyPassphrase
    )
    $installScript = Join-Path $RepoRoot "tools/install_selfhost_ssh_key.ps1"
    if (-not (Test-Path $installScript)) {
        throw "SSH key install script not found: $installScript"
    }

    $installArgs = @{
        ServerHost = $ServerHost
        ServerUser = $ServerUser
        SshPort = $SshPort
    }
    if ($SshKeyPath) {
        $installArgs.SshKeyPath = $SshKeyPath
    }
    if ($ReplaceExistingKey) {
        $installArgs.ReplaceExistingKey = $true
    }
    if ($NoKeyPassphrase) {
        $installArgs.NoKeyPassphrase = $true
    }

    & $installScript @installArgs
}

function Ensure-ProjectSshKeyReady {
    param(
        [string]$RepoRoot,
        [string]$ServerHost,
        [string]$ServerUser,
        [int]$SshPort,
        [string]$ConfiguredSshKeyPath
    )
    $resolvedSshKeyPath = Resolve-SshKeyPath -ConfiguredPath $ConfiguredSshKeyPath
    if (-not $resolvedSshKeyPath) {
        Write-Host "Project SSH key not found locally. Creating and installing one now..."
        Invoke-InstallProjectSshKey -RepoRoot $RepoRoot -ServerHost $ServerHost -ServerUser $ServerUser -SshPort $SshPort -SshKeyPath $ConfiguredSshKeyPath -NoKeyPassphrase
        $resolvedSshKeyPath = Resolve-SshKeyPath -ConfiguredPath $ConfiguredSshKeyPath
        if (-not $resolvedSshKeyPath) {
            throw "Project SSH key was not created successfully."
        }
        return $resolvedSshKeyPath
    }

    if (-not (Test-SshKeyAvailableWithoutPrompt -KeyPath $resolvedSshKeyPath)) {
        Write-Warning "Project SSH key exists locally but is locked behind a forgotten or unavailable passphrase."
        Write-Host "Rotating it to a no-passphrase deploy key and reinstalling it on the server..."
        Invoke-InstallProjectSshKey -RepoRoot $RepoRoot -ServerHost $ServerHost -ServerUser $ServerUser -SshPort $SshPort -SshKeyPath $resolvedSshKeyPath -ReplaceExistingKey -NoKeyPassphrase
        $resolvedSshKeyPath = Resolve-SshKeyPath -ConfiguredPath $ConfiguredSshKeyPath
        if (-not $resolvedSshKeyPath) {
            throw "Project SSH key rotation did not produce a usable key."
        }
        return $resolvedSshKeyPath
    }

    if (-not (Test-SshKeyAcceptedByServer -KeyPath $resolvedSshKeyPath -ServerHost $ServerHost -ServerUser $ServerUser -SshPort $SshPort)) {
        Write-Host "Project SSH key is ready locally but not installed on the server. Installing it now..."
        Invoke-InstallProjectSshKey -RepoRoot $RepoRoot -ServerHost $ServerHost -ServerUser $ServerUser -SshPort $SshPort -SshKeyPath $resolvedSshKeyPath
        return $resolvedSshKeyPath
    }

    return $resolvedSshKeyPath
}

function Assert-CleanGitWorktree {
    param(
        [string]$RepoRoot,
        [switch]$AllowDirty,
        [switch]$PromptOnDirty
    )
    if ($AllowDirty) {
        return
    }
    $gitDir = Join-Path $RepoRoot ".git"
    if (-not (Test-Path $gitDir)) {
        return
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        return
    }
    $statusLines = @(& git -C $RepoRoot status --short)
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed"
    }
    if ($statusLines.Count -eq 0) {
        return
    }
    $preview = ($statusLines | Select-Object -First 20) -join [Environment]::NewLine
    if ($PromptOnDirty) {
        Write-Warning "Git worktree is dirty. Deploying now will include local uncommitted changes."
        Write-Host $preview
        $confirmation = Read-Host "Continue deploy with dirty worktree? [y/N]"
        if ($confirmation -match '^(?i:y|yes)$') {
            return
        }
        throw "Deploy cancelled because git worktree is dirty.`n$preview"
    }
    throw "Git worktree is dirty. Commit or stash changes before deploying, or rerun with -AllowDirtyWorktree.`n$preview"
}

function Get-LatestBundlePath {
    param([string]$RepoRoot)
    $releaseDir = Join-Path $RepoRoot "release"
    $bundle = Get-ChildItem -Path $releaseDir -Filter "LearningPyramid-*-selfhost-source.zip" |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if ($null -eq $bundle) {
        throw "No self-host bundle zip found under $releaseDir"
    }
    return $bundle.FullName
}

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action,
        [Parameter(Mandatory = $true)]
        [string]$Description,
        [int]$MaxAttempts = 6,
        [int]$DelaySeconds = 2
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return (& $Action)
        }
        catch {
            if ($attempt -ge $MaxAttempts) {
                throw
            }
            Write-Warning "${Description} failed on attempt ${attempt}/${MaxAttempts}. Retrying in ${DelaySeconds}s. $($_.Exception.Message)"
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function New-DeployPayloadArchive {
    param(
        [string]$BundlePath,
        [string]$ScratchRoot
    )
    $tempRoot = Join-Path $ScratchRoot ("learningpyramid-deploy-payload-" + [guid]::NewGuid().ToString("N"))
    $stageDir = Join-Path $tempRoot "payload"
    try {
        New-Item -ItemType Directory -Path $stageDir -Force | Out-Null
        Invoke-WithRetry -Description "Staging self-host bundle" -Action {
            Copy-Item -Path $BundlePath -Destination (Join-Path $stageDir "latest.zip") -Force
        }
        $archivePath = Join-Path $tempRoot "learningpyramid-deploy-payload.zip"
        Invoke-WithRetry -Description "Compressing deploy payload" -Action {
            Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $archivePath -CompressionLevel Optimal -Force
        }
        return @{
            TempRoot = $tempRoot
            ArchivePath = $archivePath
        }
    }
    catch {
        Remove-PathIfPresent -Path $tempRoot
        throw
    }
}

function Remove-PathIfPresent {
    param([string]$Path)
    if (-not $Path) {
        return
    }
    if (Test-Path $Path) {
        Remove-Item -Path $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Get-DeployScratchRoot {
    param([string]$RepoRoot)
    $scratchRoot = Join-Path $RepoRoot "release\.deploy-work"
    New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
    return $scratchRoot
}

function Remove-StaleDeployTempDirectories {
    param([string[]]$Roots)
    $patterns = @(
        "learningpyramid-deploy-payload-*"
    )
    foreach ($root in $Roots) {
        if (-not $root -or -not (Test-Path $root)) {
            continue
        }
        foreach ($pattern in $patterns) {
            Get-ChildItem -Path $root -Directory -Filter $pattern -ErrorAction SilentlyContinue |
                ForEach-Object {
                    Remove-PathIfPresent -Path $_.FullName
                }
        }
    }
}

function Start-SshConnectionReuse {
    param(
        [string[]]$BaseSshArgs,
        [string]$Destination
    )
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("learningpyramid-ssh-" + [System.IO.Path]::GetRandomFileName().Replace(".", ""))
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    $controlPath = Join-Path $tempRoot "mux"
    $controlArgs = @(
        "-o", "ControlMaster=auto",
        "-o", "ControlPersist=30m",
        "-o", "ControlPath=$controlPath"
    )
    $openArgs = @($BaseSshArgs + $controlArgs + @("-M", "-N", "-f", $Destination))

    Write-Host "Opening reusable SSH session..."
    Write-Host "Authenticate now; the same connection will be reused for upload and remote deploy."
    & ssh @openArgs
    if ($LASTEXITCODE -ne 0) {
        Remove-PathIfPresent -Path $tempRoot
        throw "Failed to establish reusable SSH session."
    }

    return @{
        TempRoot = $tempRoot
        ControlArgs = $controlArgs
    }
}

function Stop-SshConnectionReuse {
    param(
        [string[]]$BaseSshArgs,
        [string[]]$ControlArgs,
        [string]$Destination,
        [string]$TempRoot
    )
    try {
        if ($ControlArgs -and $Destination) {
            $closeArgs = @($BaseSshArgs + $ControlArgs + @("-O", "exit", $Destination))
            & ssh @closeArgs *> $null
        }
    }
    finally {
        Remove-PathIfPresent -Path $TempRoot
    }
}

function Invoke-SshPreflightAuthCheck {
    param(
        [string[]]$BaseSshArgs,
        [string]$Destination
    )
    $checkArgs = @($BaseSshArgs + @($Destination, "printf 'ssh-auth-ok\n'"))
    Write-Host "Checking SSH authentication before upload..."
    & ssh @checkArgs
    if ($LASTEXITCODE -ne 0) {
        throw "SSH authentication check failed before upload."
    }
}

Require-Command python
Require-Command scp
Require-Command ssh
Require-Command ssh-keygen

$repoRoot = Get-RepoRoot
Assert-CleanGitWorktree -RepoRoot $repoRoot -AllowDirty:$AllowDirtyWorktree -PromptOnDirty:$PromptOnDirtyWorktree
$deployScratchRoot = Get-DeployScratchRoot -RepoRoot $repoRoot
Remove-StaleDeployTempDirectories -Roots @([System.IO.Path]::GetTempPath(), $deployScratchRoot)

$sshCommonArgs = @(
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=8",
    "-o", "TCPKeepAlive=yes",
    "-o", "ConnectTimeout=15"
)
$resolvedSshKeyPath = $null
if ($DisableSshKey) {
    $sshCommonArgs += @(
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=password,keyboard-interactive"
    )
    Write-Host "SSH auth mode: interactive password / keyboard-interactive"
}
else {
    $resolvedSshKeyPath = Ensure-ProjectSshKeyReady -RepoRoot $repoRoot -ServerHost $ServerHost -ServerUser $ServerUser -SshPort $SshPort -ConfiguredSshKeyPath $SshKeyPath
    $sshCommonArgs += @("-o", "PreferredAuthentications=publickey,password,keyboard-interactive")
    $sshCommonArgs += @("-i", $resolvedSshKeyPath, "-o", "IdentitiesOnly=yes")
    Write-Host "Using SSH key: $resolvedSshKeyPath"
}

$baseScpArgs = @($sshCommonArgs + @("-P", "$SshPort"))
$baseSshArgs = @($sshCommonArgs + @("-p", "$SshPort"))
$scpArgs = @($baseScpArgs)
$sshArgs = @($baseSshArgs)

if (-not $SkipBuild) {
    Write-Host "Building self-host bundle..."
    & python (Join-Path $repoRoot "tools/build_selfhost_bundle.py") --build-frontend
    if ($LASTEXITCODE -ne 0) {
        throw "build_selfhost_bundle.py failed"
    }
}

$bundlePath = Get-LatestBundlePath -RepoRoot $repoRoot
$bundleHash = (Get-FileHash -Path $bundlePath -Algorithm SHA256).Hash.ToUpperInvariant()
$remotePayloadPath = "$RemoteRoot/upload/deploy-payload.zip"
$remoteTarget = "${ServerUser}@${ServerHost}:${remotePayloadPath}"
$payloadArchiveTempRoot = $null
$payloadArchivePath = $null
$sshReuseTempRoot = $null
$sshReuseControlArgs = @()
$sshDestination = "${ServerUser}@${ServerHost}"

$payloadInfo = New-DeployPayloadArchive -BundlePath $bundlePath -ScratchRoot $deployScratchRoot
$payloadArchiveTempRoot = $payloadInfo.TempRoot
$payloadArchivePath = $payloadInfo.ArchivePath

try {
    $supportsSshConnectionReuse = $true
    if (($null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue) -and $IsWindows) -or $env:OS -eq "Windows_NT") {
        $supportsSshConnectionReuse = $false
    }

    if ($supportsSshConnectionReuse) {
        try {
            $sshReuseInfo = Start-SshConnectionReuse -BaseSshArgs $baseSshArgs -Destination $sshDestination
            $sshReuseTempRoot = $sshReuseInfo.TempRoot
            $sshReuseControlArgs = $sshReuseInfo.ControlArgs
            $scpArgs = @($baseScpArgs + $sshReuseControlArgs)
            $sshArgs = @($baseSshArgs + $sshReuseControlArgs)
        }
        catch {
            Write-Warning "Reusable SSH session setup failed. Falling back to a preflight auth check before upload."
            Invoke-SshPreflightAuthCheck -BaseSshArgs $baseSshArgs -Destination $sshDestination
        }
    }
    else {
        Write-Host "SSH connection reuse is unavailable on this machine. Running auth check before upload."
        Invoke-SshPreflightAuthCheck -BaseSshArgs $baseSshArgs -Destination $sshDestination
    }

    Write-Host "Uploading deploy payload: $payloadArchivePath"
    & scp @scpArgs $payloadArchivePath $remoteTarget
    if ($LASTEXITCODE -ne 0) {
        throw "scp upload failed"
    }

    $remoteScript = @"
set -euo pipefail

REMOTE_ROOT='$RemoteRoot'
APP_DIR="`$REMOTE_ROOT/app"
TMP_DIR="`$REMOTE_ROOT/release-tmp"
PAYLOAD_PATH="`$REMOTE_ROOT/upload/deploy-payload.zip"
ZIP_PATH="`$REMOTE_ROOT/upload/latest.zip"
EXPECTED_HASH='$bundleHash'

mkdir -p "`$REMOTE_ROOT/upload" "`$TMP_DIR" "`$APP_DIR"

if [ ! -f "`$APP_DIR/.env" ]; then
  echo "Remote .env not found at `$APP_DIR/.env. Copy .env.selfhost.example to .env on the server and edit secrets first." >&2
  exit 1
fi

read_env() {
  local name="`$1"
  grep "^`$name=" "`$APP_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

looks_like_placeholder() {
  case "`$1" in
    *change-me*|*CHANGE-ME*|*replace-me*|*REPLACE-ME*)
      return 0
      ;;
  esac
  return 1
}

MEDIA_ACCESS_TOKEN_SECRET=`$(read_env PLM_MEDIA_ACCESS_TOKEN_SECRET)
POSTGRES_PASSWORD=`$(read_env PLM_POSTGRES_PASSWORD)
ALLOW_SIGNUP=`$(printf '%s' "`$(read_env PLM_ALLOW_SIGNUP)" | tr '[:upper:]' '[:lower:]')
SECURE_COOKIES=`$(printf '%s' "`$(read_env PLM_SECURE_COOKIES)" | tr '[:upper:]' '[:lower:]')
PUBLIC_ORIGIN=`$(read_env PLM_PUBLIC_ORIGIN)
TRUSTED_HOSTS_RAW=`$(read_env PLM_TRUSTED_HOSTS)

if [ -z "`$MEDIA_ACCESS_TOKEN_SECRET" ] || looks_like_placeholder "`$MEDIA_ACCESS_TOKEN_SECRET"; then
  echo "PLM_MEDIA_ACCESS_TOKEN_SECRET must be set to a non-placeholder value in `$APP_DIR/.env before deploy." >&2
  exit 1
fi

if [ -z "`$POSTGRES_PASSWORD" ] || [ "`$POSTGRES_PASSWORD" = "learningpyramid" ] || looks_like_placeholder "`$POSTGRES_PASSWORD"; then
  echo "PLM_POSTGRES_PASSWORD still looks unset or example-like in `$APP_DIR/.env. Update it before deploy." >&2
  exit 1
fi

if [ "`$ALLOW_SIGNUP" = "1" ] || [ "`$ALLOW_SIGNUP" = "true" ] || [ "`$ALLOW_SIGNUP" = "yes" ] || [ "`$ALLOW_SIGNUP" = "on" ]; then
  echo "Warning: PLM_ALLOW_SIGNUP=true keeps the hosted deployment open for self-registration." >&2
fi

if [ "`$SECURE_COOKIES" != "1" ] && [ "`$SECURE_COOKIES" != "true" ] && [ "`$SECURE_COOKIES" != "yes" ] && [ "`$SECURE_COOKIES" != "on" ]; then
  echo "Warning: PLM_SECURE_COOKIES is disabled. Use that only for temporary plain-HTTP localhost testing." >&2
fi

if [ -z "`$PUBLIC_ORIGIN" ]; then
  echo "Warning: PLM_PUBLIC_ORIGIN is empty. Set it before public deployment." >&2
fi

if [ -z "`$TRUSTED_HOSTS_RAW" ]; then
  echo "Warning: PLM_TRUSTED_HOSTS is empty. Set it before public deployment." >&2
fi

if [ ! -f "`$PAYLOAD_PATH" ]; then
  echo "Deploy payload not found: `$PAYLOAD_PATH" >&2
  exit 1
fi

rm -f "`$ZIP_PATH"
unzip -o "`$PAYLOAD_PATH" -d "`$REMOTE_ROOT/upload" >/dev/null

ACTUAL_HASH=`$(sha256sum "`$ZIP_PATH" | awk '{print toupper(`$1)}')
if [ "`$ACTUAL_HASH" != "`$EXPECTED_HASH" ]; then
  echo "Bundle SHA256 mismatch: expected=`$EXPECTED_HASH actual=`$ACTUAL_HASH" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  apt-get update
  apt-get install -y rsync
fi

rm -rf "`$TMP_DIR"/*
unzip -o "`$ZIP_PATH" -d "`$TMP_DIR" >/dev/null

SRC_DIR=`$(find "`$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
if [ -z "`$SRC_DIR" ]; then
  echo "Could not find extracted bundle directory under `$TMP_DIR" >&2
  exit 1
fi

rsync -a --delete --exclude '.env' --exclude 'data/' --exclude 'release/' "`$SRC_DIR"/ "`$APP_DIR"/

cd "`$APP_DIR"
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  up -d --build

docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  ps

PUBLIC_HOST=`$(grep '^PLM_PUBLIC_HOST=' .env | cut -d= -f2- | tr -d '\r' | xargs || true)
TRUSTED_HOSTS=`$(grep '^PLM_TRUSTED_HOSTS=' .env | cut -d= -f2- | tr -d '\r' | xargs || true)
HOST_HEADER="`$PUBLIC_HOST"
if [ -z "`$HOST_HEADER" ] && [ -n "`$TRUSTED_HOSTS" ]; then
  HOST_HEADER=`$(printf '%s' "`$TRUSTED_HOSTS" | cut -d, -f1 | xargs)
fi
if [ -z "`$HOST_HEADER" ]; then
  HOST_HEADER="localhost"
fi

ATTEMPTS=30
SLEEP_SECONDS=3
i=1
while [ `$i -le `$ATTEMPTS ]; do
  if curl -fsS -H "Host: `$HOST_HEADER" http://127.0.0.1:8001/api/health; then
    echo
    if curl -fsS -H "Host: `$HOST_HEADER" http://127.0.0.1:8001/api/system/capabilities >/dev/null; then
      echo "Smoke check passed: /api/system/capabilities"
      exit 0
    fi
    echo "Smoke check failed: /api/system/capabilities" >&2
    break
  fi
  echo "Health check not ready yet (`$i/`$ATTEMPTS), retrying in `$SLEEP_SECONDS s..."
  sleep `$SLEEP_SECONDS
  i=`$((i + 1))
done

echo "Health check did not become ready in time." >&2
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  ps >&2
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  logs --tail=80 app >&2 || true
exit 1
"@

    Write-Host "Deploying on server..."
    $remoteScript | & ssh @sshArgs $sshDestination bash -s
    if ($LASTEXITCODE -ne 0) {
        throw "Remote deploy failed. See remote output above."
    }
}
finally {
    Stop-SshConnectionReuse -BaseSshArgs $baseSshArgs -ControlArgs $sshReuseControlArgs -Destination $sshDestination -TempRoot $sshReuseTempRoot
    Remove-PathIfPresent -Path $payloadArchiveTempRoot
}

Write-Host ""
Write-Host "Deploy finished."
Write-Host "Server host: $ServerHost"
