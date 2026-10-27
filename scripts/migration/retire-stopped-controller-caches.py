"""Retire fixed completed private-worker caches, preserving every source/artifact.

Inspect by default. No daemon stop, image/volume prune, publication or build.
"""
import argparse
import collections
import datetime
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
C = F / 'operator-control'
ALLOWED = {
    'homepage-aa157513b991-5314aaaa2d8a', 'homepage-2416f68cc1cb-94943ae43cb2',
    'homepage-0946c373ff28-a5d9b4936405', 'mealie-c692b307681c-540ac3a24c60',
    'mealie-766e20940e51-251e7197fbb8', 'jackett-9090c0aa2ee9-c1da97fb5e55',
}
GIT = '/usr/bin/git'
REPO = '/mnt/c/Users/james/.codex/local-ci/branconet-charts-local-ci'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    before = ident(path)
    with path.open('rb') as source:
        result = hashlib.file_digest(source, 'sha256').hexdigest()
    need(ident(path) == before, 'changed_during_hash')
    return result


def ident(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def read(path):
    return json.loads(path.read_text())


def command(args):
    p = subprocess.run(args, capture_output=True, timeout=90)
    need(p.returncode == 0, 'required_readonly_command_' + Path(args[0]).name)
    return p.stdout


def preserved(name):
    root = F / name
    provenance = read(root / 'artifacts/local-operator-provenance.json')
    owner = read(root / 'artifacts/owned-builder.json')
    need(provenance['state'] == 'artifact-built-not-qualified-not-deployed' and provenance['source_kind'] == 'local-operator', 'original_completed_builder_provenance')
    need(all(provenance[k] is True for k in ('new_builder_stopped', 'source_manifest_unchanged', 'builder_config_unchanged', 'helper_unchanged')), 'completed_stopped_original_consumer')
    need(owner['source_kind'] == 'local-operator' and owner['run_id'] == provenance['run_id'] and root.stat().st_uid == 1000, 'original_stage_owner')
    need(provenance['storage_contract']['filesystem_uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b', 'original_F_source_contract')
    need(sha(root / 'artifacts/local-build-security-image.py') == provenance['helper_sha256'], 'original_frozen_builder_source')
    command([GIT, '-c', 'safe.directory=' + REPO, '-C', REPO, 'cat-file', '-e', provenance['source_commit'] + '^{commit}'])
    recipe = read(root / 'artifacts/recipe-sha256.json')
    context = root / 'context'
    actual = {}
    # This is the original producer's recursive manifest contract, including
    # nested backports. Directories are structural, not manifest file entries.
    for p in sorted(context.rglob('*')):
        s = p.lstat()
        need(not stat.S_ISLNK(s.st_mode), 'original_context_symlink')
        if stat.S_ISDIR(s.st_mode):
            continue
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'original_context_file_type')
        actual[str(p.relative_to(context))] = {'sha256': sha(p), 'bytes': s.st_size, 'mode': stat.S_IMODE(s.st_mode)}
    need(actual == recipe, 'original_complete_recursive_context_manifest')
    for name, expected in recipe.items():
        p = root / 'context' / name
        need(p.resolve() == p and p.is_file() and p.stat().st_size == expected['bytes']
             and stat.S_IMODE(p.stat().st_mode) == expected['mode'] and sha(p) == expected['sha256'], 'original_recipe_and_source_bytes')
    archive = Path(provenance['archive_path'])
    need(archive.parent == root / 'artifacts' and archive.resolve() == archive and archive.stat().st_size == provenance['archive_bytes']
         and sha(archive) == provenance['archive_sha256'], 'complete_retained_original_artifact')
    seen = {}
    with tarfile.open(archive, 'r:') as source:
        for member in source:
            if member.isfile() and member.name.startswith('blobs/sha256/'):
                with source.extractfile(member) as data:
                    digest = hashlib.file_digest(data, 'sha256').hexdigest()
                need(digest == member.name.rsplit('/', 1)[1] and 'sha256:' + digest not in seen, 'retained_OCI_blob_integrity')
                seen['sha256:' + digest] = member.size
    need(seen == {k: v['bytes'] for k, v in provenance['oci_proof']['blob_proofs'].items()}, 'complete_original_OCI_proof')
    protected = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        parent = Path(parent)
        if parent == root:
            dirs[:] = [d for d in dirs if d != 'state']
        for name in files:
            p = parent / name
            need(p.resolve() == p and p.is_file(), 'unknown_unselected_original_type')
            protected[str(p)] = {'identity': ident(p), 'sha256': sha(p)}
    return {'stage': root.name, 'sourceCommit': provenance['source_commit'], 'runID': provenance['run_id'],
            'originalArchiveSHA256': provenance['archive_sha256'], 'originalArchive': str(archive),
            'originalBuilderSHA256': provenance['helper_sha256'], 'protected': protected,
            'lastConsumer': 'completed private compiler/layer worker; explicit new_builder_stopped=true',
            'regeneration': 'Fresh authorized worker using preserved original pinned source/context/helper; retained exact OCI artifact remains independent of compiler cache'}


def measure(path):
    need(path.resolve() == path and path.parent.parent == F and path.name == 'state' and path.is_dir() and not path.is_mount(), 'exact_canonical_private_state')
    links = {}
    allocated, count = 0, 0
    for parent, dirs, files in os.walk(path, followlinks=False):
        need('.git' not in dirs and '.git' not in files, 'repository_metadata_inside_target')
        # Real directories are counted only when walked; symlink directories
        # are entries, never followed. Ordinary single-link files need no map.
        for name in ('.', *files, *[d for d in dirs if (Path(parent) / d).is_symlink()]):
            p = Path(parent) if name == '.' else Path(parent) / name
            s = p.lstat()
            need(s.st_dev == F.stat().st_dev, 'nested_foreign_filesystem')
            count += 1
            need(count <= 2_000_000, 'bounded_private_cache_entries')
            if stat.S_ISDIR(s.st_mode) or s.st_nlink == 1:
                allocated += s.st_blocks * 512
                continue
            key = (s.st_dev, s.st_ino)
            if key not in links:
                links[key] = {'bytes': s.st_blocks * 512, 'nlink': s.st_nlink, 'seen': 0}
            links[key]['seen'] += 1
    need(all(v['seen'] == v['nlink'] for v in links.values()), 'hardlink_outside_exact_private_cache')
    return {'allocatedBytes': allocated + sum(v['bytes'] for v in links.values()), 'entries': count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', action='append', required=True, choices=sorted(ALLOWED))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--reconcile-startup-failure', action='store_true',
                        help='Same paths/tool only: preserve and diagnose the pre-deletion Go virtual-address startup refusal')
    parser.add_argument('--reconcile-context-membership', action='store_true',
                        help='Same paths/tool only: verify the exact original recursive producer manifest after the flat-manifest refusal')
    args = parser.parse_args()
    stages = sorted(args.stage)
    need(not (args.reconcile_startup_failure and args.reconcile_context_membership), 'one_exact_diagnosed_refusal_only')
    need(1 <= len(stages) <= 3 and len(set(stages)) == len(stages), 'bounded_explicit_three_stage_maximum')
    need(os.geteuid() == 0 and F.is_mount() and F.resolve() == F and shutil.rmtree.avoids_symlink_attacks
         and 'dir_fd' in inspect.signature(shutil.rmtree).parameters, 'root_exact_F_and_safe_recursive_primitive')
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    filesystem = json.loads(command(['findmnt', '-J', '-T', str(F), '-o', 'UUID,FSTYPE']))['filesystems'][0]
    need(filesystem['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b' and filesystem['fstype'] == 'ext4', 'declared_physical_volume')
    os.umask(0o077)
    token = hashlib.sha256(json.dumps(stages, separators=(',', ':')).encode()).hexdigest()[:16]
    planpath = C / ('stopped-controller-cache-' + token + '-plan.json')
    original_receipt = C / ('stopped-controller-cache-' + token + '-removal.json')
    receipt = original_receipt
    reconcile_tag = ''
    if args.reconcile_startup_failure:
        prior = read(original_receipt)
        diagnosis = read(C / 'stopped-cache-resource-guard-diagnosis.json')
        need(prior['status'] == 'retained_failed_safety_check' and prior['failedCheck'] == 'required_readonly_command_docker'
             and not prior['removed'] and prior['stages'] == stages
             and prior['sourceSHA256'] == diagnosis['sourceSHA256'] == sha(C / 'stopped-cache-first-resource-guard-source.py'),
             'only_exact_preserved_pre_deletion_startup_refusal')
        need(diagnosis['ordinaryClientExit'] == 0 and diagnosis['ordinaryContainerCount'] == 0
             and diagnosis['virtualAddressCapClientExit'] != 0
             and 'failed to reserve page summary memory' in diagnosis['cappedClientDiagnostic'], 'actual_startup_cause_diagnosed_without_data_or_reference_bypass')
        receipt = C / ('stopped-controller-cache-' + token + '-startup-reconciliation.json')
        reconcile_tag = '-startup-reconciliation'
    if args.reconcile_context_membership:
        prior = read(original_receipt)
        diagnosis = read(C / 'stopped-cache-recursive-recipe-proof.json')
        need(prior['status'] == 'retained_failed_safety_check' and prior['failedCheck'] == 'original_complete_context_membership'
             and not prior['removed'] and prior['stages'] == stages
             and prior['sourceSHA256'] == diagnosis['oldOperatorSHA256'] == sha(C / 'stopped-cache-first-flat-context-source.py'),
             'only_exact_preserved_pre_deletion_recursive_manifest_refusal')
        rows = {r['stage']: r for r in diagnosis['proof']}
        need(all(name in rows and rows[name]['allOriginalBytesModesSizesAndMembershipMatch'] for name in stages),
             'every_original_recursive_manifest_entry_verified_without_weakening')
        receipt = C / ('stopped-controller-cache-' + token + '-context-reconciliation.json')
        reconcile_tag = '-context-reconciliation'
    need(not receipt.exists(), 'prior_failed_or_completed_target_receipt_preserved')
    unit = 'branconet-stopped-cache-' + token + ('-apply' if args.apply else '-inspect')
    if os.environ.get('BRANCONET_CACHE_SCOPE') != unit:
        ownership = C / ('stopped-controller-cache-' + token + reconcile_tag + '-ownership.json')
        if not ownership.exists():
            need(os.statvfs(F).f_bavail * os.statvfs(F).f_frsize >= 64 * 1024**2, 'complete_metadata_peak_before_output')
            with ownership.open('x') as out:
                json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F), 'physicalVolume': filesystem,
                           'targets': [str(F / name / 'state') for name in stages], 'peakMetadataBytes': 64 * 1024**2,
                           'generatedPaths': [str(planpath), str(receipt)], 'sourceSHA256': sha(Path(__file__)),
                           'regeneration': 'preserved pinned builder helper/context/original artifact; fresh private worker only if authorized',
                           'lastConsumer': 'original compilation completed and its worker stopped',
                           'protected': 'all originals, artifacts/receipts, real workloads, images/volumes/models and every other failed safety target',
                           'endCondition': 'resident-memory-budgeted full source/artifact/reference checks before state-cache removal'}, out, indent=2)
            os.chown(ownership, 1000, 1000)
        else:
            need(read(ownership)['sourceSHA256'] == sha(Path(__file__)), 'declared_operator_source_unchanged')
        props = ['User=root', 'MemoryMax=536870912', 'MemorySwapMax=0', 'CPUQuota=100%', 'TasksMax=64',
                 'Nice=15', 'UMask=0077', 'PrivateNetwork=yes', 'NoNewPrivileges=yes', 'ProtectSystem=strict',
                 'RuntimeMaxSec=1200', 'WorkingDirectory=/home/brajam',
                 'ReadWritePaths=' + str(C) + ' ' + ' '.join(str(F / name) for name in stages)]
        cmd = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect', '--unit=' + unit,
               '--setenv=BRANCONET_CACHE_SCOPE=' + unit] + ['--property=' + p for p in props]
        cmd += ['/usr/bin/env', 'TMPDIR=' + str(C / 'tmp'), 'TMP=' + str(C / 'tmp'), 'TEMP=' + str(C / 'tmp'),
                '/usr/bin/python3', '-B', str(Path(__file__).resolve()), *sys.argv[1:]]
        raise SystemExit(subprocess.run(cmd).returncode)
    observed = dict(line.split('=', 1) for line in command(['systemctl', 'show', unit + '.service', '-p', 'MemoryMax',
        '-p', 'MemorySwapMax', '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax', '-p', 'PrivateNetwork', '-p', 'NoNewPrivileges']).decode().splitlines() if '=' in line)
    need(all(observed.get(k) == v for k, v in {'MemoryMax': '536870912', 'MemorySwapMax': '0',
         'CPUQuotaPerSecUSec': '1s', 'TasksMax': '64', 'PrivateNetwork': 'yes', 'NoNewPrivileges': 'yes'}.items()), 'actual_private_worker_resource_budget')
    guard = F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
    raw = guard.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'full_existing_reference_guard')
    scope = {'__name__': 'controller_cache_reference_guard'}
    exec(compile(raw, str(guard), 'exec'), scope)
    scope.update(BASE=F, ATTEMPTS=tuple(name + '/state' for name in stages))
    result = {'status': 'started', 'stages': stages, 'removed': [], 'failedTargetsRetained': [], 'sourceSHA256': sha(Path(__file__)),
              'startupRefusalReconciled': args.reconcile_startup_failure, 'recursiveManifestRefusalReconciled': args.reconcile_context_membership,
              'oldRefusalReceiptPreserved': str(original_receipt) if reconcile_tag else None}
    locks = []
    try:
        for name in stages:
            for path in (F / name / 'operation.lock', F / name / 'phase.lock'):
                if path.exists():
                    need(path.is_file() and not path.is_symlink(), 'existing_lock_type')
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    locks.append(fd)
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refs = scope['idle']()
        containers = command(['docker', '--host', 'unix:///var/run/docker.sock', 'ps', '-q']).decode().split()
        # The current Docker engine has no running containers. Refuse a changed
        # state rather than infer absence of cross-VM ancestor bind references.
        need(not containers, 'Docker_container_reference_inventory_requires_review')
        original = [preserved(name) for name in stages]
        targets = [{'path': str(F / name / 'state'), 'identity': ident(F / name / 'state'), **measure(F / name / 'state')} for name in stages]
        plan = {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F), 'filesystem': filesystem,
                'sourceSHA256': sha(Path(__file__)), 'stages': stages, 'protectedOriginals': original,
                'targets': targets, 'references': refs, 'DockerRunningContainers': 0, 'observedResourceBudget': observed,
                'endCondition': 'original completed private workers stopped, originals/OCI verified and complete references absent; remove only state caches',
                'imagesVolumesModelsAndSourcesRemoved': False}
        if not args.apply:
            need(not planpath.exists(), 'prior_plan_preserved')
            with planpath.open('x') as out:
                json.dump(plan, out, indent=2)
            os.chown(planpath, 1000, 1000)
            print(json.dumps({'status': 'qualified', 'key': token, 'targets': targets}))
            return
        old = read(planpath)
        need(all(old[k] == plan[k] for k in ('sourceSHA256', 'stages', 'protectedOriginals', 'targets')), 'exact_frozen_plan_and_protected_originals')
        scope['idle']()
        before = os.statvfs(F)
        for item in targets:
            p = Path(item['path'])
            need(ident(p) == item['identity'] and measure(p)['allocatedBytes'] == item['allocatedBytes'], 'immediate_target_identity_and_extent_count')
            scope['idle']()
            need(not command(['docker', '--host', 'unix:///var/run/docker.sock', 'ps', '-q']).strip(), 'Docker_inventory_changed_before_removal')
            fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                s = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
                need((s.st_dev, s.st_ino) == (item['identity']['dev'], item['identity']['ino']), 'opened_original_directory_identity')
                shutil.rmtree(p.name, dir_fd=fd)
            finally:
                os.close(fd)
            result['removed'].append(item)
        need([preserved(name) for name in stages] == original, 'all_originals_artifacts_and_failure_evidence_unchanged')
        after = os.statvfs(F)
        result.update(status='completed', removedAllocatedLinuxBytes=sum(x['allocatedBytes'] for x in result['removed']),
                      availableBeforeBytes=before.f_bavail * before.f_frsize, availableAfterBytes=after.f_bavail * after.f_frsize,
                      originalsUnchanged=True, DockerContainersStopped=False, runtimeImagesPruned=False, WindowsRecoveryClaimed=False)
    except Exception as error:
        result.update(status='retained_failed_safety_check', failedCheck=str(error) if isinstance(error, ValueError) else type(error).__name__)
        removed = {x['path'] for x in result['removed']}
        result['failedTargetsRetained'] = [str(F / name / 'state') for name in stages if str(F / name / 'state') not in removed]
        raise
    finally:
        for fd in locks:
            os.close(fd)
        if args.apply or result['status'] == 'retained_failed_safety_check':
            with receipt.open('x') as out:
                json.dump(result, out, indent=2)
            os.chown(receipt, 1000, 1000)
            print(json.dumps({k: v for k, v in result.items() if k not in ('removed',)}))


if __name__ == '__main__':
    main()
