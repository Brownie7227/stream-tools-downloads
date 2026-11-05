@echo off
:: Starting TikTok Streaming Setup
:: Only starts what isn't already running, so double-clicking twice never makes duplicates.
title Start Stream
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$ErrorActionPreference = 'SilentlyContinue'
$Programs = $env:HERE.TrimEnd('\')
$Apps = (Get-Content (Join-Path $Programs 'config.json') -Raw | ConvertFrom-Json).apps

function Scripts($pattern) {
    Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name = 'node.exe'" | Where-Object { $_.CommandLine -match $pattern }
}

function Start-App($process, $shortcut, $label) {
    if (Get-Process -Name $process -ErrorAction SilentlyContinue) { Write-Host "  $label already running" -ForegroundColor Gray }
    elseif (-not $shortcut -or $shortcut -like 'INSERT_*' -or -not (Test-Path -LiteralPath $shortcut)) {
        Write-Host "  Skipped $label - set where it is under apps in config.json" -ForegroundColor Yellow
    }
    else { Start-Process $shortcut; Write-Host "  Started $label" -ForegroundColor Green }
}

Write-Host ''
Write-Host '  Starting stream setup...' -ForegroundColor Cyan
Write-Host ''

# End Stream didn't finish last time if this list is still here. Game Boost re-pauses the services in a moment
# anyway, so there's nothing to put back now - just say so, and End Stream will put them all back tonight.
if (Test-Path (Join-Path $env:LOCALAPPDATA 'GameBoost\paused-services.txt')) {
    Write-Host '  Note: End Stream did not finish last time, so Windows services stayed paused until a reboot' -ForegroundColor Yellow
}

# make reports for any past streams that don't have one yet (quietly, in the background)
Start-Process py -ArgumentList '-3', '-B', "`"$(Join-Path $Programs 'stream_report.py')`"", '--missing' -WindowStyle Hidden

Start-App 'bettertok-desktop' $Apps.bettertok 'BetterTok'
Start-App 'Spotify' $Apps.spotify 'Spotify'
Start-App 'TikTok LIVE Studio' $Apps.live_studio 'TikTok LIVE Studio'

# the old flashbang.py fights Fortnite Chaos for port 8765 - Fortnite Chaos does the flashbang now
Scripts 'flashbang\.py' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host '  Closed the old flashbang.py' -ForegroundColor Yellow }

# the Discord jumpscare is built into Fortnite Chaos now - an old bot.js still running would scare you twice
Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" | Where-Object { $_.CommandLine -match 'bot\.js' } |
    ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null }
Scripts 'bot\.js' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host '  Closed the old Discord bot (Fortnite Chaos does it now)' -ForegroundColor Yellow }

$chaos = @(Scripts 'fortnite_chaos')
if ($chaos.Count -eq 1) { Write-Host '  Fortnite Chaos already running' -ForegroundColor Gray }
else {
    if ($chaos.Count -gt 1) {  # duplicates cancel each other out - restart with just one
        $chaos | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep -Milliseconds 500
    }
    Start-Process cmd -ArgumentList '/k', "title Fortnite Chaos && cd /d `"$Programs`" && py -3 fortnite_chaos.py"
    Write-Host '  Started Fortnite Chaos' -ForegroundColor Green
}

# give TikTok LIVE Studio High priority once it's open, so the stream gets the CPU first
Write-Host ''
Write-Host '  Waiting for TikTok LIVE Studio...' -ForegroundColor Gray
$done = 0
for ($i = 0; $i -lt 60; $i++) {
    $procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*TikTok LIVE Studio*' }
    if ($procs -and ($procs | Where-Object { $_.MainWindowHandle -ne 0 })) {
        Start-Sleep -Seconds 3  # let it finish opening all its helper processes
        $procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*TikTok LIVE Studio*' }
        foreach ($p in $procs) { try { $p.PriorityClass = 'High'; $done++ } catch { } }
        break
    }
    Start-Sleep -Seconds 1
}
if ($done) { Write-Host "  TikTok LIVE Studio set to High priority ($done processes)" -ForegroundColor Green }
else { Write-Host "  TikTok LIVE Studio didn't open within a minute - run focus_tiktok_live_studio.bat later for High priority" -ForegroundColor Yellow }

# Game Boost last, as admin, once everything above is open (it asks Y/N in its own window)
$boost = Join-Path $Programs 'Game Boost.bat'
try { Start-Process $boost -Verb RunAs -ErrorAction Stop; Write-Host '  Started Game Boost (as admin)' -ForegroundColor Green }
catch { Start-Process cmd -ArgumentList '/c', "`"$boost`" noadmin"; Write-Host '  Started Game Boost without admin (admin prompt was declined)' -ForegroundColor Yellow }

Write-Host ''
Write-Host '  All started. Run "Stream Doctor.bat" for a full check before going live.' -ForegroundColor Cyan
Start-Sleep -Seconds 4
