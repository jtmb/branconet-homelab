import pathlib,hashlib,json,subprocess,sys
base=pathlib.Path(__file__).parent
original=base/'dispatch-functional-4668ceb.py'
text=original.read_text()
old='5bcdb86fd8a795d72f195dbf5163a46ad09de79b54d0eadb0743470'
new='5bcdb86fd8a795d72f195dbf5163a46ad09de79b54d0ead4dbba0eadb0743470'
assert text.count(old)==1
actual=pathlib.Path(r'C:\Users\james\.codex\worktrees\8cdf\branconet-charts\scripts\export_bortus_source.py').read_bytes()
raw=subprocess.check_output(['git','cat-file','blob','a82a6cb9e244b0ec05489bc7251f3e29411c64dc:scripts/export_bortus_source.py'],cwd=r'C:\Users\james\.codex\worktrees\8cdf\branconet-charts')
assert actual==raw and hashlib.sha256(actual).hexdigest()==new
target=base/'dispatch-functional-4668ceb-v2.py';assert not target.exists();target.write_text(text.replace(old,new))
(base/'functional-4668ceb-attempt1-launch-failure.json').write_text(json.dumps({'phase':'pre-Linux exporter assertion','toolChunk':'15c251','actualExit':1,'originalScriptSha256':hashlib.sha256(original.read_bytes()).hexdigest(),'reason':'Mistyped pinned digest; actual exporter raw Git and working bytes verified equal to frozen a82a6cb9 blob.','correctedExporterSha256':new,'noLinuxOrContainerLaunch':True},indent=2)+'\n')
raise SystemExit(subprocess.call([sys.executable,str(target)]))
