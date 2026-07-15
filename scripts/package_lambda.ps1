param(
    [string]$OutputPath = "dist\lambda-deploy.zip",
    [string]$BuildDir = "build\lambda",
    [string]$Python = "python",
    [string]$LambdaPythonVersion = "3.12",
    [string]$Platform = "manylinux2014_x86_64"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$buildPath = Join-Path $repoRoot $BuildDir
$outputFile = Join-Path $repoRoot $OutputPath
$outputDir = Split-Path -Parent $outputFile

if (Test-Path $buildPath) {
    Remove-Item -LiteralPath $buildPath -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

& $Python -m pip install `
    -r (Join-Path $repoRoot "requirements.txt") `
    -t $buildPath `
    --platform $Platform `
    --implementation cp `
    --python-version $LambdaPythonVersion `
    --only-binary=:all: `
    --upgrade

if ($LASTEXITCODE -ne 0) {
    throw "Lambda dependency installation failed (exit code: $LASTEXITCODE)."
}

Copy-Item -Path (Join-Path $repoRoot "main.py") -Destination $buildPath
Copy-Item -Path (Join-Path $repoRoot "ocr_service") -Destination $buildPath -Recurse

if (Test-Path $outputFile) {
    Remove-Item -LiteralPath $outputFile -Force
}

Compress-Archive -Path (Join-Path $buildPath "*") -DestinationPath $outputFile -Force
& $Python (Join-Path $repoRoot "scripts\check_lambda_deployment.py") --skip-env --package $outputFile
if ($LASTEXITCODE -ne 0) {
    throw "Lambda package validation failed (exit code: $LASTEXITCODE)."
}
Write-Host "Created $outputFile"
