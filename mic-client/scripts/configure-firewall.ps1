[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$RemoteAddress,

    [ValidateRange(1, 65535)]
    [int]$Port = 8787,

    [string]$RuleName = "MadeInChinaGateway",

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$addresses = @(
    $RemoteAddress |
        ForEach-Object { $_ -split "," } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)

if ($addresses.Count -eq 0) {
    throw "At least one trusted remote address is required."
}

$forbidden = @("*", "0.0.0.0/0", "::/0")
foreach ($address in $addresses) {
    if ($forbidden -contains $address) {
        throw "Unrestricted remote ranges are not permitted."
    }
}

if ($DryRun) {
    Write-Output "Firewall rule: $RuleName"
    Write-Output "Direction: Inbound"
    Write-Output "Protocol: TCP"
    Write-Output "LocalPort: $Port"
    Write-Output "RemoteAddress: $($addresses -join ',')"
    exit 0
}

$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Remove-NetFirewallRule -DisplayName $RuleName
}

New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -RemoteAddress $addresses `
    -Profile Private | Out-Null

Write-Output "Configured $RuleName for trusted remote addresses only."
