# Sets up backend + frontend for local development on Windows.
$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "== Checking prerequisites =="
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python 3.11+ is required and was not found on PATH."
    exit 1
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg not found on PATH. Install it (e.g. via winget install Gyan.FFmpeg) before running the pipeline."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "NOTE: Node.js not found (only needed if you replace the static frontend)."
}

Write-Host "== Creating virtual environment =="
python -m venv .venv
& .\.venv\Scripts\Activate.ps1

Write-Host "== Installing backend dependencies =="
python -m pip install --upgrade pip
pip install -r backend\requirements.txt

Write-Host "== Preparing directories =="
New-Item -ItemType Directory -Force -Path data\downloads, data\audio, data\jobs, data\output | Out-Null

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example"
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next steps:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  uvicorn app.main:app --reload --app-dir backend"
Write-Host "  # or: python cli\cli.py `"https://www.youtube.com/watch?v=...`""
