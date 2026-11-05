from pathlib import Path
import hashlib,json,subprocess
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
out=base/'native-distinct-span-quality-v1';out.mkdir(exist_ok=False)
paths=subprocess.check_output(['git','ls-files','--','k8s-rewrite/front-end'],cwd=repo).decode().splitlines()
paths+=['k8s-rewrite/front-end/src/lib/secret-ascii-span.ts','k8s-rewrite/front-end/tests/native-ascii-span.test.ts']
rows=[]
for path in sorted(set(paths)):
 b=(repo/path).read_bytes();dest=out/'working-source'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
 rows.append({'path':path,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(out/'source-manifest.json').write_text(json.dumps({'base':'7524a9633eecea6a11d73b763451030e07ea7af4','files':rows,'performanceAcceptance':False},indent=2)+'\n')
s=(base/'native-summary-selected-ascii-quality.ps1').read_text()
s=s.replace("$taskEvidence='../../docs/implementation-evidence/native-summary-selected-ascii-quality.json'","$taskEvidence=Join-Path $PSScriptRoot 'terminal.json'")
s=s.replace("$taskLog='../../docs/implementation-evidence/native-summary-selected-ascii-quality-cli.txt'","$taskLog=Join-Path $PSScriptRoot 'full-cli.txt'")
s=s.replace("source='0554aaa plus selected unescaped ASCII same-chunk strings only; fresh full qualification'","source='7524a963 plus distinct 4KiB unselected-value method; qualification source-manifest.json';processStartUtc=(Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o')")
s=s.replace("'tests/native-list-concurrency.test.ts'","'tests/native-ascii-span.test.ts','tests/native-list-concurrency.test.ts'")
s=s.replace('foreach($taskPhase in $taskPhases){','foreach($taskPhase in $taskPhases){\n  $taskRecord.currentPhase=$taskPhase.command;$taskRecord.phaseStartedAt=(Get-Date).ToUniversalTime().ToString(\'o\');$taskRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEvidence -Encoding utf8')
(out/'quality.ps1').write_text(s,encoding='utf-8')
print(json.dumps({'directory':str(out),'sourceFiles':len(rows)}))
