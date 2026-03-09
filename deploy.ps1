<#
.SYNOPSIS
  Deploy the Rural Credit AI Advisor to AWS (all services + frontend).

.DESCRIPTION
  Deploys 8 backend microservices via SAM, then builds and deploys the
  React frontend to S3 + CloudFront.

.PARAMETER Region
  AWS region to deploy to. Default: ap-south-1 (Mumbai)

.PARAMETER Stage
  Deployment stage. Default: prod

.PARAMETER GroqApiKey
  Groq API key for Llama AI. Required for AI Advisor service.

.PARAMETER FrontendBucket
  S3 bucket name for frontend static files.

.EXAMPLE
  .\deploy.ps1 -GroqApiKey "gsk_xxx" -FrontendBucket "rural-credit-frontend-123"
#>

param(
    [string]$Region = "ap-south-1",
    [string]$Stage = "prod",
    [Parameter(Mandatory=$true)]
    [string]$GroqApiKey,
    [string]$FrontendBucket = "rural-credit-frontend-$(Get-Random -Maximum 99999)",
    [string]$StackPrefix = "rural-credit"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# ─────────────────────────────────────────────
# Verify prerequisites
# ─────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Rural Credit AI Advisor - Deployment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

foreach ($cmd in @("aws", "sam", "node", "npm")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "ERROR: '$cmd' is not installed or not in PATH. Please install it first."
        exit 1
    }
}

# Verify AWS credentials
Write-Host "[1/8] Verifying AWS credentials..." -ForegroundColor Yellow
try {
    $identity = aws sts get-caller-identity --region $Region 2>&1 | ConvertFrom-Json
    Write-Host "  Account: $($identity.Account)" -ForegroundColor Green
    Write-Host "  User:    $($identity.Arn)" -ForegroundColor Green
} catch {
    Write-Error "AWS credentials not configured. Run: aws configure"
    exit 1
}

# ─────────────────────────────────────────────
# Deploy order (respects dependencies):
# 1. Security (no dependencies)
# 2. Profile Service (no dependencies)
# 3. Loan Tracker (depends on Profile)
# 4. Risk Assessment (depends on Profile + Loan)
# 5. Cashflow Service (depends on Profile + Loan)
# 6. Early Warning (no dependencies)
# 7. Guidance (no dependencies)
# 8. AI Advisor (depends on all above)
# ─────────────────────────────────────────────

$ServiceOutputs = @{}

