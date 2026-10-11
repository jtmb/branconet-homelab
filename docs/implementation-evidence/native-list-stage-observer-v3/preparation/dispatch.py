import json,os,pathlib,re,subprocess,sys
arguments=sys.argv[1:];owner=arguments[arguments.index('--owner')+1];assert re.fullmatch('native-stage-[a-z0-9-]{8,80}',owner)
os.umask(0o077);work=pathlib.Path.home()/'.cache/bortus-controlled-perf'/owner;work.mkdir(mode=0o700,exist_ok=False)
out=(work/'supervisor.stdout').open('xb');err=(work/'supervisor.stderr').open('xb');child=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).with_name('supervise.py')),*arguments],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
handle={'owner':owner,'supervisor_pid':child.pid,'supervisor_start_ticks':pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19],'protected_work':str(work)};(work/'handle.json').write_text(json.dumps(handle,indent=2)+'\n');out.close();err.close();print(json.dumps(handle),flush=True)
