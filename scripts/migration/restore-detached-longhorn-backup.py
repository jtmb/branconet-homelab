"""Independently restore an explicitly completed detached NAS backup in F scratch.

No production restore, mount, Secret read, image pull or package installation.
Stages: tools (WSL), nas (Windows), restore (isolated WSL systemd service).
"""
import argparse
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
REL = 'platform-upstream-review-20261027/detached-volume-backups-20261027'
R = F / REL
WINDOWS_F = Path(r'\\?\UNC\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
VOLUME = 'pvc-9317472a-a68f-4a2b-ad93-5d02e91492b0'
BACKUP = 'migration-preserve-cc51ac63e008-backup'
ALIAS = 'storage-proof'
ALLOWED = {
    'storage-proof': VOLUME,
    'storage-restored': 'pvc-8e780ab5-6f6d-4c93-8b2b-4410da2e841f',
    'nas-bortus-restore': 'pvc-ba85233b-81d5-4061-9f7b-feff295071e0',
    'bortus-restore': 'pvc-42bafa5c-bf7a-4751-8fc3-ba3104a76784',
    'pihole-old-0': 'pvc-224e40cf-cfd1-488a-bab6-545568c8e4f7',
    'pihole-old-1': 'pvc-bd9d5442-8665-4328-9a62-53d03d704ca7',
    'gluetun-old': 'pvc-2d2591cd-8809-4957-b56a-2f4d405bd9e2',
    'qbittorrent-old': 'pvc-6aa3aaa5-f609-4f74-88f0-b5c15e846703',
    'ruckus-old': 'pvc-0bf707c8-628e-4284-9aa0-35b711c8749b',
}
CONTEXT = None
POD = 'instance-manager-0f44e66d715a28714766cec73f9ec067'
POD_UID = '8e75c63b-70ff-40f6-b18b-27d989d9750b'
IMAGE_ID = 'docker.io/longhornio/longhorn-instance-manager@sha256:b255f3279dd9d830ea153e9369928646dee519fd853036388926dddb5c66094b'
ENGINE = '/var/lib/longhorn/engine-binaries/docker.io-longhornio-longhorn-engine-v1.12.1/longhorn'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o',
       'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def save(path, data):
    with path.open('x', encoding='utf-8') as out:
        json.dump(data, out, indent=2)


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def context(root, alias):
    global ALIAS, VOLUME, BACKUP, CONTEXT
    run = root / alias
    profile = json.loads((run / 'profile.json').read_text())
    result = json.loads((run / 'apply-result.json').read_text())
    backup = json.loads((run / 'completed-backup.json').read_text())
    attached = json.loads((run / 'attached-proof.json').read_text())
    need(profile['volume']['metadata']['name'] == ALLOWED[alias] == result['volume'] == backup['status']['volumeName'], 'fixed_completed_dataset')
    need(result['status'] == 'completed_native_backup_and_detach' and result['originalVolumeSpecRestored']
         and result['originalReplicaUIDsPreserved'] and result['detachedAgain']
         and result['coldNoFrontendNoConsumer'] and not result['forceDetach'], 'normal_detached_backup_required')
    need(backup['metadata']['uid'] == result['backupUID'] and backup['metadata']['name'] == result['backup']
         and backup['status']['state'] == 'Completed' and result['volumeUID'] == profile['volume']['metadata']['uid'], 'native_backup_and_original_volume_UID_chain')
    need(profile['volume']['spec']['encrypted'] and profile['volume']['spec']['dataEngine'] == 'v1', 'encrypted_v1_dataset')
    ALIAS, VOLUME, BACKUP = alias, result['volume'], result['backup']
    payload = int(profile['volume']['spec']['size'])
    need(int(attached['engine']['status']['currentSize']) == payload, 'reported_encrypted_payload_size')
    # Longhorn V1 >=1.12 reserves 16 MiB outside the reported encrypted payload.
    # The native backup's volume.cfg records this complete raw backend size.
    CONTEXT = {'backendBytes': payload + 16 * 1024**2, 'reportedPayloadBytes': payload,
               'backupBlockBytes': int(backup['status']['size']), 'volumeUID': result['volumeUID'], 'backupUID': result['backupUID']}


def ssh(command, worker=False):
    result = subprocess.run(SSH + ['james@192.168.0.' + ('6' if worker else '4'), command],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    need(result.returncode == 0, 'readonly_export_failed_' + str(result.returncode))
    return result.stdout


def bound_pod():
    pod = json.loads(ssh('kubectl get pod -n longhorn-system ' + POD + ' -o json'))
    need(pod['metadata']['uid'] == POD_UID and pod['spec']['nodeName'] == 'workernode1', 'installed_tool_pod_identity')
    status = pod['status']['containerStatuses'][0]
    need(status['imageID'] == IMAGE_ID and status['ready'] and status['restartCount'] == 0, 'installed_tool_image_identity')
    return {'pod': POD, 'uid': POD_UID, 'imageID': IMAGE_ID, 'containerID': status['containerID']}


def tools():
    need(os.geteuid() == 1000 and F.is_mount() and R.resolve() == R, 'existing_F_mount_and_owner')
    for path in [F, Path('/mnt/c')]:
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 15 * 1024**3 + 384 * 1024**2, 'capacity_before_tool_export')
    output = R / 'independent-restore-tools'
    first_failure = R / 'restore-first-stage-failures.json'
    need(not output.exists() or (first_failure.is_file() and not any(output.iterdir())), 'preserve_prior_tool_attempt')
    ownership = {
        'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
        'physicalVolume': 'F: ext4 3c792469-ea0e-4a2c-98e8-1185b141607b',
        'outputs': ['independent-restore-tools', 'storage-proof/nas-stage', 'storage-proof/restore-work'],
        'estimatedStageBytes': 384 * 1024**2,
        'regeneration': 'this script: tools, nas, then restore inside the recorded isolated service',
        'protected': 'all production data, replicas, source, native Secrets, NAS originals, failures and receipts',
        'toolProvenance': 'read-only exports of the already installed Longhorn 1.12.1 engine and instance-manager utilities',
        'cleanup': 'independent reference-qualified removal after successful verification; retain failed evidence'}
    if not (R / 'independent-restore-ownership.json').exists():
        save(R / 'independent-restore-ownership.json', ownership)
    else:
        need(json.loads((R / 'independent-restore-ownership.json').read_text()) == ownership, 'original_ownership_preserved')
    output.mkdir(mode=0o700, exist_ok=True)
    before = bound_pod()
    exec_prefix = 'kubectl exec -n longhorn-system ' + POD + ' -- '
    ldd = ssh(exec_prefix + 'ldd /usr/bin/qemu-img').decode()
    need('not found' not in ldd, 'source_tool_complete_libraries')
    libraries = sorted(set(re.findall(r'(?<!\S)(/(?:usr/)?lib64/[A-Za-z0-9_.+-]+)', ldd)))
    need(len(libraries) >= 20 and '/lib64/ld-linux-x86-64.so.2' in libraries, 'bounded_library_closure')
    paths = ['/usr/bin/qemu-img'] + libraries
    hashes = ssh(exec_prefix + 'sha256sum ' + ' '.join(shlex.quote(p) for p in paths)).decode()
    expected = {line.split()[1]: line.split()[0] for line in hashes.splitlines()}
    need(set(expected) == set(paths), 'source_library_hashes')
    payload = ssh(exec_prefix + 'tar -C / -chf - ' + ' '.join(shlex.quote(p.lstrip('/')) for p in paths))
    need(len(payload) < 80 * 1024**2, 'bounded_native_utility_export')
    sysroot = output / 'sysroot'
    sysroot.mkdir()
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        members = archive.getmembers()
        need(len(members) == len(paths) and {'/' + m.name for m in members} == set(paths), 'only_exact_native_utilities')
        for member in members:
            need(member.isfile() and member.size <= 32 * 1024**2, 'regular_bounded_native_tool')
            path = sysroot / member.name
            need(path.resolve().is_relative_to(sysroot), 'native_tool_export_scope')
            path.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(member).read()
            need(hashlib.sha256(data).hexdigest() == expected['/' + member.name], 'native_tool_hash_match')
            with path.open('xb') as out:
                out.write(data)
            path.chmod(0o700 if member.name.endswith(('qemu-img', 'ld-linux-x86-64.so.2')) else 0o600)
    need(ssh(exec_prefix + 'sha256sum ' + ' '.join(shlex.quote(p) for p in paths)).decode() == hashes, 'native_utilities_unchanged_during_export')
    engine_before = ssh('sha256sum ' + ENGINE, worker=True).decode().split()[0]
    engine = ssh('cat ' + ENGINE, worker=True)
    need(len(engine) == 47397952 and hashlib.sha256(engine).hexdigest() == engine_before, 'installed_engine_hash_match')
    need(ssh('sha256sum ' + ENGINE, worker=True).decode().split()[0] == engine_before, 'installed_engine_unchanged')
    with (output / 'longhorn').open('xb') as out:
        out.write(engine)
    (output / 'longhorn').chmod(0o700)
    wrapper = output / 'qemu-img'
    with wrapper.open('x') as out:
        out.write('#!/bin/sh\nexec ' + shlex.quote(str(sysroot / 'lib64/ld-linux-x86-64.so.2')) +
                  ' --library-path ' + shlex.quote(str(sysroot / 'lib64') + ':' + str(sysroot / 'usr/lib64')) +
                  ' ' + shlex.quote(str(sysroot / 'usr/bin/qemu-img')) + ' "$@"\n')
    wrapper.chmod(0o700)
    need(bound_pod() == before, 'tool_source_pod_unchanged')
    save(R / 'independent-restore-tools.json', {'source': before, 'libraries': expected,
         'engineSource': ENGINE, 'engineSHA256': engine_before, 'qemuWrapperSHA256': sha(wrapper),
         'toolPaths': {str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file()},
         'stageComplete': True, 'packageInstall': False, 'imagePull': False})
    print(json.dumps({'stage': 'tools', 'files': len(paths) + 2, 'verified': True}))


def nas():
    need(os.name == 'nt', 'windows_existing_authenticated_NAS_session')
    import ctypes
    import msvcrt
    import shutil
    from ctypes import wintypes
    root = WINDOWS_F / REL
    context(root, ALIAS)
    ownership = json.loads((root / 'independent-restore-ownership.json').read_text())
    need(ownership['physicalVolume'].startswith('F:'), 'recorded_physical_storage')
    source = Path(r'\\?\UNC\TRUENAS\container_backups\k8s-migration-20261009\longhorn')
    checksum = hashlib.sha512(VOLUME.encode()).hexdigest()[:64]
    relative = Path('backupstore') / 'volumes' / checksum[:2] / checksum[2:4] / VOLUME
    target = root / ALIAS / 'nas-stage'
    resume = (root / ALIAS / 'first-nas-stage-failure.json').is_file()
    need(not target.exists() or ((root / 'restore-first-stage-failures.json').is_file() and not any(p.is_file() for p in target.rglob('*')))
         or (resume and not (root / ALIAS / 'nas-stage-result.json').exists()
             and all(p.suffix == '.cfg' for p in target.rglob('*') if p.is_file())), 'preserve_prior_NAS_attempt')
    budget = 3 * CONTEXT['backupBlockBytes'] + 128 * 1024**2
    need(shutil.disk_usage('C:\\').free >= 15 * 1024**3 and
         shutil.disk_usage(WINDOWS_F).free >= 15 * 1024**3 + budget, 'NAS_stage_and_double_raw_capacity_floor')
    target.mkdir(exist_ok=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    class FileInfo(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                    ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                    ('volume', wintypes.DWORD), ('sizeHigh', wintypes.DWORD), ('sizeLow', wintypes.DWORD),
                    ('links', wintypes.DWORD), ('indexHigh', wintypes.DWORD), ('indexLow', wintypes.DWORD)]
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileInfo)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    def info(src):
        value = FileInfo()
        need(kernel.GetFileInformationByHandle(msvcrt.get_osfhandle(src.fileno()), ctypes.byref(value)), 'standard_NAS_handle_metadata')
        return {'fileID': value.indexHigh * 2**32 + value.indexLow, 'size': value.sizeHigh * 2**32 + value.sizeLow,
                'writeTime': value.write.dwHighDateTime * 2**32 + value.write.dwLowDateTime, 'volumeSerial': value.volume}
    def opened(path):
        handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        need(handle != ctypes.c_void_p(-1).value, 'NAS_read_lock_' + str(ctypes.get_last_error()))
        return os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY), 'rb')
    records = []
    def copy(rel):
        with opened(source / rel) as src:
            before = info(src)
            need(before['size'] <= 3 * 1024**2, 'bounded_native_config_or_block')
            data = src.read()
            need(len(data) == before['size'], 'complete_locked_NAS_read')
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(data).hexdigest()
            if dst.exists():
                need(resume and sha(dst) == digest, 'only_resume_identical_locked_NAS_config')
            else:
                with dst.open('xb') as out:
                    out.write(data)
            need(sha(dst) == digest, 'NAS_stage_full_readback')
            after = info(src)
            need(before == after, 'locked_NAS_identity_unchanged')
            records.append({'relativePath': str(rel).replace('\\', '/'), 'size': len(data), 'sha256': digest,
                            'sourceIdentity': before})
            return json.loads(data) if rel.suffix == '.cfg' else None
    volume = copy(relative / 'volume.cfg')
    backup = copy(relative / 'backups' / ('backup_' + BACKUP + '.cfg'))
    need(volume['Name'] == VOLUME and backup['Name'] == BACKUP and backup['VolumeName'] == VOLUME, 'exact_native_backup_binding')
    need(int(volume['Size']) == CONTEXT['backendBytes'] and backup['Blocks']
         and len(backup['Blocks']) <= 100000 and backup['IsIncremental'] is False
         and int(backup['Size']) == CONTEXT['backupBlockBytes'], 'full_encrypted_backend_size_and_blocks')
    checksums = sorted(set(b['BlockChecksum'] for b in backup['Blocks']))
    need(all(re.fullmatch('[0-9a-f]{64}', c) for c in checksums), 'native_block_path_allowlist')
    for c in checksums:
        copy(relative / 'blocks' / c[:2] / c[2:4] / (c + '.blk'))
    save(root / ALIAS / 'nas-stage-result.json', {'status': 'complete_locked_NAS_readback',
         'source': str(source), 'files': records, 'backup': BACKUP, 'volume': VOLUME,
         'backendSize': int(volume['Size']), 'blockCount': len(backup['Blocks']), 'sourceWrite': False,
         'workingBudgetBytes': budget, 'originalUIDs': CONTEXT})
    print(json.dumps({'stage': 'nas', 'files': len(records), 'bytes': sum(r['size'] for r in records), 'verified': True}))


