param(
    [string]$HostIp = "192.168.0.232",
    [string]$ExpectedPcIp = "192.168.0.100",
    [string]$LocalReportsDir = ""
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($LocalReportsDir)) {
    $LocalReportsDir = Join-Path $ProjectDir "reports"
}
$LocalReportsDir = (New-Item -ItemType Directory -Force -Path $LocalReportsDir).FullName
$ReportTxt = Join-Path $LocalReportsDir "board_connection_check.txt"
$ReportJson = Join-Path $LocalReportsDir "board_connection_check.json"

function Get-IPv4Prefix24 {
    param([string]$Ip)
    $parts = $Ip.Split(".")
    if ($parts.Count -lt 3) {
        return ""
    }
    return "$($parts[0]).$($parts[1]).$($parts[2])."
}

function Get-LocalIPv4Addresses {
    $addresses = @()
    if (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue) {
        $addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -and $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
            Select-Object InterfaceAlias, IPAddress, PrefixLength
    }

    if ($addresses.Count -eq 0) {
        $raw = ipconfig
        $addresses = $raw |
            Select-String -Pattern "IPv4" |
            ForEach-Object {
                $ip = ($_.Line -split ":")[-1].Trim()
                [PSCustomObject]@{
                    InterfaceAlias = "ipconfig"
                    IPAddress = $ip
                    PrefixLength = 24
                }
            }
    }
    return @($addresses)
}

$hostPrefix = Get-IPv4Prefix24 $HostIp
$expectedPrefix = Get-IPv4Prefix24 $ExpectedPcIp
$localAddresses = Get-LocalIPv4Addresses
$sameSubnet = @($localAddresses | Where-Object { $_.IPAddress.StartsWith($hostPrefix) })
$expectedIpPresent = @($localAddresses | Where-Object { $_.IPAddress -eq $ExpectedPcIp }).Count -gt 0
$pingOk = Test-Connection -ComputerName $HostIp -Count 2 -Quiet

$status = if ($pingOk) {
    "reachable"
} elseif ($sameSubnet.Count -eq 0) {
    "pc_not_in_board_subnet"
} else {
    "same_subnet_but_unreachable"
}

$recommendations = New-Object System.Collections.Generic.List[string]
if (-not $expectedIpPresent) {
    $recommendations.Add("Set the Windows Ethernet IPv4 address to $ExpectedPcIp with mask 255.255.255.0 and empty gateway.")
}
if ($sameSubnet.Count -eq 0) {
    $recommendations.Add("The PC is not on the ${hostPrefix}0/24 subnet, so $HostIp cannot be reached directly.")
}
if (-not $pingOk -and $sameSubnet.Count -gt 0) {
    $recommendations.Add("PC and board appear to be on the same subnet; check cable, board power, board IP, and firewall.")
}
if ($pingOk) {
    $recommendations.Add("Board network is reachable. You can run tools\pull_board_reports.ps1 or tools\sync_to_board.ps1.")
}

$summary = [PSCustomObject]@{
    host_ip = $HostIp
    expected_pc_ip = $ExpectedPcIp
    host_prefix_24 = $hostPrefix
    expected_prefix_24 = $expectedPrefix
    status = $status
    ping_ok = $pingOk
    expected_ip_present = $expectedIpPresent
    same_subnet_addresses = @($sameSubnet | ForEach-Object {
        [PSCustomObject]@{
            interface = $_.InterfaceAlias
            ip = $_.IPAddress
            prefix_length = $_.PrefixLength
        }
    })
    local_ipv4_addresses = @($localAddresses | ForEach-Object {
        [PSCustomObject]@{
            interface = $_.InterfaceAlias
            ip = $_.IPAddress
            prefix_length = $_.PrefixLength
        }
    })
    recommendations = @($recommendations)
}

$summary | ConvertTo-Json -Depth 5 | Set-Content -Path $ReportJson -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("SafeLab-Vision Pro Board Connection Check")
$lines.Add("Host IP: $HostIp")
$lines.Add("Expected PC IP: $ExpectedPcIp")
$lines.Add("Status: $status")
$lines.Add("Ping OK: $pingOk")
$lines.Add("Expected IP present: $expectedIpPresent")
$lines.Add("")
$lines.Add("Local IPv4 addresses:")
foreach ($addr in $localAddresses) {
    $lines.Add("- $($addr.InterfaceAlias): $($addr.IPAddress)/$($addr.PrefixLength)")
}
$lines.Add("")
$lines.Add("Recommendations:")
foreach ($item in $recommendations) {
    $lines.Add("- $item")
}
$lines | Set-Content -Path $ReportTxt -Encoding UTF8

Write-Host ($summary | ConvertTo-Json -Depth 5)
if ($pingOk) {
    exit 0
}
exit 1
