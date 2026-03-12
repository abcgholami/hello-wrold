<#
.SYNOPSIS
    Build the VisionForge Windows installer (.exe) on a Windows developer machine.

.DESCRIPTION
    Prerequisites:
      - NSIS 3.x installed (add makensis.exe to PATH)
        https://nsis.sourceforge.io/Download
      - Run from the repo root or from installer\windows\

.PARAMETER Version
    Override the product version embedded in the installer (default: reads from
    the NSIS script or uses "1.0.0").

.PARAMETER Sign
    Code-sign the resulting .exe with signtool.exe using the specified certificate
    thumbprint. Requires Windows SDK and a code-signing certificate.

.PARAMETER CertThumbprint
    SHA-1 thumbprint of the code-signing certificate (required when -Sign is used).

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Version 2.1.0
    .\build.ps1 -Sign -CertThumbprint "AABBCCDDEEFF..."
#>
param(
    [string]$Version        = "1.0.0",
    [switch]$Sign,
    [string]$CertThumbprint = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot    = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$InstallerDir = $PSScriptRoot
$NsiScript   = Join-Path $InstallerDir "visionforge-setup.nsi"
$OutputExe   = Join-Path $InstallerDir "VisionForge-Setup-$Version.exe"

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# ── 1. Verify makensis is available ──────────────────────────────────────────
Write-Step "Checking for NSIS..."
$makensis = Get-Command makensis -ErrorAction SilentlyContinue
if (-not $makensis) {
    $candidates = @(
        "C:\Program Files (x86)\NSIS\makensis.exe",
        "C:\Program Files\NSIS\makensis.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $makensis = $c; break }
    }
}
if (-not $makensis) {
    Write-Host "ERROR: makensis.exe not found." -ForegroundColor Red
    Write-Host "Install NSIS from https://nsis.sourceforge.io/Download" -ForegroundColor Yellow
    exit 1
}
Write-Host "Found: $makensis" -ForegroundColor Green

# ── 2. Create placeholder assets if missing (CI environments) ────────────────
Write-Step "Checking assets..."
$assetsDir = Join-Path $InstallerDir "assets"
if (-not (Test-Path $assetsDir)) { New-Item -ItemType Directory -Path $assetsDir | Out-Null }

# Generate a minimal valid .ico if none present (1×1 white pixel ICO)
$iconPath = Join-Path $assetsDir "icon.ico"
if (-not (Test-Path $iconPath)) {
    Write-Host "Generating placeholder icon..." -ForegroundColor Yellow
    # Minimal valid 16×16 ICO file (binary, base64-encoded)
    $icoB64 = "AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAA" +
               "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" +
               "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" +
               "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" +
               "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" +
               "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
    [System.IO.File]::WriteAllBytes($iconPath, [Convert]::FromBase64String($icoB64))
}

# Generate placeholder 164×314 BMP for the sidebar (required by MUI2)
$bmpPath = Join-Path $assetsDir "installer-side.bmp"
if (-not (Test-Path $bmpPath)) {
    Write-Host "Generating placeholder sidebar bitmap..." -ForegroundColor Yellow
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap 164, 314
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::FromArgb(30, 30, 46))
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $font  = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
    $g.DrawString("VisionForge", $font, $brush, 12, 280)
    $font.Dispose(); $brush.Dispose(); $g.Dispose()
    $bmp.Save($bmpPath, [System.Drawing.Imaging.ImageFormat]::Bmp)
    $bmp.Dispose()
}

# Create a placeholder LICENSE if missing
$licensePath = Join-Path $RepoRoot "LICENSE"
if (-not (Test-Path $licensePath)) {
    "MIT License`r`n`r`nCopyright (c) $(Get-Date -Format yyyy) VisionForge Team" |
        Set-Content -Path $licensePath -Encoding UTF8
}

# Create placeholder RELEASE_NOTES.txt
$notesPath = Join-Path $InstallerDir "RELEASE_NOTES.txt"
if (-not (Test-Path $notesPath)) {
    "VisionForge $Version`r`n`r`nInitial release." |
        Set-Content -Path $notesPath -Encoding UTF8
}

# ── 3. Copy .env.template from repo root into installer dir ─────────────────
Write-Step "Copying .env.template..."
Copy-Item (Join-Path $RepoRoot ".env.example") (Join-Path $InstallerDir ".env.template") -Force

# ── 4. Compile with NSIS ─────────────────────────────────────────────────────
Write-Step "Compiling installer (makensis)..."
Push-Location $InstallerDir
try {
    & $makensis /DPRODUCT_VERSION=$Version $NsiScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: makensis failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $OutputExe)) {
    Write-Host "ERROR: Expected output file not found: $OutputExe" -ForegroundColor Red
    exit 1
}

Write-Host "Installer built: $OutputExe" -ForegroundColor Green

# ── 5. Optional code signing ─────────────────────────────────────────────────
if ($Sign) {
    if ([string]::IsNullOrWhiteSpace($CertThumbprint)) {
        Write-Host "ERROR: -CertThumbprint is required when using -Sign." -ForegroundColor Red
        exit 1
    }
    Write-Step "Code-signing installer..."
    $signtool = Get-Command signtool -ErrorAction SilentlyContinue
    if (-not $signtool) {
        # Try common Windows SDK paths
        $sdkPaths = @(
            "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe",
            "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
        )
        foreach ($p in $sdkPaths) {
            if (Test-Path $p) { $signtool = $p; break }
        }
    }
    if (-not $signtool) {
        Write-Host "ERROR: signtool.exe not found. Install Windows 10 SDK." -ForegroundColor Red
        exit 1
    }
    & $signtool sign /sha1 $CertThumbprint /tr "http://timestamp.digicert.com" /td sha256 /fd sha256 $OutputExe
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Code signing failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Installer signed successfully." -ForegroundColor Green
}

Write-Host ""
Write-Host "Done! Distribute: $OutputExe" -ForegroundColor Green