def restore():
    need(os.geteuid() == 1000 and F.is_mount() and R.resolve() == R, 'F_restore_scope')
    context(R, ALIAS)
    toolroot = R / 'independent-restore-tools'
    tools_proof = json.loads((R / 'independent-restore-tools.json').read_text())
    need(all(sha(toolroot / p) == h for p, h in tools_proof['toolPaths'].items()), 'frozen_installed_tools')
    stage = R / ALIAS / 'nas-stage'
    nas_proof = json.loads((R / ALIAS / 'nas-stage-result.json').read_text())
    need(all(sha(stage / r['relativePath']) == r['sha256'] for r in nas_proof['files']), 'frozen_NAS_stage')
    work = R / ALIAS / 'restore-work'
    need(work.is_dir() and not any(work.iterdir()) and Path.cwd() == work, 'empty_owned_restore_workdir')
    url = 'vfs://' + str(stage) + '?backup=' + BACKUP + '&volume=' + VOLUME
    env = dict(os.environ, PATH=str(toolroot) + ':/usr/bin:/bin', TMPDIR=str(work), TMP=str(work), TEMP=str(work))
    result = {'status': 'started', 'volume': VOLUME, 'backup': BACKUP,
              'productionRestore': False, 'decryptedOrMounted': False, 'nativeToolExit': None}
    try:
        unit = 'branconet-detached-restore-' + BACKUP.removeprefix('migration-preserve-').removesuffix('-backup')
        properties = subprocess.check_output(['systemctl', 'show', unit + '.service', '-p', 'User', '-p', 'PrivateNetwork',
            '-p', 'MemoryMax', '-p', 'MemorySwapMax', '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax', '-p', 'NoNewPrivileges'], text=True)
        observed = dict(line.split('=', 1) for line in properties.splitlines() if '=' in line)
        need(all(observed.get(k) == v for k, v in {'User': 'brajam', 'PrivateNetwork': 'yes', 'MemoryMax': '536870912',
             'MemorySwapMax': '0', 'CPUQuotaPerSecUSec': '1s', 'TasksMax': '64', 'NoNewPrivileges': 'yes'}.items()), 'observed_isolated_restore_unit')
        save(work.parent / 'native-restore-unit.json', observed)
        with (work.parent / 'native-restore.log').open('xb') as log:
            command = [str(toolroot / 'longhorn'), 'backup', 'restore-to-file', url,
                       '--output-format', 'raw', '--output-file', 'volume.raw', '--concurrent-limit', '1']
            restored = subprocess.run(command, cwd=work, env=env, stdout=log, stderr=log, timeout=300)
        result['nativeToolExit'] = restored.returncode
        need(restored.returncode == 0, 'native_restore_command_success')
        raw = work / 'volume.raw'
        need(raw.stat().st_size == nas_proof['backendSize'], 'complete_encrypted_backend_not_truncated_to_PVC')
        cfg = next(stage.glob('backupstore/volumes/*/*/*/backups/*.cfg'))
        backup = json.loads(cfg.read_text())
        blocks = sorted(backup['Blocks'], key=lambda x: x['Offset'])
        blocksize = int(backup['Parameters']['backup-block-size'])
        cursor = 0
        with raw.open('rb') as data:
            for block in blocks:
                offset = int(block['Offset'])
                need(offset >= cursor and offset + blocksize <= raw.stat().st_size, 'ordered_nonoverlapping_backup_blocks')
                while cursor < offset:
                    piece = data.read(min(1024**2, offset - cursor))
                    need(piece and not any(piece), 'unwritten_sparse_region_is_zero')
                    cursor += len(piece)
                piece = data.read(blocksize)
                need(len(piece) == blocksize and hashlib.sha512(piece).hexdigest()[:64] == block['BlockChecksum'], 'native_decompressed_block_checksum')
                cursor += len(piece)
            while cursor < raw.stat().st_size:
                piece = data.read(min(1024**2, raw.stat().st_size - cursor))
                need(piece and not any(piece), 'trailing_sparse_region_is_zero')
                cursor += len(piece)
            data.seek(0)
            need(data.read(6) == b'LUKS\xba\xbe', 'encrypted_LUKS_header_preserved')
        result.update(status='native_restore_and_all_block_checks_passed', backendBytes=raw.stat().st_size,
                      allocatedBytes=raw.stat().st_blocks * 512, rawSHA256=sha(raw), verifiedBlocks=len(blocks),
                      allUnbackedRegionsZero=True, encryptedHeaderVerified=True,
                      completedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
    except Exception as error:
        result.update(status='failed_preserve_work_and_evidence', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        save(work.parent / 'independent-restore-result.json', result)
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['tools', 'nas', 'restore'])
    parser.add_argument('--volume', choices=sorted(ALLOWED), default='storage-proof')
    args = parser.parse_args()
    ALIAS = args.volume
    if os.name != 'nt':
        os.umask(0o077)
    {'tools': tools, 'nas': nas, 'restore': restore}[args.phase]()
