@echo off
setlocal
cd /d "%~dp0"

rem ---- PVZ hybrid-edition Mod editor launcher ----
set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"

rem usage:
rem   start_editor.bat                        open the editor UI (auto browser)
rem   start_editor.bat --no-browser           no browser
rem   start_editor.bat --port 8888            custom port
rem   start_editor.bat --build                headless build from mod_project.json
rem   start_editor.bat --unpack "D:\path"     custom unpack dir

"%PY%" mod_editor.py %*
if errorlevel 1 (
  echo.
  echo [ERR] editor exited with code %errorlevel%
  pause
)
endlocal
