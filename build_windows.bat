@echo off
setlocal
cd /d %~dp0

set "PYTHON_EXE="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_EXE=py"
if not defined PYTHON_EXE (
  where python >nul 2>nul
  if %errorlevel%==0 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
  echo Python was not found. Install Python or run PyInstaller with a full python.exe path.
  exit /b 1
)

if not exist .env (
  copy windows.env.example .env >nul
)

%PYTHON_EXE% -m PyInstaller --clean --noconfirm bitaxe-agent.spec

echo.
echo Build complete.
echo Run: dist\bitaxe-agent.exe
