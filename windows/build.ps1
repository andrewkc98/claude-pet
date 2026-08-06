<#
.SYNOPSIS
    Builds ClaudePet.exe and petsend.exe with PyInstaller.

.DESCRIPTION
    Both are one-dir builds, deliberately. One-file builds unpack themselves to a
    temp directory on every launch, which costs roughly a second — irrelevant for
    the app, but petsend runs on *every Claude Code tool call*, so that latency
    would land on every hook invocation.

    Output lands in dist\ClaudePet\, with petsend nested inside it so the app can
    copy it out to %USERPROFILE%\.claudepet\bin on launch.
#>

[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$RepoRoot = Split-Path $Root -Parent
$Assets = Join-Path $RepoRoot "Assets"
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "No venv found at $Python. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}
if (-not (Test-Path $Assets)) {
    throw "Assets folder not found at $Assets"
}

if ($Clean) {
    foreach ($dir in @("build", "dist")) {
        $path = Join-Path $Root $dir
        if (Test-Path $path) { Remove-Item -Recurse -Force $path }
    }
}

Push-Location $Root
try {
    Write-Host "Building petsend.exe..." -ForegroundColor Cyan
    & $Python -m PyInstaller `
        --noconfirm `
        --onedir `
        --console `
        --name petsend `
        --distpath (Join-Path $Root "dist") `
        --workpath (Join-Path $Root "build") `
        --specpath (Join-Path $Root "build") `
        (Join-Path $Root "petsend\petsend.py")
    if ($LASTEXITCODE -ne 0) { throw "petsend build failed" }

    Write-Host "Building ClaudePet.exe..." -ForegroundColor Cyan
    & $Python -m PyInstaller `
        --noconfirm `
        --onedir `
        --windowed `
        --name ClaudePet `
        --add-data "$Assets;Assets" `
        --manifest (Join-Path $Root "ClaudePet.manifest") `
        --paths $Root `
        --distpath (Join-Path $Root "dist") `
        --workpath (Join-Path $Root "build") `
        --specpath (Join-Path $Root "build") `
        (Join-Path $Root "run_claudepet.py")
    if ($LASTEXITCODE -ne 0) { throw "ClaudePet build failed" }

    # Nest petsend inside the app folder so install_petsend() can find and copy it.
    $petsendSrc = Join-Path $Root "dist\petsend"
    $petsendDst = Join-Path $Root "dist\ClaudePet\petsend"
    if (Test-Path $petsendDst) { Remove-Item -Recurse -Force $petsendDst }
    Copy-Item -Recurse $petsendSrc $petsendDst

    Write-Host ""
    Write-Host "Done. Run: dist\ClaudePet\ClaudePet.exe" -ForegroundColor Green
}
finally {
    Pop-Location
}
