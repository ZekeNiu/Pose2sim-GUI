@echo off
setlocal

set "PYTHON_EXE=D:\Application\Anaconda\envs\sports3d\python.exe"
set "APP_DIR=%~dp0"

if not exist "%PYTHON_EXE%" (
  echo Could not find Python at:
  echo %PYTHON_EXE%
  echo.
  echo Please update launch_pose2sim_gui.bat to point to your Pose2Sim environment.
  pause
  exit /b 1
)

cd /d "%APP_DIR%"
"%PYTHON_EXE%" -m pose2sim_gui
if errorlevel 1 pause
