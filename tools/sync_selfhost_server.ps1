param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [string]$ServerUser = "root",
    [string]$RemoteRoot = "/opt/learningpyramid",
    [int]$SshPort = 22,
    [string]$SshKeyPath = "",
    [switch]$SkipBuild,
    [switch]$IncludePublicDownloads,
    [switch]$AllowDirtyWorktree,
    [switch]$PromptOnDirtyWorktree,
    [switch]$DisableSshKey
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

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

    $connectHostInfo = Resolve-DeployConnectHost -ServerHost $ServerHost
    $testArgs = @(
        "-o", "BatchMode=yes",
        "-o", "PreferredAuthentications=publickey",
        "-o", "PubkeyAuthentication=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=10"
    )
    if ($connectHostInfo.HostKeyAlias) {
        $testArgs += @("-o", "HostKeyAlias=$($connectHostInfo.HostKeyAlias)")
    }
    $testArgs += @(
        "-i", $KeyPath,
        "-p", "$SshPort",
        "${ServerUser}@$($connectHostInfo.ConnectHost)",
        "printf 'ssh-key-ok\n'"
    )

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $outputLines = @(& ssh @testArgs 2>&1)
        if ($LASTEXITCODE -eq 0) {
            return $true
        }

        $outputText = ($outputLines | Out-String)
        if ($attempt -ge 5 -or -not (Test-IsTransientSshFailure -ExitCode $LASTEXITCODE -OutputText $outputText)) {
            return $false
        }

        Start-Sleep -Seconds 2
    }

    return $false
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

function Test-IsIpAddress {
    param([string]$Value)
    $parsed = $null
    return [System.Net.IPAddress]::TryParse($Value, [ref]$parsed)
}

function Resolve-DeployConnectHost {
    param([string]$ServerHost)
    if (Test-IsIpAddress -Value $ServerHost) {
        return @{
            ConnectHost = $ServerHost
            HostKeyAlias = $null
        }
    }

    $resolvedAddresses = Invoke-WithRetry -Description "Resolving deploy host $ServerHost" -MaxAttempts 6 -DelaySeconds 2 -Action {
        try {
            $addresses = [System.Net.Dns]::GetHostAddresses($ServerHost) |
                Where-Object {
                    $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -or
                    $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetworkV6
                }
            if (-not $addresses -or $addresses.Count -eq 0) {
                throw "No IP address records returned."
            }
            return $addresses
        }
        catch {
            throw "DNS lookup failed for ${ServerHost}: $($_.Exception.Message)"
        }
    }

    $selectedAddress = $resolvedAddresses |
        Sort-Object {
            if ($_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
                0
            }
            else {
                1
            }
        } |
        Select-Object -First 1

    return @{
        ConnectHost = $selectedAddress.IPAddressToString
        HostKeyAlias = $ServerHost
    }
}

function Test-IsTransientSshFailure {
    param(
        [int]$ExitCode,
        [string]$OutputText
    )
    if ($ExitCode -eq 0) {
        return $false
    }

    $retryPatterns = @(
        "Could not resolve hostname",
        "No such host is known",
        "Name or service not known",
        "Temporary failure in name resolution",
        "Connection closed by",
        "kex_exchange_identification",
        "Connection reset by",
        "Connection timed out",
        "Operation timed out",
        "Broken pipe",
        "No route to host",
        "Network is unreachable",
        "Connection refused"
    )

    foreach ($pattern in $retryPatterns) {
        if ($OutputText -like "*$pattern*") {
            return $true
        }
    }

    return ($ExitCode -eq 255)
}

function Invoke-ExternalCommandWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [int]$MaxAttempts = 6,
        [int]$DelaySeconds = 3
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $outputLines = @(& $Command 2>&1)
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }

        foreach ($line in $outputLines) {
            if ($null -ne $line) {
                Write-Host $line
            }
        }

        if ($exitCode -eq 0) {
            return
        }

        $outputText = ($outputLines | Out-String)
        $shouldRetry = Test-IsTransientSshFailure -ExitCode $exitCode -OutputText $outputText
        if (-not $shouldRetry -or $attempt -ge $MaxAttempts) {
            throw "${Description} failed with exit code ${exitCode}."
        }

        Write-Warning "${Description} failed on attempt ${attempt}/${MaxAttempts}. Retrying in ${DelaySeconds}s."
        Start-Sleep -Seconds $DelaySeconds
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
    Invoke-ExternalCommandWithRetry -Description "SSH authentication check" -Command {
        & ssh @checkArgs
    } -MaxAttempts 6 -DelaySeconds 3
}

