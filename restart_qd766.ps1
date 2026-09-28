$ErrorActionPreference = "Stop"

$listener = netstat -ano | Select-String ":8767 .*LISTENING" | Select-Object -First 1
if ($listener) {
    $backendProcessId = [int](($listener.ToString().Trim() -split "\s+")[-1])
    Stop-Process -Id $backendProcessId -Force
    Start-Sleep -Seconds 1
}

Start-Process powershell.exe `
    -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File "D:\QD766\app\tools\start_backend.ps1"' `
    -WorkingDirectory "D:\QD766\app" `
    -WindowStyle Hidden

Start-Sleep -Seconds 5
$response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8767/"
Write-Host "QD766_OK"
Write-Host "URL=http://127.0.0.1:8767/"
Write-Host "STATUS=$($response.StatusCode)"
