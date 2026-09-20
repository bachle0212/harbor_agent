Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Python launcher 'py' not found. Install Python 3.11+."
}

py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt

if (-not (Test-Path .env)) {
  Copy-Item .env.sample .env
  Write-Host "Created .env from .env.sample — add GEMINI_API_KEY before uploading."
}

Write-Host "OK. Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Scrape only:      python main.py --scrape-only"
Write-Host "Tests:            python -m pytest"
