@echo off
chcp 65001 >nul 2>&1
setlocal

echo.
echo ============================================================
echo   Delphi MCP Server 安装脚本
echo ============================================================
echo.

REM 检查 PowerShell 是否可用
where powershell >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 PowerShell，请安装 PowerShell 5.1 或更高版本
    pause
    exit /b 1
)

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"

REM 检查 install.ps1 是否存在
if not exist "%SCRIPT_DIR%install.ps1" (
    echo [错误] 未找到 install.ps1，请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

REM 收集命令行参数，透传给 PowerShell 脚本
set "PS_ARGS="
:parse_args
if "%~1"=="" goto run_ps
set "PS_ARGS=%PS_ARGS% %~1"
shift
goto parse_args

:run_ps
REM 以 Bypass 执行策略运行 PowerShell 脚本
echo 正在启动安装脚本...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%install.ps1" %PS_ARGS%

if %ERRORLEVEL% neq 0 (
    echo.
    echo [错误] 安装脚本执行失败
    pause
    exit /b 1
)

echo.
pause
exit /b 0
