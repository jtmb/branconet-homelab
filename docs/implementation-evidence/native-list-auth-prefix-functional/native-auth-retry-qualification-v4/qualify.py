from pathlib import Path
import datetime,hashlib,json,os,subprocess,time
folder=Path(__file__).resolve().parent
repo=Path(r"C:\Users\james\.codex\worktrees\bortus-native-evidence\kubernetes migration")
cwd=repo/"k8s-rewrite/front-end"
node=Path(r"C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe")
hashes=json.loads((folder/"source-manifest.json").read_text(encoding="utf-8"))
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
state={"owner":folder.name,"scope":"Fresh-account consolidation and bounded rejected-prefix hint functional qualification; no performance acceptance","launcher_pid":os.getpid(),"started_utc":now(),"source_parent":"6ebcd116601253c3bff1e021253fbc10b6540ca8","source_working_sha256":hashes,"node_version":subprocess.check_output([str(node),"--version"],text=True).strip(),"checks":[],"terminal":False}
write=lambda name,obj:(folder/name).write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8",newline="\n")
write("handle.json",state)
checks=[("pre-types",["node_modules/typescript/bin/tsc","--noEmit","--incremental","false"]),("focused-auth",["node_modules/tsx/dist/cli.mjs","--test","tests/native-auth-snapshot.test.ts"]),("focused-prefix",["node_modules/tsx/dist/cli.mjs","--test","tests/native-list-prefix.test.ts"]),("native-window",["node_modules/tsx/dist/cli.mjs","--test","tests/native-list-window.test.ts"]),("full-unit",["node_modules/tsx/dist/cli.mjs","--test"]+[str(p.relative_to(cwd)).replace("\\","/") for p in sorted((cwd/"tests").glob("*.test.ts"))]),("lint",["node_modules/eslint/bin/eslint.js",".","--max-warnings=0"]),("final-types",["node_modules/typescript/bin/tsc","--noEmit","--incremental","false"])]
exitcode=1
try:
 assert state["node_version"]=="v22.23.3"
 for name,args in checks:
  assert hashes=={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in hashes},"Source changed during qualification"
  started=time.perf_counter();entry={"name":name,"started_utc":now(),"command":[str(node)]+args}
  with (folder/(name+".stdout")).open("wb") as out,(folder/(name+".stderr")).open("wb") as err:
   proc=subprocess.Popen([str(node)]+args,cwd=cwd,stdout=out,stderr=err);entry["pid"]=proc.pid;state["active"]=entry;write("progress.json",state);code=proc.wait()
  entry.update(exit_code=code,wall_seconds=time.perf_counter()-started,finished_utc=now());state["checks"].append(entry);state.pop("active",None);write("progress.json",state)
  if code:exitcode=code;break
 else:exitcode=0
finally:
 state.update(terminal=True,actual_launcher_exit_code=exitcode,finished_utc=now());state.pop("active",None);write("terminal.json",state)
raise SystemExit(exitcode)
