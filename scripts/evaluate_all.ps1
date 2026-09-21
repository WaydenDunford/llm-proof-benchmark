param([string]$Backend = '')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    Get-ChildItem -LiteralPath 'results/raw' -Filter '*.json' | ForEach-Object {
        if ($Backend) { python -m src.cli evaluate $_.FullName --backend $Backend }
        else { python -m src.cli evaluate $_.FullName }
        if ($LASTEXITCODE -ne 0) { throw "Evaluation failed: $($_.FullName)" }
    }
} finally { Pop-Location }
