@echo off
title Matix Brain - the club's own Python AI
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 matix_brain.py
) else (
  python matix_brain.py
)
pause