Require-Command python
Require-Command scp
Require-Command ssh
Require-Command ssh-keygen

$repoRoot = Get-RepoRoot
Assert-CleanGitWorktree -RepoRoot $repoRoot -AllowDirty:$AllowDirtyWorktree -PromptOnDirty:$PromptOnDirtyWorktree
$connectHostInfo = Resolve-DeployConnectHost -ServerHost $ServerHost
$connectHost = $connectHostInfo.ConnectHost

$sshCommonArgs = @(
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=8",
    "-o", "TCPKeepAlive=yes",
    "-o", "ConnectTimeout=15"
)
if ($connectHostInfo.HostKeyAlias) {
    $sshCommonArgs += @("-o", "HostKeyAlias=$($connectHostInfo.HostKeyAlias)")
    Write-Host "Resolved deploy host: $ServerHost -> $connectHost"
}
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
    $buildArgs = @((Join-Path $repoRoot "tools/build_selfhost_bundle.py"), "--build-frontend")
    if ($IncludePublicDownloads) {
        $buildArgs += "--include-public-downloads"
        Write-Host "Including public-downloads/ in the deploy bundle."
    }
    else {
        Write-Host "Skipping public-downloads/ to keep the deploy bundle smaller."
    }
    & python @buildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "build_selfhost_bundle.py failed"
    }
}

$bundlePath = Get-LatestBundlePath -RepoRoot $repoRoot
$bundleItem = Get-Item -LiteralPath $bundlePath
$bundleSizeMb = [math]::Round(($bundleItem.Length / 1MB), 1)
Write-Host "Selected self-host bundle: $bundlePath (${bundleSizeMb} MB)"
if ($SkipBuild -and -not $IncludePublicDownloads -and $bundleItem.Length -gt 100MB) {
    Write-Warning "The latest bundle is still very large. It was probably built earlier with public-downloads included. Re-run once without -SkipBuild to generate a smaller deploy bundle."
}
$bundleHash = (Get-FileHash -Path $bundlePath -Algorithm SHA256).Hash.ToUpperInvariant()
$includePublicDownloadsValue = if ($IncludePublicDownloads) { "1" } else { "0" }
$envSyncFile = Join-Path $repoRoot ".env.selfhost.sync"
$hasEnvSyncFile = Test-Path $envSyncFile
$remoteZipPath = "$RemoteRoot/upload/latest.zip"
$remoteTarget = "${ServerUser}@${connectHost}:${remoteZipPath}"
$remoteEnvSyncPath = "$RemoteRoot/upload/selfhost.env.sync"
$remoteEnvSyncTarget = "${ServerUser}@${connectHost}:${remoteEnvSyncPath}"
$sshReuseTempRoot = $null
$sshReuseControlArgs = @()
$sshDestination = "${ServerUser}@${connectHost}"

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

    Write-Host "Uploading self-host bundle: $bundlePath"
    Invoke-ExternalCommandWithRetry -Description "scp upload" -Command {
        & scp @scpArgs $bundlePath $remoteTarget
    } -MaxAttempts 6 -DelaySeconds 3

    if ($hasEnvSyncFile) {
        Write-Host "Uploading deploy-time env overlay: $envSyncFile"
        Invoke-ExternalCommandWithRetry -Description "scp env overlay upload" -Command {
            & scp @scpArgs $envSyncFile $remoteEnvSyncTarget
        } -MaxAttempts 6 -DelaySeconds 3
    }

$remoteScript = @"
set -euo pipefail

REMOTE_ROOT='$RemoteRoot'
APP_DIR="`$REMOTE_ROOT/app"
TMP_DIR="`$REMOTE_ROOT/release-tmp"
ZIP_PATH="`$REMOTE_ROOT/upload/latest.zip"
EXPECTED_HASH='$bundleHash'
INCLUDE_PUBLIC_DOWNLOADS='$includePublicDownloadsValue'
HAS_ENV_SYNC='$(if ($hasEnvSyncFile) { "1" } else { "0" })'
ENV_SYNC_UPLOAD_PATH="`$REMOTE_ROOT/upload/selfhost.env.sync"

mkdir -p "`$REMOTE_ROOT/upload" "`$TMP_DIR" "`$APP_DIR"

if [ ! -f "`$APP_DIR/.env" ]; then
  echo "Remote .env not found at `$APP_DIR/.env. Copy .env.selfhost.example to .env on the server and edit secrets first." >&2
  exit 1
fi

read_env() {
  local name="`$1"
  grep "^`$name=" "`$APP_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r' || true
}

