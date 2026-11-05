@echo off
:: First-time setup. Safe to run again: it never overwrites your config.json.
title Stream Tools setup
cd /d "%~dp0"
echo.
echo   Stream Tools setup
echo   ------------------
echo.

where py >nul 2>nul && goto python_ok
where python >nul 2>nul && goto python_ok
echo   Installing Python...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
:python_ok
echo   [OK] Python

where ffmpeg >nul 2>nul && goto ffmpeg_ok
choice /m "  Install ffmpeg? Only Chaos Clips needs it"
if errorlevel 2 goto ffmpeg_done
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
goto ffmpeg_done
:ffmpeg_ok
echo   [OK] ffmpeg
:ffmpeg_done

if exist config.json (
    echo   [OK] config.json already exists, leaving it alone
) else (
    copy /y config.example.json config.json >nul
    echo   [OK] Made config.json
)
echo.
echo   Next: check config.json. Notepad is opening it now.
echo   Replace any INSERT_... you want to use. README.md explains each one.
echo.
start "" notepad config.json
pause
