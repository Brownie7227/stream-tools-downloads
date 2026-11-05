@echo off
:: Makes a report of how your last stream ran (CPU, RAM, lag) and opens it in your browser.
:: For an older stream, run:  py -3 stream_report.py 2026-10-19
title Stream Report
cd /d "%~dp0"
py -3 stream_report.py %*
timeout /t 8
