@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local.ps1" -Mode start
pause
