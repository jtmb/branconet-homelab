$ErrorActionPreference = 'Stop'
$taskOwner = $PSScriptRoot
$taskRepo = 'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration\k8s-rewrite\front-end'
$taskNode = 'C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe'
$taskStages = @(
  @{name='focused';args=@('node_modules/tsx/dist/cli.mjs','--test','tests/native-auth-snapshot.test.ts')},
  @{name='types';args=@('node_modules/typescript/bin/tsc','--noEmit')},
  @{name='lint';args=@('node_modules/eslint/bin/eslint.js','.','--max-warnings=0')}
)
$taskResults = @(); $taskExit = 0
foreach ($taskStage in $taskStages) {
  $taskStart = [DateTime]::UtcNow.ToString('o')
  $taskChild = Start-Process -FilePath $taskNode -ArgumentList $taskStage.args -WorkingDirectory $taskRepo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOwner ($taskStage.name+'.stdout')) -RedirectStandardError (Join-Path $taskOwner ($taskStage.name+'.stderr'))
  @{stage=$taskStage.name;pid=$taskChild.Id;startUtc=$taskChild.StartTime.ToUniversalTime().ToString('o');startedUtc=$taskStart} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOwner 'active-handle.json') -Encoding utf8
  $taskChild.WaitForExit(); $taskChild.Refresh()
  $taskResult = @{stage=$taskStage.name;pid=$taskChild.Id;startedUtc=$taskStart;completedUtc=[DateTime]::UtcNow.ToString('o');actualExit=$taskChild.ExitCode;reaped=$taskChild.HasExited;pidAbsent=($null -eq (Get-Process -Id $taskChild.Id -ErrorAction SilentlyContinue))}
  $taskResults += $taskResult
  $taskResult | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOwner ($taskStage.name+'-terminal.json')) -Encoding utf8
  if ($taskChild.ExitCode -ne 0) {$taskExit=$taskChild.ExitCode;break}
}
@{actualExit=$taskExit;completedUtc=[DateTime]::UtcNow.ToString('o');stages=$taskResults} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskOwner 'launcher-terminal.json') -Encoding utf8
exit $taskExit
