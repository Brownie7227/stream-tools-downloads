@echo off
:: Setup. Safe to run any time: anything already done gets confirmed and skipped, and your settings stay as they are
:: unless you choose to change them.
title Stream Tools setup
cd /d "%~dp0"
echo.
echo   Stream Tools setup
echo   ------------------
echo.

:: ---- Python
call :findpy
if defined PY (
    echo   [OK] Python already installed
    goto python_done
)
echo   Installing Python...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
call :findpy
if defined PY goto python_done
echo   Python didn't install. Get it from python.org, then run this again.
pause
exit /b 1
:python_done

:: ---- ffmpeg
where ffmpeg >nul 2>nul && goto ffmpeg_ok
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe" goto ffmpeg_ok
choice /m "  Install ffmpeg? Only Chaos Clips needs it"
if errorlevel 2 goto ffmpeg_done
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
goto ffmpeg_done
:ffmpeg_ok
echo   [OK] ffmpeg already installed
:ffmpeg_done

:: ---- your settings
echo.
"%PY%" setup_wizard.py --check
if errorlevel 1 goto open_window
echo.
echo   Already set up.
choice /m "  Open the settings window? It starts with your current settings, and Cancel changes nothing"
if errorlevel 2 goto finished
:open_window
echo.
echo   Opening the setup window...
"%PY%" setup_wizard.py
if errorlevel 1 (
    echo   The setup window didn't open, so you can fill in config.json by hand instead.
    if not exist config.json copy /y config.example.json config.json >nul
    start "" notepad config.json
)

:finished
echo.
echo   Setup is done. Next, open fortnite_chaos_LAUNCHER.bat or Start Stream.bat.
echo.
pause
exit /b 0

:findpy
set "PY="
where py >nul 2>nul && py --version >nul 2>nul && (set "PY=py" & exit /b)
where python >nul 2>nul && python --version >nul 2>nul && (set "PY=python" & exit /b)
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
    "%WINDIR%\py.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python312\python.exe"
) do if exist %%P (set "PY=%%~P" & exit /b)
exit /b
