"""Final encrypted pre-upgrade checkpoint through the existing Ansible owner.

The operator credential stays in a protected TTY, RAM and SSH stdin. No plaintext
configuration archive, credential environment or node-side build is created.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'
F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
Q = O / 'final-control-plane-checkpoint-20261028'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    a = parser.parse_args()
    repo = a.repository.resolve()
    s = repo / 'k8s-rewrite/ansible-playbook'
    need(os.geteuid() == 1000 and F.is_mount() and not Q.exists(), 'existing_owner_storage_and_unique_operation')
    for p in (F, Path('/mnt/c')):
        st = os.statvfs(p)
        need(st.f_bavail * st.f_frsize >= 17 * 1024**3, 'windows_and_destination_floor_plus_complete_two_gib_peak')
    need('BRANCONET_MIGRATION_SUDO_PASSWORD' not in os.environ, 'no_credential_environment')
    os.umask(0o077)
    run_id = uuid.uuid4().hex
    backup = O / 'flux-control-plane-backup' / ('control-plane-' + run_id)
    scratch = Q / 'ansible-scratch'
    paths = [Path(__file__).resolve(), s / 'roles/control_plane_backup/files/control_plane_backup.py',
             s / 'action_plugins/control_plane_backup_inline.py', s / 'roles/control_plane_backup/tasks/main.yml',
             s / 'roles/control_plane_backup/defaults/main.yml', s / 'playbooks/control-plane-backup.yml']
    sources = {str(p): sha(p) for p in paths}
    Q.mkdir(mode=0o700)

    def save(name, value):
        with (Q / name).open('x') as stream:
            json.dump(value, stream, indent=2)

    save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
         'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'runID': run_id,
         'generatedPaths': [str(scratch), str(backup), str(Q / 'operator.json')],
         'completePeakBytes': 2 * 1024**3, 'sources': sources,
         'remoteTemporarySnapshot': '/var/lib/etcd/cluster-maintenance-' + run_id + '/snapshot.db',
         'remoteEndCondition': 'Only this producer-owned snapshot is removed after authenticated encrypted archive verification',
         'retainedConsumer': 'Encrypted checkpoint and independent NAS readback/offline restore before supported Longhorn upgrade',
         'regeneration': 'Same maintained playbook and source pins; a fresh snapshot is a new checkpoint, never overwrite this one',
         'protected': 'Original cluster data, native Secrets and keys, existing backups, source and all other running projects'})
    scratch.mkdir(mode=0o700)
    fd0 = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(fd0, fcntl.F_DUPFD, 200)
    os.close(fd0)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(s / 'ansible.cfg'),
        ANSIBLE_ACTION_PLUGINS=str(s / 'action_plugins'), ANSIBLE_ROLES_PATH=str(s / 'roles'),
        ANSIBLE_HOME=str(scratch / 'home'), ANSIBLE_LOCAL_TEMP=str(scratch / 'local'),
        ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'), TMPDIR=alias, TMP=alias, TEMP=alias,
        ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C', ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    pr = {'__name__': 'existing_protected_privilege_input'}
    exec(compile((s / 'roles/legacy_plex_preservation/files/controller.py').read_bytes(), '<protected-input>', 'exec'), pr)
    password = pr['privilege_input']().decode()
    from ansible.cli.playbook import PlaybookCLI
    settings = json.loads((O / 'flux-control-plane-backup-settings.json').read_text())
    settings.update(control_plane_backup_run_id=run_id,
        ansible_ssh_private_key_file='/home/brajam/.ssh/id_ed25519',
        ansible_ssh_common_args='-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts')
    cli = PlaybookCLI(['ansible-playbook', '-i', str(s / 'inventory/production.ini'),
        str(s / 'playbooks/control-plane-backup.yml'), '-e', json.dumps(settings)])
    cli.ask_passwords = lambda: (None, password)
    result = {'status': 'started', 'runID': run_id, 'backupPath': str(backup), 'sources': sources}
    try:
        result['exitCode'] = cli.run()
        need(result['exitCode'] == 0, 'backup_playbook_failed_preserve_receipts')
        receipt = json.loads((backup / 'receipt.json').read_text())
        need(receipt['status'] == 'completed' and receipt['authenticated_archive_verified']
             and receipt['snapshot_footer_verified'] and not receipt['remote_plaintext_retained'],
             'authenticated_checkpoint_and_remote_cleanup_required')
        result.update(status='completed', receiptSHA256=sha(backup / 'receipt.json'),
            archiveSHA256=receipt['archive_sha256'], archiveBytes=receipt['archive_bytes'])
    except Exception as error:
        result.update(status='failed_preserve_receipts', errorType=type(error).__name__)
        raise
    finally:
        password = None
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        result['sourcesUnchanged'] = all(sha(Path(p)) == h for p, h in sources.items())
        save('operator.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'runID', 'archiveSHA256', 'archiveBytes')}))


if __name__ == '__main__':
    main()
