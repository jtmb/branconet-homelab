"""Independent NAS readback and private-network restore of the final checkpoint."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
O = BASE + '/platform-upstream-review-20261027'
Q = O + '/final-control-plane-checkpoint-20261028'
E = O + '/etcd-restore-qualification'
OLD = 'cp-e90319b39ff741ab9dbc9f7d09cc6187-'
PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with path.open('x') as out:
        json.dump(value, out, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['nas', 'restore'])
    a = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if a.mode == 'nas':
        need(os.name == 'nt', 'authenticated_native_windows_nas_access_required')
        root = Path(r'\\wsl.localhost\Ubuntu' + BASE.replace('/', '\\'))
        q = root / 'platform-upstream-review-20261027/final-control-plane-checkpoint-20261028'
        e = root / 'platform-upstream-review-20261027/etcd-restore-qualification'
        op = json.loads((q / 'operator.json').read_text())
        need(op['status'] == 'completed' and op['sourcesUnchanged'], 'completed_authenticated_producer')
        run = op['runID']
        backup = root / 'platform-upstream-review-20261027/flux-control-plane-backup' / ('control-plane-' + run)
        receipt = backup / 'receipt.json'
        source = backup / 'control-plane.tar.age'
        expected = op['archiveSHA256']
        need(sha(receipt) == op['receiptSHA256'] and sha(source) == expected, 'exact_cipher_and_producer_receipt')
        prefix = 'cp-' + run + '-'
        nas = Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts') / ('sha256-' + expected + '.age')
        os.environ.update(TEMP=str(root / 'operator-control/tmp'), TMP=str(root / 'operator-control/tmp'))
        helper = repo / 'k8s-rewrite/ansible-playbook/roles/control_plane_restore_qualification/files/restore.py'
        save(q / 'qualification-ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': BASE,
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b',
            'generatedPaths': [E + '/' + prefix + n for n in ['nas-proof.json', 'tool-provenance.json', 'restore-frozen.py', 'scratch', 'restore-result.json', 'operator-result.json']],
            'durableEncryptedRecoveryCopy': str(nas), 'completePeakBytes': 2 * 1024**3,
            'regeneration': 'Existing encrypted checkpoint, authenticated NAS copy, pinned age/etcdutl and maintained offline-restore helper',
            'endCondition': 'Offline restore qualified; remove only proven inactive generated scratch after Linux and Windows exclusion',
            'protected': 'Encrypted original/NAS copy, producer metadata, source, all keys and unrelated workloads',
            'restoreSourceSHA256': sha(helper)})
        need(nas.parent.is_dir() and not nas.exists(), 'existing_recovery_store_and_new_cipher_identity')
        before = source.stat()
        with source.open('rb') as src, nas.open('xb') as dst:
            while chunk := src.read(1024**2):
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        after = source.stat()
        need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
             and nas.stat().st_size == op['archiveBytes'] and sha(nas) == expected and sha(source) == expected,
             'complete_independent_nas_readback_and_unchanged_source')
        ns = subprocess.run(['wsl', '--user', 'brajam', '--exec', 'readlink', '/proc/self/ns/net'],
            capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode().strip()
        save(e / (prefix + 'nas-proof.json'), {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source': str(nas), 'sha256': expected, 'bytes': op['archiveBytes'], 'fullNASReadback': True,
            'sourceReceiptSHA256': sha(receipt), 'ordinaryNetworkNamespace': ns})
        old = json.loads((e / (OLD + 'tool-provenance.json')).read_text())
        need(sha(e / 'tools/etcdutl') == old['binary']['sha256']
             == 'e3bd459308395080493488003f8cd4498db7ad4237584881b00f948a47950d2f', 'unchanged_pinned_stock_tool')
        old.update(reusedVerifiedPublicTool=True, previousProofSHA256=sha(e / (OLD + 'tool-provenance.json')))
        save(e / (prefix + 'tool-provenance.json'), old)
        with (e / (prefix + 'restore-frozen.py')).open('xb') as out:
            out.write(helper.read_bytes())
        print(json.dumps({'status': 'independent_NAS_readback_passed', 'runID': run, 'bytes': op['archiveBytes'], 'sha256': expected}))
        return
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    import fcntl
    need(os.geteuid() == 0 and Path(BASE).is_mount(), 'original_root_for_private_network_unit_only')
    q, e = Path(Q), Path(E)
    op = json.loads((q / 'operator.json').read_text())
    run, expected = op['runID'], op['archiveSHA256']
    prefix = 'cp-' + run + '-'
    helper = repo / 'k8s-rewrite/ansible-playbook/roles/control_plane_restore_qualification/files/restore.py'
    need(helper.read_bytes() == (e / (prefix + 'restore-frozen.py')).read_bytes(), 'same_frozen_restore_source')
    for path in (Path(BASE), Path('/mnt/c')):
        st = os.statvfs(path)
        need(st.f_bavail * st.f_frsize >= 17 * 1024**3, 'complete_restore_peak_and_original_floor')
    scratch = q / 'restore-ansible-scratch'
    need(not scratch.exists() and not (e / (prefix + 'operator-result.json')).exists(), 'no_repeated_restore_attempt')
    # Extend the declared operation inventory before generating packaging scratch.
    save(q / 'restore-packaging-ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd',
        'root': BASE, 'generatedPaths': [str(scratch)], 'regeneration': 'Same maintained Ansible restore playbook',
        'endCondition': 'Terminal Ansible run, independent Linux/native Windows reference checks, remove empty packaging directories'})
    os.umask(0o077)
    scratch.mkdir(mode=0o700)
    fd0 = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(fd0, fcntl.F_DUPFD, 200)
    os.close(fd0)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    s = repo / 'k8s-rewrite/ansible-playbook'
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(s / 'ansible.cfg'),
        ANSIBLE_ROLES_PATH=str(s / 'roles'), ANSIBLE_ACTION_PLUGINS=str(s / 'action_plugins'),
        ANSIBLE_HOME=str(scratch / 'home'), ANSIBLE_LOCAL_TEMP=str(scratch / 'local'),
        ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'), TMPDIR=alias, TEMP=alias, TMP=alias,
        ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C', ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    from ansible.cli.playbook import PlaybookCLI
    v = {'control_plane_restore_qualification_apply': True, 'control_plane_restore_qualification_backup_id': run,
         'control_plane_restore_qualification_archive_sha256': expected,
         'ansible_ssh_private_key_file': '/home/brajam/.ssh/id_ed25519',
         'ansible_ssh_common_args': '-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
    cli = PlaybookCLI(['ansible-playbook', '-i', str(s / 'inventory/production.ini'),
        str(s / 'playbooks/control-plane-restore-qualification.yml'), '-e', json.dumps(v)])
    cli.ask_passwords = lambda: (None, None)
    result = {'status': 'started', 'sourceSHA256': sha(helper)}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed_preserve_receipts'
    finally:
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        result['sourceUnchanged'] = helper.read_bytes() == (e / (prefix + 'restore-frozen.py')).read_bytes()
        save(e / (prefix + 'operator-result.json'), result)
    need(result['status'] == 'completed' and result['sourceUnchanged'], 'qualified_actual_restore_required')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
