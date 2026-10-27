"""Plex preservation controller; privilege input stays in TTY/RAM/SSH stdin."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import termios

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'node-cleanup-20261027/worker2-legacy-plex-preservation'
WINDOWS = r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def privilege_input():
    fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    previous = termios.tcgetattr(fd)
    hidden = previous[:]
    hidden[3] &= ~termios.ECHO
    try:
        termios.tcsetattr(fd, termios.TCSAFLUSH, hidden)
        need(not termios.tcgetattr(fd)[3] & termios.ECHO, 'non_echoing_terminal_required')
        os.write(fd, b'Existing authorized privilege input (terminal echo disabled): ')
        raw = bytearray()
        while True:
            value = os.read(fd, 1)
            if value in (b'\n', b'\r'):
                break
            need(value and len(raw) < 128, 'bounded_privilege_input')
            raw.extend(value)
        need(bool(raw), 'required_privilege_input')
        result = bytes(raw)
        raw[:] = b'\0' * len(raw)
        return result
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, previous)
        os.write(fd, b'\n')
        os.close(fd)


def windows(path):
    return WINDOWS + '\\' + str(path.relative_to(F)).replace('/', '\\')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inventory', 'backup'])
    parser.add_argument('--repository', type=Path, required=True)
    a = parser.parse_args()
    repository = a.repository.resolve()
    need(F.is_mount() and repository.is_dir(), 'existing_controller_mount_and_repository')
    os.umask(0o077)
    helper = repository / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/archive.py'
    safe = repository / 'k8s-rewrite/ansible-playbook/roles/retired_build_tools/files/retire.py'
    if a.mode == 'backup':
        need(R.is_dir() and (R / 'profile.json').is_file() and not (R / 'backup-operator-source.json').exists(), 'original_inventory_and_new_backup')
        need((R / 'archive-frozen.py').read_bytes() == helper.read_bytes()
             and (R / 'reference-frozen.py').read_bytes() == safe.read_bytes(), 'reviewed_frozen_sources')
        source = repository / 'scripts/migration/backup-legacy-plex-to-nas.py'
        frozen = R / 'backup-native-frozen.py'
        need(not frozen.exists(), 'earlier_native_operator_preserved')
        frozen.write_bytes(source.read_bytes())
        record = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'controllerOperatorPID': os.getpid(),
                  'nativeOperatorSHA256': hashlib.sha256(frozen.read_bytes()).hexdigest(),
                  'helperSHA256': hashlib.sha256(helper.read_bytes()).hexdigest(), 'sourceDeleted': False}
        (R / 'backup-operator-source.json').write_text(json.dumps(record, indent=2) + '\n')
        env = dict(os.environ, TEMP=WINDOWS + r'\operator-control\tmp', TMP=WINDOWS + r'\operator-control\tmp')
        command = ['/mnt/c/Users/james/AppData/Local/Programs/Python/Python312/python.exe', '-I', '-B', windows(frozen),
                   '--profile', windows(R / 'profile.json'), '--helper', windows(R / 'archive-frozen.py'),
                   '--safety-source', windows(R / 'reference-frozen.py')]
        need(subprocess.run(command, env=env, timeout=14400).returncode == 0, 'native_backup_and_restore_failed_evidence_retained')
        return
    need(os.geteuid() == 0 and not R.exists(), 'new_inventory_root_and_local_tty_owner')
    R.mkdir(mode=0o700)
    os.chown(R, 1000, 1000)
    for path, source in [(R / 'archive-frozen.py', helper), (R / 'reference-frozen.py', safe)]:
        path.write_bytes(source.read_bytes())
        os.chown(path, 1000, 1000)
    raw_safe = safe.read_bytes()
    args = ['legacy', 'inventory', '--safety-source', base64.b64encode(raw_safe).decode(),
            '--safety-sha256', hashlib.sha256(raw_safe).hexdigest()]
    remote = 'import sys;sys.argv=' + repr(args) + '\n' + helper.read_text()
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no',
               '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.5',
               shlex.join(['sudo', '-S', '-p', '', '--', 'python3', '-B', '-c', remote])]
    password = privilege_input()
    partial = R / 'profile.json.incomplete'
    try:
        with partial.open('xb') as out:
            child = subprocess.run(command, input=password + b'\n', stdout=out, stderr=subprocess.PIPE, timeout=1800)
        need(child.returncode == 0 and partial.stat().st_size <= 192 * 1024**2, 'complete_privileged_inventory')
        profile = json.loads(partial.read_text())
        need(profile['schema'] == 1 and profile['sourceDeleted'] is False, 'inventory_schema')
        partial.rename(R / 'profile.json')
        os.chown(R / 'profile.json', 1000, 1000)
    finally:
        password = None


if __name__ == '__main__':
    main()
