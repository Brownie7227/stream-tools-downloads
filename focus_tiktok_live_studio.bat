@echo off
REM Focuses TikTok LIVE Studio and sets all of its processes to High priority.
REM Matches on the process name OR the name Task Manager shows, so it works
REM even if the .exe is named something different.
set "MATCH=TikTok LIVE Studio"

set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$match = $env:MATCH
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like "*$match*" -or $_.Name -like '*tiktok*live*' -or $_.Description -like "*$match*"
}

if (-not $procs) {
    Write-Host "$match isn't running."
    Start-Sleep -Seconds 2
    exit
}

# High priority for every matching process (all 17 or so)
$ok = 0
foreach ($p in $procs) {
    try { $p.PriorityClass = 'High'; $ok++ } catch { }
}
Write-Host "Set High priority on $ok of $($procs.Count) processes."

# Bring the main window to the front
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
}
"@

$win = $procs | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } | Select-Object -First 1
if (-not $win) { $win = $procs | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1 }

if ($win) {
    [Win]::ShowWindow($win.MainWindowHandle, 9) | Out-Null   # restore if minimized
    [Win]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)          # Alt press/release trick so Windows
    [Win]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)          # allows the focus change
    [Win]::SetForegroundWindow($win.MainWindowHandle) | Out-Null
    Write-Host "Window focused."
} else {
    Write-Host "No visible window found."
}
Start-Sleep -Seconds 1
