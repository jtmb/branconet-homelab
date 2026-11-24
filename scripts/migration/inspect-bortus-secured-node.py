"""Read-only reconciliation of the uncertain exact secured-image import."""
import argparse,importlib.util,json,shlex,subprocess
from pathlib import Path
S=Path(__file__).parent;O=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--repair-alias',action='store_true');parser.add_argument('--host',choices=['192.168.0.4','192.168.0.5'],default='192.168.0.4');args=parser.parse_args()
 s=importlib.util.spec_from_file_location('saved_inspection',S/'saved-node-credential.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);password=m.existing_password()
 definition=(S/'bortus-secured-preload-node.py').read_text();code="import json,os,traceback; n={'__name__':'readonly_inspection'};exec("+repr(definition)+",n);"+'''
v=os.statvfs('/var/lib/containerd-k8s');result={'free_bytes':v.f_bavail*v.f_frsize,'disk_bytes':v.f_blocks*v.f_frsize,'mem_available_kib':next(int(x.split()[1])for x in open('/proc/meminfo')if x.startswith('MemAvailable:'))}
result['image_digest']=n['image_digest']();result['parent_unpacked']='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'in n['metadata'](['images','check','--quiet']).decode().splitlines()
result['bortus_image_rows']=[x.split()[:3]for x in n['metadata'](['images','list']).decode().splitlines()[1:]if'bortus'in x]
if result['image_digest']:
 try:n['verify_runtime']();result['all_layer_hashes_and_unpack_verified']=True
 except Exception as e:result['verification_error']={'type':type(e).__name__,'lines':[f.lineno for f in traceback.extract_tb(e.__traceback__)]}
print(json.dumps(result))
'''
 if args.repair_alias:
  code+="\nn['ensure_manifest_reference']();n['verify_runtime']();print(json.dumps({'manifest_alias_and_all_layers_verified':True}))\n"
 try:
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-o','ConnectTimeout=10','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@'+args.host,'sudo -S -k -p '+shlex.quote('')+' python3 -c '+shlex.quote(code)],input=(password+'\n').encode(),capture_output=True,timeout=180)
  if p.returncode:raise RuntimeError('secured_image_node_read_failed:'+str(p.returncode)+':'+p.stderr.decode(errors='replace')[-1800:])
  replies=[json.loads(x)for x in p.stdout.decode().splitlines()];d=replies[0];path=O/('preload-node01-alias-reconciliation.json'if args.repair_alias else'preload-inspection-node01-after-import.json')
  if args.host=='192.168.0.5':path=O/'preload-inspection-node03-capacity.json'
  if args.repair_alias:
   if len(replies)!=2 or replies[1].get('manifest_alias_and_all_layers_verified')is not True:raise RuntimeError('alias_reconciliation_incomplete')
   d['manifest_alias_and_all_layers_verified']=True
  with path.open('x')as f:json.dump(d,f)
  print(json.dumps(d))
 finally:password=None
if __name__=='__main__':main()
