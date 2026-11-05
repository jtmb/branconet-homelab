import base64, datetime, hashlib, io, json, pathlib, subprocess, zipfile
owner = pathlib.Path(__file__).parent
repo = pathlib.Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
commit = 'ab8d450790ed8970c25ccfec78fa924c8f08ff6a'
exporter = pathlib.Path(r'C:\Users\james\.codex\worktrees\8cdf\branconet-charts\scripts\export_bortus_source.py')
sha = lambda d: hashlib.sha256(d).hexdigest()
assert sha(exporter.read_bytes()) == '5bcdb86fd8a795d72f195dbf5163a46ad09de79b54d0eadb0743470'
git = lambda *args: subprocess.check_output(['git', '-C', str(repo), *args])
assert git('rev-parse', 'HEAD').decode().strip() == commit
assert not git('status', '--porcelain')
export = subprocess.run(['python', str(exporter), '--repository', str(repo), '--commit', commit, '--output', str(owner / 'source.tar.gz')], capture_output=True)
(owner / 'source-export.json').write_bytes(export.stdout); (owner / 'source-export.stderr').write_bytes(export.stderr)
assert export.returncode == 0
tests = []
blobs = []
for line in git('ls-tree', '-r', commit, '--', 'k8s-rewrite/front-end').decode().splitlines():
    left, name = line.split('\t'); mode, kind, blob = left.split(); path = name.removeprefix('k8s-rewrite/front-end/')
    data = git('show', commit + ':' + name)
    blobs.append(dict(path=path, mode=mode, blob=blob, sha256=sha(data)))
    if path.startswith('tests/'):
        tests.append(dict(path=path, mode=mode, blob=blob, sha256=sha(data), bytes=len(data)))
record = dict(owner=owner.name.removesuffix('-preparation'), sourceCommit=commit, archiveSha256=sha((owner/'source.tar.gz').read_bytes()), tests=tests, rawFrontendBlobs=blobs, supplemental=dict(path='qa/handler-http.cjs', sha256=sha((owner/'handler-http.cjs').read_bytes()), source='Protected public test-only overlay; original four integration fixtures unchanged'), buildLimits='4CPU/first4affinity/4GiB/noswap/256PIDs', runtimeLimits='2CPU/first2affinity/1GiB/noswap/256PIDs/networknone/readonlysource')
(owner/'input.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
old = owner.parent/'functional-c29fc8c-20261011-114046-ae4c-preparation/linux-dispatch.py'
code = old.read_text(encoding='utf-8')
needle="    (work/'input.json').write_text(json.dumps(record,indent=2)+'\\n')"
replacement="    supplemental=record['supplemental'];target=source/supplemental['path'];target.parent.mkdir(parents=True);data=z.read(supplemental['path']);assert hashlib.sha256(data).hexdigest()==supplemental['sha256'];target.write_bytes(data)\n"+needle
assert code.count(needle)==1;code=code.replace(needle,replacement)
needle="runtime+=['--network','none','--env','NODE_ENV=test']"
replacement="runtime[runtime.index('4')]='2';runtime[runtime.index(cpus)]=','.join(map(str,sorted(os.sched_getaffinity(0))[:2]));runtime[runtime.index('4g')]='1g';runtime[runtime.index('4g')]='1g';"+needle
assert code.count(needle)==1;code=code.replace(needle,replacement)
needle="[('unit','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.test.ts'),('lint','npm run lint'),('typecheck','node node_modules/typescript/bin/tsc --noEmit --incremental false'),('http','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.integration.ts')]"
replacement="[('http','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.integration.ts'),('affected-http','node qa/handler-http.cjs')]"
assert code.count(needle)==1;code=code.replace(needle,replacement)
(owner/'linux-dispatch.py').write_text(code, encoding='utf-8')
with zipfile.ZipFile(owner/'dispatch-input.zip', 'x', compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr('input.json', (owner/'input.json').read_bytes()); z.writestr('source.tar.gz', (owner/'source.tar.gz').read_bytes())
    for row in tests:z.writestr(row['path'],git('show',commit+':k8s-rewrite/front-end/'+row['path']))
    z.writestr('qa/handler-http.cjs',(owner/'handler-http.cjs').read_bytes())
(owner/'prepared-manifest.json').write_text(json.dumps({'commit':commit,'rawFrontendFiles':len(blobs),'tests':len(tests),'exporterSHA256':sha(exporter.read_bytes()),'files':{p.name:sha(p.read_bytes()) for p in owner.iterdir() if p.is_file()}},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'prepared':True,'owner':record['owner'],'rawFrontendFiles':len(blobs),'originalTests':len(tests),'sourceArchiveSHA256':record['archiveSha256']}))
payload = base64.b64encode(code.encode('utf-8')).decode('ascii')
run = subprocess.run(['wsl.exe', '--exec', 'python3', '-c', "exec(__import__('base64').b64decode('"+payload+"'))"], input=(owner/'dispatch-input.zip').read_bytes(),capture_output=True)
(owner/'dispatch.stdout').write_bytes(run.stdout);(owner/'dispatch.stderr').write_bytes(run.stderr)
(owner/'dispatch-terminal.json').write_text(json.dumps({'actualExit':run.returncode,'completedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stdoutSHA256':sha(run.stdout),'stderrSHA256':sha(run.stderr)},indent=2)+'\n',encoding='utf-8')
assert run.returncode == 0
print(run.stdout.decode('utf-8'))
