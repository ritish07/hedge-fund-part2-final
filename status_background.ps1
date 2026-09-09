$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $scriptDir "server.log"

try {
    $status = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host " Status: RUNNING" -ForegroundColor Green
    Write-Host " URL:    http://localhost:8000" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host " Engine Active:    $($status.is_running)" -ForegroundColor White
    Write-Host " Account Equity:   `$$($status.equity)" -ForegroundColor White
    Write-Host " Active Positions: $($status.open_positions.Count)" -ForegroundColor White
} catch {
    Write-Host "=========================================" -ForegroundColor Yellow
    Write-Host " Status: STOPPED (http://localhost:8000 is not responding)" -ForegroundColor Yellow
    Write-Host "=========================================" -ForegroundColor Yellow
}

if (Test-Path $logFile) {
    Write-Host "`n--- Recent Logs (last 10 lines) ---" -ForegroundColor Gray
    Get-Content $logFile -Tail 10
}
