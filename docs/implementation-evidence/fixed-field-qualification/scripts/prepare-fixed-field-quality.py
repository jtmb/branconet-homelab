from pathlib import Path
import json,hashlib
b=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
out=b/'fixed-field-quality-v1';out.mkdir(exist_ok=False)
previous=json.loads((b/'native-distinct-span-quality-v1/source-manifest.json').read_bytes())
rows=previous['files']; paths=[row['path'] for row in rows]
new='k8s-rewrite/front-end/tests/native-summary-fields.test.ts'
assert new not in paths;paths.append(new)
frozen=[]
for rel in sorted(paths):
 raw=(repo/rel).read_bytes();target=out/'working-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 frozen.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
(out/'source-manifest.json').write_bytes((json.dumps({'base':'08304d8d8b695f827af347ebcc9b294e4d93fed8','stage':'fixed schema field duplicate bits','files':frozen},indent=2)+'\n').encode())
quality=(b/'native-distinct-span-quality-v1/quality.ps1').read_bytes().decode()
quality=quality.replace("7524a963 plus distinct 4KiB unselected-value method; qualification source-manifest.json","08304d8 plus fixed-known-field scalar duplicate guards; qualification source-manifest.json")
quality=quality.replace("'tests/native-summary-json.test.ts'","'tests/native-summary-json.test.ts','tests/native-summary-fields.test.ts'")
(out/'quality.ps1').write_bytes(quality.encode())
print(json.dumps({'path':str(out),'frozenFiles':len(frozen),'sourceSHA256':hashlib.sha256((repo/'k8s-rewrite/front-end/src/lib/secret-summary-json.ts').read_bytes()).hexdigest()}))
