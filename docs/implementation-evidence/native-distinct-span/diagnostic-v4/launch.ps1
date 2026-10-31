$diagRoot = $PSScriptRoot
$nodeExe = 'C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe'
$diagScript = Join-Path $diagRoot 'diagnostic.cjs'
$ownedNode = Start-Process -FilePath $nodeExe -ArgumentList ('"' + $diagScript + '"') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diagRoot 'stdout') -RedirectStandardError (Join-Path $diagRoot 'stderr') -PassThru
$ownedStart = $ownedNode.StartTime.ToUniversalTime().ToString('o')
$ownedNode.ProcessorAffinity = [IntPtr]1
$startRecord = [ordered]@{ pid=$ownedNode.Id; start_utc=$ownedStart; command=$diagScript; executable=$nodeExe; affinity=[long]$ownedNode.ProcessorAffinity; max_wall_seconds=60; scope='one CPU pure public parser diagnostic' }
[IO.File]::WriteAllText((Join-Path $diagRoot 'owner.json'), ($startRecord | ConvertTo-Json) + "`n", [Text.UTF8Encoding]::new($false))
$finished = $ownedNode.WaitForExit(60000)
if (-not $finished) { Stop-Process -Id $ownedNode.Id; $ownedNode.WaitForExit() }
$ownedNode.Refresh()
$terminal = [ordered]@{ pid=$ownedNode.Id; start_utc=$ownedStart; actual_exit=$ownedNode.ExitCode; timeout=(-not $finished); reaped=$ownedNode.HasExited; completed_utc=[DateTime]::UtcNow.ToString('o'); stdout_sha256=(Get-FileHash -LiteralPath (Join-Path $diagRoot 'stdout') -Algorithm SHA256).Hash.ToLower(); stderr_sha256=(Get-FileHash -LiteralPath (Join-Path $diagRoot 'stderr') -Algorithm SHA256).Hash.ToLower(); owned_pid_absent=(-not [bool](Get-Process -Id $ownedNode.Id -ErrorAction SilentlyContinue)) }
[IO.File]::WriteAllText((Join-Path $diagRoot 'terminal.json'), ($terminal | ConvertTo-Json) + "`n", [Text.UTF8Encoding]::new($false))
$terminal | ConvertTo-Json
Get-Content -LiteralPath (Join-Path $diagRoot 'stdout')
Get-Content -LiteralPath (Join-Path $diagRoot 'stderr')