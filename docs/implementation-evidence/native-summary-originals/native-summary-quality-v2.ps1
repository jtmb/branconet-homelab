$ErrorActionPreference='Stop'
Set-Location -LiteralPath 'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration\k8s-rewrite\front-end'
$env:PATH='C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64;'+$env:PATH
Remove-Item Env:RUST_LOG -ErrorAction SilentlyContinue
$taskEvidence='../../docs/implementation-evidence/native-summary-quality-v2.json'
$taskLog='../../docs/implementation-evidence/native-summary-quality-v2-cli.txt'
$taskRecord=[ordered]@{source='55f46b1 plus explicit typed native summary parser/transport; full qualification';startedAt=(Get-Date).ToUniversalTime().ToString('o');pid=$PID;checks=@();terminal=$false}
$taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEvidence -Encoding utf8
try {
 $taskPhases=@(
  @{command='focused native prefix/window/capacity/auth';binary='node.exe';arguments=@('node_modules/tsx/dist/cli.mjs','--test','tests/native-summary-json.test.ts','tests/native-list-prefix.test.ts','tests/native-list-window.test.ts','tests/secret-capacity.test.ts','tests/native-auth-snapshot.test.ts')},
  @{command='npm run build';binary='npm.cmd';arguments=@('run','build')},
  @{command='npm test';binary='npm.cmd';arguments=@('test')},
  @{command='npm run lint';binary='npm.cmd';arguments=@('run','lint')},
  @{command='npm run typecheck';binary='npm.cmd';arguments=@('run','typecheck')},
  @{command='npm run test:integration';binary='npm.cmd';arguments=@('run','test:integration')}
 )
 foreach($taskPhase in $taskPhases){
  & $taskPhase.binary @($taskPhase.arguments) 2>&1 | Out-File -LiteralPath $taskLog -Append -Encoding utf8
  $taskCode=$LASTEXITCODE
  $taskRecord.checks += [ordered]@{command=$taskPhase.command;exitCode=$taskCode;completedAt=(Get-Date).ToUniversalTime().ToString('o')}
  $taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEvidence -Encoding utf8
  if($taskCode -ne 0){$taskRecord.terminal=$true;$taskRecord.exitCode=$taskCode;$taskRecord.completedAt=(Get-Date).ToUniversalTime().ToString('o');$taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEvidence -Encoding utf8;exit $taskCode}
 }
 $taskRecord.terminal=$true;$taskRecord.exitCode=0;$taskRecord.completedAt=(Get-Date).ToUniversalTime().ToString('o')
 $taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEvidence -Encoding utf8
 exit 0
} catch {
 $taskRecord.terminal=$true;$taskRecord.exitCode=1;$taskRecord.launcherError='Inspect retained CLI and phase markers'
 $taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEvidence -Encoding utf8
 exit 1
}



