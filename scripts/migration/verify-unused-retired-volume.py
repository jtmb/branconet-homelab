"""Read-only lineage and physical non-initialization proof for retired WordPress.

No mount, attachment, snapshot, initialization, Secret-value read or deletion.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'platform-upstream-review-20261027/unused-wordpress-lineage-20261027'
OLD = F / 'wordpress-retirement-20261026'
NAME = 'pvc-49df631b-614f-4180-b6e5-f719db4bfe2c'
VUID = '4d5c0099-2068-4268-aa7f-98ab37c26001'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def get(kind, name=None, namespace='longhorn-system'):
    args = SSH + ['james@192.168.0.4', 'kubectl', 'get', kind]
    if name:
        args.append(name)
    if namespace:
        args += ['-n', namespace]
    p = subprocess.run(args + ['-o', 'json'], capture_output=True, timeout=60)
    need(p.returncode == 0 and len(p.stdout) < 8 * 1024**2, 'bounded_metadata_read')
    return json.loads(p.stdout)


def main():
    need(os.geteuid() == 0 and F.is_mount() and F.resolve() == F and not R.exists(), 'fixed_original_controller_no_replay')
    os.umask(0o077)
    before = json.loads((OLD / 'before.json').read_text())
    cancelled = json.loads((OLD / 'cancelled-database-preparation.json').read_text())
    accepted = json.loads((OLD / 'acceptance.json').read_text())
    original = next(c for c in before['claims'] if c['name'] == 'wordpress-db-upstream-20261026')
    need(cancelled['userCancelledDatabaseUpgrade'] and cancelled['noColdBackupOrUpgradeOrDataCopyExecuted']
         and accepted['passed'] and accepted['allFourClaimsSameUIDSpecAndBound']
         and all(not rows for rows in accepted['remainingWordPressRuntimeObjects'].values()), 'original_cancellation_and_retirement_lineage')
    R.mkdir(mode=0o700)
    os.chown(R, 1000, 1000)
    with (R / 'ownership.json').open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'sourceSHA256': sha(Path(__file__)),
            'generatedPaths': [str(R / 'ownership.json'), str(R / 'result.json')], 'peakMetadataBytes': 1024**2,
            'protected': 'retained WordPress claims/data, existing NAS backups, native Secrets and all workloads',
            'endCondition': 'read-only fixed-path absence/UID/spec/source proof; retain minimal metadata only',
            'regeneration': 'same maintained read-only verifier against original retirement sources and fixed live identities'}, out, indent=2)
    result = {'status': 'started', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': sha(Path(__file__)), 'historicalSourceHashes': {str(OLD / n): sha(OLD / n)
              for n in ['before.json', 'cancelled-database-preparation.json', 'acceptance.json']},
              'clusterChanged': False, 'volumeInitializedOrMounted': False, 'nativeSecretValuesRead': False}
    password = None
    try:
        claim = get('pvc', original['name'], 'wordpress')
        pv = get('pv', NAME, None)
        volume = get('volumes.longhorn.io', NAME)
        need(claim['metadata']['uid'] == original['uid'] and claim['spec'] == original['spec']
             and claim['status']['phase'] == 'Bound' and pv['spec']['claimRef']['uid'] == original['uid']
             and pv['spec']['csi']['volumeHandle'] == NAME and volume['metadata']['uid'] == VUID, 'original_claim_spec_and_complete_identity_chain')
        need(volume['status']['state'] == 'detached' and int(volume['status'].get('actualSize', -1)) == 0
             and not volume['spec']['nodeID'] and not volume['spec'].get('lastAttachedBy')
             and not volume['status'].get('lastBackup'), 'unchanged_uninitialized_volume_metadata')
        va = get('volumeattachments.longhorn.io', NAME)
        need(not va['spec'].get('attachmentTickets'), 'no_attachment_ticket')
        pods = get('pods', namespace='wordpress')['items']
        need(not any(v.get('persistentVolumeClaim', {}).get('claimName') == original['name']
             for p in pods for v in p['spec'].get('volumes', [])), 'no_existing_claim_consumer')
        replicas = [x for x in get('replicas.longhorn.io')['items'] if x['spec']['volumeName'] == NAME]
        engines = [x for x in get('engines.longhorn.io')['items'] if x['spec']['volumeName'] == NAME]
        need(len(replicas) == 2 and {r['spec']['nodeID'] for r in replicas} == {'workernode1', 'workernode2'}
             and all(r['status']['currentState'] == 'stopped' and not r['spec'].get('healthyAt')
                     and not r['spec'].get('failedAt') for r in replicas)
             and len(engines) == 1 and engines[0]['status']['currentState'] == 'stopped'
             and int(engines[0]['status'].get('currentSize', -1)) == 0 and not engines[0]['spec']['nodeID'], 'never_healthy_replica_and_zero_unstarted_engine_lineage')
        library = {'__name__': 'non_echoing_privilege_input'}
        source = Path('/mnt/c/Users/james/.codex/worktrees/cluster-maintenance-ansible/kubernetes migration/k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py')
        exec(compile(source.read_bytes(), str(source), 'exec'), library)
        password = library['privilege_input']()
        proofs = []
        for replica in replicas:
            spec = replica['spec']
            need(spec['diskPath'] == '/var/lib/longhorn/' and spec['dataDirectoryName'].startswith(NAME + '-')
                 and '/' not in spec['dataDirectoryName'], 'fixed_original_replica_directory')
            path = '/var/lib/longhorn/replicas/' + spec['dataDirectoryName']
            address = {'workernode1': '192.168.0.6', 'workernode2': '192.168.0.5'}[spec['nodeID']]
            code = ('import json,os,socket;from pathlib import Path;'
                    + 'p=Path(' + repr(path) + ');'
                    + 'assert socket.gethostname()==' + repr(spec['nodeID']) + ';'
                    + 'assert p.parent.resolve()==p.parent and p.parent.is_dir();'
                    + 'assert not os.path.lexists(p);'
                    + 'print(json.dumps({"path":str(p),"absent":True,"hostname":socket.gethostname()}))')
            p = subprocess.run(SSH + ['james@' + address, shlex.join(['sudo', '-S', '-p', '', '--', 'python3', '-B', '-c', code])],
                               input=password + b'\n', capture_output=True, timeout=45)
            need(p.returncode == 0 and len(p.stdout) < 4096, 'physical_original_replica_directory_absence_' + spec['nodeID'])
            proofs.append(dict(json.loads(p.stdout), replicaUID=replica['metadata']['uid']))
        need(get('pvc', original['name'], 'wordpress')['metadata']['resourceVersion'] == claim['metadata']['resourceVersion']
             and get('volumes.longhorn.io', NAME)['spec'] == volume['spec']
             and not get('volumeattachments.longhorn.io', NAME)['spec'].get('attachmentTickets'), 'identities_specs_and_no_attachment_still_match')
        result.update(status='unused_retired_volume_has_no_initialized_payload', claimUID=original['uid'],
            pvUID=pv['metadata']['uid'], volumeUID=VUID, physicalReplicaProofs=proofs,
            originalSpecPreserved=True, originalRetirementProvesNoDataCopy=True,
            emptyAllocationIsNotSoleProof=True, nativePayloadBackupRequired=False,
            metadataRecovery='Preserved original Kubernetes/Longhorn objects; independent encrypted control-plane checkpoint',
            claimAndVolumeRetained=True)
    except Exception as e:
        result.update(status='unresolved_preserve_originals', failedCheck=str(e) if isinstance(e, ValueError) else type(e).__name__)
        raise
    finally:
        password = None
        with (R / 'result.json').open('x') as out:
            json.dump(result, out, indent=2)
        os.chown(R / 'result.json', 1000, 1000)
        os.chown(R / 'ownership.json', 1000, 1000)
        print(json.dumps({k: v for k, v in result.items() if k not in ('historicalSourceHashes',)}))


if __name__ == '__main__':
    main()
