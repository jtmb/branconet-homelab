param([int]$AdapterIndex = 16)
$ErrorActionPreference = 'Stop'
$client = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "Index=$AdapterIndex"
if (!$client.DHCPEnabled -or $client.DHCPServer -ne '192.168.0.5' -or
    $client.IPAddress -notcontains '192.168.0.13' -or
    $client.DefaultIPGateway -notcontains '192.168.0.1' -or
    ($client.DNSServerSearchOrder -join ',') -ne '192.168.0.253,192.168.0.5') {
    throw 'Real client lease does not match the approved server, reservation, gateway and DNS options'
}
$probes = foreach ($server in $client.DNSServerSearchOrder) {
    $transaction = Get-Random -Minimum 1 -Maximum 65535
    $packet = [Collections.Generic.List[byte]]::new()
    $packet.AddRange([byte[]]@(($transaction -shr 8), ($transaction -band 255), 1, 0, 0, 1, 0, 0, 0, 0, 0, 0))
    foreach ($label in 'k8s-api.branconet.lan'.Split('.')) {
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
        if ($reply.Length -lt 12 -or $reply[0] -ne $packet[0] -or $reply[1] -ne $packet[1] -or
            ($reply[2] -band 128) -eq 0 -or ($reply[3] -band 15) -ne 0 -or
            (($reply[6] -shl 8) + $reply[7]) -lt 1) {
            throw "Resolver $server returned an invalid or empty DNS answer"
        }
        [ordered]@{ resolver = $server; udp_reply_from = $peer.Address.ToString(); answer_count = (($reply[6] -shl 8) + $reply[7]); passed = $true }
    } finally {
        $socket.Dispose()
    }
    $tcpAnswer = Resolve-DnsName -Name k8s-api.branconet.lan -Type A -Server $server -TcpOnly -DnsOnly -NoHostsFile
    if (@($tcpAnswer.IPAddress) -notcontains '192.168.0.251') { throw "Resolver $server TCP answer differs from the expected API address" }
}
$defaultAnswer = Resolve-DnsName -Name homepage.branconet.lan -Type A -DnsOnly -NoHostsFile
if (@($defaultAnswer.IPAddress) -notcontains '192.168.0.252') { throw 'Normal Windows DNS did not resolve the LAN ingress' }
[ordered]@{
    dhcp_server = $client.DHCPServer
    client_address = @($client.IPAddress)
    gateway = @($client.DefaultIPGateway)
    dns = @($client.DNSServerSearchOrder)
    obtained = $client.DHCPLeaseObtained.ToString('o')
    expires = $client.DHCPLeaseExpires.ToString('o')
    direct_dns_probes = @($probes)
    default_dns_passed = $true
} | ConvertTo-Json -Depth 5
