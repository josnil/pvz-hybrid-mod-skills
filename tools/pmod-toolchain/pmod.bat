@echo off
rem ASCII-only wrapper for patch_pmod_attrs.py (same directory as this file).
rem Usage: pmod <pmod-file> --list
rem        pmod <pmod-file> --cost 500 --fire-interval 1.0 --dry-run
setlocal
set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0patch_pmod_attrs.py" %*
exit /b %ERRORLEVEL%