merge_env_overlay() {
  local dst_file="`$1"
  local src_file="`$2"
  local tmp_file
  tmp_file=`$(mktemp)
  awk '
    BEGIN { n = 0 }
    FNR == NR {
      if (`$0 ~ /^[A-Za-z_][A-Za-z0-9_]*=/) {
        key = `$0
        sub(/=.*/, "", key)
        value = `$0
        sub(/^[^=]*=/, "", value)
        overlay[key] = value
        order[++n] = key
      }
      next
    }
    {
      if (`$0 ~ /^[A-Za-z_][A-Za-z0-9_]*=/) {
        key = `$0
        sub(/=.*/, "", key)
        if (key in overlay) {
          print key "=" overlay[key]
          seen[key] = 1
        } else {
          print `$0
        }
      } else {
        print `$0
      }
    }
    END {
      for (i = 1; i <= n; i++) {
        key = order[i]
        if (!(key in seen)) {
          print key "=" overlay[key]
        }
      }
    }
  ' "`$src_file" "`$dst_file" > "`$tmp_file"
  mv "`$tmp_file" "`$dst_file"
}

looks_like_placeholder() {
  case "`$1" in
    *change-me*|*CHANGE-ME*|*replace-me*|*REPLACE-ME*)
      return 0
      ;;
  esac
  return 1
}

if [ ! -f "`$ZIP_PATH" ]; then
  echo "Deploy bundle not found: `$ZIP_PATH" >&2
  exit 1
fi

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

RSYNC_ARGS=(-a --delete --exclude '.env' --exclude 'data/' --exclude 'release/')
if [ "`$INCLUDE_PUBLIC_DOWNLOADS" != "1" ]; then
  RSYNC_ARGS+=(--exclude 'public-downloads/')
fi
rsync "`${RSYNC_ARGS[@]}" "`$SRC_DIR"/ "`$APP_DIR"/

if [ "`$HAS_ENV_SYNC" = "1" ]; then
  if [ ! -f "`$ENV_SYNC_UPLOAD_PATH" ]; then
    echo "Deploy-time env overlay upload missing: `$ENV_SYNC_UPLOAD_PATH" >&2
    exit 1
  fi
  cp "`$ENV_SYNC_UPLOAD_PATH" "`$APP_DIR/.env.selfhost.sync"
else
  rm -f "`$APP_DIR/.env.selfhost.sync" "`$ENV_SYNC_UPLOAD_PATH"
fi

if [ -f "`$APP_DIR/.env.selfhost.sync" ]; then
  merge_env_overlay "`$APP_DIR/.env" "`$APP_DIR/.env.selfhost.sync"
fi

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

cd "`$APP_DIR"
if [ -f tools/post_deploy_selfhost.sh ]; then
  chmod +x tools/post_deploy_selfhost.sh
  docker compose \
    -f docker-compose.selfhost.yml \
    -f docker-compose.selfhost.postgres.yml \
    --env-file .env \
    up -d postgres
  bash tools/post_deploy_selfhost.sh
fi

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
  if curl -fsS -H "Host: `$HOST_HEADER" http://127.0.0.1:8001/api/health/live >/dev/null; then
    echo
    if curl -fsS -H "Host: `$HOST_HEADER" http://127.0.0.1:8001/api/system/capabilities >/dev/null; then
      echo "Smoke check passed: /api/system/capabilities"
      if [ -f "`$APP_DIR/public-downloads/catalog.json" ]; then
        CATALOG_PAYLOAD=`$(curl -fsS -H "Host: `$HOST_HEADER" http://127.0.0.1:8001/api/system/public-downloads)
        if printf '%s' "`$CATALOG_PAYLOAD" | grep -q '"items":[[:space:]]*\[[[:space:]]*{'; then
          echo "Smoke check passed: /api/system/public-downloads"
          exit 0
        fi
        echo "Smoke check failed: /api/system/public-downloads returned no items" >&2
        printf '%s\n' "`$CATALOG_PAYLOAD" >&2
        break
      fi
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
    $remoteScript = $remoteScript -replace "`r`n", "`n"

    Write-Host "Deploying on server..."
    Invoke-ExternalCommandWithRetry -Description "Remote deploy" -Command {
        $remoteScript | & ssh @sshArgs $sshDestination bash -s
    } -MaxAttempts 4 -DelaySeconds 5
}
finally {
    Stop-SshConnectionReuse -BaseSshArgs $baseSshArgs -ControlArgs $sshReuseControlArgs -Destination $sshDestination -TempRoot $sshReuseTempRoot
}

Write-Host ""
Write-Host "Deploy finished."
Write-Host "Server host: $ServerHost"
