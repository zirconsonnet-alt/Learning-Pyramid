@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_CMD=python"
where %PYTHON_CMD% >nul 2>nul
if errorlevel 1 set "PYTHON_CMD=py -3"

%PYTHON_CMD% "%~dp0tools\stop_plm.py" %*
