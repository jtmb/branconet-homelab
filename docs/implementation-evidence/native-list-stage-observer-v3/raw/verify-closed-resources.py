import pathlib,subprocess,json
live=[p for p in [1796890,1796891] if pathlib.Path('/proc/'+str(p)+'/stat').exists()]
run=subprocess.run(['docker','ps','--filter','name=native-stage-15786222-observer-44e1f8d2-v3','--format','{{.Names}}'],capture_output=True,text=True)
print(json.dumps({'live_pids':live,'containers':run.stdout.splitlines(),'docker_exit':run.returncode,'stderr':run.stderr}))
raise SystemExit(1 if live or run.returncode or run.stdout.strip() else 0)
