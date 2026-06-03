@echo off
rem Dev launcher for the Python sidecar. Mirrors what the PyInstaller
rem binary will eventually do in week 12. Lives next to the Tauri exe
rem under `binaries/cs2_sidecar.cmd`.
rem
rem Usage from Rust (via tokio::Command): the path is set in main.rs.
rem The sidecar is spawned with stdin/stdout piped.

setlocal
set "HERE=%~dp0"

rem Prefer the venv in python_sidecar/.venv if present (dev).
if exist "%HERE%..\..\..\python_sidecar\.venv\Scripts\python.exe" (
    set "PY=%HERE%..\..\..\python_sidecar\.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

"%PY%" -m cs2_sidecar
