import datetime,json,os,pathlib,subprocess,sys
arguments=sys.argv[1:];owner=arguments[arguments.index('--owner')+1];work=pathlib.Path.home()/'.cache/bortus-controlled-perf'/owner
child=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).with_name('launch.py')),*arguments],stdin=subprocess.DEVNULL)
(work/'launcher-handle.json').write_text(json.dumps({'owner':owner,'supervisor_pid':os.getpid(),'launcher_pid':child.pid,'launcher_start_ticks':pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19]},indent=2)+'\n')
code=child.wait();temporary=work/'terminal.json.next';temporary.write_text(json.dumps({'owner':owner,'actual_launcher_exit_code':code,'terminal':True,'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n');temporary.replace(work/'terminal.json');raise SystemExit(code)
