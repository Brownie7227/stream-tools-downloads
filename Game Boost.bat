@echo off
:: Game Boost - a lighter Razer Cortex boost. Run it once before you play; it does its job and closes,
:: nothing is left running in the background.
::   Game Boost.bat          boost: goes through your apps biggest first and asks Y/N to close each one,
::                           then pauses some Windows services (asks for admin for that part)
::   Game Boost.bat undo     restarts the services it paused (End Stream.bat does this for you)
::   Game Boost.bat test     shows what it would ask about and do, without changing anything
:: Rebooting also undoes it - the services are only paused, never disabled.
title Game Boost
if /i "%~1"=="test" goto run
:: Start Stream opens it as admin; "noadmin" is its fallback when the admin prompt was declined, so don't ask again
if /i "%~1"=="noadmin" goto run
net session >nul 2>&1
if %errorlevel%==0 goto run
:: (ArgumentList only when there is one - an empty one makes Start-Process fail, so a plain run never got admin)
powershell -NoProfile -Command "$a=@{Verb='RunAs'; FilePath='%~f0'; ErrorAction='Stop'}; if ('%~1') { $a.ArgumentList='%~1' }; try { Start-Process @a; exit 0 } catch { exit 1 }"
if not errorlevel 1 exit /b
echo   No admin rights - closing and lowering apps only, Windows services left alone.
:run
set "MODE=%~1"
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$ErrorActionPreference = 'SilentlyContinue'

# ---------------- settings ----------------
# Apps using at least this much memory get a Y/N question, biggest first
$AskAboveMB = 100
# ...or at least this much CPU (percent of the whole CPU), since the CPU is the bottleneck while streaming
$AskAboveCPU = 1

# Never asked about, because you need them while live: everything Start Stream opens, Discord, Fortnite,
# your audio/camera/stream tools, and the bits of Windows that keep the desktop working.
# Names as Task Manager's Details tab shows them, without ".exe".
$Keep = @(
    'TikTok LIVE Studio', 'MediaSDK_Server', 'bettertok-desktop', 'Spotify', 'node', 'python', 'pythonw', 'py',
    'Discord', 'FortniteClient-Win64-Shipping', 'FortniteClient-Win64-Shipping_EAC_EOS', 'FortniteLauncher', 'EasyAntiCheat', 'EasyAntiCheat_EOS', 'EOSOverlayRenderer-Win64-Shipping', 'EpicOnlineServicesUserHelper',
    'Elgato.WaveLink', 'WaveLinkSE', 'Camera Hub', 'StreamDeck', 'NVIDIA Broadcast', 'TikFinity', 'Streamer.bot', 'obs64',
    'explorer', 'dwm', 'powershell', 'cmd', 'conhost', 'WindowsTerminal', 'OpenConsole', 'Memory Compression', 'System',
    'ShellExperienceHost', 'StartMenuExperienceHost', 'SearchHost', 'TextInputHost', 'ctfmon', 'sihost', 'audiodg',
    'SecurityHealthSystray', 'msedgewebview2', 'csrss', 'winlogon', 'wininit', 'lsass', 'services', 'smss',
    'svchost', 'fontdrvhost', 'RuntimeBroker', 'dllhost'
)
# Helpers installed in the same folder as a kept app are kept too (e.g. Stream Deck's QtWebEngineProcess).
# Anything Game Boost can't see the location of is skipped, so core Windows processes are never offered.

# Apps you say N to stay open, but get lower priority: Windows takes memory back from them first when RAM
# runs low, and they get the CPU last. Discord is never asked about, but gets the memory part only,
# so voice chat doesn't crackle when the PC is busy.
$LowerMemoryOnly = @('Discord')

# The stream's processes get above-normal CPU priority, ahead of Fortnite
$StreamFirst = @('TikTok LIVE Studio', 'MediaSDK_Server', 'AISDK_Server')

# Notes shown next to an app's name when it's asked about
$Notes = @{
    'claude'            = "this is Claude - closing it ends our chat"
    'EpicGamesLauncher' = 'Epic Games Launcher - fine to close once Fortnite is open'
    'RazerCortex'       = "Game Boost replaces its boost"
}

# Windows services paused while you play (what Cortex paused, minus the ones that can break things).
# Not paused: VaultSvc (saved logins), FontCache and StorSvc (slow app launches), swprv (already off).
$Services = [ordered]@{
    'WSearch'       = 'Windows Search indexing'
    'SysMain'       = 'SysMain / Superfetch'
    'DiagTrack'     = 'Telemetry'
    'DPS'           = 'Diagnostic Policy'
    'PcaSvc'        = 'Program Compatibility Assistant'
    'WMPNetworkSvc' = 'Media Player sharing'
    'Spooler'       = 'Print Spooler'
    'StiSvc'        = 'Scanner/camera import'
    'TrkWks'        = 'Link tracking'
    # these three use your internet, which the stream's upload needs
    'DoSvc'         = 'Delivery Optimization (shares Windows updates with other PCs over your upload)'
    'wuauserv'      = 'Windows Update'
    'BITS'          = 'Background downloads'
}
# ------------------------------------------

