param(
    [switch]$CloseReviewedCircuit
)

$ErrorActionPreference = "Stop"

git -c http.sslBackend=openssl push origin main
if ($LASTEXITCODE -ne 0) {
    throw "Không đẩy được bản sửa lên GitHub."
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
