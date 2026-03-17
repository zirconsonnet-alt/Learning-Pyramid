@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "INSTALL_SCRIPT=%REPO_ROOT%tools\install_selfhost_ssh_key.ps1"

if not exist "%INSTALL_SCRIPT%" (
  echo install_selfhost_ssh_key.ps1 not found:
  echo   %INSTALL_SCRIPT%
  pause
  exit /b 1
)

set "SERVER_HOST=plm.xuebao.chat"
set "SERVER_USER=root"
set "SSH_PORT=22"
set "SSH_KEY_PATH=%USERPROFILE%\.ssh\learningpyramid_selfhost_ed25519"

echo.
echo SSH key install target:
echo   Host: %SERVER_HOST%
echo   User: %SERVER_USER%
echo   Port: %SSH_PORT%
echo   Key:  %SSH_KEY_PATH%
echo.

powershell -ExecutionPolicy Bypass -File "%INSTALL_SCRIPT%" -ServerHost "%SERVER_HOST%" -ServerUser "%SERVER_USER%" -SshPort %SSH_PORT% -SshKeyPath "%SSH_KEY_PATH%" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo SSH key install failed with exit code %EXIT_CODE%.
  pause
  exit /b %EXIT_CODE%
)

echo SSH key install finished successfully.
pause
exit /b 0
