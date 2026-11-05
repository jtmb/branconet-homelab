import datetime,hashlib,json,os,pathlib,stat,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent
OWNER='paired-dafb41c-20261011-074727-252a'
WORK=pathlib.Path.home()/'.cache/bortus-controlled-perf'/OWNER
FROZEN=HERE/'benchmarks/bortus-controlled-perf'
def write(name,value):
 temp=WORK/(name+'.next');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(WORK/name)
manifest=json.loads((FROZEN/'manifest.json').read_bytes())
for row in manifest['rawGitProof']:assert hashlib.sha256((FROZEN/row['path']).read_bytes()).hexdigest()==row['sha256']
for row in manifest['rawGitProof']:assert stat.S_IMODE((FROZEN/row['path']).stat().st_mode)==int(row['mode'][-3:],8)
command=[sys.executable,str(FROZEN/'run.py'),'--repository','/mnt/c/Users/james/.codex/worktrees/bortus-app-recovered/kubernetes migration','--exporter','/mnt/c/Users/james/.codex/worktrees/8cdf/branconet-charts/scripts/export_bortus_source.py','--candidate','dafb41c3c226ef03913df2ab6c113a9820a709c6','--baseline','51e8cd66379c1f40a95ea02f4da7c8aed848f2a4','--image','sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678','--runs','3','--report',str(WORK/'raw-report.json')]
child=subprocess.Popen(command,stdin=subprocess.DEVNULL)
write('runner-handle.json',{'owner':OWNER,'supervisor_pid':os.getpid(),'runner_pid':child.pid,'runner_start_ticks':pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19],'command':command,'frozen_manifest':manifest})
code=child.wait()
terminal={'owner':OWNER,'actual_runner_exit_code':code,'terminal':True,'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runner_pid':child.pid}
lines=(WORK/'supervisor.stdout').read_text().splitlines()
for line in lines:
 try: item=json.loads(line)
 except ValueError:continue
 if 'protected_work' in item:terminal['protected_work']=item['protected_work']
if 'protected_work' in terminal:
 suffix=pathlib.Path(terminal['protected_work']).name
 names=subprocess.run(['docker','ps','--format','{{.Names}}'],check=True,stdout=subprocess.PIPE).stdout.decode().splitlines()
 terminal['owned_live_containers']=[name for name in names if name.startswith('bortus-perf-') and name.endswith(suffix)]
write('terminal.json',terminal)
raise SystemExit(code)
