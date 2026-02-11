#!/usr/bin/env pwsh
# Usage:
#   pwsh scripts/hpc_cli_smoke_test.ps1 <PERIOGT_CHECKPOINT_DIR>
# or set PERIOGT_CHECKPOINT_DIR in the environment.

param(
    [Parameter(Position = 0)]
    [string]$CheckpointDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$pathSep = [System.IO.Path]::PathSeparator

if ([string]::IsNullOrWhiteSpace($env:DGLBACKEND)) {
    $env:DGLBACKEND = "pytorch"
}

$pythonPathParts = @(
    (Join-Path $repoRoot "services/modal-api"),
    (Join-Path $repoRoot "services/hpc")
)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $pythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = [string]::Join($pathSep, $pythonPathParts)

$env:PERIOGT_RUNTIME_PACKAGE_DIR = Join-Path $repoRoot "services/modal-api"

if ([string]::IsNullOrWhiteSpace($env:PERIOGT_SRC_DIR)) {
    $env:PERIOGT_SRC_DIR = Join-Path $repoRoot "services/modal-api/periogt_src/source_code/PerioGT_common"
}

if ([string]::IsNullOrWhiteSpace($env:PERIOGT_DEVICE)) {
    $env:PERIOGT_DEVICE = "cpu"
}

if (-not [string]::IsNullOrWhiteSpace($CheckpointDir)) {
    $env:PERIOGT_CHECKPOINT_DIR = $CheckpointDir
}

if ([string]::IsNullOrWhiteSpace($env:PERIOGT_CHECKPOINT_DIR)) {
    [Console]::Error.WriteLine("Usage: pwsh scripts/hpc_cli_smoke_test.ps1 <PERIOGT_CHECKPOINT_DIR>")
    exit 2
}

$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
New-Item -Path $tmpDir -ItemType Directory | Out-Null

try {
    $inputCsv = Join-Path $tmpDir "input.csv"
    $outputCsv = Join-Path $tmpDir "out.csv"

    @"
id,smiles
1,*CC*
2,*CC(*)C
"@ | Set-Content -Path $inputCsv -NoNewline

    Write-Host "Running periogt_hpc doctor..."
    python -m periogt_hpc doctor

    Write-Host "Running periogt_hpc predict..."
    python -m periogt_hpc predict --smiles "*CC*" --property tg --format json | Out-Null

    Write-Host "Running periogt_hpc batch..."
    python -m periogt_hpc batch --input $inputCsv --property tg --output $outputCsv

    Write-Host "Smoke test complete: $outputCsv"
}
finally {
    if (Test-Path -LiteralPath $tmpDir) {
        Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
