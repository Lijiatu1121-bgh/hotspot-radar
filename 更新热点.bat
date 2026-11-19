@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

rem Keep this file pure ASCII. Windows cmd reads .bat in the OEM codepage
rem (GBK on zh-CN), so any UTF-8 Chinese here truncates the following lines.
rem
rem Locate Python: try the standard per-user installs first (3.11-3.14),
rem then fall back to whatever "python" resolves to on PATH.
set "PYEXE="
for %%V in (314 313 312 311) do (
  if not defined PYEXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
      set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    )
  )
)
if not defined PYEXE set "PYEXE=python"

echo ============================================================
echo   Hotspot Radar - weekly update
echo ============================================================
echo   python: %PYEXE%
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
