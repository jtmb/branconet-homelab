$ErrorActionPreference = 'Stop'
$credentialLines = "protocol=https`nhost=github.com`n`n" | & git credential fill
if ($LASTEXITCODE -ne 0) { throw 'Existing Git credential unavailable' }
$credential = @{}
foreach ($line in $credentialLines) {
    $parts = $line -split '=', 2
    if ($parts.Count -eq 2) { $credential[$parts[0]] = $parts[1] }
}
try {
    $headers = @{ Authorization = 'Bearer ' + $credential['password']; Accept = 'application/vnd.github+json' }
    $repo = Invoke-RestMethod -Uri 'https://api.github.com/repos/jtmb/branconet-charts' -Headers $headers
    $actions = Invoke-RestMethod -Uri 'https://api.github.com/repos/jtmb/branconet-charts/actions/permissions' -Headers $headers
    if ($repo.private -ne $true -or $actions.enabled -ne $false) { throw 'Private repository / Actions disabled gate failed' }
    @{ repository = 'jtmb/branconet-charts'; private = $true; actions_enabled = $false } | ConvertTo-Json -Compress
} finally {
    $credential.Clear()
    $credentialLines = $null
    $headers = $null
}
