"""Fixed master cache qualification/retirement with original native API guards.

The same six original retired derivative roots are considered; absent image
records are skipped. Current images/containers/leases/other image parents and
all workload data remain protected. Never retry a previously submitted key.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/master-cache-capacity-20261028'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['qualify', 'retire'])
    p.add_argument('--qualification', type=Path)
    a = p.parse_args()
    assert os.geteuid() == 1000 and F.is_mount() and (H / 'ownership.json').is_file()
    here = Path(__file__).resolve().parent
    inventory = runpy.run_path(str(here / 'inventory.py'))['REMOTE']
    assert inventory.count('assert targets<=set(image_rows)') == 1
    inventory = inventory.replace('workernode2', 'masternode').replace('assert targets<=set(image_rows)',
        'targets &= set(image_rows);assert targets')
    physical = runpy.run_path(str(here / 'physical.py'))['REMOTE'].replace("'node':'workernode2'", "'node':'masternode'")
    remote = runpy.run_path(str(here / 'retire.py'))['REMOTE'].replace("'node':'workernode2'", "'node':'masternode'")
    remote = remote.replace("request=json.load(sys.stdin);", "request=json.load(sys.stdin);assert json.loads(subprocess.check_output(['findmnt','-J','-T','/var/lib/containerd-k8s','-o','UUID']))['filesystems'][0]['uuid']=='763cda3d-0777-4b03-a882-9d21060466e3';")
    guard = (F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py').read_bytes()
    assert hashlib.sha256(guard).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    programs = {'inventory': inventory.encode(), 'physical': physical.encode(), 'retirement': remote.encode()}
    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in programs.items()}
    history, excluded = {}, set()
    for path in H.glob('retire-output-*.jsonl'):
        raw = path.read_bytes()
        history[path.name] = hashlib.sha256(raw).hexdigest()
        for line in raw.splitlines():
            row = json.loads(line)
            if 'intent' in row:
                excluded.add(row['intent'])
    request = {'mode': a.phase, 'inventorySource': base64.b64encode(programs['inventory']).decode(),
        'inventorySHA256': hashes['inventory'], 'physicalSource': base64.b64encode(programs['physical']).decode(),
        'physicalSHA256': hashes['physical'], 'guardSource': base64.b64encode(guard).decode(),
        'excludedPreviouslyAttemptedKeys': sorted(excluded), 'priorOutputHashes': history}
    if a.phase == 'retire':
        assert a.qualification and a.qualification.resolve() == a.qualification and a.qualification.parent == H
        q = json.loads(a.qualification.read_text())
        assert q['controllerSourceSHA256'] == source and q['programHashes'] == hashes
        request['qualification'] = q
    else:
        assert a.qualification is None
    os.umask(0o077)
    ident = uuid.uuid4().hex
    with (H / (a.phase + '-intent-' + ident + '.json')).open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'generatedPaths': [str(H)], 'peakBytes': 128 * 1024**2, 'node': 'masternode',
            'nodeFilesystemUUID': '763cda3d-0777-4b03-a882-9d21060466e3',
            'controllerSourceSHA256': source, 'programHashes': hashes,
            'excludedPreviouslyAttemptedKeys': sorted(excluded), 'priorOutputHashes': history,
            'qualificationSHA256': hashlib.sha256(a.qualification.read_bytes()).hexdigest() if a.qualification else None,
            'regeneration': 'Verified original root/config/layer payloads and original native offline unpack',
            'protected': 'Every image record/original blob/lease/container/data volume and every previously submitted key'}, out, indent=2)
    repo = here.parents[4]
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    try:
        output = H / (a.phase + '-output-' + ident + '.jsonl')
        with output.open('xb') as stream:
            child = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
                '-p', '2002', 'james@192.168.0.4', shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', remote])],
                stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.PIPE)
            _, errors = child.communicate(password + b'\n' + json.dumps(request).encode(), timeout=900)
        assert output.stat().st_size <= 4 * 1024**2
        with (H / (a.phase + '-execution-' + ident + '.json')).open('x') as out:
            json.dump({'controllerSourceSHA256': source, 'programHashes': hashes, 'exitCode': child.returncode,
                'outputSHA256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'stderrSHA256': hashlib.sha256(errors).hexdigest(), 'stderr': errors.decode()[-2500:] if child.returncode else ''}, out, indent=2)
        assert child.returncode == 0, ('native_cache_operation_incomplete_inspect_no_replay', child.returncode)
        value = json.loads(output.read_bytes().splitlines()[-1])
        value.update(controllerSourceSHA256=source, programHashes=hashes)
        target = H / (a.phase + '-' + ident + '.json')
        with target.open('x') as out:
            json.dump(value, out, indent=2)
        print(json.dumps({'status': value['status'], 'receipt': str(target),
            'candidatePaths': len(value.get('profile', {}).get('mappedCandidates', [])),
            'originalBlobsVerified': len(value.get('verifiedOriginalBlobs', [])),
            'removedAllocatedLinuxBytes': value.get('removedAllocatedLinuxBytes', 0)}))
    finally:
        password = None


if __name__ == '__main__':
    os.umask(0o077)
    with (H / 'retirement.lock').open('a+b') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
