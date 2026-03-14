@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "SYNC_SCRIPT=%REPO_ROOT%tools\sync_selfhost_server.ps1"

if not exist "%SYNC_SCRIPT%" (
  echo sync_selfhost_server.ps1 not found:
  echo   %SYNC_SCRIPT%
  pause
  exit /b 1
)

set "SERVER_HOST="
set "SERVER_USER=root"
set "SSH_PORT=22"
set "SSH_KEY_PATH=%USERPROFILE%\.ssh\learningpyramid_selfhost_ed25519"

if "%SERVER_HOST%"=="" (
  set /p SERVER_HOST=Server host or public IP:
)

if "%SERVER_HOST%"=="" (
  echo Server host is required.
  pause
  exit /b 1
)

echo.
echo Deploy target:
echo   Host: %SERVER_HOST%
echo   User: %SERVER_USER%
echo   Port: %SSH_PORT%
if exist "%SSH_KEY_PATH%" (
  echo   Auth: SSH key ^(%SSH_KEY_PATH%^)
) else (
  echo   Auth: interactive SSH auth ^(run Install-Selfhost-Server-SshKey.bat recommended^)
)
echo.

if exist "%SSH_KEY_PATH%" (
  powershell -ExecutionPolicy Bypass -File "%SYNC_SCRIPT%" -ServerHost "%SERVER_HOST%" -ServerUser "%SERVER_USER%" -SshPort %SSH_PORT% -SshKeyPath "%SSH_KEY_PATH%"
) else (
  powershell -ExecutionPolicy Bypass -File "%SYNC_SCRIPT%" -ServerHost "%SERVER_HOST%" -ServerUser "%SERVER_USER%" -SshPort %SSH_PORT%
)
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo Deploy failed with exit code %EXIT_CODE%.
  pause
  exit /b %EXIT_CODE%
)

echo Deploy finished successfully.
pause
exit /b 0
