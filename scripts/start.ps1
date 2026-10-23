param([int]$Port = 8000, [switch]$Lan)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$bindAddress = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
Write-Host "Signal Studio: http://localhost:$Port"
conda run --no-capture-output -n xkd_env_py312 python -m uvicorn backend.app:app --host $bindAddress --port $Port
