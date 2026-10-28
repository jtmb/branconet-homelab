"""Opt-in, serial official image staging through existing Ansible/SSH ownership."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'
F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
U = F / 'platform-upstream-review-20261027/longhorn-production-prestage-20261028'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, value):
    with (U / name).open('x') as f:
        json.dump(value, f, indent=2)


def capture(source, name):
    p = subprocess.run(SSH + ['python3 -B - --remote'], input=source.read_bytes(), capture_output=True, timeout=900)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'complete_readonly_cluster_capture')
    value = json.loads(p.stdout)
    save(name, value)
    return value


def fence(value):
    need(len(value['nodes']) == 3 and all(x['ready'] and not x['pressure'] for x in value['nodes']), 'three_ready_original_nodes')
    need(len(value['claims']) == 58 and all(x['phase'] == 'Bound' for x in value['claims']), 'all_fifty_eight_claims_bound')
    need(len(value['volumes']) == 44 and all(v['dataEngine'] == 'v1' and v['encrypted'] and v['replicasDesired'] == 2
                                          for v in value['volumes']), 'original_encrypted_v1_two_replica_volume_scope')
    attached = [v for v in value['volumes'] if v['state'] == 'attached']
    for v in attached:
        need(v['robustness'] == 'healthy' and len(v['engines']) == 1 and v['engines'][0]['state'] == 'running'
             and len(v['engines'][0]['replicaModes']) == 2
             and list(v['engines'][0]['replicaModes'].values()).count('RW') == 2
             and len({r['node'] for r in v['replicas'] if r['state'] == 'running' and not r['failedAt']}) == 2,
             'every_attached_volume_has_two_actual_healthy_RW_replicas')
    need(value['settings']['current-longhorn-version'] == 'v1.12.1'
         and value['settings']['concurrent-automatic-engine-upgrade-per-node-limit'] == '0'
         and value['settings']['storage-minimal-available-percentage'] == '25', 'unchanged_manual_upgrade_and_storage_controls')
    need(all(v['completedBackupCount'] for v in value['volumes'] if v['name'] != 'pvc-49df631b-614f-4180-b6e5-f719db4bfe2c'),
         'all_initialized_volumes_have_completed_native_backups')
    need(len([p for p in value['persistentVolumes'] if p['driver'] == 'smb.csi.k8s.io']) == 14, 'original_fourteen_NAS_bindings')
    need(all(t['available'] and not t['errorPresent'] for t in value['backupTargets']) and value['backupTargets'], 'original_available_backup_target')
    return {'attachedVolumes': len(attached), 'claims': 58, 'volumes': 44, 'NASBindings': 14,
            'allInitializedNativeBackupsPresent': True, 'twoActualRWOnEveryAttachedVolume': True}


def stable(value):
    return {'claims': sorted((x['namespace'], x['name'], x['uid'], x['volumeName'], x['storageClassName']) for x in value['claims']),
            'volumes': sorted((x['name'], x['uid'], x['state'], x['encrypted'], x['size'], x['replicasDesired'], x['currentImage'])
                              for x in value['volumes']),
            'replicas': sorted((r['name'], r['uid'], r['node']) for v in value['volumes'] for r in v['replicas']),
            'engines': sorted((e['name'], e['uid'], e['currentImage']) for v in value['volumes'] for e in v['engines']),
            'NASBindings': sorted((p['name'], p['uid'], p['volumeHandle'], p['claimRef']['uid']) for p in value['persistentVolumes'] if p['driver'] == 'smb.csi.k8s.io'),
            'settings': value['settings']}


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    a = parser.parse_args()
    repo = a.repository.resolve()
    s = repo / 'k8s-rewrite/ansible-playbook'
    need(os.geteuid() == 1000 and F.is_mount() and not U.exists(), 'original_owner_root_and_new_operation')
    for p in (F, Path('/mnt/c')):
        stat = os.statvfs(p)
        need(stat.f_bavail * stat.f_frsize >= 15 * 1024**3 + 64 * 1024**2, 'complete_metadata_peak_and_original_windows_destination_floors')
    os.umask(0o077)
    U.mkdir(mode=0o700)
    scratch = U / 'ansible-scratch'
    source = s / 'roles/longhorn_upgrade_preflight/files/check.py'
    paths = [Path(__file__).resolve(), source, s / 'roles/longhorn_upgrade_preload/files/preload.py',
             s / 'action_plugins/longhorn_upgrade_preload.py', s / 'playbooks/longhorn-upgrade-preload.yml']
    sources = {str(p): sha(p) for p in paths}
    outputs = ['ownership.json', 'source-binding.json', 'prestage-before.json', 'prestage-before-fence.json',
               'postflight.json', 'postflight-comparison.json', 'ansible-operator.json', 'ansible-scratch']
    outputs += ['node-' + n + '-' + kind + '.json' for n in ['masternode', 'workernode2', 'workernode1'] for kind in ['intent', 'result']]
    save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
         'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(U / n) for n in outputs],
         'completePeakBytes': 64 * 1024**2, 'sources': sources, 'protected': 'All applications, data, native keys, original archives and other projects; no container starts or volume/workload patches',
         'requiredRuntimeArtifacts': 'Exact thirteen official pinned upstream Longhorn images in the existing production runtime; required for the supported manager/engine rollout',
         'productionRuntimeDestinations': {n: '/var/lib/containerd-k8s' for n in ['masternode', 'workernode2', 'workernode1']},
         'productionArtifactRule': 'Required runtime content on the original cluster disks; no node build, transfer archive, scratch or dependency copy is created',
         'regeneration': 'Existing hash-bound source and native inspected upstream digests; never reset the cluster or replay a completed operation',
         'endCondition': 'Three actual node results, unchanged data/runtime fences and full source/scratch reconciliation'})
    save('source-binding.json', {'sources': sources})
    before = capture(source, 'prestage-before.json')
    save('prestage-before-fence.json', fence(before))
    scratch.mkdir(mode=0o700)
    fd0 = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(fd0, fcntl.F_DUPFD, 200)
    os.close(fd0)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(s / 'ansible.cfg'),
        ANSIBLE_ACTION_PLUGINS=str(s / 'action_plugins'), ANSIBLE_ROLES_PATH=str(s / 'roles'),
        ANSIBLE_HOME=str(scratch / 'home'), ANSIBLE_LOCAL_TEMP=str(scratch / 'local'), ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'),
        TMPDIR=alias, TMP=alias, TEMP=alias, ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C',
        ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    pr = {'__name__': 'existing_protected_privilege_input'}
    exec(compile((s / 'roles/legacy_plex_preservation/files/controller.py').read_bytes(), '<protected-input>', 'exec'), pr)
    password = pr['privilege_input']().decode()
    from ansible.cli.playbook import PlaybookCLI
    variables = {'longhorn_upgrade_preload': True, 'ansible_ssh_private_key_file': '/home/brajam/.ssh/id_ed25519',
                 'ansible_ssh_common_args': '-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
    cli = PlaybookCLI(['ansible-playbook', '-i', str(s / 'inventory/production.ini'),
                       str(s / 'playbooks/longhorn-upgrade-preload.yml'), '-e', json.dumps(variables)])
    cli.ask_passwords = lambda: (None, password)
    result = {'status': 'started', 'sources': sources, 'scratch': str(scratch),
              'kubernetesWorkloadOrVolumeWrites': False, 'productionRuntimeCacheWrites': True}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed_preserve_runtime_and_receipts'
        if result['exitCode'] == 0:
            after = capture(source, 'postflight.json')
            checks = fence(after)
            need(stable(before) == stable(after), 'all_original_volume_replica_engine_claim_NAS_identities_and_controls_preserved')
            save('postflight-comparison.json', dict(checks, status='all_original_identities_and_controls_preserved',
                beforeSHA256=sha(U / 'prestage-before.json'), afterSHA256=sha(U / 'postflight.json')))
    except Exception as error:
        result.update(status='failed_preserve_runtime_and_receipts', errorType=type(error).__name__)
        raise
    finally:
        password = None
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        result['sourcesUnchanged'] = all(sha(Path(p)) == h for p, h in sources.items())
        save('ansible-operator.json', result)
    raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    main()
