param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [string]$ServerUser = "root",
    [int]$SshPort = 22,
    [string]$SshKeyPath = "",
    [switch]$ReplaceExistingKey,
    [switch]$NoKeyPassphrase
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Resolve-OrCreate-SshKeyPath {
    param(
        [string]$ConfiguredPath,
        [switch]$ReplaceExisting,
        [switch]$NoPassphrase
    )
    if ($ConfiguredPath) {
        $fullPath = $ConfiguredPath
    }
    else {
        $fullPath = Join-Path $HOME ".ssh\learningpyramid_selfhost_ed25519"
    }
    $keyDir = Split-Path -Parent $fullPath
    if (-not (Test-Path $keyDir)) {
        New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
    }
    $keyExists = (Test-Path $fullPath) -or (Test-Path "${fullPath}.pub")
    if ($ReplaceExisting -and $keyExists) {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        foreach ($path in @($fullPath, "${fullPath}.pub")) {
            if (-not (Test-Path $path)) {
                continue
            }
            $backupPath = "${path}.bak-${timestamp}"
            Move-Item -Path $path -Destination $backupPath -Force
            Write-Host "Backed up existing key file: $backupPath"
        }
        $keyExists = $false
    }
    if (-not (Test-Path $fullPath)) {
        Write-Host "Generating SSH key: $fullPath"
        if ($NoPassphrase) {
            Write-Host "Generating project SSH key without a passphrase."
            & ssh-keygen -t ed25519 -C "learningpyramid-selfhost" -f $fullPath -N '""'
        }
        else {
            Write-Host "Generating project SSH key with an interactive passphrase prompt."
            & ssh-keygen -t ed25519 -C "learningpyramid-selfhost" -f $fullPath
        }
        if ($LASTEXITCODE -ne 0) {
            throw "ssh-keygen failed"
        }
    }
    elseif ($ReplaceExisting -and $keyExists) {
        throw "Failed to rotate SSH key at $fullPath"
    }
    else {
        Write-Host "Reusing existing SSH key: $fullPath"
    }
    return (Resolve-Path $fullPath).Path
}

Require-Command ssh
Require-Command ssh-keygen

$resolvedKeyPath = Resolve-OrCreate-SshKeyPath -ConfiguredPath $SshKeyPath -ReplaceExisting:$ReplaceExistingKey -NoPassphrase:$NoKeyPassphrase
$publicKeyPath = "${resolvedKeyPath}.pub"
if (-not (Test-Path $publicKeyPath)) {
    throw "SSH public key not found: $publicKeyPath"
}

$sshArgs = @(
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=4",
    "-o", "TCPKeepAlive=yes",
    "-o", "ConnectTimeout=15",
    "-p", "$SshPort"
)
$installAuthArgs = @(
    $sshArgs + @(
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=password,keyboard-interactive"
    )
)

Write-Host "Installing SSH public key on ${ServerUser}@${ServerHost}:${SshPort}"
Get-Content -Raw $publicKeyPath | & ssh @installAuthArgs "${ServerUser}@${ServerHost}" "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; cat >> ~/.ssh/authorized_keys; sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys"
if ($LASTEXITCODE -ne 0) {
    throw "SSH public key install failed"
}

Write-Host "Testing SSH key login..."
& ssh @sshArgs -i $resolvedKeyPath -o "IdentitiesOnly=yes" "${ServerUser}@${ServerHost}" "printf 'ssh-key-ok\n'"
if ($LASTEXITCODE -ne 0) {
    throw "SSH key verification failed"
}

Write-Host ""
Write-Host "SSH key installed successfully."
Write-Host "Private key: $resolvedKeyPath"
Write-Host "Public key:  $publicKeyPath"
