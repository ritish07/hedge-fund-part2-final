$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$pythonExe = Join-Path $scriptDir ".venv\Scripts\python.exe"
$gatewayPy = Join-Path $scriptDir "mt5_gateway.py"
$logFile = Join-Path $scriptDir "gateway.log"

$cmd = "cmd.exe /c `"$pythonExe`" `"$gatewayPy`" > `"$logFile`" 2>&1"
$res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmd
    CurrentDirectory = $scriptDir
}

if ($res.ReturnValue -eq 0) {
    Write-Host "[SUCCESS] MT5 Execution Gateway started in background (PID: $($res.ProcessId))" -ForegroundColor Green
    Write-Host "Gateway URL: http://0.0.0.0:8001" -ForegroundColor Cyan
    Write-Host "Log file:    $logFile" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Your Linux server can now send trades to this machine!" -ForegroundColor Yellow
} else {
    Write-Host "[ERROR] Failed to start gateway. Error code: $($res.ReturnValue)" -ForegroundColor Red
}
