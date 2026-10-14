@echo off
rem ASCII-only wrapper for patch_pmod_attrs.py (same directory as this file).
rem Usage: pmod <pmod-file> --list
rem        pmod <pmod-file> --cost 500 --fire-interval 1.0 --dry-run
setlocal
rem 本机适配：优先显式指定（PVZ_PY 环境变量），否则用 PATH 上的 python
set "PY=%PVZ_PY%"
if not exist "%PY%" set "PY=py"
if not exist "%PY%" set "PY=python"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0patch_pmod_attrs.py" %*
exit /b %ERRORLEVEL%
