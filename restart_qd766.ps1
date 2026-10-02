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
    $summaryDeadline = (Get-Date).AddSeconds(60)
    do {
        $nationalSummaryState = (Get-ScheduledTask -TaskName "QD766 National Summary").State
        if ($nationalSummaryState -ne "Running") {
            break
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $summaryDeadline)
    Write-Host "NATIONAL_SUMMARY_TASK=$nationalSummaryState"
    $nationalSummaryInfo = Get-ScheduledTaskInfo -TaskName "QD766 National Summary"
    Write-Host "NATIONAL_SUMMARY_LAST_RESULT=$($nationalSummaryInfo.LastTaskResult)"
    $summaryResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8767/api/v1/national-summaries?limit=10"
    $summaries = @($summaryResponse | Where-Object { $null -ne $_ })
    Write-Host "NATIONAL_SUMMARY_COUNT=$($summaries.Count)"
    try {
        $currentYear = (Get-Date).Year
        $yearSummary = Invoke-RestMethod -Uri "http://127.0.0.1:8767/api/v1/national-summaries/latest?period_type=year&year=$currentYear"
        if ($yearSummary.completenessState -ne "complete" -or $yearSummary.groupCount -ne 6) {
            throw "National summary is not a complete six-group snapshot."
        }
        Write-Host "NATIONAL_SUMMARY_COMPLETENESS=$($yearSummary.completenessState)"
        Write-Host "NATIONAL_SUMMARY_GROUP_COUNT=$($yearSummary.groupCount)"
        $provinceRows = @($yearSummary.data.evaluation | ForEach-Object { $_ })
        $phuTho = $provinceRows | Where-Object { $_.departmentName -eq "UBND tỉnh Phú Thọ" } | Select-Object -First 1
        if ($null -ne $phuTho) {
            $phuThoRank = 0
            for ($index = 0; $index -lt $provinceRows.Count; $index++) {
                if ($provinceRows[$index].departmentId -eq $phuTho.departmentId) {
                    $phuThoRank = $index + 1
                    break
                }
            }
            Write-Host "PHU_THO_YEAR_SCORE=$($phuTho.totalScore)"
            Write-Host "PHU_THO_YEAR_RANK=$phuThoRank/$($provinceRows.Count)"
            Write-Host "NATIONAL_SUMMARY_CAPTURED_AT=$($yearSummary.capturedAt)"
        }
    }
    catch {
        Write-Host "NATIONAL_SUMMARY_YEAR=NOT_AVAILABLE"
        $nationalSummaryLog = "D:\QD766\logs\national-summary.log"
        if (Test-Path -LiteralPath $nationalSummaryLog) {
            Get-Content -LiteralPath $nationalSummaryLog -Tail 3 | ForEach-Object {
                Write-Host "NATIONAL_SUMMARY_LOG=$_"
            }
        }
    }
}
