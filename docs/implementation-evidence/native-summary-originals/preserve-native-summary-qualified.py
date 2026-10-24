import hashlib,json,pathlib,shutil,datetime
repo=pathlib.Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
base=pathlib.Path(__file__).parent
out=base/'native-summary-qualified-v3'
out.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
v2=json.loads((base/'native-summary-prequalification-v2-source.json').read_text())
v3=json.loads((base/'native-summary-prequalification-v3-source.json').read_text())
old={f['path']:f['sha256'] for f in v2['files']}
changed=[f['path'] for f in v3['files'] if old.get(f['path'])!=f['sha256']]
assert changed==['k8s-rewrite/front-end/tests/native-list-concurrency.test.ts'],changed
for f in v3['files']:
 p=repo/f['path']; b=p.read_bytes(); assert sha(b)==f['sha256'] and len(b)==f['bytes'],f['path']
 dst=out/'working-source'/f['path'];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
build=json.loads((base/'native-summary-reused-build-output.json').read_text())
for f in build['files']:
 b=(repo/'k8s-rewrite/front-end'/f['path']).read_bytes();assert sha(b)==f['sha256'] and len(b)==f['bytes'],f['path']
record=json.loads((repo/'docs/implementation-evidence/native-summary-quality-v3.json').read_text())
assert record['terminal'] and record['exitCode']==0 and all(c['exitCode']==0 for c in record['checks'])
v2record=json.loads((repo/'docs/implementation-evidence/native-summary-quality-v2.json').read_text())
assert next(c for c in v2record['checks'] if c['command']=='npm run build')['exitCode']==0
artifacts=[]
for p in sorted(base.glob('native-summary-*')):
 if p.is_file() and p.name!=pathlib.Path(__file__).name:
  dst=out/'originals'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(p,dst);assert sha(dst.read_bytes())==sha(p.read_bytes());artifacts.append({'path':str(p),'copy':str(dst),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
for p in sorted((repo/'docs/implementation-evidence').glob('native-summary-*')):
 if p.is_file():
  dst=out/'originals'/('repo-'+p.name);shutil.copyfile(p,dst);assert sha(dst.read_bytes())==sha(p.read_bytes());artifacts.append({'path':str(p),'copy':str(dst),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
receipt={'base':'55f46b19888269d7c52d3551a19b2861a835faf0','verifiedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'workingSourceFiles':len(v3['files']),'workingSourceManifest':v3,'reusedCompiledOutputFiles':len(build['files']),'reusedCompiledOutputManifest':build,'onlyV2ToV3Change':changed,'qualification':record,'originalSuccessfulBuild':v2record,'artifacts':artifacts,'counts':{'focused':48,'units':205,'httpSuites':4,'skipped':0},'scope':'Windows Node22.23.3 functional qualification only; unchanged paired performance/Linux functional/image/live/AT remain open. V2 production build reused with exact source/config/runtime/lock equivalence and687 compiled output hashes unchanged. Early focusedv2 log has no complete pre-run freeze and is not exact initial-source qualification.'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
(repo/'docs/implementation-evidence/native-summary-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'output':str(out),'workingSourceFiles':len(v3['files']),'compiledOutputFiles':len(build['files']),'originals':len(artifacts),'receiptSHA':sha((out/'receipt.json').read_bytes())}))
