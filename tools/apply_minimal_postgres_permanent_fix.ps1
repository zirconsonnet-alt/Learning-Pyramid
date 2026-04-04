param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [string]$ServerUser = "root",
    [string]$RemoteRoot = "/opt/learningpyramid",
    [int]$SshPort = 22
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$remoteAppDir = "$RemoteRoot/app"

$storeFile = (Join-Path $repoRoot "backend/system/postgres_store.py")
$toolFiles = @(
    (Join-Path $repoRoot "tools/postgres_optional_tables_hotfix.sql"),
    (Join-Path $repoRoot "tools/apply_postgres_optional_tables_hotfix.sh")
)

if (-not (Test-Path $storeFile)) {
    throw "Required file not found: $storeFile"
}
foreach ($toolFile in $toolFiles) {
    if (-not (Test-Path $toolFile)) {
        throw "Required file not found: $toolFile"
    }
}

& scp -P $SshPort $storeFile "${ServerUser}@${ServerHost}:$remoteAppDir/backend/system/postgres_store.py"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed for $storeFile"
}

& scp -P $SshPort @toolFiles "${ServerUser}@${ServerHost}:$remoteAppDir/tools/"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed for tool hotfix files"
}

$remoteScript = @"
set -euo pipefail

cd $remoteAppDir
chmod +x tools/apply_postgres_optional_tables_hotfix.sh

if grep -q '^PLM_ENABLE_BAIDU_NETDISK=' .env; then
  sed -i 's/^PLM_ENABLE_BAIDU_NETDISK=.*/PLM_ENABLE_BAIDU_NETDISK=false/' .env
else
  printf '\nPLM_ENABLE_BAIDU_NETDISK=false\n' >> .env
fi

./tools/apply_postgres_optional_tables_hotfix.sh

docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  up -d --build app

sleep 10

docker logs --since 2m app-app-1 2>&1 | tail -80
"@

$remoteScript | & ssh -p $SshPort "${ServerUser}@${ServerHost}" "bash -s"
if ($LASTEXITCODE -ne 0) {
    throw "remote permanent fix apply failed"
}
