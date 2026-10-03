param(
    [switch]$CloseReviewedCircuit
)

$ErrorActionPreference = "Stop"

git -c http.sslBackend=openssl push origin main
if ($LASTEXITCODE -ne 0) {
    throw "Không đẩy được bản sửa lên GitHub."
}

# Recover actual deployed UI/backend sources before the full application copy.
# Keep this local, ignored and excluded from deployment; never print configuration contents.
$existingApplication = 'D:\QD766\app'
if (Test-Path -LiteralPath (Join-Path $existingApplication 'web\index.html')) {
    $sourceBackup = Join-Path $PSScriptRoot ('.tmp-application-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
    New-Item -ItemType Directory -Path $sourceBackup -Force | Out-Null
    foreach ($entry in @('web','src','tools','.env','pyproject.toml','alembic.ini')) {
        $savedSource = Join-Path $existingApplication $entry
        if (Test-Path -LiteralPath $savedSource) {
            Copy-Item -LiteralPath $savedSource -Destination (Join-Path $sourceBackup $entry) -Recurse -Force
        }
    }
    Write-Output "APPLICATION_BACKUP=$sourceBackup"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
    (Join-Path $PSScriptRoot "tools\deploy_local_server.ps1") `
    -RegisterTasks
if ($LASTEXITCODE -ne 0) {
    throw "Triển khai QD766 không thành công."
}

if ($CloseReviewedCircuit) {
    & (Join-Path $PSScriptRoot ".venv\Scripts\python.exe") `
        (Join-Path $PSScriptRoot "tools\manage_collection_control.py") `
        close --confirm-reviewed
    if ($LASTEXITCODE -ne 0) {
        throw "Không đóng được circuit sau khi đã xác nhận kiểm tra."
    }
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
    (Join-Path $PSScriptRoot "restart_qd766.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Khởi động lại QD766 không thành công."
}
