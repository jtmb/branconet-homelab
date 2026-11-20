param([switch]$ValidateOnly)

$ErrorActionPreference = 'Stop'
# Existing task control state and its singleton lock stay in place. This is not
# permission to move/reset historical attempts, credentials or another checkout.
$stateRoot = 'F:/branconet-migration-artifacts/maintenance-storage-20261025/branconet-charts-local-ci-state'
$checkout = 'C:/Users/james/.codex/local-ci/branconet-charts-local-ci'
$python = 'C:/Users/james/AppData/Local/Programs/Python/Python312/python.exe'
$watchScript = $checkout + '/scripts/local-ci-watch.py'
$outputRoot = 'H:/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z'
$logRoot = $outputRoot + '/logs/charts-local-ci'
$tempRoot = $outputRoot + '/temp/charts-local-ci'
$nativeStageRoot = '/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/local-charts-publisher'
$expectedVolume = '\\?\Volume{b15e53e6-a2e9-4870-b263-3dbf35759e8c}\'

if (-not (Test-Path -LiteralPath $stateRoot -PathType Container) -or
    -not (Test-Path -LiteralPath ($stateRoot + '/owner.json') -PathType Leaf) -or
    -not (Test-Path -LiteralPath ($stateRoot + '/watcher.lock') -PathType Leaf)) {
    throw 'Original watcher control state/lock is unavailable; nothing started'
}
$owner = Get-Content -LiteralPath ($stateRoot + '/owner.json') -Raw | ConvertFrom-Json
if ($owner.origin -ne 'https://github.com/jtmb/branconet-charts.git' -or
    $owner.repository.Replace('\', '/').TrimEnd('/') -ne $checkout) {
    throw 'Existing watcher owner does not match; nothing started'
}
$volume = Get-Volume -DriveLetter H
if ($volume.UniqueId -ne $expectedVolume -or $volume.FileSystem -ne 'NTFS' -or
    -not (Test-Path -LiteralPath $outputRoot -PathType Container)) {
    throw 'Original H artifact volume/root is unavailable; no fallback'
}
foreach ($path in @('H:/AgentArtifacts', 'H:/AgentArtifacts/projects',
    'H:/AgentArtifacts/projects/branconet', 'H:/AgentArtifacts/projects/branconet/runs', $outputRoot)) {
    if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'H output root unexpectedly redirects; nothing started'
    }
}
if ((Get-PSDrive C).Free -lt 15GB -or $volume.SizeRemaining -lt (15GB + 256MB)) {
    throw 'Existing retained free-space floor is not met; nothing started'
}
foreach ($path in @(($outputRoot + '/logs'), ($outputRoot + '/temp'), $logRoot, $tempRoot)) {
    [IO.Directory]::CreateDirectory($path) | Out-Null
    if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'H output child unexpectedly redirects; nothing started'
    }
}
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:TMPDIR = $tempRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
# --help exits before locks, fetch, mounts, staging or publication. An old
# committed watcher must fail here rather than silently reuse its F/C path.
$help = (& $python -B $watchScript --help 2>&1 | Out-String)
$sourceReady = $LASTEXITCODE -eq 0 -and $help.Contains('--stage-root')
if ($ValidateOnly) {
    [pscustomobject]@{
        StateRoot = $stateRoot; Checkout = $checkout; OutputRoot = $outputRoot
        LogRoot = $logRoot; TempRoot = $tempRoot; NativeStageRoot = $nativeStageRoot
        HVolume = $volume.UniqueId; HCompatibleSourceInstalled = $sourceReady
        PublisherStarted = $false; TaskStateChanged = $false
    } | ConvertTo-Json -Compress
    exit 0
}
if (-not $sourceReady) { throw 'Reviewed H-compatible watcher source is not installed; nothing started' }

$run = [Guid]::NewGuid().ToString('N')
$keeper = $null
$watcher = $null
$result = 1
try {
    # Retain the existing keeper pattern and stop only the processes created by
    # this invocation. The watcher continues to acquire its original kernel lock.
    $keeper = Start-Process -FilePath wsl.exe -ArgumentList '-d Ubuntu -u root --exec /usr/sbin/runuser -u brajam -- /usr/bin/sleep infinity' -WindowStyle Hidden -PassThru
    $arguments = '-B ' + $watchScript + ' --state-dir ' + $stateRoot + ' --interval 45 --stage-root ' + $nativeStageRoot
    $watcher = Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput ($logRoot + '/watcher-' + $run + '.stdout.log') -RedirectStandardError ($logRoot + '/watcher-' + $run + '.stderr.log')
    while (-not $watcher.HasExited) {
        $keeper.Refresh()
        if ($keeper.HasExited) { throw 'Owned Ubuntu keeper exited; stopping only this watcher' }
        Start-Sleep -Seconds 2
        $watcher.Refresh()
    }
    $result = $watcher.ExitCode
} finally {
    foreach ($owned in @($watcher, $keeper)) {
        if ($owned -and -not $owned.HasExited) { $owned.Kill(); $owned.WaitForExit() }
        if ($owned) { $owned.Dispose() }
    }
}
exit $result
