@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ============================================================
echo   Daofy 完整测试
echo ============================================================
echo.

set FAILED=0

echo [1/4] test_delphi_versions.py
python -u tests/test_delphi_versions.py
if errorlevel 1 set FAILED=1
echo.

echo [2/4] test_kb_service_extended.py
python -u tests/run_extended_tests.py
if errorlevel 1 set FAILED=1
echo.

echo [3/4] test_mcp_tools.py
python -u tests/test_mcp_tools.py
if errorlevel 1 set FAILED=1
echo.

echo [4/4] test_compiler_service.py
python -u tests/test_compiler_service.py
if errorlevel 1 set FAILED=1
echo.

echo ============================================================
if %FAILED%==0 (
    echo   所有测试通过
) else (
    echo   有测试失�?)
echo ============================================================

exit /b %FAILED%

