"""Authenticate and restore the existing control-plane snapshot locally only.

No server is started. Configuration and key files are checked in memory; only
the encrypted-at-rest etcd snapshot and its isolated restored database touch disk.
"""
import base64
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'platform-upstream-review-20261027/etcd-restore-qualification'
B = F / 'platform-upstream-review-20261027/flux-control-plane-backup/control-plane-0df321f4e951400db817e07a20d0bec8'
EXPECTED = 'de348e280924bfaa4637aaeb4f94cef4396612be973eda0732209fa5516ee268'
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def run(args):
    child = subprocess.run(args, capture_output=True, timeout=90)
    need(child.returncode == 0, 'isolated_restore_tool_failed')
    return child


def main():
    global B, EXPECTED
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-existing', action='store_true')
    parser.add_argument('--backup-id')
    parser.add_argument('--archive-sha256')
    args = parser.parse_args()
    need(bool(args.backup_id) == bool(args.archive_sha256), 'complete_explicit_backup_selection')
    prefix = ''
    if args.backup_id:
        need(re.fullmatch('[0-9a-f]{32}', args.backup_id)
             and re.fullmatch('[0-9a-f]{64}', args.archive_sha256)
             and not args.verify_existing, 'bounded_fresh_backup_selection')
        B = F / 'platform-upstream-review-20261027/flux-control-plane-backup' / ('control-plane-' + args.backup_id)
        EXPECTED = args.archive_sha256
        prefix = 'cp-' + args.backup_id + '-'
    proof_path = R / (prefix + 'nas-proof.json')
    work = R / (prefix + 'scratch')
    regular_result = R / (prefix + 'restore-result.json')
    need(F.is_mount() and R.resolve() == R and os.geteuid() == 1000, 'owned_unprivileged_local_job')
    need(os.readlink('/proc/self/ns/net') != json.loads(proof_path.read_text())['ordinaryNetworkNamespace'],
         'private_network_namespace_required')
    original = json.loads((B / 'receipt.json').read_text())
    proof = json.loads(proof_path.read_text())
    need(proof['sha256'] == EXPECTED == original['archive_sha256'] and proof['fullNASReadback'], 'exact_nas_source')
    if args.backup_id:
        need(original['status'] == 'completed' and original['run_id'] == args.backup_id
             and original['authenticated_archive_verified'] and original['snapshot_footer_verified']
             and proof['sourceReceiptSHA256'] == sha(B / 'receipt.json'), 'exact_completed_backup_producer')
    source = B / 'control-plane.tar.age'
    need(source.resolve() == source and source.stat().st_size == original['archive_bytes'] and sha(source) == EXPECTED,
         'local_cipher_identical_to_nas')
    tool = R / 'tools/etcdutl'
    provenance = json.loads((R / (prefix + 'tool-provenance.json')).read_text())
    need(tool.resolve() == tool and sha(tool) == provenance['binary']['sha256'], 'pinned_public_restore_tool')
    age = Path('/home/brajam/.local/share/branconet-migration/bin/age')
    need(sha(age) == AGE_SHA, 'pinned_age')
    previous = None
    if args.verify_existing:
        previous = json.loads((R / 'restore-result.json').read_text())
        need(previous['status'] == 'failed' and previous['errorCategory'] == 'restored_keyspace_hash_revision_count'
             and (R / 'scratch/restored/member/snap/db').is_file(), 'only_reviewed_existing_restore')
    else:
        need(not work.exists() and not regular_result.exists(), 'prior_scratch_and_result_preserved')
    output = R / 'restore-result-verified.json' if args.verify_existing else regular_result
    need(not output.exists(), 'prior_qualification_receipt_preserved')
    space = os.statvfs(F)
    need(space.f_bavail * space.f_frsize >= 15 * 1024**3 + 512 * 1024**2, 'restore_capacity_floor')
    os.umask(0o077)
    if not args.verify_existing:
        work.mkdir(mode=0o700)
    os.environ.update(TMPDIR=str(work), TMP=str(work), TEMP=str(work), GOMAXPROCS='1', GOMEMLIMIT='128MiB')
    snapshot = work / ('authenticated-source.db' if args.verify_existing else 'snapshot.db')
    need(not snapshot.exists(), 'fresh_authenticated_probe_preserves_prior_failure')
    result = {'status': 'started', 'sourceArchiveSHA256': EXPECTED, 'productionMutation': False,
              'secretConfigurationExtractedToDisk': False, 'networkListenerStarted': False,
              'wholeClusterRestoreExecuted': False}
    crypt = None
    try:
        crypt = subprocess.Popen([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(source)],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        manifest = None
        seen = set()
        verified = []
        encrypted_secrets = False
        volume_key = False
        with tarfile.open(fileobj=crypt.stdout, mode='r|') as archive:
            total = 0
            for member in archive:
                need(member.isfile() and member.name not in seen and not member.name.startswith('/')
                     and '..' not in Path(member.name).parts and len(seen) <= 258, 'safe_unique_archive_member')
                seen.add(member.name)
                total += member.size
                need(total <= 576 * 1024**2, 'bounded_archive')
                inp = archive.extractfile(member)
                if member.name == 'manifest.json':
                    need(len(seen) == 1 and member.size <= 262144, 'first_bounded_manifest')
                    manifest = json.loads(inp.read())
                    need(manifest['schema_version'] == 1, 'original_manifest_schema')
                    continue
                need(manifest is not None, 'manifest_precedes_payload')
                if member.name == 'snapshot.db':
                    need(member.size == manifest['snapshot']['bytes'] <= 512 * 1024**2, 'snapshot_byte_bound')
                    with snapshot.open('xb') as out:
                        for block in iter(lambda: inp.read(1024**2), b''):
                            out.write(block)
                        out.flush()
                        os.fsync(out.fileno())
                    need(snapshot.stat().st_size == member.size and sha(snapshot) == manifest['snapshot']['sha256']
                         == original['snapshot_sha256'], 'exact_authenticated_snapshot')
                    continue
                need(member.name.startswith('etc/kubernetes/') and member.name in manifest['files']
                     and member.size <= 1024**2, 'configuration_member_scope')
                data = inp.read()
                need(len(data) == member.size == manifest['files'][member.name]['bytes']
                     and hashlib.sha256(data).hexdigest() == manifest['files'][member.name]['sha256'], 'configuration_full_hash')
                if member.name == 'etc/kubernetes/encryption-config.json':
                    cfg = json.loads(data)
                    need(cfg['kind'] == 'EncryptionConfiguration', 'encryption_configuration_type')
                    for rule in cfg['resources']:
                        if 'secrets' not in rule['resources']:
                            continue
                        for provider in rule['providers']:
                            for algorithm in ('aescbc', 'aesgcm', 'secretbox'):
                                for key in provider.get(algorithm, {}).get('keys', []):
                                    need(len(base64.b64decode(key['secret'], validate=True)) == 32, 'encryption_key_length')
                                    encrypted_secrets = True
                if member.name == 'etc/kubernetes/longhorn-crypto-key':
                    need(len(data.strip()) >= 16, 'volume_encryption_key_present')
                    volume_key = True
                verified.append(member.name)
                del data
        need(manifest is not None and seen == {'manifest.json', 'snapshot.db'} | set(manifest['files']), 'every_archive_member_checked')
        trailing = crypt.stdout.read(1024**2 + 1)
        need(len(trailing) <= 1024**2 and not any(trailing) and crypt.wait(timeout=30) == 0, 'complete_age_authentication')
        need(encrypted_secrets and volume_key and len(verified) == original['config_file_count'], 'all_original_key_configuration_present')
        before = json.loads(run([str(tool), 'snapshot', 'status', str(snapshot), '--write-out=json']).stdout)
        need(all(before[k] == value for k, value in original['snapshot_status'].items()), 'original_snapshot_status_matches')
        restored = work / 'restored'
        command = [str(tool), 'snapshot', 'restore', str(snapshot), '--name=branconet-offline-restore',
                   '--data-dir=' + str(restored), '--initial-cluster=branconet-offline-restore=http://127.0.0.1:2380',
                   '--initial-advertise-peer-urls=http://127.0.0.1:2380', '--initial-cluster-token=branconet-offline-20261027']
        restored_run = None if args.verify_existing else run(command)
        after = json.loads(run([str(tool), 'snapshot', 'status', str(restored / 'member/snap/db'), '--write-out=json']).stdout)
        logical_before = json.loads(run([str(tool), 'hashkv', str(snapshot), '--write-out=json']).stdout)
        logical_after = json.loads(run([str(tool), 'hashkv', str(restored / 'member/snap/db'), '--write-out=json']).stdout)
        need(all(before[k] == after[k] for k in ('revision', 'totalKey')) and logical_before == logical_after,
             'restored_logical_key_history_revision_count')
        need(sha(source) == EXPECTED and sha(tool) == provenance['binary']['sha256'], 'source_and_tool_unchanged')
        result.update(status='completed', completedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      completeAgeAuthentication=True, verifiedConfigurationFiles=len(verified),
                      nativeSecretEncryptionConfigurationPresent=True, volumeEncryptionKeyPresent=True,
                      snapshotBefore=before, restoredDatabaseAfter=after,
                      logicalHistoryBefore=logical_before, logicalHistoryAfter=logical_after,
                      keyValueHistoryHashUnchanged=True, offlineSnapshotRestoreExecuted=not args.verify_existing,
                      existingOfflineRestoreQualified=args.verify_existing,
                      authenticatedSnapshotSHA256BeforeTool=original['snapshot_sha256'],
                      keyHashToolMayUpdateDisposableDatabaseMetadata=True,
                      previousAttemptReceiptSHA256=sha(R / 'restore-result.json') if args.verify_existing else None,
                      previousExecutedSourceSHA256=sha(R / 'restore-frozen.py') if args.verify_existing else None,
                      restoreDiagnosticsSHA256=hashlib.sha256(restored_run.stderr).hexdigest() if restored_run else None,
                      sourceFilesRetained=True, scratchRequiresInactiveCleanup=True)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__,
                      retainedScratch=str(work), retentionReason='qualification or safety remains incomplete')
        raise
    finally:
        if crypt is not None and crypt.poll() is None:
            crypt.terminate()
            crypt.wait(timeout=15)
        with output.open('x') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('offline_restore_refused:' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
