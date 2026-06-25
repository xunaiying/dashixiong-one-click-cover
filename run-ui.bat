@echo off
setlocal
cd /d %~dp0
if exist env\python.exe (
    env\python.exe launcher_ui.py
) else (
    python launcher_ui.py
)
