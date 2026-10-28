#!/usr/bin/env python3
"""WSL relay for the opt-in Ansible qBittorrent compatibility operation."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
REMOTE = '/home/james/.local/share/branconet-migration/'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source-id', required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    assert a.apply and os.getuid() == 1000 and re.fullmatch('[a-f0-9]{64}', a.source_id)
    keyfile = BASE / 'qbittorrent-acceptance-20261025/operator.key'
    s = keyfile.lstat()
    assert keyfile.resolve() == keyfile and stat.S_ISREG(s.st_mode) and s.st_uid == 1000 and not s.st_mode & 0o077
    key = keyfile.read_bytes()
    assert len(key) == 32
    folder = REMOTE + 'qbittorrent-compatibility-playbook-' + a.source_id
    receipt = REMOTE + 'qbittorrent-acceptance-20261025/compatible-settings-' + uuid.uuid4().hex + '.json'
    command = ['python3', folder + '/restore-qbittorrent-compatible-settings.py', '--apply',
               '--baseline', REMOTE + 'qbittorrent-acceptance-20261025/baseline-ef3b87a13b424d7ab55339295efe7c27.json',
               '--receipt', receipt]
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4', shlex.join(command)]
    result = subprocess.run(ssh, input=key.hex().encode(), capture_output=True, timeout=90)
    del key
    assert len(result.stdout) <= 8192
    report = json.loads(result.stdout)
    print(json.dumps({'exit': result.returncode, 'receipt': receipt, 'result': report}))
    return result.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'passed': False, 'raw_details_suppressed': True}))
        raise SystemExit(1)
