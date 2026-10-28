#!/usr/bin/env python3
"""Verify the same Redis PVC/RDB and patched runtime; no cache values or writes."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
BASE = Path('/home/brajam/.local/share/branconet-migration')
spec = importlib.util.spec_from_file_location('cold_redis_contract', HERE / 'cold-application-state-backup.py')
cold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cold)
shared = cold.shared
IMAGE = 'docker.io/library/redis:8.6.7-alpine@sha256:7033ad495c19b6bca38aea38f9130d1a3d5b647ac94f3ebe644c8c0fb804e039'
CHILD = 'sha256:3247e05722d248a515f7554707085bb31440618c400b147e4e8a10d66c065d50'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def receipt(path, sha):
    shared.protected(path, True)
    need(path.stat().st_size <= 4 * 1024 ** 2 and shared.file_hash(path) == sha, 'private_exact_receipt')
    return json.loads(path.read_bytes())


def call(argv):
    result = subprocess.run(shared.SSH + [shlex.join(argv)], capture_output=True, timeout=40)
    need(result.returncode == 0 and len(result.stdout) <= 1024 ** 2, 'bounded_cluster_read')
    return result.stdout


def get(kind, name, namespace='wordpress'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', namespace, 'get', kind, name, '-o', 'json']))


def fence():
    namespace, deployment_uid, release_uid, claim_uid, _ = cold.TARGETS['wordpress-redis']
    d = get('deployment', 'wordpress-redis')
    h = get('helmrelease', 'wordpress-redis', 'flux-system')
    claim = get('pvc', 'wordpress-redis-data')
    need(d['metadata']['uid'] == deployment_uid and h['metadata']['uid'] == release_uid, 'original_workload_identity')
    need(d['status'].get('observedGeneration') == d['metadata']['generation'] and d['spec']['replicas'] == 1
         and all(d['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']), 'ready_one_writer')
    need(h['status'].get('observedGeneration') == h['metadata']['generation'] and not h['spec'].get('suspend', False)
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status'].get('conditions', [])), 'flux_observed_ready')
    need(claim['metadata']['uid'] == claim_uid and claim['status']['phase'] == 'Bound'
         and claim['spec']['volumeName'] == 'pvc-' + claim_uid and claim['spec']['storageClassName'] == 'longhorn', 'original_bound_claim')
    pv = get('pv', 'pvc-' + claim_uid)
    need(pv['spec']['claimRef']['uid'] == claim_uid and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
         and pv['spec']['csi']['volumeHandle'] == 'pvc-' + claim_uid, 'original_longhorn_binding')
    pods = json.loads(call(['kubectl', '-n', namespace, 'get', 'pods', '-l', 'app=wordpress-redis', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_owned_pod')
    p = pods[0]
    c = p['spec']['containers'][0]
    status = p['status']['containerStatuses'][0]
    need(not p['metadata'].get('deletionTimestamp') and len(p['spec']['containers']) == 1 and status['ready']
         and c['image'] == IMAGE and status['imageID'].rsplit('@', 1)[-1] in [IMAGE.rsplit('@', 1)[-1], CHILD]
         and not p['spec'].get('initContainers') and not p['spec'].get('ephemeralContainers'), 'exact_patched_writer')
    rs_owner = [o for o in p['metadata'].get('ownerReferences', []) if o.get('controller')]
    need(len(rs_owner) == 1 and rs_owner[0]['kind'] == 'ReplicaSet', 'replicaset_owner')
    rs = get('replicaset', rs_owner[0]['name'])
    need(rs['metadata']['uid'] == rs_owner[0]['uid'] and any(o.get('controller') and o['uid'] == deployment_uid for o in rs['metadata']['ownerReferences']), 'original_deployment_owner')
    need(c.get('envFrom') == [{'secretRef': {'name': 'wordpress-redis-runtime'}}] and not c.get('command') and not c.get('args'), 'original_launch_and_secret_reference')
    need(any(v['name'] == 'data' and v.get('persistentVolumeClaim', {}).get('claimName') == 'wordpress-redis-data' for v in p['spec']['volumes'])
         and any(m['name'] == 'data' and m['mountPath'] == '/data' and not m.get('subPath') for m in c['volumeMounts']), 'original_data_mount')
    return {'deployment_uid': deployment_uid, 'helmrelease_uid': release_uid, 'pvc_uid': claim_uid,
            'pv_uid': pv['metadata']['uid'], 'pod_name': p['metadata']['name'], 'pod_uid': p['metadata']['uid'],
            'deployment_generation': d['metadata']['generation'], 'helmrelease_generation': h['metadata']['generation'],
            'image': c['image'], 'imageID': status['imageID'], 'restart_count': status.get('restartCount', 0)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--cold-receipt', required=True, type=Path)
    p.add_argument('--cold-receipt-sha256', required=True)
    p.add_argument('--previous-receipt', type=Path)
    p.add_argument('--previous-receipt-sha256', default='')
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    need(a.apply and os.name == 'posix', 'explicit_native_observation')
    os.umask(0o077)
    need(bool(a.previous_receipt) == bool(a.previous_receipt_sha256), 'paired_restart_receipt')
    need(a.output_dir.is_absolute() and a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(a.output_dir.stat().st_uid == os.getuid() and not a.output_dir.stat().st_mode & 0o077, 'private_output_mode')
    record = {'application': 'wordpress-redis', 'passed': False, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'coldReceiptSHA256': a.cold_receipt_sha256, 'cacheValuesReadOrWritten': False, 'wholeGoalComplete': False,
              'sourceSHA256': shared.file_hash(Path(__file__))}
    try:
        backup = receipt(a.cold_receipt, a.cold_receipt_sha256)
        need(backup['status'] == 'completed' and backup['application'] == 'wordpress-redis'
             and backup['cold_archive_verified'] and backup['temporary_pod_deleted'], 'complete_cold_backup')
        cipher = Path(backup['archive_path'])
        shared.protected(cipher, True)
        need(shared.file_hash(cipher) == backup['archive_sha256'], 'retained_original_archive')
        decryptor = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        manifest = shared.verify_archive(decryptor.stdout)
        trailer = decryptor.stdout.read(1024 ** 2 + 1)
        need(len(trailer) <= 1024 ** 2 and not any(trailer) and decryptor.wait(timeout=30) == 0, 'whole_archive_authenticated')
        original = manifest['entries']['data-0/dump.rdb']
        need(original['kind'] == 'file' and 0 < original['bytes'] <= 64 * 1024 ** 2, 'original_bounded_rdb')
        before = fence()
        if a.previous_receipt:
            prior = receipt(a.previous_receipt, a.previous_receipt_sha256)
            need(prior['passed'] and prior['coldReceiptSHA256'] == a.cold_receipt_sha256
                 and prior['writer']['pod_uid'] != before['pod_uid'], 'independent_controlled_restart')
            record['previousReceiptSHA256'] = a.previous_receipt_sha256
        program = 'set -eu; redis-cli --raw PING; redis-cli --raw INFO server | grep "^redis_version:"; redis-cli --raw INFO persistence | grep -E "^(loading|rdb_last_bgsave_status|aof_enabled|aof_last_write_status|rdb_last_load_keys_loaded|rdb_last_load_keys_expired):"; sha256sum /data/dump.rdb'
        lines = call(['kubectl', '-n', 'wordpress', 'exec', before['pod_name'], '--', 'sh', '-c', program]).decode().splitlines()
        need(lines[0] == 'PONG' and lines[-1].split()[0] == original['sha256'], 'ping_and_original_rdb_retained')
        info = dict(line.rstrip('\r').split(':', 1) for line in lines[1:-1])
        need(info.get('redis_version') == '8.6.7' and info.get('loading') == '0'
             and info.get('aof_enabled') == '0' and info.get('rdb_last_bgsave_status') == 'ok'
             and info.get('aof_last_write_status') == 'ok', 'patched_healthy_persistence')
        need(fence() == before and shared.file_hash(Path(__file__)) == record['sourceSHA256'], 'writer_and_source_stable')
        record.update(passed=True, writer=before, persistence=info, originalRDBSHA256=original['sha256'], originalRDBBytes=original['bytes'],
                      normalCacheExpirationAndWritesAllowed=True, allLiveCacheValuesEquivalentClaimed=False)
    except Exception as error:
        record['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    record['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = a.output_dir / ('redis-functional-' + uuid.uuid4().hex + '.json')
    with out.open('x') as f:
        json.dump(record, f, sort_keys=True, indent=2)
    print(json.dumps({'passed': record['passed'], 'receipt': str(out), 'receiptSHA256': shared.file_hash(out)}))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
