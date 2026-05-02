@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PS1=%ROOT%dev_tools_menu.ps1"
set "PWSH=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%PWSH%" (
  echo [ERROR] powershell.exe not found:
  echo %PWSH%
  pause
  exit /b 1
)

if not exist "%PS1%" (
  echo [ERROR] Script not found:
  echo %PS1%
  pause
  exit /b 1
)

"%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo [ERROR] dev_tools_menu.ps1 failed. exit=%EXITCODE%
  pause
)
exit /b %EXITCODE%
