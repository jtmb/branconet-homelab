$ErrorActionPreference = 'Stop'
$diagnosticOwner = $PSScriptRoot
$diagnosticInput = Get-Content -LiteralPath (Join-Path $diagnosticOwner 'inputs.json') -Raw | ConvertFrom-Json
$diagnosticFile = Join-Path $diagnosticOwner 'diagnostic.cjs'
$diagnosticFrozen = @{
    createdAt = [DateTime]::UtcNow.ToString('o')
    harnessSHA256 = (Get-FileHash -LiteralPath $diagnosticFile -Algorithm SHA256).Hash.ToLowerInvariant()
    launcherSHA256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    inputSHA256 = (Get-FileHash -LiteralPath (Join-Path $diagnosticOwner 'inputs.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    nodeSHA256 = (Get-FileHash -LiteralPath $diagnosticInput.node -Algorithm SHA256).Hash.ToLowerInvariant()
    cpuAffinityMask = 3
    globalProcessTimeoutMs = 60000
    scope = 'One owned Node run; no production edits/network/dependencies/Docker'
}
if ($diagnosticFrozen.nodeSHA256 -ne $diagnosticInput.nodeSHA256) { throw 'Frozen Node mismatch' }
$diagnosticFrozen | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $diagnosticOwner 'launch-frozen.json') -Encoding utf8
$diagnosticProcess = Start-Process -FilePath $diagnosticInput.node -ArgumentList ('"' + $diagnosticFile + '"') -WorkingDirectory $diagnosticOwner -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diagnosticOwner 'node.stdout') -RedirectStandardError (Join-Path $diagnosticOwner 'node.stderr') -PassThru
$diagnosticProcess.ProcessorAffinity = [IntPtr]3
$diagnosticStarted = $diagnosticProcess.StartTime.ToUniversalTime().ToString('o')
@{ pid=$diagnosticProcess.Id; startedUtc=$diagnosticStarted; recordedAt=[DateTime]::UtcNow.ToString('o'); affinity=[long]$diagnosticProcess.ProcessorAffinity; source=$diagnosticInput.productionSource; owner=$diagnosticOwner } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $diagnosticOwner 'handle.json') -Encoding utf8
$diagnosticTimedOut = -not $diagnosticProcess.WaitForExit(60000)
if ($diagnosticTimedOut) { $diagnosticProcess.Kill(); $diagnosticProcess.WaitForExit() }
$diagnosticProcess.Refresh()
$diagnosticExit = $diagnosticProcess.ExitCode
$diagnosticAbsent = $null -eq (Get-Process -Id $diagnosticProcess.Id -ErrorAction SilentlyContinue)
$diagnosticTerminal = @{ pid=$diagnosticProcess.Id; startedUtc=$diagnosticStarted; completedUtc=[DateTime]::UtcNow.ToString('o'); actualOSExit=$diagnosticExit; timedOut=$diagnosticTimedOut; reaped=$true; ownedPIDAbsent=$diagnosticAbsent; harnessSHA256=(Get-FileHash -LiteralPath $diagnosticFile -Algorithm SHA256).Hash.ToLowerInvariant(); nodeRuns=1 }
$diagnosticTerminal | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $diagnosticOwner 'launcher-terminal.json') -Encoding utf8
if ($diagnosticTimedOut -or -not $diagnosticAbsent -or $diagnosticExit -ne 0) { exit 1 }
exit 0
