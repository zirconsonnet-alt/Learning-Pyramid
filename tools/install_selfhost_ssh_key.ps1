param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [string]$ServerUser = "root",
    [int]$SshPort = 22,
    [string]$SshKeyPath = ""
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Resolve-OrCreate-SshKeyPath {
    param([string]$ConfiguredPath)
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
    if (-not (Test-Path $fullPath)) {
        Write-Host "Generating SSH key: $fullPath"
        & ssh-keygen -t ed25519 -C "learningpyramid-selfhost" -f $fullPath -N ""
        if ($LASTEXITCODE -ne 0) {
            throw "ssh-keygen failed"
        }
    }
    return (Resolve-Path $fullPath).Path
}

Require-Command ssh
Require-Command ssh-keygen

$resolvedKeyPath = Resolve-OrCreate-SshKeyPath -ConfiguredPath $SshKeyPath
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

Write-Host "Installing SSH public key on ${ServerUser}@${ServerHost}:${SshPort}"
Get-Content -Raw $publicKeyPath | & ssh @sshArgs "${ServerUser}@${ServerHost}" "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; cat >> ~/.ssh/authorized_keys; sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys"
if ($LASTEXITCODE -ne 0) {
    throw "SSH public key install failed"
}

Write-Host "Testing SSH key login..."
& ssh @sshArgs -i $resolvedKeyPath "${ServerUser}@${ServerHost}" "printf 'ssh-key-ok\n'"
if ($LASTEXITCODE -ne 0) {
    throw "SSH key verification failed"
}

Write-Host ""
Write-Host "SSH key installed successfully."
Write-Host "Private key: $resolvedKeyPath"
Write-Host "Public key:  $publicKeyPath"
