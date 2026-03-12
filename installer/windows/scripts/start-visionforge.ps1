<#
.SYNOPSIS
    Start all VisionForge Docker services.
    Supports CPU-only and GPU-enabled modes based on .env / registry flag.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Compose    = Join-Path $InstallDir "infra\docker-compose.yml"
$ComposeGpu = Join-Path $InstallDir "infra\docker-compose.gpu.yml"
$EnvFile    = Join-Path $InstallDir ".env"

function Write-Step([string]$msg) {
    Write-Host "[VisionForge] $msg" -ForegroundColor Cyan
}

# ── Detect GPU flag ──────────────────────────────────────────────────────────
$gpuEnabled = $false
if (Test-Path $EnvFile) {
    $envContents = Get-Content $EnvFile -Raw
    if ($envContents -match "COMPOSE_PROFILES\s*=\s*gpu") {
        $gpuEnabled = $true
    }
}

# ── Ensure Docker is running ─────────────────────────────────────────────────
Write-Step "Checking Docker Desktop..."
$dockerOk = $false
for ($i = 0; $i -lt 3; $i++) {
    try {
        $null = & docker info 2>$null
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
    } catch {}
    if ($i -lt 2) {
        Write-Step "Docker not ready, waiting 5 seconds..."
        Start-Sleep -Seconds 5
    }
}

if (-not $dockerOk) {
    Write-Host "[VisionForge] ERROR: Docker Desktop is not running." -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Start services ────────────────────────────────────────────────────────────
Push-Location $InstallDir
try {
    if ($gpuEnabled) {
        Write-Step "Starting services with GPU support..."
        & docker compose -f $Compose -f $ComposeGpu --profile gpu up -d
    } else {
        Write-Step "Starting services (CPU mode)..."
        & docker compose -f $Compose up -d
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[VisionForge] ERROR: Services failed to start (exit $LASTEXITCODE)." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "  VisionForge is starting up!" -ForegroundColor Green
Write-Host ""
Write-Host "  It may take up to 60 seconds for all services to become ready." -ForegroundColor White
Write-Host ""
Write-Host "  Service URLs:" -ForegroundColor White
Write-Host "    Main UI          http://localhost" -ForegroundColor Cyan
Write-Host "    MinIO Console    http://localhost:9001  (visionforge / visionforge_secret)" -ForegroundColor Cyan
Write-Host "    MLflow           http://localhost:5000" -ForegroundColor Cyan
Write-Host "    Grafana          http://localhost:3001  (admin / admin)" -ForegroundColor Cyan
Write-Host "    Core API docs    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

# Open browser after a short delay
Start-Sleep -Seconds 5
Start-Process "http://localhost"
