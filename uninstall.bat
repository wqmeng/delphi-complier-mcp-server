@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "PYTHON="
if exist "%SCRIPT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON=%SCRIPT_DIR%\venv\Scripts\python.exe"
)
if not defined PYTHON (
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        for /f "delims=" %%p in ('where python') do set "PYTHON=%%p"
    )
)
if not defined PYTHON (
    echo [ERROR] Python 未找到，请先安装 Python 3.10+
    pause
    exit /b 1
)

"%PYTHON%" "%SCRIPT_DIR%\install_mcp.py" --uninstall %*
exit /b %ERRORLEVEL%
