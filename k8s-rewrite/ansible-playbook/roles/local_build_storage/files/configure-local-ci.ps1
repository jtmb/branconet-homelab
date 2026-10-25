$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$name = 'Branconet Charts Local CI'
$stateRoot = 'C:/Users/james/.codex/local-ci/branconet-charts-local-ci-state'
$state = $stateRoot + '/status.json'
$wrapper = $stateRoot + '/watch-with-wsl.ps1'
$scriptFragment = 'branconet-charts-local-ci/scripts/local-ci-watch.py'
$content = @'
$ErrorActionPreference = 'Stop'
$stateRoot = 'C:/Users/james/.codex/local-ci/branconet-charts-local-ci-state'
$run = [Guid]::NewGuid().ToString('N')
$keeper = Start-Process -FilePath wsl.exe -ArgumentList '-d Ubuntu -u brajam -- /usr/bin/sleep infinity' -WindowStyle Hidden -PassThru
$watcher = $null
$result = 1
try {
    $watcher = Start-Process -FilePath 'C:/Users/james/AppData/Local/Programs/Python/Python312/python.exe' -ArgumentList '-B C:/Users/james/.codex/local-ci/branconet-charts-local-ci/scripts/local-ci-watch.py --state-dir C:/Users/james/.codex/local-ci/branconet-charts-local-ci-state --interval 45 --offloaded-storage' -WindowStyle Hidden -PassThru -RedirectStandardOutput ($stateRoot + '/watcher-' + $run + '.stdout.log') -RedirectStandardError ($stateRoot + '/watcher-' + $run + '.stderr.log')
    while (-not $watcher.HasExited) {
        $keeper.Refresh()
        if ($keeper.HasExited) { throw 'Ubuntu controller keeper exited; stopping only this watcher' }
        Start-Sleep -Seconds 2
        $watcher.Refresh()
    }
    $result = $watcher.ExitCode
} finally {
    if ($watcher -and -not $watcher.HasExited) { Stop-Process -Id $watcher.Id -ErrorAction SilentlyContinue }
    if (-not $keeper.HasExited) { Stop-Process -Id $keeper.Id -ErrorAction SilentlyContinue }
}
exit $result
'@
$task = Get-ScheduledTask -TaskName $name
if ($task.Actions.Count -ne 1) { throw 'Unexpected publisher task actions' }
$action = $task.Actions[0]
if (-not $action.Arguments.Contains($scriptFragment) -and -not $action.Arguments.Contains($wrapper)) {
    throw 'Unexpected publisher task identity'
}
if ($action.Arguments.Contains($wrapper) -and (Test-Path -LiteralPath $wrapper) -and (Get-Content -LiteralPath $wrapper -Raw).Trim() -eq $content.Trim()) {
    [pscustomobject]@{changed=$false;task=$name;offloadedStorage=$true;ownedControllerKeeper=$true} | ConvertTo-Json -Compress
    exit 0
}
$status = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
if ($status.phase -notin @('published_await_flux','failed_or_uncertain_no_automatic_same_sha_retry')) {
    throw 'Publisher must finish its current attempt'
}
Stop-ScheduledTask -TaskName $name
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'python*' -and $_.CommandLine -like ('*' + $scriptFragment + '*')
} | ForEach-Object { Stop-Process -Id $_.ProcessId }
try {
    [IO.File]::WriteAllText($wrapper, $content, [Text.UTF8Encoding]::new($false))
    $updated = New-ScheduledTaskAction -Execute $action.Execute -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $wrapper + '"')
    Set-ScheduledTask -TaskName $name -Action $updated | Out-Null
    Start-ScheduledTask -TaskName $name
    [pscustomobject]@{changed=$true;task=$name;offloadedStorage=$true;ownedControllerKeeper=$true} | ConvertTo-Json -Compress
} catch {
    Set-ScheduledTask -TaskName $name -Action $action | Out-Null
    Start-ScheduledTask -TaskName $name
    throw
}
