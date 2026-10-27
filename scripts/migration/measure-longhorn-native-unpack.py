"""Qualify pinned upstream image unpacking in an isolated disposable controller.

Exports existing public node binaries read-only. No cluster writes, containers,
production-runtime connection, image publication or runtime pruning.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
B = F / 'platform-upstream-review-20261027/longhorn-capacity-budget'
R = B / 'native-unpack-20261027'
S = R / 'scratch'
UNIT = 'branconet-longhorn-native-unpack-20261027'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
PEAK = 8 * 1024**3


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(name, value):
    with (R / name).open('x') as out:
        json.dump(value, out, indent=2)
    os.chown(R / name, 1000, 1000)


def call(args, timeout=90):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    need(p.returncode == 0 and len(p.stdout) <= 8 * 1024**2,
         'bounded_required_command_' + Path(args[0]).name)
    return p.stdout


def space(path):
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize


def inputs():
    p = B / 'measurement-result.json'
    data = json.loads(p.read_text())
    need(data['status'] == 'completed' and data['allLayersFullyAuthenticated'], 'original_full_layer_authentication')
    images = [i for i in data['images'] if '/longhorn-cli:' not in i['reference']]
    need(len(images) == 13 and all(i['reference'].startswith('docker.io/longhornio/')
         and '@sha256:' in i['reference'] for i in images), 'exact_thirteen_consumed_public_candidates')
    return images, {'measurementSHA256': sha(p), 'operatorSHA256': sha(Path(__file__))}


def worker():
    need(os.environ.get('BRANCONET_NATIVE_UNPACK') == UNIT, 'isolated_private_unit_required')
    props = dict(line.split('=', 1) for line in call(['systemctl', 'show', UNIT + '.service',
        '-p', 'MemoryMax', '-p', 'MemorySwapMax', '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax']).decode().splitlines())
    need(all(props.get(k) == v for k, v in {'MemoryMax': '536870912', 'MemorySwapMax': '0',
         'CPUQuotaPerSecUSec': '1s', 'TasksMax': '96'}.items()), 'actual_bounded_worker_resources')
    images, binding = inputs()
    need(binding == json.loads((R / 'ownership.json').read_text())['sourceBinding'], 'frozen_original_inputs')
    S.mkdir(mode=0o700)
    (S / 'tmp').mkdir()
    os.environ.update(TMPDIR=str(S / 'tmp'), TMP=str(S / 'tmp'), TEMP=str(S / 'tmp'))
    tools = S / 'tools'
    tools.mkdir()
    exports = {}
    for name in ('containerd', 'ctr'):
        source = '/opt/containerd-k8s/bin/' + name
        before = call(SSH + ['sha256sum', source]).decode().split()[0]
        target = tools / name
        with target.open('xb') as out:
            p = subprocess.run(SSH + ['cat', source], stdout=out, stderr=subprocess.PIPE, timeout=120)
        need(p.returncode == 0 and target.stat().st_size < 128 * 1024**2, 'bounded_existing_public_binary_export')
        after = call(SSH + ['sha256sum', source]).decode().split()[0]
        need(before == after == sha(target), 'complete_node_binary_before_after_hash')
        target.chmod(0o700)
        version = call([str(target), '--version']).decode().strip()
        need('v2.4.2' in version, 'exact_production_containerd_generation')
        exports[name] = {'originalNode': '192.168.0.4', 'source': source, 'sha256': before,
                         'bytes': target.stat().st_size, 'version': version}
    save('public-binary-exports.json', exports)
    original_default = call([str(tools / 'containerd'), 'config', 'default']).decode()
    need(original_default.startswith('version = 4\n'), 'actual_native_config_version')
    save('native-default-config.json', {'text': original_default, 'sha256': hashlib.sha256(original_default.encode()).hexdigest()})
    fd = os.open(S, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    need(Path(alias).resolve() == S, 'owned_short_socket_path_resolves_inside_F')
    address = alias + '/containerd.sock'
    config = ('version = 4\nroot = ' + repr(str(S / 'root')) + '\nstate = ' + repr(alias + '/state')
              + '\ntemp = ' + repr(str(S / 'tmp')) + '\nimports = []\n'
              + 'disabled_plugins = ["io.containerd.cri.v1.images", "io.containerd.cri.v1.runtime", '
              + '"io.containerd.grpc.v1.cri", "io.containerd.nri.v1.nri"]\n'
              + '[plugins."io.containerd.server.v1.grpc"]\naddress = ' + repr(address) + '\nuid = 0\ngid = 0\n'
              + '[plugins."io.containerd.server.v1.ttrpc"]\naddress = ' + repr(alias + '/containerd.sock.ttrpc') + '\n'
              + '[plugins."io.containerd.server.v1.grpc-tcp"]\naddress = ""\n'
              + '[plugins."io.containerd.server.v1.metrics"]\naddress = ""\n'
              + '[plugins."io.containerd.server.v1.debug"]\naddress = ""\n')
    (R / 'native-config.toml').write_text(config)
    os.chown(R / 'native-config.toml', 1000, 1000)
    ctr = [str(tools / 'ctr'), '--address', address, '--namespace', 'migration-unpack', '--timeout', '10m']
    result = {'status': 'started', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceBinding': binding, 'exports': exports, 'resourceBudget': props,
              'clusterChanged': False, 'containersStarted': False, 'images': []}
    daemon = None
    try:
        with (R / 'native-daemon.log').open('xb') as log:
            daemon = subprocess.Popen([str(tools / 'containerd'), '--config', str(R / 'native-config.toml')],
                                      stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, TMPDIR=str(S / 'tmp')))
            for _ in range(100):
                need(daemon.poll() is None, 'private_daemon_stayed_active')
                if (S / 'containerd.sock').exists():
                    break
                time.sleep(0.1)
            need((S / 'containerd.sock').is_socket(), 'private_F_socket_ready')
            call(ctr + ['version'])
            need(not call(ctr + ['containers', 'list', '--quiet']).strip(), 'no_private_containers')
            for image in images:
                need(space(F) >= 15 * 1024**3 + PEAK, 'unchanged_full_peak_and_free_floor_before_each_pull')
                name = image['reference'].split('/')[2].split(':')[0]
                with (R / (name + '-pull.log')).open('xb') as pull:
                    p = subprocess.run(ctr + ['images', 'pull', '--local', '--platform', 'linux/amd64',
                        '--snapshotter', 'overlayfs', '--skip-metadata', '--max-concurrent-downloads', '1',
                        image['reference']], stdout=pull, stderr=subprocess.STDOUT, timeout=600)
                need(p.returncode == 0, 'native_pull_' + name)
                parent, verified = '', []
                for layer in image['layers']:
                    blob = S / 'root/io.containerd.content.v1.content/blobs/sha256' / layer['digest'][7:]
                    need(blob.stat().st_size == layer['compressedBytes'] and sha(blob) == layer['digest'][7:], 'exact_native_content_blob')
                    key = layer['diffID'] if not parent else 'sha256:' + hashlib.sha256((parent + ' ' + layer['diffID']).encode()).hexdigest()
                    info = json.loads(call(ctr + ['snapshots', '--snapshotter', 'overlayfs', 'info', key]))
                    need(info['Name'] == key and info.get('Parent', '') == parent and info['Kind'] == 'Committed', 'complete_committed_native_chain')
                    verified.append({'chainID': key, 'parent': parent, 'diffID': layer['diffID'], 'blobSHA256': layer['digest']})
                    parent = key
                used = int(call(['du', '-s', '-B1', str(S)]).decode().split()[0])
                need(used <= PEAK, 'declared_complete_peak_not_exceeded')
                result['images'].append({'reference': image['reference'], 'amd64ManifestDigest': image['amd64ManifestDigest'],
                    'chains': verified, 'allocatedPrivateFilesystemBytesAfterImage': used})
                print(json.dumps({'nativeUnpacked': name, 'verifiedLayers': len(verified), 'allocatedBytes': used}), flush=True)
            need(not call(ctr + ['containers', 'list', '--quiet']).strip(), 'no_container_started_during_qualification')
            result.update(status='all_thirteen_native_unpacks_verified',
                actualAllocatedBytes=int(call(['du', '-s', '-B1', str(S)]).decode().split()[0]),
                nativeSnapshotter='overlayfs', nativeControllerFilesystem='ext4',
                directProductionNodeUnpackClaimed=False)
    except Exception as e:
        result.update(status='failed', failedCheck=str(e) if isinstance(e, ValueError) else type(e).__name__)
        raise
    finally:
        if daemon is not None:
            if daemon.poll() is None:
                daemon.terminate()
            try:
                daemon.wait(timeout=30)
            except subprocess.TimeoutExpired:
                # Do not force-kill or retire a tree still owned by a live process.
                result['privateDaemonStillActive'] = True
            result['privateDaemonExitCode'] = daemon.poll()
        os.close(fd)
        save('native-result.json', result)


def reconcile():
    # This runs only after the private systemd worker has ended. Never stop a
    # workload or bypass a mount/reference refusal to make cleanup succeed.
    need(S.resolve() == S and S.parent == R and not S.is_mount(), 'exact_owned_scratch')
    need(shutil.rmtree.avoids_symlink_attacks, 'safe_recursive_primitive')
    guard = F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
    raw = guard.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'original_full_reference_guard')
    scope = {'__name__': 'native_unpack_cleanup_guard'}
    exec(compile(raw, str(guard), 'exec'), scope)
    scope.update(BASE=F, ATTEMPTS=(str(S.relative_to(F)),))
    scope['idle']()
    images, binding = inputs()
    need(binding == json.loads((R / 'ownership.json').read_text())['sourceBinding'], 'original_sources_preserved_before_cleanup')
    size = int(call(['du', '-s', '-B1', str(S)]).decode().split()[0])
    # There are no source repositories or required runtime artifacts in this
    # private generated tree. Public tools and every layer have pinned recipes.
    need(not any(p.name == '.git' for p in S.rglob('.git')), 'no_source_repository_in_generated_scratch')
    before = space(F)
    shutil.rmtree(S)
    need(not S.exists(), 'complete_private_scratch_removed')
    save('scratch-reconciliation.json', {'status': 'completed', 'removedPath': str(S),
        'removedAllocatedLinuxBytes': size, 'availableBeforeBytes': before, 'availableAfterBytes': space(F),
        'sourceBindingUnchanged': True, 'WindowsRecoveryClaimed': False,
        'regeneration': 'Read-only export the hash-bound node containerd/ctr; use this frozen operator and original pinned public image manifests',
        'remainingConsumer': None, 'productionImagesPruned': False})
    print(json.dumps({'scratchRemovedAllocatedLinuxBytes': size, 'availableAfterBytes': space(F)}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker', action='store_true')
    args = p.parse_args()
    need(os.geteuid() == 0 and F.is_mount() and F.resolve() == F, 'root_existing_authorized_filesystem')
    fs = json.loads(call(['findmnt', '-J', '-T', str(F), '-o', 'UUID,FSTYPE']))['filesystems'][0]
    need(fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b' and fs['fstype'] == 'ext4', 'same_declared_physical_volume')
    os.umask(0o077)
    if args.worker:
        worker()
        return
    need(not R.exists(), 'original_attempt_preserved')
    need(space('/mnt/c') >= 15 * 1024**3 and space(F) >= 15 * 1024**3 + PEAK, 'measured_C_and_destination_peak_floor')
    images, binding = inputs()
    R.mkdir(mode=0o700)
    os.chown(R, 1000, 1000)
    save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
        'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'sourceBinding': binding,
        'peakDisposableBytes': PEAK, 'generatedPaths': [str(S), str(R / '*.json'), str(R / '*.log'), str(R / 'native-config.toml')],
        'availableCBeforeBytes': space('/mnt/c'), 'availableDestinationBeforeBytes': space(F),
        'protected': 'all original inputs, source, deployed runtimes, workload data, recovery archives and failures',
        'lastConsumer': 'one exact native image-unpack observation',
        'endCondition': 'worker and private daemon exit; full reference/source checks; remove all generated tools/content/snapshots',
        'regeneration': 'this frozen operator, read-only hash-bound installed node binaries and the original thirteen pinned upstream manifests'})
    props = ['MemoryMax=536870912', 'MemorySwapMax=0', 'CPUQuota=100%', 'TasksMax=96',
             'Nice=15', 'UMask=0077', 'ProtectSystem=strict', 'ReadWritePaths=' + str(R),
             'WorkingDirectory=/home/brajam', 'RuntimeMaxSec=1800', 'KillMode=control-group', 'NoNewPrivileges=yes']
    code = 1
    try:
        with (R / 'worker.log').open('xb') as out:
            code = subprocess.run(['systemd-run', '--quiet', '--wait', '--pipe', '--collect', '--unit=' + UNIT,
                '--setenv=BRANCONET_NATIVE_UNPACK=' + UNIT,
                *['--property=' + x for x in props], '/usr/bin/python3', '-B', str(Path(__file__).resolve()), '--worker'],
                stdout=out, stderr=subprocess.STDOUT).returncode
    finally:
        save('worker-terminal.json', {'exitCode': code, 'sourceBinding': binding,
             'completedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        if S.exists():
            try:
                reconcile()
            except Exception as e:
                save('scratch-retained-safety-exception.json', {'status': 'retained_failed_safety_check',
                    'exactPath': str(S), 'failedCheck': str(e) if isinstance(e, ValueError) else type(e).__name__,
                    'alternatePathOrToolRetryPermitted': False})
                raise
    raise SystemExit(code)


if __name__ == '__main__':
    main()
