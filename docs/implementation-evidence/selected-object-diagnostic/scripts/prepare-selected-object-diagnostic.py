from pathlib import Path
import json,hashlib
b=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
out=b/'selected-object-diagnostic-v1';out.mkdir(exist_ok=False)
paths=['src/lib/secret-summary-json.ts','src/lib/secret-ascii-span.ts','src/lib/cluster-secrets.ts']
manifest=[]
for p in paths:
 raw=(repo/'k8s-rewrite/front-end'/p).read_bytes();(out/Path(p).name).write_bytes(raw);manifest.append({'path':p,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
(out/'inputs.json').write_text(json.dumps({'commit':'3d4d9677c816e9e3959035e5c94fb5df8050c417','productionCandidate':'4668ceb40c3120c7e4053d94edff31f57b7e1f7f','sources':manifest},indent=2)+'\n')
(out/'launch.ps1').write_bytes((b/'parser-native-span-7e30-20261011-v2/launch.ps1').read_bytes())
print(out)
