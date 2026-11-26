@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Сначала выполните: python -m venv .venv
  echo Затем: .venv\Scripts\python.exe -m pip install -r requirements-local.txt
  pause
  exit /b 1
)
start "SwimRocket Встречи" ".venv\Scripts\pythonw.exe" "main.py"
