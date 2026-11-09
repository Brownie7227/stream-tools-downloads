@echo off
REM Stream Doctor - run before going live. Checks your stream setup and fixes the easy stuff.
title Stream Doctor
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$ErrorActionPreference = 'SilentlyContinue'
$Programs = $env:HERE.TrimEnd('\')
$results = New-Object System.Collections.ArrayList

function Report($level, $text) {
    # level: ok / warn / bad
    $colour = @{ ok = 'Green'; warn = 'Yellow'; bad = 'Red' }[$level]
    $mark = @{ ok = '[ OK ]'; warn = '[WARN]'; bad = '[FAIL]' }[$level]
    Write-Host "$mark $text" -ForegroundColor $colour
    [void]$results.Add($level)
}

function Ask($question) {
    $a = Read-Host "       $question (Y/N)"
    return $a -match '^[Yy]'
}

function Get-Http($url) {
    try { return (Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 3).StatusCode } catch { return 0 }
}

function Scripts($pattern) {
    Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name = 'node.exe'" |
        Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch '--child' } | Sort-Object CreationDate
}

Write-Host ''
Write-Host '  STREAM DOCTOR' -ForegroundColor Cyan
Write-Host '  -------------' -ForegroundColor Cyan
Write-Host ''

# ---- 1. duplicate / old script copies -------------------------------------------------
$chaos = @(Scripts 'fortnite_chaos')
if ($chaos.Count -gt 1) {
    Report 'bad' "$($chaos.Count) copies of Fortnite Chaos are running (they cancel each other out)."
    if (Ask 'Close all of them so you can start one fresh?') {
        $chaos | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep -Milliseconds 500
        Start-Process cmd -ArgumentList '/k', "cd /d `"$Programs`" && py -3 fortnite_chaos.py" -WindowStyle Minimized
        Start-Sleep -Seconds 4
        Write-Host '       Started one fresh copy.' -ForegroundColor Gray
    }
} elseif ($chaos.Count -eq 0) {
    Report 'bad' 'Fortnite Chaos is not running.'
    if (Ask 'Start it now?') {
        Start-Process cmd -ArgumentList '/k', "cd /d `"$Programs`" && py -3 fortnite_chaos.py" -WindowStyle Minimized
        Start-Sleep -Seconds 4
    }
} else {
    Report 'ok' 'Fortnite Chaos is running (one copy).'
}

$flash = @(Scripts 'flashbang\.py')
if ($flash.Count -gt 0) {
    Report 'warn' 'The old flashbang.py is running - Fortnite Chaos does the flashbang now, and they fight over port 8765.'
    if (Ask 'Close the old flashbang?') { $flash | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }
}

$bot = @(Scripts 'bot\.js')
if ($bot.Count -gt 0) {
    Report 'warn' 'The old Discord bot (bot.js) is running - Fortnite Chaos does the Discord jumpscare now, so it would play twice.'
    if (Ask 'Close the old bot?') { $bot | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }
}

# ---- 2. does Fortnite Chaos answer? ---------------------------------------------------
if ((Get-Http 'http://127.0.0.1:8766/status') -eq 200) {
    Report 'ok' 'Fortnite Chaos answers gifts (port 8766).'
    $discord = (Invoke-RestMethod 'http://127.0.0.1:8766/status' -TimeoutSec 3).discord
    switch ($discord) {
        'connected' { Report 'ok' 'Discord jumpscare is connected.' }
        'error'     { Report 'bad' 'Discord jumpscare is off - check the Fortnite Chaos window for why.' }
        'off'       { Report 'warn' 'Discord jumpscare is off (no bot token found).' }
        $null       { Report 'warn' 'Fortnite Chaos is an old version without the Discord jumpscare - restart it.' }
        default     { Report 'warn' "Discord jumpscare is $discord - give it a few seconds." }
    }
    if ((Get-Http 'http://127.0.0.1:8766/overlay.html') -eq 200) { Report 'ok' 'Viewer overlay is up (overlay.html).' }
    else { Report 'bad' 'Viewer overlay is not loading - the old version of Fortnite Chaos may be running.' }
    try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8765/check' -TimeoutSec 2 | Out-Null; $fb = $true }
    catch { $fb = [bool]$_.Exception.Response }
    if ($fb) { Report 'ok' 'Old flashbang links (port 8765) go to Fortnite Chaos.' }
    else { Report 'warn' 'Port 8765 is not answering - TikFinity flashbang links pointing at 8765 will do nothing.' }
} else {
    Report 'bad' 'Fortnite Chaos is not answering on port 8766 - gifts will do nothing.'
}

# ---- 3. TikTok LIVE Studio -------------------------------------------------------------
$ls = Get-Process -Name 'TikTok LIVE Studio' -ErrorAction SilentlyContinue
if ($ls) { Report 'ok' 'TikTok LIVE Studio is running.' } else { Report 'warn' 'TikTok LIVE Studio is not running yet.' }
$svc = Join-Path $env:APPDATA 'TikTok LIVE Studio\TTStore\services.json'
if (Test-Path $svc) {
    $orientation = ([regex]'"currentOrientation":\s*"(\w+)"').Match([IO.File]::ReadAllText($svc)).Groups[1].Value
    if ($orientation -eq 'dual') {
        Report 'warn' 'LIVE Studio is set to landscape + vertical (two streams). Vertical only is lighter on your PC.'
    } elseif ($orientation) {
        Report 'ok' "LIVE Studio layout: $orientation only."
    }
}

