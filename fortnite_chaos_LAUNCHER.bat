@echo off
cd /d "%~dp0"

call :findpy
if defined PY goto run

echo Python not found. Installing it now...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements

call :findpy
if defined PY goto run

echo Python install failed. Get it from python.org, then run this again.
pause
exit /b 1

:run
start "Fortnite Chaos" cmd /k "%PY%" fortnite_chaos.py
exit /b

:findpy
set "PY="
where py >nul 2>nul && (set "PY=py" & exit /b)
where python >nul 2>nul && (set "PY=python" & exit /b)
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
    "%WINDIR%\py.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python312\python.exe"
) do if exist %%P (set "PY=%%~P" & exit /b)
exit /b