@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo:
echo ============================================================
echo   Daofy Installer
echo ============================================================
echo:

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR%"

:: 1. venv Python
set "PYTHON="
if exist "%SCRIPT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON=%SCRIPT_DIR%\venv\Scripts\python.exe"
    echo [INFO] 使用虚拟环境 Python: !PYTHON!
)

:: 2. 系统 Python
if not defined PYTHON (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        for /f "delims=" %%p in ('where python 2^>nul') do (
            set "PYTHON=%%p"
            echo [INFO] 使用系统 Python: %%p
        )
    )
)

:: 3. 常见安装路径
if not defined PYTHON (
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python\Python314"
        "%LOCALAPPDATA%\Programs\Python\Python313"
        "%LOCALAPPDATA%\Programs\Python\Python312"
        "%LOCALAPPDATA%\Programs\Python\Python311"
        "%LOCALAPPDATA%\Programs\Python\Python310"
    ) do (
        if not defined PYTHON (
            if exist "%%~d\python.exe" (
                set "PYTHON=%%~d\python.exe"
                echo [INFO] 找到 Python: !PYTHON!
            )
        )
    )
)

:: 4. 下载安装 Python 3.14
if not defined PYTHON (
    echo [WARNING] 未找到 Python，将自动下载并安装 Python 3.14
    echo:

    set "PY_INSTALLER=%TEMP%\python-3.14.0-amd64.exe"
    set "PY_URL=https://www.python.org/ftp/python/3.14.0/python-3.14.0-amd64.exe"

    echo [INFO] 正在下载 Python 3.14.0 ...
    echo        !PY_URL!

    where curl >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        curl -L -o "!PY_INSTALLER!" "!PY_URL!" 2>nul
    ) else (
        echo [INFO] curl 不可用，尝试 PowerShell 下载 ...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PY_INSTALLER!'" 2>nul
    )

    if not exist "!PY_INSTALLER!" (
        echo [ERROR] Python 下载失败，请手动安装: https://www.python.org/downloads/
        pause
        exit /b 1
    )

    echo [INFO] 正在安装 Python 3.14.0 (InstallAllUsers=0, PrependPath=1) ...
    echo        请等待安装完成 ...
    echo:

    "!PY_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=0

    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Python 安装失败，请手动安装: https://www.python.org/downloads/
        del "!PY_INSTALLER!" 2>nul
        pause
        exit /b 1
    )

    del "!PY_INSTALLER!" 2>nul

    :: 重新检测
    set "PYTHON="
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python\Python314"
    ) do (
        if not defined PYTHON (
            if exist "%%~d\python.exe" (
                set "PYTHON=%%~d\python.exe"
            )
        )
    )
    if not defined PYTHON (
        where python >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            for /f "delims=" %%p in ('where python 2^>nul') do set "PYTHON=%%p"
        )
    )

    if not defined PYTHON (
        echo [ERROR] Python 安装后仍未找到，请重启终端后重试
        pause
        exit /b 1
    )

    echo [SUCCESS] Python 3.14.0 安装成功: !PYTHON!
    echo:
)

:: 验证 Python 版本
"%PYTHON%" -c "import sys; v=sys.version_info; sys.exit(0 if v.major==3 and v.minor>=10 else 1)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 版本过低，需要 3.10+
    pause
    exit /b 1
)

:: 如果 install_mcp.py 不存在，先从 GitHub release 下载引导
if not exist "%SCRIPT_DIR%\install_mcp.py" (
    echo [INFO] install_mcp.py 不存在，正在从 GitHub 下载引导脚本...

    :: 创建临时下载脚本（避免 python -c 引号转义问题）
    set "DL_SCRIPT=%TEMP%\_daofy_dl_install_mcp.py"
    echo import urllib.request> "!DL_SCRIPT!"
    echo import time>> "!DL_SCRIPT!"
    echo import sys>> "!DL_SCRIPT!"
    echo url = 'https://raw.githubusercontent.com/daofy-nlp/delphi-complier-mcp-server/main/install_mcp.py'>> "!DL_SCRIPT!"
    echo dest = r'%SCRIPT_DIR%\install_mcp.py'>> "!DL_SCRIPT!"
    echo for attempt in range(1, 31):>> "!DL_SCRIPT!"
    echo     try:>> "!DL_SCRIPT!"
    echo         urllib.request.urlretrieve(url, dest)>> "!DL_SCRIPT!"
    echo         sys.exit(0)>> "!DL_SCRIPT!"
    echo     except Exception as e:>> "!DL_SCRIPT!"
    echo         if attempt %% 5 == 0:>> "!DL_SCRIPT!"
    echo             print('[INFO] 下载重试 {}/30 ...'.format(attempt))>> "!DL_SCRIPT!"
    echo         time.sleep(min(attempt * 2, 30))>> "!DL_SCRIPT!"
    echo sys.exit(1)>> "!DL_SCRIPT!"

    "%PYTHON%" "!DL_SCRIPT!"
    set "DL_RESULT=!ERRORLEVEL!"
    del "!DL_SCRIPT!" 2>nul

    if !DL_RESULT! neq 0 (
        if exist "%SCRIPT_DIR%\install_mcp.py" del "%SCRIPT_DIR%\install_mcp.py" 2>nul
        echo [ERROR] 无法下载 install_mcp.py（已重试30次），请手动下载完整包
        pause
        exit /b 1
    )
    echo [SUCCESS] 引导脚本下载成功
)

echo [INFO] 使用 Python: %PYTHON%
echo:

"%PYTHON%" "%SCRIPT_DIR%\install_mcp.py" %*

if %ERRORLEVEL% neq 0 (
    echo:
    echo [ERROR] 安装失败
    pause
    exit /b 1
)

echo:
pause
exit /b 0
