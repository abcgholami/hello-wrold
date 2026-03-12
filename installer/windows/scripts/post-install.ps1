<#
.SYNOPSIS
    VisionForge post-installation setup script.
    Invoked by the NSIS installer immediately after file extraction.

.PARAMETER InstallDir
    The directory where VisionForge was installed (passed in by NSIS).
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "[VisionForge Setup] $msg" -ForegroundColor Cyan
}

function Write-Success([string]$msg) {
    Write-Host "[VisionForge Setup] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "[VisionForge Setup] WARNING: $msg" -ForegroundColor Yellow
}

# ── 1. Generate a random JWT secret and write .env ────────────────────────────
Write-Step "Generating .env configuration..."

$template  = Join-Path $InstallDir ".env.template"
$envFile   = Join-Path $InstallDir ".env"

if (Test-Path $template) {
    $envContent = Get-Content $template -Raw
} else {
    Write-Warn ".env.template not found; writing minimal .env"
    $envContent = ""
}

# Generate a 32-byte random hex JWT secret
$randomBytes = New-Object byte[] 32
([System.Security.Cryptography.RandomNumberGenerator]::Create()).GetBytes($randomBytes)
$jwtSecret = ($randomBytes | ForEach-Object { "{0:x2}" -f $_ }) -join ""

# Replace placeholder or append
if ($envContent -match "super-secret-jwt-key") {
    $envContent = $envContent -replace "super-secret-jwt-key[^\n]*", "JWT_SECRET=$jwtSecret"
} else {
    $envContent += "`r`nJWT_SECRET=$jwtSecret`r`n"
}

# Fix TRAINING_TEMP_DIR for Windows paths (Docker uses Linux paths in WSL)
$envContent = $envContent -replace "TRAINING_TEMP_DIR=/tmp/visionforge", "TRAINING_TEMP_DIR=/tmp/visionforge"

Set-Content -Path $envFile -Value $envContent -Encoding UTF8
Write-Success ".env written with a generated JWT secret."

# ── 2. Ensure Docker is running ───────────────────────────────────────────────
Write-Step "Checking Docker Desktop status..."

$dockerRunning = $false
$retries = 0
while (-not $dockerRunning -and $retries -lt 5) {
    try {
        $null = & docker info 2>$null
        if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
    } catch {}
    if (-not $dockerRunning) {
        Write-Warn "Docker not responding yet (attempt $($retries+1)/5). Waiting 10 seconds..."
        Start-Sleep -Seconds 10
        $retries++
    }
}

if (-not $dockerRunning) {
    Write-Warn "Docker Desktop does not appear to be running."
    Write-Warn "Please start Docker Desktop and then run start-visionforge.bat."
    exit 0
}

Write-Success "Docker Desktop is running."

# ── 3. Pull / build images ───────────────────────────────────────────────────
Write-Step "Pulling Docker images (this may take several minutes on first run)..."

$compose = Join-Path $InstallDir "infra\docker-compose.yml"
Push-Location $InstallDir
try {
    & docker compose -f $compose pull 2>&1 | Tee-Object -Variable pullOutput
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "docker compose pull exited with $LASTEXITCODE. Will attempt local build instead."
        & docker compose -f $compose build
    }
} finally {
    Pop-Location
}

Write-Success "Images ready."

# ── 4. Start services ────────────────────────────────────────────────────────
Write-Step "Starting VisionForge services..."

Push-Location $InstallDir
try {
    & docker compose -f $compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Services did not start cleanly (exit $LASTEXITCODE). Check Docker Desktop logs."
        exit 1
    }
} finally {
    Pop-Location
}

Write-Success "Services started."

# ── 5. Wait for core_api to become healthy, then run migrations ───────────────
Write-Step "Waiting for database to become ready..."

$healthy = $false
$retries = 0
while (-not $healthy -and $retries -lt 18) {
    Start-Sleep -Seconds 5
    $status = & docker inspect --format="{{.State.Health.Status}}" visionforge-postgres-1 2>$null
    if ($status -eq "healthy") { $healthy = $true }
    $retries++
}

if (-not $healthy) {
    Write-Warn "Postgres health check timed out. Skipping automatic migration."
    Write-Warn "Run 'docker compose exec core_api alembic upgrade head' manually."
    exit 0
}

Write-Step "Running database migrations..."
Push-Location $InstallDir
try {
    & docker compose -f $compose exec -T core_api alembic upgrade head
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Migrations applied."
    } else {
        Write-Warn "Migration exited with $LASTEXITCODE. Check logs for details."
    }
} finally {
    Pop-Location
}

Write-Success "VisionForge setup complete! Open http://localhost to get started."
