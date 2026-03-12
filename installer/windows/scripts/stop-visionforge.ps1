<#
.SYNOPSIS
    Stop all VisionForge Docker services (data is preserved in Docker volumes).
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Compose    = Join-Path $InstallDir "infra\docker-compose.yml"

function Write-Step([string]$msg) {
    Write-Host "[VisionForge] $msg" -ForegroundColor Cyan
}

Write-Step "Stopping VisionForge services..."

Push-Location $InstallDir
try {
    & docker compose -f $Compose down
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[VisionForge] WARNING: docker compose down exited with $LASTEXITCODE." -ForegroundColor Yellow
    } else {
        Write-Host "[VisionForge] All services stopped. Your data is preserved in Docker volumes." -ForegroundColor Green
    }
} finally {
    Pop-Location
}
