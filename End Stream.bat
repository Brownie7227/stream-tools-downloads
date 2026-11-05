@echo off
:: Ending TikTok Streaming Setup - closes the stream scripts so nothing is left running overnight.
title End Stream
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$ErrorActionPreference = 'SilentlyContinue'
$Programs = $env:HERE.TrimEnd('\')

function Close-Script($pattern, $label) {
    # the cmd windows they run in first, then anything left over
    $found = $false
    Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" | Where-Object { $_.CommandLine -match $pattern } |
        ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null; $found = $true }
    Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name = 'node.exe' or Name = 'py.exe'" |
        Where-Object { $_.CommandLine -match $pattern } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $found = $true }
    if ($found) { Write-Host "  Closed $label" -ForegroundColor Green } else { Write-Host "  $label wasn't running" -ForegroundColor Gray }
}

function Close-App($process, $label) {
    $procs = Get-Process -Name $process -ErrorAction SilentlyContinue
    if (-not $procs) { Write-Host "  $label wasn't running" -ForegroundColor Gray; return }
    $procs | ForEach-Object { [void]$_.CloseMainWindow() }
    Start-Sleep -Seconds 5
    if (Get-Process -Name $process -ErrorAction SilentlyContinue) { return $false }
    Write-Host "  Closed $label" -ForegroundColor Green
    return $true
}

Write-Host ''
Write-Host '  Ending stream...' -ForegroundColor Cyan
Write-Host ''
Close-Script 'fortnite_chaos' 'Fortnite Chaos'
Close-Script 'flashbang\.py' 'the old flashbang'

# put back the Windows services Game Boost paused (asks for admin)
$pausedList = Join-Path $env:LOCALAPPDATA 'GameBoost\paused-services.txt'
if (Test-Path $pausedList) {
    # asks for admin here and waits for it to finish, so the message below is the truth
    try { Start-Process (Join-Path $Programs 'Game Boost.bat') -ArgumentList 'undo' -Verb RunAs -Wait -ErrorAction Stop } catch { }
    if (Test-Path $pausedList) { Write-Host "  Windows services are still paused (admin prompt declined?) - a reboot puts them back" -ForegroundColor Yellow }
    else { Write-Host '  Put back the Windows services Game Boost paused' -ForegroundColor Green }
}

Write-Host ''
$a = Read-Host '  Also close TikTok LIVE Studio, BetterTok and Spotify? (Y/N)'
if ($a -match '^[Yy]') {
    # LIVE Studio is asked nicely (never force-closed) so it can save your scenes
    if ((Close-App 'TikTok LIVE Studio' 'TikTok LIVE Studio') -eq $false) {
        Write-Host '  TikTok LIVE Studio is still in the tray - right-click its icon by the clock and choose Quit.' -ForegroundColor Yellow
    }
    foreach ($app in @(@('bettertok-desktop', 'BetterTok'), @('Spotify', 'Spotify'))) {
        if ((Close-App $app[0] $app[1]) -eq $false) {
            Get-Process -Name $app[0] -ErrorAction SilentlyContinue | Stop-Process -Force
            Write-Host "  Closed $($app[1])" -ForegroundColor Green
        }
    }
}

$report = Join-Path $Programs 'Stream Report.bat'
if (Test-Path $report) {
    Write-Host ''
    $a = Read-Host '  Make a report of how this stream ran (CPU, RAM, lag)? (Y/N)'
    if ($a -match '^[Yy]') { Start-Process $report }
}

$clips = Join-Path $Programs 'Chaos Clips.bat'
if (Test-Path $clips) {
    $a = Read-Host '  Cut clips of the best moments? (needs a recording of the stream) (Y/N)'
    if ($a -match '^[Yy]') { Start-Process $clips }
}
Write-Host ''
Write-Host '  Done. GG!' -ForegroundColor Cyan
Start-Sleep -Seconds 3
