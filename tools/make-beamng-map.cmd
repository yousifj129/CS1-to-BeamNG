@echo off
REM ===========================================================================================
REM  CS1-to-BeamNG :: convert a Cities: Skylines export into a BeamNG.drive level
REM ===========================================================================================
REM  Double-click this file. It finds the newest city_layout.json (from the project's exports
REM  folder, or from the Desktop), converts it, and writes the finished mod to dist\.
REM
REM  Extra options can be passed through, for example:
REM      make-beamng-map.cmd --install                 also copy the mod into BeamNG
REM      make-beamng-map.cmd --include-non-drivable    convert rail/paths too
REM      make-beamng-map.cmd "C:\path\city_layout.json"
REM ===========================================================================================

setlocal
set "HERE=%~dp0"
set "REPO=%HERE%.."
set "SCRIPT=%HERE%beamng_convert.py"

if not exist "%SCRIPT%" (
    echo.
    echo   ERROR: could not find "%SCRIPT%"
    echo.
    pause
    exit /b 1
)

echo.
echo   CS1-to-BeamNG converter
echo   -----------------------
echo.

python "%SCRIPT%" --repo-root "%REPO%" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo   Done.
) else (
    echo   Converter exited with code %EXITCODE%.
)
echo.
pause
exit /b %EXITCODE%
