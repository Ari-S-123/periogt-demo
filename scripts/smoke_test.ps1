#!/usr/bin/env pwsh
# Smoke test for PerioGT API endpoints.
# Usage: pwsh scripts/smoke_test.ps1 <BASE_URL>
# Example: pwsh scripts/smoke_test.ps1 https://your-workspace--periogt-api-periogt-api.modal.run
#
# For Modal proxy auth, set MODAL_KEY and MODAL_SECRET env vars.
# For HPC server mode auth, set PERIOGT_API_KEY env var.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BaseUrl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BaseUrl = $BaseUrl.TrimEnd("/")
$headers = @{}

if (-not [string]::IsNullOrWhiteSpace($env:MODAL_KEY) -and -not [string]::IsNullOrWhiteSpace($env:MODAL_SECRET)) {
    $headers["Modal-Key"] = $env:MODAL_KEY
    $headers["Modal-Secret"] = $env:MODAL_SECRET
}

if (-not [string]::IsNullOrWhiteSpace($env:PERIOGT_API_KEY)) {
    $headers["X-Api-Key"] = $env:PERIOGT_API_KEY
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
    if (-not [string]::IsNullOrEmpty($response.Content)) {
        Write-Host $response.Content
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
