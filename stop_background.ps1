$ErrorActionPreference = "SilentlyContinue"

$killed = $false
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' or Name = 'cmd.exe'" | Where-Object {
    $_.CommandLine -like "*hedge-fund-part2-final*main.py*"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[SUCCESS] Stopped background process (PID $($_.ProcessId))" -ForegroundColor Green
    $killed = $true
}

$lines = netstat -ano | Select-String ":8000\s+LISTENING\s+(\d+)"
foreach ($line in $lines) {
    if ($line.Line -match ":8000\s+LISTENING\s+(\d+)") {
        $p = [int]$matches[1]
        if ($p -gt 0) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "[SUCCESS] Stopped process $p listening on port 8000" -ForegroundColor Green
            $killed = $true
        }
    }
}

if (-not $killed) {
    Write-Host "[INFO] No running instance of the app was found on port 8000." -ForegroundColor Yellow
}
