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
Write-Host "      Abhaengigkeiten installiert (requests, plotext, numpy, json-repair)"

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

# -- 4. Modelle pullen (Manager + Council) -----------------------------------
Write-Host ""
Write-Host "[4/4] Modelle laden (Manager + Council)" -ForegroundColor Cyan

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

# phi4-mini   = Manager (Microsoft, strongest overall, BBH 70.4)
# qwen3:4b    = Statistician (Alibaba, best math after phi4-mini, MMLU ~70%)
# llama3.2:3b = Domain Expert (Meta, best commonsense HellaSwag 77.2)
# gemma3:4b   = Skeptic (Google, replaces gemma2:2b whose GSM8K was only 23.9%)
# See docs/council-architecture.md for full benchmark rationale.
$models = @("phi4-mini", "qwen3:4b", "llama3.2:3b", "gemma3:4b")
foreach ($m in $models) {
    Write-Host "      Pulling $m ..."
    ollama pull $m
}

# Remove models that were replaced in the council upgrade.
# qwen2.5:3b  -> qwen3:4b   (Statistician: gen-2 Qwen with better math)
# gemma2:2b   -> gemma3:4b  (Skeptic: gemma2 had GSM8K of only 23.9%)
$deprecated = @("qwen2.5:3b", "gemma2:2b")
foreach ($m in $deprecated) {
    $exists = ollama list 2>$null | Select-String $m
    if ($exists) {
        Write-Host "      Removing deprecated model $m ..."
        ollama rm $m
    }
}

Write-Host ""
Write-Host "[OK] Setup abgeschlossen." -ForegroundColor Green
Write-Host "     Umgebung aktivieren:      .venv\Scripts\Activate.ps1"
Write-Host "     Dataset erstellen:           cd Dataset; python main.py"
Write-Host "     Visualisierungen starten: cd visualise; python main.py"
Write-Host "     Modell starten:           cd Model; python main.py"