function Deploy-Service {
    param(
        [string]$ServiceName,
        [string]$StackName,
        [string]$TemplatePath,
        [string]$ParameterOverrides = ""
    )

    Write-Host "`n--- Deploying: $ServiceName ---" -ForegroundColor Magenta
    Write-Host "  Stack: $StackName" -ForegroundColor Gray
    Write-Host "  Template: $TemplatePath" -ForegroundColor Gray

    Push-Location (Split-Path $TemplatePath)

    try {
        Write-Host "  Building..." -ForegroundColor Yellow
        sam build --template-file (Split-Path $TemplatePath -Leaf) --use-container 2>&1 | Out-Null

        $deployArgs = @(
            "deploy",
            "--stack-name", $StackName,
            "--region", $Region,
            "--capabilities", "CAPABILITY_IAM",
            "--no-confirm-changeset",
            "--no-fail-on-empty-changeset",
            "--resolve-s3"
        )

        if ($ParameterOverrides) {
            $deployArgs += "--parameter-overrides"
            $deployArgs += $ParameterOverrides
        }

        Write-Host "  Deploying..." -ForegroundColor Yellow
        & sam @deployArgs 2>&1

        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to deploy $ServiceName"
            exit 1
        }

        # Get outputs (API URL)
        $outputs = aws cloudformation describe-stacks `
            --stack-name $StackName `
            --region $Region `
            --query "Stacks[0].Outputs" `
            --output json 2>&1 | ConvertFrom-Json

        $apiUrl = ($outputs | Where-Object { $_.OutputKey -match "Api" }).OutputValue
        if ($apiUrl) {
            $ServiceOutputs[$ServiceName] = $apiUrl
            Write-Host "  API URL: $apiUrl" -ForegroundColor Green
        }

        Write-Host "  $ServiceName deployed successfully!" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# ─────────────────────────────────────────────
# [2/8] Deploy Security Service
# ─────────────────────────────────────────────
Write-Host "`n[2/8] Deploying backend services..." -ForegroundColor Yellow

Deploy-Service `
    -ServiceName "security" `
    -StackName "$StackPrefix-security" `
    -TemplatePath "$ProjectRoot\services\security\template.yaml"

# ─────────────────────────────────────────────
# [3/8] Deploy Profile Service
# ─────────────────────────────────────────────
Deploy-Service `
    -ServiceName "profile" `
    -StackName "$StackPrefix-profile" `
    -TemplatePath "$ProjectRoot\services\profile_service\template.yaml"

# ─────────────────────────────────────────────
# [4/8] Deploy Loan Tracker (depends on Profile)
# ─────────────────────────────────────────────
$profileUrl = $ServiceOutputs["profile"]
Deploy-Service `
    -ServiceName "loan-tracker" `
    -StackName "$StackPrefix-loan-tracker" `
    -TemplatePath "$ProjectRoot\services\loan_tracker\template.yaml" `
    -ParameterOverrides "ProfileServiceUrl=$profileUrl"

# ─────────────────────────────────────────────
# [5/8] Deploy Risk Assessment (depends on Profile + Loan)
# ─────────────────────────────────────────────
$loanUrl = $ServiceOutputs["loan-tracker"]
Deploy-Service `
    -ServiceName "risk" `
    -StackName "$StackPrefix-risk" `
    -TemplatePath "$ProjectRoot\services\risk_assessment\template.yaml" `
    -ParameterOverrides "ProfileServiceUrl=$profileUrl LoanServiceUrl=$loanUrl"

# ─────────────────────────────────────────────
# Deploy Cashflow, Early Warning, Guidance (independent)
# ─────────────────────────────────────────────
Deploy-Service `
    -ServiceName "cashflow" `
    -StackName "$StackPrefix-cashflow" `
    -TemplatePath "$ProjectRoot\services\cashflow_service\template.yaml"

Deploy-Service `
    -ServiceName "early-warning" `
    -StackName "$StackPrefix-early-warning" `
    -TemplatePath "$ProjectRoot\services\early_warning\template.yaml"

Deploy-Service `
    -ServiceName "guidance" `
    -StackName "$StackPrefix-guidance" `
    -TemplatePath "$ProjectRoot\services\guidance\template.yaml"

# ─────────────────────────────────────────────
# [6/8] Deploy AI Advisor (depends on all services)
# ─────────────────────────────────────────────
$riskUrl = $ServiceOutputs["risk"]
$cashflowUrl = $ServiceOutputs["cashflow"]
$ewUrl = $ServiceOutputs["early-warning"]
$guidanceUrl = $ServiceOutputs["guidance"]

Deploy-Service `
    -ServiceName "ai-advisor" `
    -StackName "$StackPrefix-ai-advisor" `
    -TemplatePath "$ProjectRoot\services\ai_advisor\template.yaml" `
    -ParameterOverrides "GroqApiKey=$GroqApiKey GroqModelId=llama-3.3-70b-versatile ProfileServiceUrl=$profileUrl RiskServiceUrl=$riskUrl CashFlowServiceUrl=$cashflowUrl LoanServiceUrl=$loanUrl EarlyWarningServiceUrl=$ewUrl GuidanceServiceUrl=$guidanceUrl"

# ─────────────────────────────────────────────
# [7/8] Build & Deploy Frontend
# ─────────────────────────────────────────────
Write-Host "`n[7/8] Building & deploying frontend..." -ForegroundColor Yellow

# Create .env.production with real API URLs
$envContent = @"
# Auto-generated by deploy.ps1 — $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
VITE_SECURITY_API_URL=$($ServiceOutputs["security"])
VITE_PROFILE_API_URL=$($ServiceOutputs["profile"])
VITE_LOAN_API_URL=$($ServiceOutputs["loan-tracker"])
VITE_RISK_API_URL=$($ServiceOutputs["risk"])
VITE_CASHFLOW_API_URL=$($ServiceOutputs["cashflow"])
VITE_EARLY_WARNING_API_URL=$($ServiceOutputs["early-warning"])
VITE_GUIDANCE_API_URL=$($ServiceOutputs["guidance"])
VITE_AI_ADVISOR_API_URL=$($ServiceOutputs["ai-advisor"])
"@

$envContent | Set-Content "$ProjectRoot\frontend\.env.production" -Encoding UTF8
Write-Host "  Created frontend/.env.production with API URLs" -ForegroundColor Green

Push-Location "$ProjectRoot\frontend"
try {
    npm ci 2>&1 | Out-Null
    npm run build 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend build failed"
        exit 1
    }
    Write-Host "  Frontend built successfully" -ForegroundColor Green

    # Create S3 bucket
    Write-Host "  Creating S3 bucket: $FrontendBucket" -ForegroundColor Yellow
    aws s3 mb "s3://$FrontendBucket" --region $Region 2>&1 | Out-Null

    # Enable static website hosting
    aws s3 website "s3://$FrontendBucket" `
        --index-document index.html `
        --error-document index.html 2>&1

    # Set bucket policy for public read
    $bucketPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::$FrontendBucket/*"
    }]
}
"@
    $policyFile = "$env:TEMP\bucket-policy.json"
    $bucketPolicy | Set-Content $policyFile -Encoding UTF8

    # Disable block public access (needed for static hosting)
    aws s3api put-public-access-block `
        --bucket $FrontendBucket `
        --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" `
        --region $Region 2>&1

    aws s3api put-bucket-policy `
        --bucket $FrontendBucket `
        --policy "file://$policyFile" `
        --region $Region 2>&1

    # Upload files
    Write-Host "  Uploading to S3..." -ForegroundColor Yellow
    aws s3 sync dist/ "s3://$FrontendBucket/" --delete --region $Region 2>&1

    $frontendUrl = "http://$FrontendBucket.s3-website.$Region.amazonaws.com"
    Write-Host "  Frontend URL: $frontendUrl" -ForegroundColor Green
} finally {
    Pop-Location
}

# ─────────────────────────────────────────────
# [8/8] Summary
# ─────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Backend Service URLs:" -ForegroundColor Yellow
foreach ($key in $ServiceOutputs.Keys | Sort-Object) {
    Write-Host "  $($key.PadRight(16)) : $($ServiceOutputs[$key])" -ForegroundColor Green
}

Write-Host "`nFrontend:" -ForegroundColor Yellow
Write-Host "  URL: $frontendUrl" -ForegroundColor Green
Write-Host "  S3:  s3://$FrontendBucket" -ForegroundColor Green

Write-Host "`nLLM:" -ForegroundColor Yellow
Write-Host "  Provider: Groq (Llama 3.3 70B)" -ForegroundColor Green

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Update frontend CORS origins in each service's template.yaml"
Write-Host "  2. (Optional) Set up CloudFront CDN for the frontend"
Write-Host "  3. (Optional) Configure a custom domain with Route 53"
Write-Host "  4. (Optional) Set up CI/CD with GitHub Actions`n"
