from pathlib import Path
import hashlib,json,shutil
b=Path(__file__).parent;old=b/'selected-object-diagnostic-v1';out=b/'selected-object-diagnostic-v2';out.mkdir(exist_ok=False)
for name in ['inputs.json','secret-summary-json.ts','secret-ascii-span.ts','cluster-secrets.ts']:(out/name).write_bytes((old/name).read_bytes())
code=(old/'diagnostic.cjs').read_text();marker="const out=__dirname,repo="
assert code.count(marker)==1
code=code.replace(marker,"process.on('exit',code=>fs.writeFileSync(path.join(__dirname,'child-exit.json'),JSON.stringify({pid:process.pid,exitCode:code,completedUtc:new Date().toISOString()})+'\\n'));\n"+marker)
(out/'diagnostic.cjs').write_text(code)
launch=(old/'launch.ps1').read_text();launch=launch.replace('$ownedStart =', '$null = $ownedNode.Handle\n$ownedStart =').replace('$ownedNode.Refresh()','$observedExit = $ownedNode.ExitCode\n$childExit = Get-Content -LiteralPath (Join-Path $diagRoot \'child-exit.json\') -Raw | ConvertFrom-Json\nif ($childExit.pid -ne $ownedNode.Id -or $childExit.exitCode -ne $observedExit) { throw \'Owned exit binding mismatch\' }').replace('actual_exit=$ownedNode.ExitCode','actual_exit=$observedExit; child_exit=$childExit.exitCode')
launch+='\nexit $observedExit\n';(out/'launch.ps1').write_text(launch)
(out/'continuation.json').write_text(json.dumps({'priorAttempt':str(old),'priorExitCode':None,'onlyDiagnosticChange':'add child normal-exit marker; same all inputs/oracles/timing counts, no trimming','launcherChange':'cache process handle; capture OS exit before any refresh; compare with child exit marker','priorDiagnosticSHA256':hashlib.sha256((old/'diagnostic.cjs').read_bytes()).hexdigest()},indent=2)+'\n')
