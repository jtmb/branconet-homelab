import json,os,pathlib,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent
owner='paired-4668ceb-20261011-104527-6b6e'
os.umask(0o077)
work=pathlib.Path.home()/'.cache/bortus-controlled-perf'/owner
work.mkdir(mode=0o700,exist_ok=False)
out=(work/'supervisor.stdout').open('xb');err=(work/'supervisor.stderr').open('xb')
child=subprocess.Popen([sys.executable,str(HERE/'full-paired-supervisor.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
handle={'owner':owner,'supervisor_pid':child.pid,'supervisor_start_ticks':pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19],'report':str(work/'raw-report.json'),'work':str(work)}
(work/'handle.json').write_text(json.dumps(handle,indent=2)+'\n');out.close();err.close();print(json.dumps(handle),flush=True)
