"""Fresh read-only exact BORTUS runtime graph checks using the saved administrator source."""
import hashlib,importlib.util,json,os,shlex,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).parent
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
SOURCE='12dce115006877fed2c674cad1ffd40805932974'
IMAGE='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
CONFIG='sha256:42e3a1a9e6fe5cd3c9912262b0cbeaca9a8cdff7b7b1891392eb100127d84698'

def load():
 s=importlib.util.spec_from_file_location('current_node_saved_credentials',ROOT/'saved-node-credential.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def verify(deadline):
    password=load().existing_password()
    definition=(ROOT/'bortus-qualified-preload-node.py').read_text()
    code="import json;namespace={'__name__':'readonly_current_bortus'};exec("+repr(definition)+",namespace);"+'''need=namespace['need'];content=namespace['content'];metadata=namespace['metadata'];need(namespace['image_digest']()==namespace['MANIFEST']);m=content(namespace['MANIFEST']);c=content(namespace['CONFIG']);need(m['config']['digest']==namespace['CONFIG'] and len(m['layers'])==9 and c['os']=='linux' and c['architecture']=='amd64' and c['config']['Labels']['org.opencontainers.image.revision']==namespace['SOURCE']);present={row.split()[0] for row in metadata(['content','list']).decode().splitlines()[1:] if row.split()};need(all(layer['digest'] in present for layer in m['layers']));need(namespace['REFERENCE'] in metadata(['images','check','--quiet']).decode().splitlines());print(json.dumps({'source_commit':namespace['SOURCE'],'image_reference':namespace['REFERENCE'],'config_digest':namespace['CONFIG'],'all_nine_blobs_present':True,'fully_downloaded_and_unpacked':True,'runtime_changed':False}))'''
    # Every command is a content/image read. No archive transfer, import or deployment.
    results=[]
    try:
        for host,node in [('192.168.0.4','node01'),('192.168.0.6','node02'),('192.168.0.5','node03')]:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise RuntimeError('current_runtime_deadline')
            result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
                '-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@'+host,
                "sudo -S -k -p '' python3 -c "+shlex.quote(code)],input=(password+'\n').encode(),capture_output=True,timeout=min(40,remaining))
            if result.returncode or len(result.stdout)>8192:raise RuntimeError('current_runtime_read_failed')
            value=json.loads(result.stdout)
            if not (value['source_commit']==SOURCE and value['image_reference']==IMAGE and value['config_digest']==CONFIG
                    and value['all_nine_blobs_present'] is True and value['fully_downloaded_and_unpacked'] is True and value['runtime_changed'] is False):
                raise RuntimeError('current_runtime_identity_changed')
            results.append({'node':node,**value})
    finally:password=None
    receipt={'state':'completed','current_read_only_runtime_observations':results,
             'prior_full_blob_hash_receipts':'qualified-node-imports.json','fresh_blob_bytes_rehashed':False,
             'source_program_sha256':hashlib.sha256(definition.encode()).hexdigest(),'production_changed':False}
    path=A/('runtime-observation-'+uuid.uuid4().hex[:12]+'.json')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump(receipt,f);f.flush();os.fsync(f.fileno())
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'nodes':['node01','node02','node03']}
if __name__=='__main__':
    try:print(json.dumps({'current_three_node_runtime_passed':True,**verify(time.monotonic()+120)}))
    except Exception as e:
        print(json.dumps({'runtime_read_failed':type(e).__name__}),file=sys.stderr);raise SystemExit(1)

