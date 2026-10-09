# Historical 22001 registration helper. Current production uses Linux supervisor on 22005.
# See docs/MIGRATION_22001_TO_22005_2026-10-09.md; do not use this for the current host.
[CmdletBinding()]
param([string]$Root = 'C:\FusanheGateway', [switch]$UpdateExisting)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$python = Join-Path $Root 'venv\Scripts\pythonw.exe'
$runner = Join-Path $Root 'scripts\run_windows_gateway.py'
$config = Join-Path $Root 'private\channels.json'
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -MultipleInstances IgnoreNew
foreach ($mode in @('alibaba', 'mic', 'bridge')) {
    $name = 'Fusanhe-22001-' + $mode
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing -and -not $UpdateExisting) {
        throw "Task already exists; stop and inspect before updating: $name"
    }
    $log = Join-Path $Root ('logs\' + $mode + '.log')
    $arguments = '-u "' + $runner + '" ' + $mode + ' --config "' + $config + '" --log-file "' + $log + '"'
    $action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $Root
    if ($existing) {
        $processes = @(Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -like "$Root\*" -and $_.Name -match '^python(w)?\.exe$' -and
            $_.CommandLine -like "*run_windows_gateway.py* $mode *"
        })
        Stop-ScheduledTask -TaskName $name
        foreach ($process in $processes) {
            if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
                & taskkill.exe /PID $process.ProcessId /T /F | Out-Null
            }
        }
        Set-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal `
            -Settings $settings | Out-Null
    } else {
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal `
            -Settings $settings -Description 'Fusanhe read-only channel collector; dedicated login required' | Out-Null
    }
    Start-ScheduledTask -TaskName $name
    Write-Output "Started $name with logon autostart and one-minute failure restart."
}
