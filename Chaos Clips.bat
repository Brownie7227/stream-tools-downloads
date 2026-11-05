@echo off
:: Cuts the best moments of your last stream into vertical clips, saved to the clips folder in config.json.
:: For an older stream, run:  py -3 chaos_clips.py 2026-11-05     (see the top of chaos_clips.py for more)
title Chaos Clips
cd /d "%~dp0"
py -3 chaos_clips.py %*
echo.
pause
