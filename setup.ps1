# Data-Analytics-Mini-Proj -- one-shot setup
#
# First time? Run these two lines in PowerShell, then this script:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
#   .\setup.ps1
#
# Requires: Python 3.11+, winget (built into Windows 11; Win 10: install "App Installer" from the Store)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# -- 1. Python venv ----------------------------------------------------------
Write-Host ""
Write-Host "[1/4] Python-Umgebung" -ForegroundColor Cyan
$venv = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $venv)) {
    python -m venv $venv
    Write-Host "      .venv erstellt"
} else {
    Write-Host "      .venv bereits vorhanden"
}

& "$venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$venv\Scripts\pip.exe" install -r "$ProjectRoot\requirements.txt" --quiet
Write-Host "      Abhaengigkeiten installiert (requests, plotext, numpy)"

# -- 2. Ollama installieren --------------------------------------------------
Write-Host ""
Write-Host "[2/4] Ollama installieren" -ForegroundColor Cyan
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "      Installiere via winget..."
    winget install --id Ollama.Ollama --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
} else {
    Write-Host "      Ollama bereits installiert"
}

# -- 3. OLLAMA_KEEP_ALIVE setzen ---------------------------------------------
Write-Host ""
Write-Host "[3/4] Ollama-Konfiguration" -ForegroundColor Cyan
[System.Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "0", "User")
$env:OLLAMA_KEEP_ALIVE = "0"
Write-Host "      OLLAMA_KEEP_ALIVE=0 gesetzt -- Modell entlaedt nach Inaktivitaet"

# -- 4. phi4-mini pullen -----------------------------------------------------
Write-Host ""
Write-Host "[4/4] Modell phi4-mini laden" -ForegroundColor Cyan

$ollamaRunning = $false
try {
    Invoke-RestMethod -Uri "http://localhost:11434" -Method Get -ErrorAction Stop | Out-Null
    $ollamaRunning = $true
} catch {}

if (-not $ollamaRunning) {
    Write-Host "      Starte ollama serve im Hintergrund..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

ollama pull phi4-mini

Write-Host ""
Write-Host "[OK] Setup abgeschlossen." -ForegroundColor Green
Write-Host "     Umgebung aktivieren:      .venv\Scripts\Activate.ps1"
Write-Host "     Dataset erstellen:           cd Dataset; python main.py"
Write-Host "     Visualisierungen starten: cd visualise; python main.py"
Write-Host "     Modell starten:           cd Model; python main.py"
