import pathlib,hashlib,json,subprocess,sys
base=pathlib.Path(__file__).parent
original=base/'dispatch-functional-4668ceb-v2.py';text=original.read_text()
old="archive=protected/'source.tar.gz'; exported=module.export(repo,commit,archive,False)"
replacement='''archive=protected/'source.tar.gz'
linux_export = r"""
import base64,hashlib,importlib.util,json,pathlib,sys
owner=sys.argv[1];commit=sys.argv[2]
file=pathlib.Path('/mnt/c/Users/james/.codex/worktrees/8cdf/branconet-charts/scripts/export_bortus_source.py')
assert hashlib.sha256(file.read_bytes()).hexdigest()=='5bcdb86fd8a795d72f195dbf5163a46ad09de79b54d0ead4dbba0eadb0743470'
spec=importlib.util.spec_from_file_location('exact',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=pathlib.Path.home()/'.cache/bortus-controlled-perf'/(owner+'-raw-source.tar.gz')
info=module.export(pathlib.Path('/mnt/c/Users/james/.codex/worktrees/bortus-app-recovered/kubernetes migration'),commit,out,False)
print(json.dumps({'info':info,'archive':base64.b64encode(out.read_bytes()).decode()}))
"""
e=subprocess.run(['wsl','-d','Ubuntu','--exec','python3','-B','-c',linux_export,owner,commit],capture_output=True)
(protected/'source-export.stderr').write_bytes(e.stderr);assert e.returncode==0, 'Exact Linux exporter failed; original stderr retained'
result=json.loads(e.stdout);exported=result['info'];archive.write_bytes(__import__('base64').b64decode(result['archive']))
(protected/'source-export.json').write_text(json.dumps(exported,indent=2)+'\\n')'''
assert text.count(old)==1
target=base/'dispatch-functional-4668ceb-v3.py';assert not target.exists();target.write_text(text.replace(old,replacement))
(base/'functional-4668ceb-attempt2-launch-failure.json').write_text(json.dumps({'phase':'pre-Linux export','toolChunk':'a6968e','actualExit':1,'originalScriptSha256':hashlib.sha256(original.read_bytes()).hexdigest(),'reason':'Unchanged frozen exporter invokes its Linux Gitleaks binary; Windows host cannot execute it. Corrected v3 runs the unchanged exact exporter under WSL --exec, preserving scan and raw archive guards.','noContainerLaunch':True},indent=2)+'\n')
raise SystemExit(subprocess.call([sys.executable,str(target)]))
