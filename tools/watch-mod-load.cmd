@echo off
REM ===========================================================================================
REM  CS1-to-BeamNG :: launcher for tools\watch-mod-load.ps1
REM ===========================================================================================
REM  Double-click this file. It runs the PowerShell script with the execution policy bypassed
REM  for this one run only, so you do not have to change any system or user settings.
REM
REM  Pass any of the script's switches through, for example:
REM      watch-mod-load.cmd -Restart
REM      watch-mod-load.cmd -Build
REM      watch-mod-load.cmd -Follow
REM ===========================================================================================

setlocal
set "SCRIPT=%~dp0watch-mod-load.ps1"

if not exist "%SCRIPT%" (
    echo.
    echo   ERROR: could not find "%SCRIPT%"
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo   Done.
) else (
    echo   Script exited with code %EXITCODE%.
)
echo.
pause
exit /b %EXITCODE%
