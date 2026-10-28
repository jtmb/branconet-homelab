"""Read-only master capacity projection for the same six retired derivatives.

Only observes existing metadata/files; no removal, pull, view or mount. The
complete retained graph and all current-container/lease/other-image exclusions
are inherited from the original maintained inventory and physical readers.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid


def main():
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/master-cache-capacity-20261028'
    assert os.geteuid() == 1000 and f.is_mount() and f.resolve() == f
    os.umask(0o077)
    h.mkdir(mode=0o700)
    with (h / 'ownership.json').open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(f),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b',
            'generatedPaths': [str(h)], 'peakBytes': 64 * 1024**2,
            'regeneration': 'Same bounded stable native image/lease/snapshot metadata and physical-inode projection',
            'protected': 'Every original image/content/lease/container/cache and workload/data object; observation only',
            'endCondition': 'Per-node native capacity budget for the two actual newly published security candidates'}, out, indent=2)
    here = Path(__file__).resolve().parent
    inv = runpy.run_path(str(here / 'inventory.py'))['REMOTE']
    assert inv.count("assert targets<=set(image_rows)") == 1
    inv = inv.replace('workernode2', 'masternode').replace('assert targets<=set(image_rows)',
        'targets &= set(image_rows);assert targets')
    remote = runpy.run_path(str(here / 'physical.py'))['REMOTE']
    request = {'inventorySource': base64.b64encode(inv.encode()).decode(),
        'inventorySHA256': hashlib.sha256(inv.encode()).hexdigest()}
    repo = here.parents[4]
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    try:
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
            '-p', '2002', 'james@192.168.0.4', shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', remote])],
            input=password + b'\n' + json.dumps(request).encode(), capture_output=True, timeout=300)
        value = {'exitCode': p.returncode, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'inventorySHA256': request['inventorySHA256'], 'physicalReaderSHA256': hashlib.sha256(remote.encode()).hexdigest(),
            'stdoutSHA256': hashlib.sha256(p.stdout).hexdigest(), 'stderr': p.stderr.decode()[-2000:] if p.returncode else ''}
        with (h / 'execution.json').open('x') as out:
            json.dump(value, out, indent=2)
        assert p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, ('read_only_profile_failed', p.returncode)
        result = json.loads(p.stdout)
        assert result['node'] == 'workernode2'  # fixed original physical reader's display label
        result['node'] = 'masternode'
        assert result['nativeInventory']['node'] == 'masternode'
        with (h / 'profile.json').open('x') as out:
            json.dump(result, out, indent=2)
        print(json.dumps({'node': result['node'], 'potentialCacheDirectories': len(result['mappedCandidates']),
            'potentialAllocatedBytes': result['actualCandidateAllocatedBytes'], 'orphans': result['orphanDirectories'],
            'mutationsPerformed': False}))
    finally:
        password = None


if __name__ == '__main__':
    main()