$Mode = "$env:MODE".ToLower()
$Test = $Mode -eq 'test'
$State = Join-Path $env:LOCALAPPDATA 'GameBoost\paused-services.txt'
$Admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host ''
if ($Mode -eq 'undo') {
    Write-Host '  Game Boost - undo' -ForegroundColor Cyan
    if (-not (Test-Path $State)) { Write-Host '  Nothing to undo.' -ForegroundColor Gray }
    else {
        foreach ($name in Get-Content $State) {
            Start-Service $name
            if ((Get-Service $name).Status -eq 'Running') { Write-Host "  Restarted $name" -ForegroundColor Green }
            else { Write-Host "  Couldn't restart $name (a reboot will)" -ForegroundColor Yellow }
        }
        Remove-Item $State
    }
    Start-Sleep -Seconds 2
    exit
}

Write-Host $(if ($Test) { '  Game Boost - TEST, nothing will be changed' } else { '  Game Boost' }) -ForegroundColor Cyan
$os = Get-CimInstance Win32_OperatingSystem
$freeBefore = $os.FreePhysicalMemory / 1MB
Write-Host ("  RAM: {0:N0}% used, {1:N1} GB free" -f (100 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize * 100), $freeBefore) -ForegroundColor Gray
Write-Host ''

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MemPrio {
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll")] static extern bool SetProcessInformation(IntPtr h, int cls, ref uint info, uint size);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    public static bool Set(int pid, uint level) {   // 1 = very low ... 5 = normal
        IntPtr h = OpenProcess(0x0200, false, pid);  // PROCESS_SET_INFORMATION
        if (h == IntPtr.Zero) return false;
        bool ok = SetProcessInformation(h, 0, ref level, 4);  // 0 = ProcessMemoryPriority
        CloseHandle(h);
        return ok;
    }
}
"@

function Lower($procs, $memoryOnly) {
    foreach ($p in $procs) {
        [void][MemPrio]::Set($p.Id, 2)
        if (-not $memoryOnly) { try { $p.PriorityClass = 'BelowNormal' } catch { } }
    }
}

