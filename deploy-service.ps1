<#
.SYNOPSIS
    Build & deploy a single SAM service using a staging directory approach.
.DESCRIPTION
    Creates a minimal staging directory with only the required code, builds with SAM, and deploys.
.PARAMETER ServiceName
    The service directory name (e.g., "security", "profile_service").
.PARAMETER StackName
    CloudFormation stack name override. Default: rural-credit-<ServiceName>.
.PARAMETER Region
    AWS region. Default: us-east-1.
.PARAMETER ExtraParams
    Extra params to pass to sam deploy (e.g., "--parameter-overrides GroqApiKey=xxx").
#>
param(
    [Parameter(Mandatory)]
    [string]$ServiceName,

    [string]$StackName = "",
    [string]$Region = "us-east-1",
    [string]$ExtraParams = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = "c:\Users\Shivansh\Desktop\Me\AiForBharatHack"
$ServiceDir = "$RepoRoot\services\$ServiceName"
$StagingDir = "$RepoRoot\_staging\$ServiceName"
$SAM = "C:\Program Files\Amazon\AWSSAMCLI\bin\sam.cmd"

if (-not $StackName) { $StackName = "rural-credit-$($ServiceName -replace '_','-')" }

Write-Host "=== Building & Deploying: $ServiceName ===" -ForegroundColor Cyan
Write-Host "Stack:   $StackName"
Write-Host "Region:  $Region"
Write-Host ""

# ──────── Step 1: Create staging directory ────────
Write-Host "[1/4] Creating staging directory..." -ForegroundColor Yellow
if (Test-Path $StagingDir) { Remove-Item -Recurse -Force $StagingDir }
New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null

# Copy only what's needed:
# - services/__init__.py
# - services/shared/ (shared library)
# - services/<ServiceName>/ (this service, excluding tests & .aws-sam)
# - requirements.txt (root-level, for pip install)
# - template.yaml (from the service directory)

# Root requirements.txt
Copy-Item "$RepoRoot\requirements.txt" "$StagingDir\requirements.txt"

# services/__init__.py
New-Item -ItemType Directory -Path "$StagingDir\services" -Force | Out-Null
Copy-Item "$RepoRoot\services\__init__.py" "$StagingDir\services\__init__.py"

# services/shared/ (entire shared library, minus __pycache__ and egg-info)
$sharedDest = "$StagingDir\services\shared"
Copy-Item "$RepoRoot\services\shared" $sharedDest -Recurse
Get-ChildItem $sharedDest -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$sharedDest\rural_credit_shared.egg-info" -ErrorAction SilentlyContinue

# services/<ServiceName>/ (minus tests, .aws-sam, __pycache__)
$svcDest = "$StagingDir\services\$ServiceName"
Copy-Item "$RepoRoot\services\$ServiceName" $svcDest -Recurse
Remove-Item -Recurse -Force "$svcDest\tests" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$svcDest\.aws-sam" -ErrorAction SilentlyContinue
Get-ChildItem $svcDest -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Copy template.yaml into staging root (we'll modify CodeUri)
$templateSrc = "$ServiceDir\template.yaml"
$templateDst = "$StagingDir\template.yaml"
# Read template and replace CodeUri: ../../ with CodeUri: ./
(Get-Content $templateSrc -Raw) -replace 'CodeUri:\s*\.\./\.\./?', 'CodeUri: ./' | Set-Content $templateDst -NoNewline

$stagingSize = (Get-ChildItem -Recurse -File $StagingDir -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Write-Host "   Staging size: $([math]::Round($stagingSize/1MB, 1)) MB" -ForegroundColor Green

# ──────── Step 2: SAM Build ────────
Write-Host "[2/4] Running SAM build..." -ForegroundColor Yellow
Push-Location $StagingDir
& $SAM build --template-file template.yaml
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "SAM build failed!" }

$buildSize = (Get-ChildItem -Recurse -File "$StagingDir\.aws-sam\build" -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Write-Host "   Build size: $([math]::Round($buildSize/1MB, 1)) MB" -ForegroundColor Green

# ──────── Step 3: SAM Deploy ────────
Write-Host "[3/4] Deploying to AWS..." -ForegroundColor Yellow
$deployCmd = "& `"$SAM`" deploy --stack-name $StackName --region $Region --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset --resolve-s3 $ExtraParams"
Invoke-Expression $deployCmd
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "SAM deploy failed!" }
Pop-Location

# ──────── Step 4: Output ────────
Write-Host "[4/4] Fetching outputs..." -ForegroundColor Yellow
$apiUrl = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='$($ServiceName -replace '_','')Api' || OutputKey=='SecurityApi' || OutputKey=='ProfileServiceApi'].OutputValue" --output text 2>$null
Write-Host ""
Write-Host "=== $ServiceName DEPLOYED ===" -ForegroundColor Green
Write-Host "API URL: $apiUrl"

# Clean up staging
Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
