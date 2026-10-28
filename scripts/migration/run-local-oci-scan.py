#!/usr/bin/env python3
"""Explicit locally bounded scan setup/launch; never contacts the cluster or Actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import uuid

LEGACY_ROOT = Path('/home/brajam/.local/share/branconet-migration/local-oci-scan-20261024')
FBASE = LEGACY_ROOT.parent / 'local-image-build-offload-20261025'
ROOT = FBASE / 'local-oci-scan'
SERVICES = ['seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden', 'tautulli', 'wordpress', 'nginx', 'phpmyadmin', 'coredns', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot', 'bazarr', 'radarr', 'sonarr', 'whoami', 'traefik']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--phase', choices=['setup', 'scan', 'status'], default='status')
    p.add_argument('--service', choices=SERVICES)
    p.add_argument('--attempt', default='')
    p.add_argument('--source-kind', choices=['github-actions', 'local-operator'], default='local-operator')
    p.add_argument('--ci-run-id', type=int, default=0)
    p.add_argument('--ci-artifact-id', type=int, default=0)
    p.add_argument('--ci-provenance-sha256', default='')
    p.add_argument('--local-run-id', default='')
    p.add_argument('--local-provenance-sha256', default='')
    p.add_argument('--archive-sha256', default='')
    p.add_argument('--root-descriptor', default='')
    p.add_argument('--storage-profile', choices=['legacy', 'offloaded'], default='offloaded')
    a = p.parse_args()
    need(a.phase == 'status' or a.storage_profile == 'offloaded', 'new_work_requires_native_F')
    # Even read-only legacy status subprocesses receive F-only scratch paths.
    os.environ.update(HOME=str(FBASE/'local-oci-scan/home'), TMPDIR=str(FBASE/'local-oci-scan/tmp'),
                      TEMP=str(FBASE/'local-oci-scan/tmp'), TMP=str(FBASE/'local-oci-scan/tmp'),
                      XDG_CACHE_HOME=str(FBASE/'local-oci-scan/cache'),
                      XDG_CONFIG_HOME=str(FBASE/'local-oci-scan/home/.config'),
                      XDG_DATA_HOME=str(FBASE/'local-oci-scan/home/.local/share'))
    if a.storage_profile == 'offloaded':
        need(a.phase != 'scan' or (a.service in ['coredns', 'jackett', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot', 'bazarr', 'radarr', 'sonarr', 'whoami', 'traefik'] and a.source_kind == 'local-operator')
             or (a.service == 'jackett' and a.source_kind == 'github-actions'), 'finite_offloaded_scan_scope')
        need(FBASE.resolve() == FBASE and FBASE.is_mount() and FBASE.stat().st_dev != Path('/').stat().st_dev,
             'dedicated_storage_mounted')
    else:
        ROOT = LEGACY_ROOT
    need(os.getuid() == 1000 and 'microsoft' in Path('/proc/sys/kernel/osrelease').read_text().lower(), 'native_WSL_operator')
    os.umask(0o077)
    source = Path(__file__).resolve().with_name('scan-local-oci.py')
    data = source.read_bytes(); need(0 < len(data) <= 256 * 1024, 'reviewed_helper_size')
    sha = hashlib.sha256(data).hexdigest()
    helper_root = ROOT / 'helpers' / sha
    helper = helper_root / 'scan-local-oci.py'
    if a.phase == 'status':
        # Current source reads old receipts without writing a new C-backed helper.
        cmd = ['/usr/bin/python3', '-B', str(source), 'status', '--storage-profile', a.storage_profile]
        if a.service and a.attempt:
            need(re.fullmatch('[0-9a-f]{12}', a.attempt), 'attempt_identity')
            cmd += ['--service', a.service, '--attempt', a.attempt]
        return subprocess.run(cmd, check=False).returncode
    need(a.apply, 'explicit_apply_required')
    # C remains a launch prerequisite, never a new output destination.
    windows_c = os.statvfs('/mnt/c')
    need(windows_c.f_bavail * windows_c.f_frsize >= 15*1024**3, 'windows_C_launch_15GiB_floor')
    capacity = os.statvfs(FBASE)
    physical = os.statvfs('/mnt/f')
    need(capacity.f_bavail*capacity.f_frsize >= 23*1024**3 and
         physical.f_bavail*physical.f_frsize >= 23*1024**3,
         'native_and_physical_F_launch_15GiB_plus_full_8GiB_cap')
    need(capacity.f_favail >= max(250000, capacity.f_files//10), 'inode_reserve')
    need(ROOT.resolve() == ROOT, 'native_root_path')
    for suffix in ['', 'bin', 'cache', 'cache/db', 'cache/java-db', 'tmp', 'home', 'docker-config', 'attempts', 'helpers', 'helpers/' + sha]:
        path = ROOT / suffix
        if path.exists():
            info = path.lstat()
            need(path.resolve() == path and stat.S_ISDIR(info.st_mode) and info.st_uid == 1000 and
                 stat.S_IMODE(info.st_mode) == 0o700 and info.st_dev == FBASE.stat().st_dev, 'existing_private_directory')
        else:
            path.mkdir(mode=0o700)
    if helper.exists():
        info = helper.lstat()
        need(helper.resolve() == helper and stat.S_ISREG(info.st_mode) and info.st_uid == 1000 and info.st_nlink == 1 and
             stat.S_IMODE(info.st_mode) == 0o500 and hashlib.sha256(helper.read_bytes()).hexdigest() == sha, 'immutable_helper_identity')
    else:
        with helper.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        helper.chmod(0o500)
    ident = uuid.uuid4().hex[:12]
    if a.phase == 'setup':
        unit = 'branconet-local-oci-setup-' + ident + '.service'
        argv = ['setup', '--apply', '--unit', unit]
    else:
        need(a.service and re.fullmatch('[0-9a-f]{64}', a.archive_sha256) and
             re.fullmatch('sha256:[0-9a-f]{64}', a.root_descriptor), 'exact_image_identity')
        if a.source_kind == 'github-actions':
            need(0 < a.ci_run_id < 2 ** 63 and 0 < a.ci_artifact_id < 2 ** 63 and
                 re.fullmatch('[0-9a-f]{64}', a.ci_provenance_sha256) and
                 not a.local_run_id and not a.local_provenance_sha256, 'historical_CI_proof')
        else:
            need(re.fullmatch('[0-9a-f]{32}', a.local_run_id) and
                 re.fullmatch('[0-9a-f]{64}', a.local_provenance_sha256) and
                 a.ci_run_id == a.ci_artifact_id == 0 and not a.ci_provenance_sha256, 'local_operator_proof')
        a.attempt = a.attempt or ident
        need(re.fullmatch('[0-9a-f]{12}', a.attempt) and not (ROOT / 'attempts' / (a.service + '-' + a.attempt)).exists(), 'exclusive_new_attempt')
        unit = 'branconet-local-oci-scan-' + a.service + '-' + a.attempt + '.service'
        argv = ['run', '--apply', '--service', a.service, '--attempt', a.attempt,
                '--source-kind', a.source_kind, '--archive-sha256', a.archive_sha256, '--root-descriptor', a.root_descriptor,
                '--ci-run-id', str(a.ci_run_id), '--ci-artifact-id', str(a.ci_artifact_id), '--ci-provenance-sha256', a.ci_provenance_sha256,
                '--local-run-id', a.local_run_id, '--local-provenance-sha256', a.local_provenance_sha256]
    log = ROOT / ('unit-' + ident + '.log'); log.touch(mode=0o600)
    cmd = ['systemd-run', '--user', '--unit=' + unit, '--property=Type=exec',
           '--property=MemoryMax=1073741824', '--property=MemorySwapMax=0', '--property=CPUQuota=200%',
           '--property=TasksMax=128', '--property=Nice=10', '--property=UMask=0077', '--property=RuntimeMaxSec=900',
           '--property=TimeoutStopSec=30', '--property=KillMode=control-group', '--property=LimitFSIZE=4294967296',
           '--property=PrivateUsers=yes', '--property=PrivateNetwork=yes', '--property=PrivateDevices=yes',
           '--property=NoNewPrivileges=yes', '--property=ProtectSystem=strict', '--property=ProtectHome=read-only',
           '--property=ProtectKernelTunables=yes', '--property=ProtectKernelModules=yes', '--property=ProtectControlGroups=yes',
           '--property=ReadWritePaths=' + str(ROOT),
           '--property=InaccessiblePaths=-/tmp -/var/tmp -/home/brajam/.ssh -/root -/mnt/c/Users -/run/docker.sock -/var/run/docker.sock -/run/containerd -/run/containerd-k8s',
           '--property=NoExecPaths=' + str(ROOT / 'cache') + ' ' + str(ROOT / 'tmp') + ' ' + str(ROOT / 'attempts'),
           '--property=StandardOutput=append:' + str(log), '--property=StandardError=append:' + str(log)]
    if a.phase == 'scan':
        cmd += ['--property=ReadOnlyPaths=' + str(ROOT / 'cache/db') + ' ' + str(ROOT / 'cache/java-db')]
    cmd += ['--', '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'LANG=C', 'LC_ALL=C',
            'XDG_RUNTIME_DIR=/run/user/1000', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
            'HOME='+str(ROOT/'home'), 'TMPDIR='+str(ROOT/'tmp'), 'TEMP='+str(ROOT/'tmp'), 'TMP='+str(ROOT/'tmp'),
            'XDG_CACHE_HOME='+str(ROOT/'cache'), 'XDG_CONFIG_HOME='+str(ROOT/'home/.config'),
            'XDG_DATA_HOME='+str(ROOT/'home/.local/share'),
            'GOMAXPROCS=2', 'GOMEMLIMIT=512MiB', '/usr/bin/python3', '-I', '-B', str(helper), *argv]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    record = {'executionHostKind': 'wsl-local-operator', 'phase': a.phase, 'unit': unit, 'helperSHA256': sha,
              'storageProfile': a.storage_profile,
              'storagePolicy': {'launchNativeAndPhysicalFBytes': 23*1024**3, 'retainedNativeAndPhysicalFBytes': 15*1024**3,
                                'aggregateCapBytes': 8*1024**3, 'windowsCLaunchFloorBytes': 15*1024**3,
                                'replacesOffloadedReserveOnly': '25percent-plus8GiB'},
              'sourceKind': a.source_kind if a.phase == 'scan' else None, 'service': a.service,
              'attempt': a.attempt if a.phase == 'scan' else None, 'startExitCode': result.returncode, 'startupDiagnostic': result.stderr[-2000:] if result.returncode else None,
              'unitLog': str(log), 'scanComplete': False, 'securityAcceptance': False}
    with (ROOT / ('launch-' + ident + '.json')).open('x') as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))
    return result.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit('Local scanner launcher refused; raw diagnostics withheld (' + type(error).__name__ + ')')
