@echo off
chcp 65001 >nul
title 大尸兄一键翻唱
setlocal
cd /d %~dp0
if exist env\python.exe (
    env\python.exe one_click_cover.py
) else (
    python one_click_cover.py
)
