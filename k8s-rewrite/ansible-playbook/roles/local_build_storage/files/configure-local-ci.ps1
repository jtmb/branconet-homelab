$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$name = 'Branconet Charts Local CI'
$state = 'C:/Users/james/.codex/local-ci/branconet-charts-local-ci-state/status.json'
$scriptFragment = 'branconet-charts-local-ci/scripts/local-ci-watch.py'
$task = Get-ScheduledTask -TaskName $name
if ($task.Actions.Count -ne 1) { throw 'Unexpected publisher task actions' }
$action = $task.Actions[0]
if (-not $action.Arguments.Contains($scriptFragment) -or -not $action.Arguments.Contains('--interval 45')) {
    throw 'Unexpected publisher task identity'
}
if ($action.Arguments.Contains('--offloaded-storage')) {
    [pscustomobject]@{changed=$false;task=$name;offloadedStorage=$true} | ConvertTo-Json -Compress
    exit 0
}
$status = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
if (-not $status.passed -or $status.phase -ne 'published_await_flux') { throw 'Publisher must finish its current attempt' }
Stop-ScheduledTask -TaskName $name
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'python*' -and $_.CommandLine -like ('*' + $scriptFragment + '*')
} | ForEach-Object { Stop-Process -Id $_.ProcessId }
try {
    $argsNew = $action.Arguments.Replace('--interval 45', '--interval 45 --offloaded-storage')
    $options = @{Execute=$action.Execute;Argument=$argsNew}
    if ($action.WorkingDirectory) { $options.WorkingDirectory=$action.WorkingDirectory }
    $updated = New-ScheduledTaskAction @options
    Set-ScheduledTask -TaskName $name -Action $updated | Out-Null
    Start-ScheduledTask -TaskName $name
    [pscustomobject]@{changed=$true;task=$name;offloadedStorage=$true} | ConvertTo-Json -Compress
} catch {
    Start-ScheduledTask -TaskName $name
    throw
}
