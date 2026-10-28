"""Budget and stage only the unchanged official Pi-hole image on both workers.

The master provides exact retained image descriptors and native cache usage.
Nothing is pulled unless the original Longhorn floor plus margin and complete
peak budget fit. Original images/data/limits are not removed or changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/longhorn-remaining-runtime-20261028'
ROOT = 'sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113'
REMOTE = r'''
import hashlib,json,os,pathlib,socket,subprocess,sys
r=json.load(sys.stdin);ctr=pathlib.Path('/opt/containerd-k8s/bin/ctr')
assert os.geteuid()==0 and hashlib.sha256(ctr.read_bytes()).hexdigest()=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
base=[str(ctr),'--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
root='sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113'
ref='docker.io/pihole/pihole@'+root
def cmd(args,timeout=60):
 p=subprocess.run(base+args,capture_output=True,timeout=timeout)
 assert p.returncode==0 and len(p.stdout)<=4194304,('bounded_native_operation_failed',p.returncode)
 return p.stdout
def blob(d):
 raw=cmd(['content','get',d]);assert 'sha256:'+hashlib.sha256(raw).hexdigest()==d
 return json.loads(raw),len(raw)
if r['phase']=='profile':
 assert socket.gethostname()=='masternode'
 manifest,ms=blob(root)
 if 'manifests' in manifest:
  matches=[x for x in manifest['manifests'] if x.get('platform',{}).get('os')=='linux' and x.get('platform',{}).get('architecture')=='amd64']
  assert len(matches)==1
  manifest,selected_size=blob(matches[0]['digest']);ms+=selected_size
 assert 'config' in manifest and 'layers' in manifest
 config,cs=blob(manifest['config']['digest']);chain=[];prior=None
 for diff in config['rootfs']['diff_ids']:
  prior=diff if prior is None else 'sha256:'+hashlib.sha256((prior+' '+diff).encode()).hexdigest();chain.append(prior)
 assert len(chain)==len(manifest['layers']) and 0<len(chain)<128
 raw=cmd(['snapshots','usage','-b',*chain]);sizes={}
 for line in raw.decode().splitlines()[1:]:
  key,size,inodes=line.split();sizes[key]=int(size)
 assert set(sizes)==set(chain)
 compressed=ms+cs+sum(x['size'] for x in manifest['layers']);unpacked=sum(sizes.values())
 # Actual native layer allocations plus 25% filesystem variance, two complete
 # descriptor-byte copies and 64MiB metadata overhead; retain the separate
 # unchanged 512MiB Longhorn operating margin as well.
 peak=(unpacked*5+3)//4+2*compressed+64*1024**2
 print(json.dumps({'node':socket.gethostname(),'rootDigest':root,'descriptors':manifest,
  'configSHA256':manifest['config']['digest'],'chainUsageBytes':sizes,'compressedBytes':compressed,
  'observedUnpackedBytes':unpacked,'completePeakAdditionalBytes':peak,'readOnly':True}))
elif r['phase']=='apply':
 assert socket.gethostname() in ('workernode2','workernode1') and r['image']==ref
 assert r['requiredBeforeBytes']>r['completePeakAdditionalBytes']>0
 fs=os.statvfs('/')
 assert fs.f_bfree*fs.f_frsize>=r['requiredBeforeBytes']
 assert fs.f_bavail*fs.f_frsize>=15*1024**3+r['completePeakAdditionalBytes']
 # Persist submission on the controller before this request. Do not replay an
 # uncertain native pull; inspect its records/cache and retain failure evidence.
 cmd(['images','pull','--platform','linux/amd64','--snapshotter','overlayfs',ref],timeout=600)
 ready=set(cmd(['images','check','--quiet','--snapshotter','overlayfs']).decode().splitlines())
 assert ref in ready
 fs=os.statvfs('/');after=fs.f_bfree*fs.f_frsize
 assert after>=r['requiredBeforeBytes']-r['completePeakAdditionalBytes']
 assert fs.f_bavail*fs.f_frsize>=15*1024**3
 print(json.dumps({'node':socket.gethostname(),'rootDigest':root,'fullyDownloadedAndUnpacked':True,
  'originalFloorAndMarginPreserved':True,'rootFreeAfter':after,'nonprivilegedAvailableAfter':fs.f_bavail*fs.f_frsize,
  'filesystemReservedBlocksChanged':False,'volumesOrWorkloadsChanged':False}))
else:raise AssertionError('fixed_phase')
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['qualify', 'apply', 'stage'])
    phase = p.parse_args().phase
    assert os.geteuid() == 1000 and F.is_mount() and (H / 'ownership.json').is_file()
    os.umask(0o077)
    repo = Path(__file__).resolve().parents[5]
    l = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
    l['controls']()
    privilege = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = privilege['privilege_input']()

    def remote(ip, request):
        child = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
            '-p', '2002', 'james@' + ip, shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])],
            input=password + b'\n' + json.dumps(request).encode(), capture_output=True, timeout=660)
        with (H / ('preload-execution-' + uuid.uuid4().hex + '.json')).open('x') as out:
            json.dump({'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'host': ip, 'phase': request['phase'], 'exitCode': child.returncode,
                'stdoutSHA256': hashlib.sha256(child.stdout).hexdigest(),
                'stderrSHA256': hashlib.sha256(child.stderr).hexdigest(),
                'stderr': child.stderr.decode()[-2000:] if child.returncode else ''}, out, indent=2)
        assert child.returncode == 0, ('native_profile_or_pull_failed_no_replay', ip, child.returncode)
        return json.loads(child.stdout)

    try:
        if phase in ('qualify', 'stage'):
            assert not (H / 'pihole-payload-budget-v3.json').exists()
            profile = remote('192.168.0.4', {'phase': 'profile'})
            budgets = []
            for n in l['get']('nodes.longhorn.io'):
                for d in n['status']['diskStatus'].values():
                    required = d['storageMaximum'] // 4 + 1 + 512 * 1024**2
                    extra = 0 if n['metadata']['name'] == 'masternode' else profile['completePeakAdditionalBytes']
                    budgets.append({'node': n['metadata']['name'], 'available': d['storageAvailable'],
                        'originalFloorAndMargin': required, 'additionalPeakBytes': extra,
                        'requiredBeforeBytes': required + extra, 'passed': d['storageAvailable'] >= required + extra})
            value = {'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'masterProfile': profile, 'budgets': budgets, 'allPassed': all(x['passed'] for x in budgets)}
            with (H / 'pihole-payload-budget-v3.json').open('x') as out:
                json.dump(value, out, indent=2)
            print(json.dumps({'allPassed': value['allPassed'], 'budgets': budgets,
                'completePeakAdditionalBytes': profile['completePeakAdditionalBytes']}))
            assert value['allPassed'], 'complete_native_peak_does_not_fit_no_pull'
            if phase == 'qualify':
                return
        plan = json.loads((H / 'pihole-payload-budget-v3.json').read_text())
        assert plan['allPassed'] and plan['sourceSHA256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        for node, ip in [('workernode2', '192.168.0.5'), ('workernode1', '192.168.0.6')]:
            for path in (F, Path('/mnt/c')):
                fs = os.statvfs(path)
                assert fs.f_bavail * fs.f_frsize >= 16 * 1024**3
            budget = next(x for x in plan['budgets'] if x['node'] == node)
            request = {'phase': 'apply', 'image': 'docker.io/pihole/pihole@' + ROOT,
                'requiredBeforeBytes': budget['requiredBeforeBytes'],
                'completePeakAdditionalBytes': budget['additionalPeakBytes']}
            with (H / (node + '-preload-intent-v3.json')).open('x') as out:
                json.dump(request, out, indent=2)
            value = remote(ip, request)
            with (H / (node + '-preload-result-v3.json')).open('x') as out:
                json.dump(value, out, indent=2)
            print(json.dumps(value))
    finally:
        password = None


if __name__ == '__main__':
    main()
