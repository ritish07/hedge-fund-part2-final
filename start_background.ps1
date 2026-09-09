$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

try {
    $existing = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -TimeoutSec 1 -ErrorAction Stop
    Write-Host "[INFO] App is already running and healthy at http://localhost:8000" -ForegroundColor Yellow
    exit 0
} catch {}

$pythonExe = Join-Path $scriptDir ".venv\Scripts\python.exe"
$mainPy = Join-Path $scriptDir "main.py"
$logFile = Join-Path $scriptDir "server.log"

$batFile = Join-Path $scriptDir "run_server.bat"
$cmd = "cmd.exe /c `"$batFile`""
$res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmd
    CurrentDirectory = $scriptDir
}

if ($res.ReturnValue -eq 0) {
    Write-Host "[SUCCESS] Autonomous AI Hedge Fund started in background (PID: $($res.ProcessId))" -ForegroundColor Green
    Write-Host "Dashboard: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Log file:  $logFile" -ForegroundColor Cyan
} else {
    Write-Host "[ERROR] Failed to start background process. Error code: $($res.ReturnValue)" -ForegroundColor Red
}
