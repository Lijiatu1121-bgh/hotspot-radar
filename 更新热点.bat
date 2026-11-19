@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

rem Keep this file pure ASCII. Windows cmd reads .bat in the OEM codepage (GBK
rem on zh-CN), so any UTF-8 Chinese here breaks the following lines.
set "PYEXE=C:\Users\20829\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo ============================================================
echo   Hotspot Radar - weekly update
echo ============================================================
echo.

"%PYEXE%" scripts\update.py %*
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
  echo [OK] finished.
) else (
  echo [WARN] exit code = %CODE%, see the log above.
)
echo.
pause
