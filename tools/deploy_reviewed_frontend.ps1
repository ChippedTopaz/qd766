param(
    [string]$Application = 'D:\QD766\app',
    [string]$RestoreBackup = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$webTarget = Join-Path ([IO.Path]::GetFullPath($Application)) 'web'
if (-not (Test-Path -LiteralPath (Join-Path $webTarget 'index.html'))) {
    throw 'Existing deployed web/index.html is required; no application is installed by this script.'
}
function TargetPath([string]$relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $webTarget $relative))
    if (-not $path.StartsWith($webTarget.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Asset path outside web directory.'
    }
    return $path
}
function RestoreAssets([string]$backup) {
    $manifest = Get-Content -LiteralPath (Join-Path $backup 'manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.target -ne $webTarget) { throw 'Backup belongs to a different deployment target.' }
    # Restore index last. Added assets may remain, but the old index no longer uses them.
    foreach ($asset in ($manifest.assets | Sort-Object { $_.path -eq 'index.html' })) {
        if ($asset.existed) {
            $saved = Join-Path $backup $asset.path
            if ((Get-FileHash -LiteralPath $saved -Algorithm SHA256).Hash -ne $asset.oldHash) {
                throw 'Backup checksum mismatch.'
            }
        }
    }
    foreach ($asset in ($manifest.assets | Sort-Object { $_.path -eq 'index.html' })) {
        if ($asset.existed) {
            $destination = TargetPath $asset.path
            Copy-Item -LiteralPath (Join-Path $backup $asset.path) -Destination $destination -Force
            if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $asset.oldHash) {
                throw 'Restore checksum mismatch.'
            }
        }
    }
    Write-Output 'FRONTEND_RESTORED=True'
}
if ($RestoreBackup) {
    RestoreAssets $RestoreBackup
    exit 0
}
$assets = @('styles.css', 'bento.css', 'collection.css')
$assets += Get-ChildItem -LiteralPath (Join-Path $repo 'web\dist') -Filter '*.js' | ForEach-Object { 'dist\' + $_.Name }
$assets += @('vendor\tom-select\tom-select.complete.min.js', 'vendor\tom-select\tom-select.default.min.css', 'vendor\exceljs\exceljs.min.js', 'vendor\exceljs\LICENSE', 'index.html')
foreach ($relative in $assets) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo ('web\' + $relative)))) { throw "Missing asset: $relative" }
}
$backupRoot = Join-Path $repo '.tmp-frontend-backups'
$backup = Join-Path $backupRoot ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$records = foreach ($relative in $assets) {
    $destination = TargetPath $relative
    $existed = Test-Path -LiteralPath $destination
    $oldHash = $null
    if ($existed) {
        $saved = Join-Path $backup $relative
        New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $destination -Destination $saved
        $oldHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
        if ((Get-FileHash -LiteralPath $saved -Algorithm SHA256).Hash -ne $oldHash) { throw 'Backup checksum mismatch.' }
    }
    [pscustomobject]@{ path=$relative; existed=$existed; oldHash=$oldHash }
}
@{ target=$webTarget; assets=@($records) } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backup 'manifest.json') -Encoding UTF8
Write-Output "FRONTEND_BACKUP=$backup"
try {
    foreach ($relative in $assets) {
        $source = Join-Path $repo ('web\' + $relative)
        $destination = TargetPath $relative
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash) {
            throw "Deployment checksum mismatch: $relative"
        }
    }
} catch {
    RestoreAssets $backup
    throw
}
Write-Output 'FRONTEND_DEPLOYED=True'
Write-Output 'BACKEND_WORKER_DATABASE_UNCHANGED=True'