# 1. your apps, biggest first: close (Y), keep but lower (N), or stop asking (Q)
$session = (Get-Process -Id $PID).SessionId
$windir = $env:windir.ToLower() + '\'
$keptFolders = @(Get-Process | Where-Object { $Keep -contains $_.Name -and $_.Path } |
    ForEach-Object { (Split-Path $_.Path).ToLower() + '\' } | Where-Object { $_ -ne $windir -and -not $_.StartsWith($windir) } |
    Sort-Object -Unique)
function Describe($path, $name) {
    $vi = [Diagnostics.FileVersionInfo]::GetVersionInfo($path)
    $d = if ($vi.FileDescription -and $vi.FileDescription.Trim() -ne $name) { $vi.FileDescription.Trim() }
         elseif ($vi.ProductName) { $vi.ProductName.Trim() } else { '' }
    if ($vi.CompanyName -and $d -notlike "*$($vi.CompanyName.Trim())*") { $d = ("$d, by " + $vi.CompanyName.Trim()).TrimStart(', ') }
    $d
}
$cands = @(Get-Process | Where-Object {
    $path = if ($_.Path) { $_.Path.ToLower() } else { $null }
    $path -and $_.SessionId -eq $session -and $_.Id -ne $PID -and $Keep -notcontains $_.Name -and
    -not $path.StartsWith($windir) -and -not ($keptFolders | Where-Object { $path.StartsWith($_) })
})
$byId = @{}
foreach ($p in $cands) { $byId[$p.Id] = $p }

# CPU use over a short sample, since the CPU is what runs out first while streaming.
# The slow process-tree lookup runs during the sample instead of before it.
$cpuStart = @{}
foreach ($p in $cands) { $cpuStart[$p.Id] = $p.TotalProcessorTime.TotalMilliseconds }
$clock = [Diagnostics.Stopwatch]::StartNew()
$parentOf = @{}
Get-CimInstance Win32_Process | ForEach-Object { $parentOf[[int]$_.ProcessId] = [int]$_.ParentProcessId }
$wait = 1500 - $clock.ElapsedMilliseconds
if ($wait -gt 0) { Start-Sleep -Milliseconds $wait }
$sampleMs = $clock.ElapsedMilliseconds
$cpuPct = @{}
foreach ($p in $cands) {
    $p.Refresh()
    $cpuPct[$p.Id] = [math]::Max(0, $p.TotalProcessorTime.TotalMilliseconds - $cpuStart[$p.Id]) / ($sampleMs * [Environment]::ProcessorCount) * 100
}

# helpers are grouped under the app that opened them, so one Y closes the whole app
function OwnerOf($p) {
    $o = $p; $ppid = $parentOf[$p.Id]; $hops = 0
    while ($ppid -and $byId[$ppid] -and $hops++ -lt 20) { $o = $byId[$ppid]; $ppid = $parentOf[$ppid] }
    $o
}
$skipParents = @('explorer', 'svchost', 'services', 'sihost', 'userinit', 'winlogon', 'cmd', 'powershell')
$apps = @($cands | Group-Object { (OwnerOf $_).Id } | ForEach-Object {
    $owner = $byId[[int]$_.Name]
    $procs = $_.Group
    [pscustomobject]@{ Name = $owner.Name; Owner = $owner; Procs = $procs
                       MB = [math]::Round(($procs | Measure-Object WorkingSet64 -Sum).Sum / 1MB)
                       CPU = ($procs | ForEach-Object { $cpuPct[$_.Id] } | Measure-Object -Sum).Sum
                       Title = ($procs | Where-Object MainWindowTitle | Select-Object -First 1).MainWindowTitle }
} | Group-Object Name | ForEach-Object {   # several copies of the same app become one line
    $g = $_.Group
    [pscustomobject]@{ Name = $_.Name; Owner = $g[0].Owner; Procs = @($g.Procs); What = ''; MB = ($g | Measure-Object MB -Sum).Sum
                       CPU = ($g | Measure-Object CPU -Sum).Sum; Title = ($g | Where-Object Title | Select-Object -First 1).Title }
} | Where-Object { $_.MB -ge $AskAboveMB -or $_.CPU -ge $AskAboveCPU } | Sort-Object CPU, MB -Descending)

# what the program is, from the description and company baked into its .exe (what Task Manager shows).
# Only worked out for the apps that will be asked about - reading every .exe is slow.
foreach ($app in $apps) {
    $owner = $app.Owner
    $what = Describe $owner.Path $owner.Name
    $parent = Get-Process -Id $parentOf[$owner.Id]
    if ($parent -and $parent.Path -and $skipParents -notcontains $parent.Name) {
        $pd = Describe $parent.Path $parent.Name
        $what = ("$what - part of " + $(if ($pd) { $pd } else { $parent.Name })).TrimStart(' -')
    }
    if (-not $what) { $what = "no description - runs from $(Split-Path $owner.Path)" }
    $helpers = @($app.Procs.Name | Where-Object { $_ -ne $owner.Name } | Sort-Object -Unique)
    if ($helpers) { $what += "  [also closes: $($helpers -join ', ')]" }
    $app.What = $what
}

$AlwaysFile = Join-Path $env:LOCALAPPDATA 'GameBoost\always-close.txt'
$always = @(if (Test-Path $AlwaysFile) { Get-Content $AlwaysFile | Where-Object { $_.Trim() } })
if ($always) { Write-Host "  Always closed: $($always -join ', ')  (to change, edit $AlwaysFile)" -ForegroundColor Gray }
$KeepFile = Join-Path $env:LOCALAPPDATA 'GameBoost\always-keep.txt'
$alwaysKeep = @(if (Test-Path $KeepFile) { Get-Content $KeepFile | Where-Object { $_.Trim() } })
if ($alwaysKeep) { Write-Host "  Always kept: $($alwaysKeep -join ', ')  (to change, edit $KeepFile)" -ForegroundColor Gray }

if (-not $apps) { Write-Host "  No apps using more than $AskAboveMB MB or $AskAboveCPU% CPU to ask about." -ForegroundColor Gray }
else { Write-Host "  Close these apps?  Y = close   N = keep open (lowered priority)   A = always close   K = always keep   Q = stop asking" -ForegroundColor Cyan }
$freed = 0
$stop = $false
foreach ($app in $apps) {
    $label = $app.Name
    if ($app.Title -and $app.Title -ne $app.Name) { $label += " - $($app.Title)" }
    if ($label.Length -gt 60) { $label = $label.Substring(0, 57) + '...' }
    $note = if ($Notes[$app.Name]) { "  ($($Notes[$app.Name]))" } else { '' }
    $line = "  {0,6:N0} MB {1,5:N1}% CPU  {2}{3}" -f $app.MB, $app.CPU, $label, $note
    $whatLine = "                         $($app.What)"
    $auto = $always -contains $app.Name
    $autoKeep = $alwaysKeep -contains $app.Name
    if ($Test) {
        Write-Host $line; Write-Host $whatLine -ForegroundColor DarkGray
        if ($auto) { Write-Host '                         would close automatically (always close)' -ForegroundColor Green }
        elseif ($autoKeep) { Write-Host '                         would keep automatically, lowered (always keep)' -ForegroundColor Gray }
        continue
    }
    $answer = 'n'
    if ($auto) { Write-Host $line; $answer = 'y' }
    elseif ($autoKeep) { Write-Host $line; $answer = 'k' }
    elseif (-not $stop) {
        Write-Host $line
        Write-Host $whatLine -ForegroundColor DarkGray -NoNewline
        do { $answer = (Read-Host '   Y/N/A/K/Q').Trim().ToLower() } until ($answer -in 'y', 'n', 'a', 'k', 'q', 'yes', 'no')
        if ($answer -eq 'q') { $stop = $true; $answer = 'n' }
        if ($answer -in 'a', 'k') {
            New-Item -ItemType Directory -Force (Split-Path $AlwaysFile) | Out-Null
            Add-Content $(if ($answer -eq 'a') { $AlwaysFile } else { $KeepFile }) $app.Name
            if ($answer -eq 'a') { $answer = 'y' }
        }
    }
    if ($answer -like 'y*') {
        $app.Procs | ForEach-Object { [void]$_.CloseMainWindow() }
        $app.Procs | Wait-Process -Timeout 2   # moves on as soon as it has closed, instead of always waiting 2s
        $app.Procs | ForEach-Object { Stop-Process -Id $_.Id -Force }
        Get-Process -Name $app.Name | Stop-Process -Force
        $freed += $app.MB
        Write-Host $(if ($auto) { '                         closed automatically' } else { '           closed' }) -ForegroundColor Green
    } else {
        Lower $app.Procs $false
        if (-not $stop -or $answer -ne 'n') { Write-Host "           kept, lowered priority" -ForegroundColor Gray }
    }
}
if ($stop) { Write-Host '  The rest were kept, with lowered priority.' -ForegroundColor Gray }
foreach ($name in $LowerMemoryOnly) {
    $procs = @(Get-Process -Name $name)
    if ($procs -and -not $Test) { Lower $procs $true; Write-Host "  Lowered memory priority for $name (kept open)" -ForegroundColor Gray }
}

# 2. the stream gets the CPU before Fortnite when it's maxed out, so what viewers see stays smooth.
# LIVE Studio runs as admin, so this only works from the admin run. It resets when the apps close.
$streamProcs = @(Get-Process -Name $StreamFirst)
if (-not $streamProcs) { Write-Host '  TikTok LIVE Studio is not open - run Game Boost after it is to give the stream priority' -ForegroundColor Yellow }
elseif (-not $Admin -and -not $Test) { Write-Host '  Skipped giving the stream priority (needs admin)' -ForegroundColor Yellow }
else {
    $raised = 0
    foreach ($p in $streamProcs) {
        if ($p.PriorityClass -in 'High', 'AboveNormal', 'RealTime') { continue }  # Start Stream may already have set High
        if (-not $Test) { try { $p.PriorityClass = 'AboveNormal' } catch { continue } }
        $raised++
    }
    Write-Host "  Stream gets priority over Fortnite: raised $raised LIVE Studio processes (others were already raised)" -ForegroundColor Green
}

# 3. pause Windows services (needs admin)
Write-Host ''
if (-not $Admin -and -not $Test) {
    Write-Host '  Skipped pausing Windows services (needs admin)' -ForegroundColor Yellow
} else {
    $paused = @()
    # boosted twice: keep the first list, minus anything a reboot has already put back
    if (Test-Path $State) { $paused = @(Get-Content $State | Where-Object { (Get-Service $_).Status -ne 'Running' }) }
    foreach ($name in $Services.Keys) {
        if ((Get-Service $name).Status -ne 'Running') { continue }
        if (-not $Test) {
            Stop-Service $name -Force
            if ((Get-Service $name).Status -ne 'Stopped') { Write-Host "  Couldn't pause $($Services[$name])" -ForegroundColor Yellow; continue }
            if ($paused -notcontains $name) { $paused += $name }
        }
        Write-Host "  $(if ($Test) { 'Would pause' } else { 'Paused' }) $($Services[$name])" -ForegroundColor Green
    }
    if ($paused -and -not $Test) {
        New-Item -ItemType Directory -Force (Split-Path $State) | Out-Null
        $paused | Set-Content $State
    }
}

Write-Host ''
if (-not $Test) {
    Start-Sleep -Seconds 1
    $freeAfter = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    Write-Host ("  Closed apps were using about {0:N1} GB. Free RAM now {1:N1} GB (was {2:N1} GB)." -f ($freed / 1024), $freeAfter, $freeBefore) -ForegroundColor Cyan
}
Write-Host '  Boosted. End Stream (or "Game Boost.bat undo", or a reboot) puts the services back.' -ForegroundColor Cyan
Start-Sleep -Seconds 5
