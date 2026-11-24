param([int]$AdapterIndex = 16)
$ErrorActionPreference = 'Stop'
$name = 'notifications.branconet.lan'
$expected = '192.168.0.252'
$client = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "Index=$AdapterIndex"
if (!$client.DHCPEnabled -or $client.DHCPServer -ne '192.168.0.5' -or
    ($client.DNSServerSearchOrder -join ',') -ne '192.168.0.253,192.168.0.5') {
    throw 'Preserve the existing DHCP lease and its two advertised resolvers'
}

function Read-U16([byte[]]$Bytes, [int]$Offset) {
    if ($Offset -lt 0 -or $Offset + 2 -gt $Bytes.Length) { throw 'Truncated DNS field' }
    return ([int]$Bytes[$Offset] -shl 8) + [int]$Bytes[$Offset + 1]
}

function Skip-DnsName([byte[]]$Bytes, [int]$Offset) {
    $labels = 0
    while ($true) {
        if ($Offset -ge $Bytes.Length -or ++$labels -gt 128) { throw 'Invalid DNS name' }
        $length = [int]$Bytes[$Offset++]
        if (($length -band 192) -eq 192) {
            if ($Offset -ge $Bytes.Length) { throw 'Truncated DNS pointer' }
            return $Offset + 1
        }
        if ($length -eq 0) { return $Offset }
        if ($length -gt 63 -or $Offset + $length -gt $Bytes.Length) { throw 'Invalid DNS label' }
        $Offset += $length
    }
}

$probes = foreach ($server in $client.DNSServerSearchOrder) {
    $transaction = Get-Random -Minimum 1 -Maximum 65535
    $packet = [Collections.Generic.List[byte]]::new()
    $packet.AddRange([byte[]]@(($transaction -shr 8), ($transaction -band 255), 1, 0, 0, 1, 0, 0, 0, 0, 0, 0))
    foreach ($label in $name.Split('.')) {
        $packet.Add([byte]$label.Length)
        $packet.AddRange([Text.Encoding]::ASCII.GetBytes($label))
    }
    $packet.AddRange([byte[]]@(0, 0, 1, 0, 1))
    $socket = [Net.Sockets.UdpClient]::new()
    try {
        $socket.Client.ReceiveTimeout = 3000
        $socket.Connect($server, 53)
        $null = $socket.Send($packet.ToArray(), $packet.Count)
        $peer = [Net.IPEndPoint]::new([Net.IPAddress]::Any, 0)
        $reply = $socket.Receive([ref]$peer)
        if ($reply.Length -lt 12 -or (Read-U16 $reply 0) -ne $transaction -or
            ($reply[2] -band 128) -eq 0 -or ($reply[2] -band 2) -ne 0 -or
            ($reply[3] -band 15) -ne 0 -or $peer.Address.ToString() -ne $server) {
            throw 'Invalid DNS UDP response'
        }
        $offset = 12
        for ($i = 0; $i -lt (Read-U16 $reply 4); $i++) {
            $offset = (Skip-DnsName $reply $offset) + 4
        }
        $addresses = @()
        for ($i = 0; $i -lt (Read-U16 $reply 6); $i++) {
            $offset = Skip-DnsName $reply $offset
            $type = Read-U16 $reply $offset
            $class = Read-U16 $reply ($offset + 2)
            $size = Read-U16 $reply ($offset + 8)
            $offset += 10
            if ($offset + $size -gt $reply.Length) { throw 'Truncated DNS answer' }
            if ($type -eq 1 -and $class -eq 1 -and $size -eq 4) {
                $addresses += ($reply[$offset..($offset + 3)] -join '.')
            }
            $offset += $size
        }
        if ((($addresses | Sort-Object -Unique) -join ',') -ne $expected) { throw 'Wrong UDP address' }
    } finally {
        $socket.Dispose()
    }
    $tcp = Resolve-DnsName -Name $name -Type A -Server $server -TcpOnly -DnsOnly -NoHostsFile
    if (@($tcp.IPAddress) -notcontains $expected) { throw 'Wrong TCP address' }
    [ordered]@{ resolver = $server; udp = $expected; tcp = $expected; passed = $true }
}
$normal = Resolve-DnsName -Name $name -Type A -DnsOnly -NoHostsFile
if (@($normal.IPAddress) -notcontains $expected) { throw 'Normal client DNS failed' }
[ordered]@{
    passed = $true
    hostname = $name
    dhcpServerUnchanged = $client.DHCPServer
    advertisedResolvers = @($client.DNSServerSearchOrder)
    directProbes = @($probes)
    normalClientDNS = $expected
    leaseRenewalOrAdapterChangePerformed = $false
    attendedPhoneReceiptClaimed = $false
} | ConvertTo-Json -Depth 5
