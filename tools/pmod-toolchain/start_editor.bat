@echo off
setlocal
cd /d "%~dp0"

rem ---- PVZ hybrid-edition Mod editor launcher ----
rem 本机适配：优先显式指定（PVZ_PY 环境变量），否则用 PATH 上的 python
set "PY=%PVZ_PY%"
if not exist "%PY%" set "PY=py"
if not exist "%PY%" set "PY=python"
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
