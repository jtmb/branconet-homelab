$ErrorActionPreference = 'Stop'
$qualityRoot = $PSScriptRoot
$qualityScript = Join-Path $qualityRoot 'quality.ps1'
$ownedQuality = Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -File "' + $qualityScript + '"') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $qualityRoot 'launch.stdout') -RedirectStandardError (Join-Path $qualityRoot 'launch.stderr') -PassThru
$null = $ownedQuality.Handle
$ownedStart = $ownedQuality.StartTime.ToUniversalTime().ToString('o')
$owner = [ordered]@{launcherPid=$PID;launcherStart=(Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o');qualityPid=$ownedQuality.Id;qualityStart=$ownedStart;sourceManifestSHA256=(Get-FileHash -LiteralPath (Join-Path $qualityRoot 'source-manifest.json') -Algorithm SHA256).Hash.ToLower()}
[IO.File]::WriteAllText((Join-Path $qualityRoot 'owner.json'), ($owner | ConvertTo-Json) + "`n", [Text.UTF8Encoding]::new($false))
$ownedQuality.WaitForExit()
$actualExit = $ownedQuality.ExitCode
$child = Get-Content -LiteralPath (Join-Path $qualityRoot 'terminal.json') -Raw | ConvertFrom-Json
if (-not $child.terminal -or $child.exitCode -ne $actualExit) { throw 'Quality actual exit binding mismatch' }
$closed = [ordered]@{actualExit=$actualExit;childExit=$child.exitCode;launcherPid=$PID;qualityPid=$ownedQuality.Id;qualityStart=$ownedStart;reaped=$ownedQuality.HasExited;qualityPidAbsent=(-not [bool](Get-Process -Id $ownedQuality.Id -ErrorAction SilentlyContinue));completedAt=[DateTime]::UtcNow.ToString('o');terminalSHA256=(Get-FileHash -LiteralPath (Join-Path $qualityRoot 'terminal.json') -Algorithm SHA256).Hash.ToLower()}
[IO.File]::WriteAllText((Join-Path $qualityRoot 'launcher-terminal.json'), ($closed | ConvertTo-Json) + "`n", [Text.UTF8Encoding]::new($false))
exit $actualExit