# ---- 4. Fortnite settings ---------------------------------------------------------------
$ini = Join-Path $env:LOCALAPPDATA 'FortniteGame\Saved\Config\WindowsClient\GameUserSettings.ini'
if (Test-Path $ini) {
    $cfg = [IO.File]::ReadAllText($ini)
    $rhi = ([regex]'(?m)^PreferredRHI=(\w+)').Match($cfg).Groups[1].Value
    $lvl = ([regex]'(?m)^PreferredFeatureLevel=(\w+)').Match($cfg).Groups[1].Value
    $fps = [double]([regex]'(?m)^FrameRateLimit=([\d.]+)').Match($cfg).Groups[1].Value
    # Performance mode is the lightest on the CPU: on 19 Oct (Performance, 144 fps) the CPU was fine for 3 hours,
    # on 21-23 Oct (DirectX 12) it was maxed from the moment you went live.
    if ($lvl -eq 'es31') { Report 'ok' 'Fortnite is on Performance mode (lightest on the CPU).' }
    else { Report 'warn' "Fortnite is on $(if ($rhi) { $rhi.ToUpper() } else { 'DirectX' }) - Performance mode uses much less CPU while streaming." }
    if ($fps -eq 0) { Report 'bad' 'Fortnite has no frame rate cap - set it to 144 or lower while streaming.' }
    elseif ($fps -gt 144) { Report 'warn' "Fortnite frame cap is $fps - 144 or lower is easier on the CPU while streaming." }
    else { Report 'ok' "Fortnite frame cap: $fps fps." }
}

# Windows background recording (Game Bar "record what happened") quietly records your game the whole time
$dvr = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' -ErrorAction SilentlyContinue
if ($dvr.AppCaptureEnabled -eq 1 -and $dvr.HistoricalCaptureEnabled -ne 0) {
    Report 'warn' 'Windows background recording may be on - turn off Settings > Gaming > Captures > "Record what happened".'
} else {
    Report 'ok' 'Windows background recording is off.'
}

# ---- 5. CPU / RAM / disk -----------------------------------------------------------------
$samples = 1..3 | ForEach-Object { (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average; Start-Sleep -Milliseconds 700 }
$cpu = [math]::Round(($samples | Measure-Object -Average).Average)
$os = Get-CimInstance Win32_OperatingSystem
$ramUsed = [math]::Round(100 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize * 100)
$ramFree = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$game = Get-Process -Name 'FortniteClient-Win64-Shipping' -ErrorAction SilentlyContinue
$cpuLimit = if ($game) { 85 } else { 50 }
if ($cpu -ge $cpuLimit) { Report 'bad' "CPU is already at $cpu% - close something before going live." }
elseif ($cpu -ge $cpuLimit - 20) { Report 'warn' "CPU is at $cpu%." }
else { Report 'ok' "CPU is at $cpu%." }
if ($ramUsed -ge 85) { Report 'bad' "RAM is $ramUsed% used ($ramFree GB free)." }
elseif ($ramUsed -ge 70) { Report 'warn' "RAM is $ramUsed% used ($ramFree GB free)." }
else { Report 'ok' "RAM is $ramUsed% used ($ramFree GB free)." }
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$diskFree = [math]::Round($disk.FreeSpace / 1GB)
if ($diskFree -lt 30) { Report 'warn' "Only $diskFree GB free on C:." } else { Report 'ok' "$diskFree GB free on C:." }

# ---- 6. background apps you don't need while live ----------------------------------------
$optional = [ordered]@{
    'EpicWebHelper'    = 'Epic Games web helper'
    'steamwebhelper'   = 'Steam'
    'steam'            = 'Steam'
    'RazerCortex'      = 'Razer Cortex'
}
if ($game) { $optional['EpicGamesLauncher'] = 'Epic Games Launcher (Fortnite is already open)' }
$found = foreach ($name in $optional.Keys) {
    $procs = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
    if ($procs) {
        [pscustomobject]@{ Name = $name; Label = $optional[$name];
            MB = [math]::Round(($procs | Measure-Object WorkingSet64 -Sum).Sum / 1MB) }
    }
}
if ($found) {
    $labels = ($found | Group-Object Label | ForEach-Object { "$($_.Name) ($(($_.Group | Measure-Object MB -Sum).Sum) MB)" }) -join ', '
    Report 'warn' "Running in the background: $labels"
    if (Ask 'Close these to free up CPU and RAM?') {
        foreach ($f in $found) { Get-Process -Name $f.Name -ErrorAction SilentlyContinue | Stop-Process -Force }
        Write-Host '       Closed.' -ForegroundColor Gray
    }
} else {
    Report 'ok' 'No unneeded background apps found.'
}
$claude = @(Get-Process -Name 'claude' -ErrorAction SilentlyContinue)
if ($claude) {
    $mb = [math]::Round(($claude | Measure-Object WorkingSet64 -Sum).Sum / 1MB)
    Write-Host "       Note: the Claude app is using $mb MB - close it yourself before going live if you don't need it." -ForegroundColor Gray
}

# ---- summary -----------------------------------------------------------------------------
$bad = @($results | Where-Object { $_ -eq 'bad' }).Count
$warn = @($results | Where-Object { $_ -eq 'warn' }).Count
Write-Host ''
if ($bad) { Write-Host "  $bad problem(s) and $warn warning(s) - fix the red ones before going live." -ForegroundColor Red }
elseif ($warn) { Write-Host "  Good to go, with $warn warning(s)." -ForegroundColor Yellow }
else { Write-Host '  All good - go live!' -ForegroundColor Green }
Write-Host ''
Read-Host '  Press Enter to close'
