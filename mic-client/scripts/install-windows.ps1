[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,

    [Parameter(Mandatory = $true)]
    [string]$AppDataDir,

    [string]$PythonCommand = "python",

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-AbsolutePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath(
        $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    )
}

$sourceRoot = Get-AbsolutePath (Join-Path $PSScriptRoot "..")
$resolvedInstall = Get-AbsolutePath $InstallDir
$resolvedAppData = Get-AbsolutePath $AppDataDir
$sourcePrefix = $sourceRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

if ($resolvedAppData.Equals($sourceRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $resolvedAppData.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "AppDataDir must be outside the source tree."
}

$venvDir = Join-Path $resolvedInstall ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if ($DryRun) {
    Write-Output "Create install directory: $resolvedInstall"
    Write-Output "Create application-data directory: $resolvedAppData"
    Write-Output "Run: $PythonCommand -m venv $venvDir"
    Write-Output "Run: $venvPython -m pip install $sourceRoot"
    Write-Output "Run: $venvPython -m playwright install chromium"
    Write-Output "Run from AppDataDir: $venvPython -m alembic -c $(Join-Path $sourceRoot 'alembic.ini') upgrade head"
    Write-Output "Set user environment: MIC_APP_DATA_DIR=$resolvedAppData"
    Write-Output "Restrict application-data ACL to the current user and local administrators"
    exit 0
}

New-Item -ItemType Directory -Path $resolvedInstall -Force | Out-Null
New-Item -ItemType Directory -Path $resolvedAppData -Force | Out-Null

& $PythonCommand -m venv $venvDir
if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $venvPython -m pip install $sourceRoot
if ($LASTEXITCODE -ne 0) { throw "package installation failed" }
& $venvPython -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium installation failed" }

Push-Location $resolvedAppData
try {
    & $venvPython -m alembic -c (Join-Path $sourceRoot "alembic.ini") upgrade head
    if ($LASTEXITCODE -ne 0) { throw "database migration failed" }
} finally {
    Pop-Location
}

[Environment]::SetEnvironmentVariable(
    "MIC_APP_DATA_DIR",
    $resolvedAppData,
    [EnvironmentVariableTarget]::User
)

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $resolvedAppData /inheritance:r /grant:r "${currentUser}:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "failed to restrict application-data ACL" }

Write-Output "Installed mic-gateway into $resolvedInstall"
Write-Output "MIC_APP_DATA_DIR is set for future processes. Sign out and back in before registering the task if needed."
