$ErrorActionPreference = "Stop"

$backendTask = Get-ScheduledTask -TaskName "QD766 Backend" -ErrorAction SilentlyContinue
$workerTask = Get-ScheduledTask -TaskName "QD766 Worker" -ErrorAction SilentlyContinue
$nationalSummaryTask = Get-ScheduledTask -TaskName "QD766 National Summary" -ErrorAction SilentlyContinue
foreach ($task in @($backendTask, $workerTask, $nationalSummaryTask)) {
    if ($null -ne $task -and $task.State -eq "Running") {
        Stop-ScheduledTask -InputObject $task
    }
}

$listener = netstat -ano | Select-String ":8767 .*LISTENING" | Select-Object -First 1
if ($listener) {
    $backendProcessId = [int](($listener.ToString().Trim() -split "\s+")[-1])
    Stop-Process -Id $backendProcessId -Force
    Start-Sleep -Seconds 1
}

if ($null -ne $backendTask) {
    Start-ScheduledTask -InputObject $backendTask
}
else {
    Start-Process powershell.exe `
        -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File "D:\QD766\app\tools\start_backend.ps1"' `
        -WorkingDirectory "D:\QD766\app" `
        -WindowStyle Hidden
}
if ($null -ne $workerTask) {
    Start-ScheduledTask -InputObject $workerTask
}
if ($null -ne $nationalSummaryTask) {
    Start-ScheduledTask -InputObject $nationalSummaryTask
}

Start-Sleep -Seconds 5
$response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8767/"
Write-Host "QD766_OK"
Write-Host "URL=http://127.0.0.1:8767/"
Write-Host "STATUS=$($response.StatusCode)"
if ($null -ne $workerTask) {
    $workerState = (Get-ScheduledTask -TaskName "QD766 Worker").State
    Write-Host "WORKER_TASK=$workerState"
}
if ($null -ne $nationalSummaryTask) {
    $nationalSummaryState = (Get-ScheduledTask -TaskName "QD766 National Summary").State
    Write-Host "NATIONAL_SUMMARY_TASK=$nationalSummaryState"
}
