@echo off
:: Starting TikTok Streaming Setup
:: Only starts what isn't already running, so double-clicking twice never makes duplicates.
title Start Stream
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$ErrorActionPreference = 'SilentlyContinue'
$Programs = $env:HERE.TrimEnd('\')
$Settings = (Get-Content (Join-Path $Programs 'config.json') -Raw | ConvertFrom-Json).start_stream

# The apps chosen in setup (config.json). Also reads the older layout, which named three fixed apps.
function Get-StreamApps {
    $apps = (Get-Content (Join-Path $env:HERE 'config.json') -Raw | ConvertFrom-Json).apps
    if ($apps -is [array]) { return $apps | Where-Object { $_.path -and $_.path -notlike 'INSERT_*' } }
    foreach ($old in @(@('bettertok', 'BetterTok', 'bettertok-desktop'), @('spotify', 'Spotify', 'Spotify'),
                       @('live_studio', 'TikTok LIVE Studio', 'TikTok LIVE Studio'))) {
        $path = $apps.($old[0])
        if ($path -and $path -notlike 'INSERT_*') { [pscustomobject]@{ name = $old[1]; process = $old[2]; path = $path } }
    }
}

function Scripts($pattern) {
    Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name = 'node.exe'" | Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch '--child' }
}

function Start-App($process, $shortcut, $label) {
    if (Get-Process -Name $process -ErrorAction SilentlyContinue) { Write-Host "  $label already running" -ForegroundColor Gray }
    elseif ($shortcut -notlike 'shell:*' -and -not (Test-Path -LiteralPath $shortcut)) {
        Write-Host "  Skipped $label - couldn't find it. Run SETUP.bat to choose it again." -ForegroundColor Yellow
    }
    else {
        try { Start-Process $shortcut -ErrorAction Stop; Write-Host "  Started $label" -ForegroundColor Green }
        catch { Write-Host "  Couldn't open $label. Run SETUP.bat to choose it again." -ForegroundColor Yellow }
    }
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

# the old flashbang.py fights Fortnite Chaos for port 8765 - Fortnite Chaos does the flashbang now
Scripts 'flashbang\.py' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host '  Closed the old flashbang.py' -ForegroundColor Yellow }

# the Discord jumpscare is built into Fortnite Chaos now - an old bot.js still running would scare you twice
Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" | Where-Object { $_.CommandLine -match 'bot\.js' } |
    ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null }
Scripts 'bot\.js' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host '  Closed the old Discord bot (Fortnite Chaos does it now)' -ForegroundColor Yellow }

$chaos = @(Scripts 'fortnite_chaos')
if ($Settings.fortnite_chaos -eq $false) { Write-Host '  Fortnite Chaos is turned off in setup' -ForegroundColor Gray }
elseif ($chaos.Count -eq 1) { Write-Host '  Fortnite Chaos already running' -ForegroundColor Gray }
else {
    if ($chaos.Count -gt 1) {  # duplicates cancel each other out - restart with just one
        $chaos | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep -Milliseconds 500
    }
    Start-Process cmd -ArgumentList '/k', "title Fortnite Chaos && cd /d `"$Programs`" && py -3 fortnite_chaos.py"
    Write-Host '  Started Fortnite Chaos' -ForegroundColor Green
}

# Your apps open once Fortnite Chaos is answering, so LIVE Studio's overlay never loads blank
if ($Settings.fortnite_chaos -ne $false) {
    $ready = $false
    for ($i = 0; $i -lt 30 -and -not $ready; $i++) {
        try { Invoke-WebRequest 'http://127.0.0.1:8766/status' -UseBasicParsing -TimeoutSec 1 | Out-Null; $ready = $true }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if ($ready) { Write-Host '  Fortnite Chaos is ready' -ForegroundColor Green }
    else { Write-Host "  Fortnite Chaos isn't answering yet - if the overlay is blank in LIVE Studio, re-save its Link source" -ForegroundColor Yellow }
}

$Apps = @(Get-StreamApps)
foreach ($app in $Apps) { Start-App $app.process $app.path $app.name }

# give TikTok LIVE Studio High priority once it's open, so the stream gets the CPU first
$usesLiveStudio = @($Apps | Where-Object { $_.process -like '*TikTok LIVE Studio*' }).Count -gt 0
if ($usesLiveStudio) {
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
}

# Game Boost last, as admin, once everything above is open (it asks Y/N in its own window)
$boost = Join-Path $Programs 'Game Boost.bat'
if ($Settings.game_boost -eq $false) { Write-Host '  Game Boost is turned off in setup' -ForegroundColor Gray }
else {
    try { Start-Process $boost -Verb RunAs -ErrorAction Stop; Write-Host '  Started Game Boost (as admin)' -ForegroundColor Green }
    catch { Start-Process cmd -ArgumentList '/c', "`"$boost`" noadmin"; Write-Host '  Started Game Boost without admin (admin prompt was declined)' -ForegroundColor Yellow }
}

Write-Host ''
Write-Host '  All started. Run "Stream Doctor.bat" for a full check before going live.' -ForegroundColor Cyan
Start-Sleep -Seconds 4
