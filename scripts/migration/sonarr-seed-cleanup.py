#!/usr/bin/env python3
"""Stop only the verified owned loopback fixture process and remove its public seed files."""
import json,pathlib,subprocess
r=pathlib.Path.home()/'.local/share/branconet-migration';s=json.loads((r/'recovery/sonarr-fixture-state.json').read_text());k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
code=r'''import hashlib,json,os,pathlib,shutil,signal
state=__STATE__;root=pathlib.Path(state['seed_container_directory'])
if root.parent!=pathlib.Path('/tmp') or root.name!=state['token'] or root.resolve()!=root or root.is_symlink():raise RuntimeError('Seed directory guard failed')
if hashlib.sha256((root/'fixture.zip').read_bytes()).hexdigest()!=state['archive_sha256']:raise RuntimeError('Seed source changed')
pid=int((root/'seed.pid').read_text());proc=pathlib.Path('/proc')/str(pid)
if pid<=1:raise RuntimeError('Unsafe PID')
stopped=False
if proc.exists():
 if (proc/'cmdline').read_bytes().split(b'\0')[:2]!=[b'python3',b'-c']:raise RuntimeError('Seed process differs')
 if state['token'].encode() not in (proc/'cmdline').read_bytes():raise RuntimeError('Seed code owner differs')
 inodes=set()
 for line in pathlib.Path('/proc/net/tcp').read_text().splitlines()[1:]:
  parts=line.split()
  if parts[1]=='0100007F:'+format(state['seed_port'],'04X') and parts[3]=='0A':inodes.add(parts[9])
 fdtargets=[]
 for fd in (proc/'fd').iterdir():
  try:fdtargets.append(os.readlink(fd))
  except FileNotFoundError:pass
 if not any('socket:['+inode+']' in fdtargets for inode in inodes):raise RuntimeError('Process does not own fixture listener')
 os.kill(pid,signal.SIGTERM);stopped=True
if any(p.is_symlink() for p in root.rglob('*')):raise RuntimeError('Seed directory contains symlink')
shutil.rmtree(root)
print(json.dumps({'owned_seed_process_stopped':stopped,'owned_seed_directory_removed':not root.exists(),'pid':pid,'listener_scope':'127.0.0.1:'+str(state['seed_port'])}))
'''.replace('__STATE__',repr(s))
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('Owned seed cleanup guard failed; private diagnostics withheld')
proof=pathlib.Path('/mnt/c/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration/evidence/sonarr-archive-import-proof.json');report=json.loads(proof.read_text());report['seed_cleanup']=json.loads(result.stdout);proof.write_text(json.dumps(report,indent=2)+'\n');print(result.stdout.decode())
