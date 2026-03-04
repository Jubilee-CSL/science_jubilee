@echo off
setlocal

set "FIRMWARE_DIR=%~dp0"
if "%FIRMWARE_DIR:~-1%"=="\" set "FIRMWARE_DIR=%FIRMWARE_DIR:~0,-1%"
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "ADDRESS=%~1"

if "%ADDRESS%"=="" (
  set /p "ADDRESS=Enter Duet IP/hostname ^(e.g. 192.168.1.2^): "
)

if "%ADDRESS%"=="" (
  echo No address provided. Aborting.
  exit /b 1
)

set "PYTHONPATH=%REPO_ROOT%\src;%PYTHONPATH%"
python "%REPO_ROOT%\scripts\download_duet_folders.py" --address "%ADDRESS%" --out-root "%FIRMWARE_DIR%" --clean
if errorlevel 1 (
  echo Download failed.
  exit /b 1
)

echo Download complete.
exit /b 0
