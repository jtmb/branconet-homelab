#!/usr/bin/env python3
"""Seal one exact local-operator build for protected Ansible artifact staging."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reviewed_local_contract', HERE / 'local-image-contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
BASE = Path('/home/brajam/.local/share/branconet-migration')
SERVICES = ['seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden', 'tautulli', 'wordpress', 'nginx', 'phpmyadmin', 'coredns', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--service', choices=SERVICES, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--build-root', type=Path, required=True)
    p.add_argument('--provenance-sha256', required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args(); need = contract.local_need
    need(a.apply and os.name == 'posix' and os.getuid() == 1000 and
         re.fullmatch('[0-9a-f]{32}', a.run_id) and
         re.fullmatch('[0-9a-f]{64}', a.provenance_sha256), 'explicit_receiver_scope')
    os.umask(0o077)
    root = a.build_root
    expected_parent = BASE / ('local-image-build-offload-20261025' if root.parent.name == 'local-image-build-offload-20261025' and a.service in ['coredns', 'jackett', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb'] else 'local-image-build-20261024')
    need(root.parent == expected_parent and
         re.fullmatch(a.service + '-[0-9a-f]{12}-' + a.run_id[:12], root.name) and
         root.resolve() == root and not root.is_symlink(), 'fixed_build_root')
    source = root / 'artifacts'
    for directory in [root.parent, root, source]:
        s = directory.lstat()
        need(directory.resolve() == directory and stat.S_ISDIR(s.st_mode) and s.st_uid == 1000 and
             stat.S_IMODE(s.st_mode) == 0o700, 'original_directory')
    original = source / 'local-operator-provenance.json'
    need(original.stat().st_size <= contract.LOCAL_CAPS[original.name] and
         contract.local_hash(original) == a.provenance_sha256, 'original_provenance_sha')
    result = json.loads(original.read_bytes())
    need(result.get('run_id') == a.run_id and result.get('service') == a.service and
         result.get('state') == 'artifact-built-not-qualified-not-deployed', 'original_scope')
    caps = dict(contract.LOCAL_CAPS, **{a.service + '.oci.tar': 4 * 1024 ** 3})
    files = {}; identities = {}
    for name, cap in caps.items():
        path = source / name; s = path.lstat()
        need(path.resolve() == path and stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and
             s.st_uid == 1000 and not stat.S_IMODE(s.st_mode) & 0o077 and 0 < s.st_size <= cap,
             'original_file_identity')
        identities[name] = contract.local_identity(s)
        files[name] = {'bytes': s.st_size, 'sha256': contract.local_hash(path)}
        need(contract.local_identity(path.stat()) == identities[name], 'original_changed_during_hash')
    need(files[original.name]['sha256'] == a.provenance_sha256, 'original_provenance_changed')
    base = BASE / 'local-image-artifacts-20261024'
    offloaded_receiver = a.service in ['unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb']
    if offloaded_receiver:
        mount = BASE / 'local-image-build-offload-20261025'
        need(mount.is_mount() and mount.resolve() == mount and mount.stat().st_uid == 1000
             and mount.stat().st_dev != os.stat('/').st_dev, 'dedicated_receiver_mount')
        filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'UUID,FSTYPE', '--target', str(mount)], timeout=10).decode().split()
        need(filesystem == [contract.OFFLOAD_STORAGE['filesystem_uuid'], 'ext4'], 'dedicated_receiver_filesystem')
        base = mount / 'local-image-artifacts-20261025'
    need(base.resolve() == base, 'sealed_base_path')
    base.mkdir(mode=0o700, exist_ok=True)
    s = base.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid == 1000 and stat.S_IMODE(s.st_mode) == 0o700,
         'sealed_base_identity')
    dest = base / (a.service + '-' + a.run_id)
    need(not dest.exists() and not dest.is_symlink(), 'sealed_destination_exists')
    v = os.statvfs(base); total = sum(row['bytes'] for row in files.values())
    def physical_capacity(pending=0):
        drive = 'F:\\' if offloaded_receiver else 'C:\\'
        script = "[pscustomobject]@{cFreeBytes=[IO.DriveInfo]::new('C:\\').AvailableFreeSpace;destinationFreeBytes=[IO.DriveInfo]::new('" + drive + "').AvailableFreeSpace}|ConvertTo-Json -Compress"
        probe = subprocess.run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, timeout=20)
        need(probe.returncode == 0, 'physical_capacity_probe')
        observed = json.loads(probe.stdout)
        # Launch-only15GiB check. Existing copies retain their original lower
        # emergency reserve; do not interrupt running work for the new guard.
        floor = (15 if pending else 2)*1024**3
        if pending:
            need(observed['cFreeBytes'] >= 15*1024**3, 'agent_launch_windows_c_below_15GiB')
        need(observed['destinationFreeBytes'] >= pending + floor, 'physical_backing_reserve')
        local = os.statvfs(base)
        need(local.f_bavail*local.f_frsize >= pending + floor, 'native_receiver_reserve')
    physical_capacity(total)
    need(v.f_bavail * v.f_frsize >= total + 2 * 1024 ** 3 and v.f_favail >= v.f_files // 10,
         'receiver_capacity')
    dest.mkdir(mode=0o700)
    for name in sorted(files):
        path = dest / name
        last_capacity = time.monotonic()
        with (source / name).open('rb') as old, path.open('xb') as new:
            for block in iter(lambda: old.read(1024**2), b''):
                new.write(block)
                if time.monotonic()-last_capacity >= 5:
                    physical_capacity();last_capacity = time.monotonic()
            new.flush(); os.fsync(new.fileno())
        physical_capacity()
        path.chmod(0o400)
        need(contract.local_identity((source / name).stat()) == identities[name] and contract.local_hash(source / name) == files[name]['sha256'],
             'original_changed_during_copy')
    proof = {'schemaVersion': 1, 'sourceKind': 'local-operator', 'repository': 'jtmb/branconet-charts',
             'service': a.service, 'runID': a.run_id, 'files': files, 'githubActionsIdentityClaimed': False,
             'verificationBoundary': 'Exact trusted local operator build and source proof; no scan/runtime/deployment acceptance.'}
    proof_path = dest / 'provenance.json'
    with proof_path.open('x') as stream:
        json.dump(proof, stream, sort_keys=True, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    proof_path.chmod(0o400)
    proof_sha = contract.local_hash(proof_path)
    verified = contract.local_verify(dest, a.service, a.run_id, proof_sha, 1000)
    print(json.dumps({'state': 'received-not-scanned-not-deployed', 'root': str(dest),
                      'provenanceSHA256': proof_sha, **verified}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'refused-originals-and-partial-copy-retained',
                          'category': str(error) if type(error) is ValueError else type(error).__name__}))
        raise SystemExit(1)
