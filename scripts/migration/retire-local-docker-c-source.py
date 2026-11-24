#!/usr/bin/env python3
"""Retire only the verified, inactive pre-migration WSL Docker stores."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import tomllib

STORE = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files')
ROOT = STORE / 'shared-docker-runtime'
TARGETS = (Path('/var/lib/docker'), Path('/var/lib/containerd'))


def run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=60).stdout


def under(value):
    return any(value == str(p) or value.startswith(str(p) + '/') for p in TARGETS)


def main():
    if os.geteuid() != 0 or not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError('Safe local root removal is required')
    receipt = json.loads((ROOT / 'migration.json').read_text())
    if receipt.get('state') != 'completed' or not receipt.get('copied_checksum_verified'):
        raise RuntimeError('Successful checked migration receipt is missing')
    info = json.loads(run(['docker', 'info', '--format', '{{json .}}']))
    config = tomllib.loads(Path('/etc/containerd/config.toml').read_text())
    if info.get('DockerRootDir') != str(ROOT / 'docker') or config.get('root') != str(ROOT / 'containerd'):
        raise RuntimeError('Live runtime does not use H configuration')
    for name in ('docker', 'containerd'):
        if os.stat(ROOT / name).st_dev != os.stat(STORE).st_dev:
            raise RuntimeError('Destination is not on the approved store')
    if run(['findmnt', '--mountpoint', str(STORE), '-n', '-o', 'FSTYPE']).strip() != 'ext4':
        raise RuntimeError('H Linux store is not mounted')
    if run(['docker', 'ps', '-aq']).strip():
        raise RuntimeError('Finish source retirement before starting review consumers')
    for target in TARGETS:
        if target.is_symlink() or target.resolve() != target or target.stat().st_uid != 0:
            raise RuntimeError('Original path identity changed')
        mounts = subprocess.run(['findmnt', '-R', '--mountpoint', str(target), '-n', '-o', 'TARGET'],
                                capture_output=True, text=True, timeout=15)
        rows = mounts.stdout.splitlines()
        if rows and rows != [str(target)]:
            raise RuntimeError('Original store has child mounts; preserve it')
        if rows:
            # Retire only Docker's inactive self-bind; no lazy or forced unmount.
            run(['umount', str(target)])
    references = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for entry in [proc / 'cwd', proc / 'root', *list((proc / 'fd').iterdir())]:
                try:
                    if under(os.readlink(entry)):
                        references.append(proc.name)
                except FileNotFoundError:
                    pass
            for line in (proc / 'mountinfo').read_text().splitlines():
                fields = line.split()
                if len(fields) > 4 and (under(fields[3]) or under(fields[4])):
                    references.append(proc.name)
            for line in (proc / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) == 6 and under(fields[5]):
                    references.append(proc.name)
        except (FileNotFoundError, ProcessLookupError):
            continue
    if references:
        raise RuntimeError('Original runtime paths still have live references; preserve them')
    before = shutil.disk_usage('/').free
    removed = []
    result = {'owner': 'BORTUS Delivery and Cluster Operations', 'state': 'removing',
              'preservation_receipt': str(ROOT / 'migration.json'), 'removed': removed}
    output = ROOT / 'source-retirement.json'
    def save():
        output.write_text(json.dumps(result, indent=2) + '\n')
        output.chmod(0o600)
    save()
    try:
        for target in TARGETS:
            allocated = int(run(['du', '-sx', '-B1', str(target)]).split()[0])
            if target.is_symlink() or target.resolve() != target or os.path.ismount(target):
                raise RuntimeError('Original source changed before retirement')
            shutil.rmtree(target)
            removed.append({'path': str(target), 'allocated_bytes': allocated, 'absent': not target.exists()})
            save()
        result.update(state='completed', completed_unix=time.time(),
                      measured_linux_free_delta=shutil.disk_usage('/').free - before,
                      windows_recovery_claimed=False)
        receipt.update(originals_retained=[], source_retirement_receipt=str(output))
        (ROOT / 'migration.json').write_text(json.dumps(receipt, indent=2) + '\n')
    except BaseException:
        result['state'] = 'partial-preserved'
        raise
    finally:
        save()
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
