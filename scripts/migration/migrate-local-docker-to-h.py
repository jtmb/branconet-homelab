#!/usr/bin/env python3
"""Move idle WSL Docker/containerd state to the existing approved H Linux store."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

STORE = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files')
BACKING = STORE.parent / 'branconet-artifacts.ext4'
ROOT = STORE / 'shared-docker-runtime'
RECEIPT = ROOT / 'migration.json'
SERVICES = ['docker.socket', 'docker.service', 'containerd.service']
CONFIGS = [Path('/etc/docker/daemon.json'), Path('/etc/containerd/config.toml')]
DROPS = [Path('/etc/systemd/system') / (s + '.d') / name
         for name in ['90-agent-artifacts.conf', '91-agent-artifacts-temp.conf']
         for s in ['docker.service', 'containerd.service']]


def run(args, timeout=30):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout).stdout


def save(record):
    temporary = ROOT / 'migration.next'
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(RECEIPT)


def active_consumers():
    if run(['docker', 'ps', '-aq']).strip():
        raise RuntimeError('Existing containers require separate consumer reconciliation')
    for namespace in run(['ctr', 'namespaces', 'list', '-q']).splitlines():
        if namespace not in ('moby', 'moby_history'):
            raise RuntimeError('Unrelated containerd namespace present')
        if run(['ctr', '--namespace', namespace, 'tasks', 'list', '-q']).strip():
            raise RuntimeError('Active containerd task present')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:
            continue
        if argv and Path(os.fsdecode(argv[0])).name in ('docker', 'docker-buildx', 'buildctl'):
            if any(x in argv for x in (b'build', b'bake', b'import', b'load')):
                raise RuntimeError('Active image writer present')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Local root required')
    device = run(['findmnt', '--mountpoint', str(STORE), '-n', '-o', 'SOURCE']).strip()
    if not re.fullmatch(r'/dev/loop\d+', device):
        raise RuntimeError('Approved H Linux store is not mounted')
    loop = json.loads(run(['losetup', '--list', '--json', '--output', 'NAME,BACK-FILE', device]))
    if Path(loop['loopdevices'][0]['back-file']).resolve() != BACKING.resolve():
        raise RuntimeError('Store is not backed by the approved H file')
    resume = sys.argv[1:] == ['--resume']
    if sys.argv[1:] and not resume:
        raise RuntimeError('Only the explicit --resume recovery option is supported')
    if ROOT.exists():
        if not resume:
            raise RuntimeError('Destination already exists; preserve and reconcile its receipt')
        previous = json.loads(RECEIPT.read_text())
        if (previous.get('owner') != 'BORTUS Delivery and Cluster Operations' or
                previous.get('root') != str(ROOT) or previous.get('state') not in ('preflight', 'failed-preserved')):
            raise RuntimeError('Existing destination is not an admitted interrupted copy')
        if json.loads(CONFIGS[0].read_text()).get('data-root') is not None:
            raise RuntimeError('The original Docker configuration is no longer active')
        for i, p in enumerate(CONFIGS):
            if (ROOT / 'configuration-backup' / str(i)).read_bytes() != p.read_bytes():
                raise RuntimeError('Original runtime configuration changed since the interrupted copy')
    active_consumers()
    images = run(['docker', 'image', 'ls', '--no-trunc', '--digests', '--format', '{{.Repository}}:{{.Tag}} {{.ID}} {{.Digest}}']).splitlines()
    source_bytes = sum(int(run(['du', '-sx', '-B1', p]).split()[0])
                       for p in ['/var/lib/docker', '/var/lib/containerd'])
    if source_bytes > 100_000_000_000 or shutil.disk_usage(STORE).free < source_bytes + 15 * 1024**3:
        raise RuntimeError('Shared runtime migration capacity check failed')
    original = {p: p.read_bytes() if p.exists() else None for p in CONFIGS + DROPS}
    ROOT.mkdir(mode=0o700, exist_ok=resume)
    backup = ROOT / 'configuration-backup'
    backup.mkdir(mode=0o700, exist_ok=resume)
    for i, (p, raw) in enumerate(original.items()):
        if raw is not None:
            b = backup / str(i)
            b.write_bytes(raw)
            b.chmod(0o600)
    record = {'owner': 'BORTUS Delivery and Cluster Operations', 'state': 'preflight',
              'purpose': 'Shared Docker runtime on H; no image build or prune',
              'backing': str(BACKING), 'root': str(ROOT), 'source_allocated_bytes': source_bytes,
              'baseline_images': images, 'configuration_backup_paths': [str(p) for p in original],
              'originals_retained': ['/var/lib/docker', '/var/lib/containerd'],
              'originals_end_condition': 'Verified H runtime and exact inactivity/preservation checks before source retirement'}
    save(record)
    print(json.dumps({'state': 'copying-existing-state', 'allocated_bytes': source_bytes}), flush=True)
    changed = False
    try:
        run(['systemctl', 'stop', *SERVICES], 90)
        if any(subprocess.run(['systemctl', 'is-active', '--quiet', s]).returncode == 0 for s in SERVICES):
            raise RuntimeError('Runtime services did not stop')
        for name in ['docker', 'containerd']:
            target = ROOT / name
            target.mkdir(mode=0o700, exist_ok=resume)
            source = '/var/lib/' + name + '/'
            run(['rsync', '-aHAX', '--numeric-ids', '--one-file-system', source, str(target) + '/'], 900)
            delta = run(['rsync', '-aHAXnc', '--numeric-ids', '--one-file-system', '--itemize-changes', source, str(target) + '/'], 900)
            if delta.strip():
                raise RuntimeError('Copied runtime state differs from source')
            print(json.dumps({'state': 'verified-copy', 'store': name}), flush=True)
        changed = True
        docker = json.loads(original[CONFIGS[0]] or b'{}')
        docker['data-root'] = str(ROOT / 'docker')
        CONFIGS[0].write_text(json.dumps(docker, indent=2) + '\n')
        containerd = (original[CONFIGS[1]] or b'').decode()
        if re.search(r'^root\s*=', containerd, re.M):
            containerd = re.sub(r'^root\s*=.*$', 'root = ' + json.dumps(str(ROOT / 'containerd')), containerd, count=1, flags=re.M)
        else:
            containerd = 'root = ' + json.dumps(str(ROOT / 'containerd')) + '\n' + containerd
        CONFIGS[1].write_text(containerd)
        for drop in DROPS:
            drop.parent.mkdir(exist_ok=True)
            if drop.name == '90-agent-artifacts.conf':
                drop.write_text('[Unit]\nRequiresMountsFor=' + str(STORE) + '\n\n[Service]\n'
                                'ExecStartPre=/usr/bin/findmnt --mountpoint ' + str(STORE) +
                                ' --types ext4 --noheadings --output TARGET\n')
            else:
                temporary = ROOT / 'temp' / drop.parent.name.removesuffix('.service.d')
                temporary.mkdir(mode=0o700, parents=True, exist_ok=True)
                drop.write_text('[Service]\nEnvironment="TMPDIR=' + str(temporary) +
                                '" "TEMP=' + str(temporary) + '" "TMP=' + str(temporary) + '"\n')
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'containerd.service', 'docker.socket', 'docker.service'], 120)
        info = json.loads(run(['docker', 'info', '--format', '{{json .}}']))
        if info.get('DockerRootDir') != str(ROOT / 'docker'):
            raise RuntimeError('Docker did not adopt H data root')
        current_images = run(['docker', 'image', 'ls', '--no-trunc', '--digests', '--format', '{{.Repository}}:{{.Tag}} {{.ID}} {{.Digest}}']).splitlines()
        if sorted(images) != sorted(current_images):
            raise RuntimeError('Existing image identity changed')
        for name in ['docker', 'containerd']:
            if os.stat(ROOT / name).st_dev != os.stat(STORE).st_dev:
                raise RuntimeError('Runtime backing differs from H store')
        record.update(state='completed', completed_unix=time.time(), copied_checksum_verified=True,
                      docker_root=info['DockerRootDir'], containerd_root=str(ROOT / 'containerd'),
                      baseline_images_preserved=True, mount_dependency_enabled=True)
        save(record)
        print(json.dumps({'state': 'completed', 'docker_root': info['DockerRootDir'],
                          'containerd_root': str(ROOT / 'containerd'), 'baseline_images_preserved': True}), flush=True)
    except BaseException:
        if changed:
            subprocess.run(['systemctl', 'stop', *SERVICES], timeout=90)
            for p, raw in original.items():
                if raw is None:
                    if p.exists():
                        p.unlink()
                else:
                    p.write_bytes(raw)
            subprocess.run(['systemctl', 'daemon-reload'], timeout=30)
        subprocess.run(['systemctl', 'start', 'containerd.service', 'docker.socket', 'docker.service'], timeout=120)
        record.update(state='failed-preserved', configuration_rolled_back=changed)
        save(record)
        raise


if __name__ == '__main__':
    main()
