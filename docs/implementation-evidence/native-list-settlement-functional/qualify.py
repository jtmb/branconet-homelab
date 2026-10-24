from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
folder=Path(__file__).resolve().parent
repo=Path(r"C:\Users\james\.codex\worktrees\bortus-native-evidence\kubernetes migration")
cwd=repo/"k8s-rewrite/front-end"
node=Path(r"C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe")
paths=["k8s-rewrite/front-end/src/lib/secret-client.ts","k8s-rewrite/front-end/tests/native-list-window.test.ts","docs/API-USAGE.md","docs/BORTUS-DEPLOYMENT.md","docs/BORTUS-NATIVE-LIST-PERFORMANCE.md","docs/SECRETS-ENGINE.md"]
hashes={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths}
assert hashes[paths[0]]=="57a3457e104b86039957229d7398b4a0d7fbd879169efc5932d1155d3aacc3a4"
assert hashes[paths[1]]=="bb3186ba972402c1885c6f7a8a319eed01dff72d2182a01e3c86c519c0752966"
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
state={"scope":"Native response settlement source qualification, no performance acceptance","owner":"native-settlement-qualification-final","launcher_pid":os.getpid(),"started_utc":now(),"source_parent":"f9a83fb1c4fb25b50ac199d4fe5de3ca2f0374b2","source_working_sha256":hashes,"node_version":subprocess.check_output([str(node),"--version"],text=True).strip(),"checks":[],"terminal":False}
write=lambda name,obj:(folder/name).write_text(json.dumps(obj,indent=2)+"\n",newline="\n")
write("handle.json",state)
suites=[("focused-settlement",["node_modules/tsx/dist/cli.mjs","--test","--test-name-pattern=settled responses discard late","tests/native-list-window.test.ts"]),("native-window",["node_modules/tsx/dist/cli.mjs","--test","tests/native-list-window.test.ts"]),("full-unit",["node_modules/tsx/dist/cli.mjs","--test"]+[str(p.relative_to(cwd)).replace("\\","/") for p in sorted((cwd/"tests").glob("*.test.ts"))]),("lint",["node_modules/eslint/bin/eslint.js",".","--max-warnings=0"]),("final-types",["node_modules/typescript/bin/tsc","--noEmit","--incremental","false"])]
exitcode=1
try:
 for name,args in suites:
  assert hashes=={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths},"Source changed during qualification"
  started=time.perf_counter();entry={"name":name,"started_utc":now(),"command":[str(node)]+args}
  with (folder/(name+".stdout")).open("wb") as out,(folder/(name+".stderr")).open("wb") as err:
   proc=subprocess.Popen([str(node)]+args,cwd=cwd,stdout=out,stderr=err);entry["pid"]=proc.pid;state["active"]=entry;write("progress.json",state);code=proc.wait()
  entry.update(exit_code=code,wall_seconds=time.perf_counter()-started,finished_utc=now());state["checks"].append(entry);state.pop("active",None);write("progress.json",state)
  if code:exitcode=code;break
 else:exitcode=0
finally:
 state.update(terminal=True,actual_launcher_exit_code=exitcode,finished_utc=now());state.pop("active",None);write("terminal.json",state)
raise SystemExit(exitcode)
