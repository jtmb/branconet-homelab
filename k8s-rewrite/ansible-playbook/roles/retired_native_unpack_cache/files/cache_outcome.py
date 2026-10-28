"""Observe actual cache path outcomes and rehash original blobs after any exit.

This reader cannot remove/retry a snapshot. Preserve failed native journals and
distinguish direct acknowledgements from paths observed absent afterwards.
"""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
NODES = {'masternode': '192.168.0.4', 'workernode2': '192.168.0.5'}
REMOTE = r'''
import base64,contextlib,hashlib,io,json,os,pathlib,stat,sys
r=json.load(sys.stdin);original=r['qualification'];old=original['profile'];code=base64.b64decode(r['physicalSource'],validate=True)
assert hashlib.sha256(code).hexdigest()==r['physicalSHA256']
scope={};stdin=sys.stdin
try:
 sys.stdin=io.StringIO(json.dumps({'inventorySource':r['inventorySource'],'inventorySHA256':r['inventorySHA256']}))
 with contextlib.redirect_stdout(io.StringIO()):exec(compile(code,'<read-only-current-cache-projection>','exec'),scope)
finally:sys.stdin=stdin
now=scope['result'];assert not now['orphanDirectories']
assert now['nativeInventory']['imageRecordsSHA256']==old['nativeInventory']['imageRecordsSHA256'],'original_image_records_changed'
root=pathlib.Path('/var/lib/containerd-k8s/io.containerd.snapshotter.v1.overlayfs/snapshots');rows=[]
for row in old['mappedCandidates']:
 p=pathlib.Path(row['path']);assert p.parent==root and p.name.isdigit() and not p.is_symlink()
 present=p.exists();item={k:row[k] for k in ('key','path','allocatedBytes')};item['present']=present
 if present:
  s=p.stat();assert stat.S_ISDIR(s.st_mode) and p.resolve()==p
  item['originalDirectoryIdentityPreserved']=all(getattr(s,'st_'+k)==row['directoryIdentity'][k] for k in ('dev','ino','mode','uid','gid'))
 rows.append(item)
for blob in original['verifiedOriginalBlobs']:
 p=pathlib.Path(blob['path']);assert p.parent==pathlib.Path('/var/lib/containerd-k8s/io.containerd.content.v1.content/blobs/sha256') and p.name==blob['digest'][7:] and p.resolve()==p
 before=p.lstat();assert stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==0
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 assert h.hexdigest()==blob['digest'][7:] and before==p.lstat(),'original_blob_changed'
old_other=set(old['allBackendIDs'])-{x['id'] for x in old['mappedCandidates']}
print(json.dumps({'node':now['nativeInventory']['node'],'readOnly':True,'rows':rows,
 'observedAbsentAllocatedBytes':sum(x['allocatedBytes'] for x in rows if not x['present']),
 'remainingPaths':[x for x in rows if x['present']],
 'originalBlobsFullyRehashed':len(original['verifiedOriginalBlobs']),
 'originalImageRecordsUnchanged':True,'missingOriginalNonTargetBackendIDs':sorted(old_other-set(now['allBackendIDs'])),
 'currentBackendIDs':now['allBackendIDs'],'currentPotentialCaches':now['mappedCandidates'],
 'orphanDirectories':now['orphanDirectories'],'rootAvailableBytes':now['nativeInventory']['rootAvailableBytes'],
 'snapshotRemovalSubmitted':False,'failedTargetsRetried':False}))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--node', choices=NODES, required=True)
    p.add_argument('--qualification', type=Path, required=True)
    a = p.parse_args()
    assert os.geteuid() == 1000 and F.is_mount() and a.qualification.resolve() == a.qualification
    assert a.qualification.is_relative_to(F) and a.qualification.is_file()
    h = a.qualification.parent
    q = json.loads(a.qualification.read_bytes())
    assert q['status'] == 'exclusive_cache_payload_and_reference_qualification_passed'
    assert q['profile']['nativeInventory']['node'] == a.node
    here = Path(__file__).resolve().parent
    inv = runpy.run_path(str(here / 'inventory.py'))['REMOTE'].replace('workernode2', a.node)
    target = next(x for x in ast.parse(inv).body if isinstance(x, ast.Assign)
        and any(isinstance(k, ast.Name) and k.id == 'targets' for k in x.targets))
    inv = inv.replace(ast.get_source_segment(inv, target), 'targets=set(' + repr(tuple(sorted(x['rootDigest'] for x in q['profile']['nativeInventory']['retiredImages']))) + ')')
    physical = runpy.run_path(str(here / 'physical.py'))['REMOTE'].encode()
    packet = {'qualification': q, 'inventorySource': base64.b64encode(inv.encode()).decode(),
        'inventorySHA256': hashlib.sha256(inv.encode()).hexdigest(),
        'physicalSource': base64.b64encode(physical).decode(), 'physicalSHA256': hashlib.sha256(physical).hexdigest()}
    os.umask(0o077)
    ident = uuid.uuid4().hex
    lib = runpy.run_path(str(here.parents[4] / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    try:
        child = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
            '-p', '2002', 'james@' + NODES[a.node], shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])],
            input=password + b'\n' + json.dumps(packet).encode(), capture_output=True, timeout=600)
        receipt = {'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'qualificationSHA256': hashlib.sha256(a.qualification.read_bytes()).hexdigest(), 'exitCode': child.returncode,
            'stdoutSHA256': hashlib.sha256(child.stdout).hexdigest(), 'stderr': child.stderr.decode()[-2000:] if child.returncode else ''}
        if child.returncode == 0:
            assert len(child.stdout) <= 4 * 1024**2
            receipt['observation'] = json.loads(child.stdout)
        with (h / ('outcome-' + ident + '.json')).open('x') as out:
            json.dump(receipt, out, indent=2)
        assert child.returncode == 0, ('post_observation_failed_no_mutation', child.returncode)
        value = receipt['observation']
        print(json.dumps({k: v for k, v in value.items() if k not in ('rows', 'currentBackendIDs', 'currentPotentialCaches')}))
    finally:
        password = None


if __name__ == '__main__':
    main()
