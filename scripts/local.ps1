param([ValidateSet('install','start')][string]$Mode = 'start')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$condaCommand = Get-Command conda -ErrorAction SilentlyContinue
$condaPath = if ($condaCommand) { $condaCommand.Source } else { $null }
if (-not $condaPath) {
    foreach ($candidate in @("$env:USERPROFILE/miniforge3/Scripts/conda.exe", "$env:USERPROFILE/miniconda3/Scripts/conda.exe", "$env:USERPROFILE/anaconda3/Scripts/conda.exe")) {
        if (Test-Path -LiteralPath $candidate) { $condaPath = $candidate; break }
    }
}
if (-not $condaPath) { throw 'Please install Miniforge / conda first, then run Install.cmd.' }
$configuration = Get-Content -LiteralPath config/app.json -Raw | ConvertFrom-Json
$environmentName = $configuration.conda_env
if ($Mode -eq 'install') {
    $environmentList = & $condaPath env list --json | ConvertFrom-Json
    if (-not ($environmentList.envs | Where-Object { (Split-Path -Leaf $_) -eq $environmentName })) {
        & $condaPath create -n $environmentName python=3.12 -y
        if ($LASTEXITCODE -ne 0) { throw 'Conda environment creation failed.' }
    }
    & $condaPath run --no-capture-output -n $environmentName python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
    Write-Host 'Installation complete. Configure .env and double-click Start.cmd.'
} else {
    & $condaPath run --no-capture-output -n $environmentName python scripts/launch.py
    if ($LASTEXITCODE -ne 0) { throw 'App startup failed. Run Install.cmd first.' }
}
