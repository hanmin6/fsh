[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,

    [string]$TaskName = "MadeInChinaGateway",

    [ValidateRange(1, 65535)]
    [int]$Port = 8787,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$resolvedInstall = [IO.Path]::GetFullPath(
    $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallDir)
)
$python = Join-Path $resolvedInstall ".venv\Scripts\python.exe"
$arguments = "-m uvicorn mic_gateway.main:create_production_app --factory --host 0.0.0.0 --port $Port"
$userId = [Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($DryRun) {
    Write-Output "Task: $TaskName"
    Write-Output "Trigger: AtLogOn for $userId"
    Write-Output "LogonType: Interactive"
    Write-Output "WorkingDirectory: $resolvedInstall"
    Write-Output "Command: $python $arguments"
    Write-Output "Restart: 3 attempts, 1 minute interval"
    exit 0
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Installed Python was not found at $python"
}

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $arguments `
    -WorkingDirectory $resolvedInstall
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Output "Registered $TaskName for interactive startup at logon."
