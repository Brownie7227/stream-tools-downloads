@echo off
REM Focuses BetterTok and sets it to High priority.
REM Change the name below if the process is called something else
REM (check Task Manager > Details tab, without the ".exe").
set "PROC=bettertok-desktop"

set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); iex ($s.Substring($s.IndexOf('#PS'+'START')))" & exit /b

#PSSTART
$name = $env:PROC
$procs = Get-Process -Name $name -ErrorAction SilentlyContinue

if (-not $procs) {
    Write-Host "$name isn't running."
    Start-Sleep -Seconds 2
    exit
}

# High priority for every matching process
foreach ($p in $procs) {
    try { $p.PriorityClass = 'High' } catch { Write-Host "Couldn't set priority on PID $($p.Id): $_" }
}

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

$win = $procs | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($win) {
    [Win]::ShowWindow($win.MainWindowHandle, 9) | Out-Null   # restore if minimized
    [Win]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)          # Alt press/release trick so Windows
    [Win]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)          # allows the focus change
    [Win]::SetForegroundWindow($win.MainWindowHandle) | Out-Null
    Write-Host "$name focused and set to High priority."
} else {
    Write-Host "Priority set, but no visible window found for $name."
}
Start-Sleep -Seconds 1
