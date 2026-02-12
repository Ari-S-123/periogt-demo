#!/usr/bin/env pwsh
# Smoke test for PerioGT API endpoints.
# Usage: pwsh scripts/smoke_test.ps1 <BASE_URL>
# Example: pwsh scripts/smoke_test.ps1 https://your-workspace--periogt-api-periogt-api.modal.run
#
# For Modal proxy auth, set either:
#   - MODAL_KEY and MODAL_SECRET, or
#   - MODAL_TOKEN_ID and MODAL_TOKEN_SECRET
# For HPC server mode auth, set PERIOGT_API_KEY env var.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BaseUrl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BaseUrl = $BaseUrl.TrimEnd("/")
$headers = @{}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$defaultEnvFile = Join-Path $repoRoot "apps/web/.env.local"

$dotenvKeys = @(
    "MODAL_KEY",
    "MODAL_SECRET",
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
    "PERIOGT_API_KEY"
)

if (Test-Path -LiteralPath $defaultEnvFile) {
    Get-Content -LiteralPath $defaultEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            return
        }

        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            return
        }

        $key = $line.Substring(0, $idx).Trim()
        if (-not ($dotenvKeys -contains $key)) {
            return
        }

        $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if ([string]::IsNullOrWhiteSpace($value)) {
            return
        }

        $existing = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrWhiteSpace($existing)) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$modalKey = if (-not [string]::IsNullOrWhiteSpace($env:MODAL_KEY)) {
    $env:MODAL_KEY
}
elseif (-not [string]::IsNullOrWhiteSpace($env:MODAL_TOKEN_ID)) {
    $env:MODAL_TOKEN_ID
}
else {
    $null
}

$modalSecret = if (-not [string]::IsNullOrWhiteSpace($env:MODAL_SECRET)) {
    $env:MODAL_SECRET
}
elseif (-not [string]::IsNullOrWhiteSpace($env:MODAL_TOKEN_SECRET)) {
    $env:MODAL_TOKEN_SECRET
}
else {
    $null
}

if ((-not [string]::IsNullOrWhiteSpace($modalKey)) -and (-not [string]::IsNullOrWhiteSpace($modalSecret))) {
    $headers["Modal-Key"] = $modalKey
    $headers["Modal-Secret"] = $modalSecret
}

if (-not [string]::IsNullOrWhiteSpace($env:PERIOGT_API_KEY)) {
    $headers["X-Api-Key"] = $env:PERIOGT_API_KEY
}

$isModalRunUrl = $BaseUrl -match "\.modal\.run$" -or $BaseUrl -match "\.modal\.run/"
if (
    $isModalRunUrl -and
    (-not [string]::IsNullOrWhiteSpace($modalKey)) -and
    (-not [string]::IsNullOrWhiteSpace($modalSecret)) -and
    ($modalKey -match "^ak") -and
    ($modalSecret -match "^as")
) {
    Write-Host "[WARN] MODAL_KEY/MODAL_SECRET look like account tokens (ak/as)."
    Write-Host "[WARN] Modal proxy auth expects workspace Proxy Auth tokens (wk/ws)."
}
if ($isModalRunUrl -and ([string]::IsNullOrWhiteSpace($modalKey) -or [string]::IsNullOrWhiteSpace($modalSecret))) {
    Write-Host "[ERROR] Modal proxy credentials are required for this URL."
    Write-Host "Set MODAL_KEY/MODAL_SECRET or MODAL_TOKEN_ID/MODAL_TOKEN_SECRET, then retry."
    exit 2
}

$script:pass = 0
$script:fail = 0

function Run-Test {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [ValidateSet("GET", "POST")]
        [string]$Method,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [string]$JsonBody,

        [int]$ExpectedStatus = 200
    )

    Write-Host -NoNewline "  $Name ... "

    $uri = "$BaseUrl$Path"
    $requestParams = @{
        Uri                = $uri
        Method             = $Method
        Headers            = $headers
        SkipHttpErrorCheck = $true
    }

    if ($Method -eq "POST") {
        $requestParams["ContentType"] = "application/json"
        $requestParams["Body"] = $JsonBody
    }

    try {
        $response = Invoke-WebRequest @requestParams
        $statusCode = [int]$response.StatusCode
    }
    catch {
        Write-Host "FAIL (request error)"
        Write-Host $_.Exception.Message
        Write-Host ""
        $script:fail++
        return
    }

    if ($statusCode -eq $ExpectedStatus) {
        Write-Host "OK ($statusCode)"
        $script:pass++
        return
    }

    Write-Host "FAIL (expected $ExpectedStatus, got $statusCode)"
    $responseText = $null
    if (-not [string]::IsNullOrEmpty($response.Content)) {
        if ($response.Content -is [byte[]]) {
            $responseText = [System.Text.Encoding]::UTF8.GetString($response.Content)
        }
        else {
            $responseText = [string]$response.Content
        }
        Write-Host $responseText
    }
    if (
        ($statusCode -eq 401) -and
        (-not [string]::IsNullOrWhiteSpace($responseText)) -and
        ($responseText -match "proxy authorization")
    ) {
        Write-Host "[HINT] Modal proxy auth expects a workspace Proxy Auth Token in Modal-Key/Modal-Secret."
    }
    Write-Host ""
    $script:fail++
}

Write-Host "PerioGT Smoke Test - $BaseUrl"
Write-Host "================================"

Run-Test -Name "GET /v1/health" -Method "GET" -Path "/v1/health"
Run-Test -Name "GET /v1/properties" -Method "GET" -Path "/v1/properties"
Run-Test -Name "POST /v1/predict (valid)" -Method "POST" -Path "/v1/predict" -JsonBody '{"smiles":"*CC*","property":"tg"}'
Run-Test -Name "POST /v1/predict (invalid SMILES)" -Method "POST" -Path "/v1/predict" -JsonBody '{"smiles":"invalid","property":"tg"}' -ExpectedStatus 422
Run-Test -Name "POST /v1/embeddings" -Method "POST" -Path "/v1/embeddings" -JsonBody '{"smiles":"*CC*"}'
Run-Test -Name "POST /v1/predict/batch" -Method "POST" -Path "/v1/predict/batch" -JsonBody '{"items":[{"smiles":"*CC*","property":"tg"},{"smiles":"*CC(*)C","property":"tg"}]}'

Write-Host "================================"
Write-Host "Results: $($script:pass) passed, $($script:fail) failed"

if ($script:fail -gt 0) {
    exit 1
}

