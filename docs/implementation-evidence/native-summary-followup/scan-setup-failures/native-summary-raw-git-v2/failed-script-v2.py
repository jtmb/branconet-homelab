import pathlib,subprocess,json,hashlib,importlib.util
repo=pathlib.Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');base=pathlib.Path(__file__).parent;commit='dafb41c3c226ef03913df2ab6c113a9820a709c6'
out=base/'native-summary-raw-git-v2';out.mkdir(exist_ok=False)
tool=pathlib.Path(r'C:\Users\james\AppData\Local\Temp\bortus-native-window-tools-70320914\bin\gitleaks.exe')
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(tool.read_bytes())=='17157e2ee8b76fc8b1d8bee607a250e34b8a8023c8bc81822d4b5ee4d78fcb7c'
exporter=pathlib.Path(r'C:\Users\james\.codex\worktrees\8cdf\branconet-charts\scripts\export_bortus_source.py')
assert sha(exporter.read_bytes())=='5bcdb86fd8a795d72f195dbf5163a46ad09de79b54d0ead4dbba0eadb0743470'
spec=importlib.util.spec_from_file_location('original_exporter',exporter);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
git=lambda *args:subprocess.check_output(['git',*args],cwd=repo)
freeze=json.loads((base/'native-summary-prequalification-v3-source.json').read_bytes());bindings=[]
for f in freeze['files']:
 data=git('show',commit+':'+f['path']);mode,kind,blob=git('ls-tree',commit,'--',f['path']).split(b'\t')[0].decode().split();work=(repo/f['path']).read_bytes()
 assert sha(work)==f['sha256']
 relation='exact' if data==work else 'literal LF-to-CRLF' if data.replace(b'\n',b'\r\n')==work else None
 assert relation,f['path']
 bindings.append(dict(path=f['path'],mode=mode,blob=blob,rawSHA256=sha(data),workingSHA256=f['sha256'],relation=relation))
sources=[]
prefix='k8s-rewrite/front-end/'
for row in git('ls-tree','-r','-z',commit,'--',prefix).split(b'\0'):
 if not row:continue
 meta,name=row.split(b'\t',1);mode,kind,blob=meta.decode().split();path=name.decode();relative=path[len(prefix):]
 if module.excluded(pathlib.PurePosixPath(relative),False):continue
 data=git('cat-file','blob',blob);assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
 dest=out/'source'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 sources.append(dict(path=path,mode=mode,blob=blob,bytes=len(data),sha256=sha(data)))
r=subprocess.run([str(tool),'dir',str(out/'source'),'--redact=100','--no-banner','--exit-code=1','--report-format','json','--report-path',str(out/'scan.json')],capture_output=True)
(out/'scan.stdout').write_bytes(r.stdout);(out/'scan.stderr').write_bytes(r.stderr)
findings=json.loads((out/'scan.json').read_bytes())
receipt={'commit':commit,'scannerVersion':subprocess.check_output([str(tool),'version']).decode().strip(),'scannerSHA256':sha(tool.read_bytes()),'actualExitCode':r.returncode,'findings':len(findings),'rawProductionFiles':len(sources),'qualifiedWorkingFileBindings':len(bindings),'sources':sources,'bindings':bindings,'scope':'Exact production export inputs only; no tests/dependencies/runtime image/whole historical evidence scan claim. Existing two historical unmatched checksum provenance findings remain open.'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'out':str(out),'exitCode':r.returncode,'findings':len(findings),'productionFiles':len(sources),'bindings':len(bindings),'receiptSHA':sha((out/'receipt.json').read_bytes())}))
raise SystemExit(r.returncode)
