"""Read-only eligible-node native image/cache gate for Pi-hole and Ingenium.

Refuse a cycle if any eligible node would need additional image content/unpack.
No downloads, pulls, native views, mounts or cache mutations are performed.
"""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/longhorn-remaining-runtime-20261028'
PIHOLE = 'sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113'
INGENIUM = 'sha256:712f40a5177079f3d7aab020632ef993ffb0775f2cb17355d77e9e81d7c31a66'
REMOTE = r'''
import hashlib,json,os,pathlib,socket,subprocess
ctr=pathlib.Path('/opt/containerd-k8s/bin/ctr')
assert os.geteuid()==0 and hashlib.sha256(ctr.read_bytes()).hexdigest()=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
base=[str(ctr),'--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
def run(args):
 p=subprocess.run(base+args,capture_output=True,timeout=90)
 assert p.returncode==0 and len(p.stdout)<=4194304
 return p.stdout
records=run(['images','list']);rows={}
for line in records.decode().splitlines()[1:]:
 x=line.split();rows.setdefault(x[2],[]).append(x[0])
ready=set(run(['images','check','--quiet','--snapshotter','overlayfs']).decode().splitlines())
digests=['sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113']
if socket.gethostname()=='workernode1':digests.append('sha256:712f40a5177079f3d7aab020632ef993ffb0775f2cb17355d77e9e81d7c31a66')
print(json.dumps({'node':socket.gethostname(),'readOnly':True,
 'imageRecordsSHA256':hashlib.sha256(records).hexdigest(),
 'requiredImages':[{'digest':d,'readyReferences':sorted(set(rows.get(d,[]))&ready),
 'completeDownloadedAndUnpacked':bool(set(rows.get(d,[]))&ready)} for d in digests]}))
'''


def main():
    assert os.geteuid() == 1000 and F.is_mount() and F.resolve() == F
    for p in (F, Path('/mnt/c')):
        s = os.statvfs(p)
        assert s.f_bavail * s.f_frsize >= 16 * 1024**3
    os.umask(0o077)
    H.mkdir(mode=0o700)
    with (H / 'ownership.json').open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b',
            'generatedPaths': [str(H)], 'peakControllerBytes': 1024**3,
            'regeneration': 'Tracked operator sources and original charts Git blobs with unchanged local publisher',
            'protected': 'All image/content/cache records, original claims/data/replicas/native Secrets, BORTUS hold and Strata',
            'endCondition': 'Two original apps restored on three new runtimes and consumed publisher exports reconciled'}, out, indent=2)
    repo = Path(__file__).resolve().parents[5]
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
    lib['controls']()
    templates = {}
    for app in ('pihole', 'ingenium'):
        dep = lib['get']('deployments', app, app)
        spec = dep['spec']['template']['spec']
        assert not spec.get('affinity')
        assert spec.get('nodeSelector', {}) == ({} if app == 'pihole' else {'kubernetes.io/hostname': 'workernode1'})
        expected = PIHOLE if app == 'pihole' else INGENIUM
        assert all(c['image'].endswith('@' + expected) and c['imagePullPolicy'] == 'IfNotPresent'
                   for c in spec.get('initContainers', []) + spec['containers'])
        templates[app] = hashlib.sha256(json.dumps(dep['spec']['template'], sort_keys=True).encode()).hexdigest()
    privilege = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = privilege['privilege_input']()
    results = []
    try:
        for ip in ('192.168.0.4', '192.168.0.5', '192.168.0.6'):
            p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
                '-p', '2002', 'james@' + ip, shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])],
                input=password + b'\n', capture_output=True, timeout=180)
            assert p.returncode == 0 and len(p.stdout) <= 1048576, ('read_only_native_cache_gate_failed', ip, p.returncode)
            results.append(json.loads(p.stdout))
    finally:
        password = None
    complete = all(x['completeDownloadedAndUnpacked'] for n in results for x in n['requiredImages'])
    with (H / 'native-cache-budget.json').open('x') as out:
        json.dump({'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'eligibleNodes': {'pihole': ['masternode', 'workernode2', 'workernode1'], 'ingenium': ['workernode1']},
            'templates': templates, 'nodes': results, 'allEligibleImagesFullyCached': complete,
            'additionalNativeImagePayloadAndUnpackBudgetBytes': 0 if complete else None,
            'cycleAuthorizedByThisRead': False, 'downloadOrUnpackPerformed': False}, out, indent=2)
    print(json.dumps({'allEligibleImagesFullyCached': complete, 'nodes': results}))
    assert complete, 'unbudgeted_native_payload_blocks_cycle_no_automatic_download'


if __name__ == '__main__':
    main()
