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

set "SERVER_HOST=plm.xuebao.chat"
set "SERVER_USER=root"
set "SSH_PORT=22"

echo.
echo Deploy target:
echo   Host: %SERVER_HOST%
echo   User: %SERVER_USER%
echo   Port: %SSH_PORT%
echo   Auth: project SSH key with automatic setup/repair; may prompt once for server password if needed
echo.

powershell -ExecutionPolicy Bypass -File "%SYNC_SCRIPT%" -ServerHost "%SERVER_HOST%" -ServerUser "%SERVER_USER%" -SshPort %SSH_PORT% -PromptOnDirtyWorktree %*
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
