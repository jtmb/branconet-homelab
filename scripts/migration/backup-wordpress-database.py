#!/usr/bin/env python3
"""Encrypt the existing WordPress user's complete transactional database snapshot."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('wordpress_cold_scope', HERE / 'cold-application-state-backup.py')
cold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cold)
shared = cold.shared
BASE = Path('/home/brajam/.local/share/branconet-migration')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(argv, body=None, timeout=45):
    p = subprocess.run(shared.SSH + [shlex.join(argv)], input=body, capture_output=True, timeout=timeout)
    need(p.returncode == 0 and len(p.stdout) <= 1024 ** 2, 'bounded_cluster_read')
    return p.stdout


def get(kind, name, namespace='wordpress'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', namespace, 'get', kind, name, '-o', 'json']))


def fence():
    wp = get('deployment', 'wordpress')
    hr = get('helmrelease', 'wordpress', 'flux-system')
    need(wp['metadata']['uid'] == 'c5b60268-c0d4-43f8-8014-4c04e427a122' and wp['spec']['replicas'] == 0
         and wp['status'].get('observedGeneration') == wp['metadata']['generation']
         and all(wp['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas', 'terminatingReplicas']), 'quiesced_original_wordpress')
    need(hr['metadata']['uid'] == '65ca0d62-fc47-4063-81a5-4ed59767e907' and hr['spec']['values']['replicaCount'] == 0
         and not hr['spec'].get('suspend', False) and hr['status'].get('observedGeneration') == hr['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])), 'flux_observed_zero_writers')
    d = get('deployment', 'wordpress-db')
    pvc = get('pvc', 'wordpress-db-data-0')
    need(d['metadata']['uid'] == 'e505c048-f9c5-4c28-b226-ee12c224bf7d' and pvc['metadata']['uid'] == 'b3f53180-5bce-4d84-ab9c-47460a1e3ad9'
         and pvc['status']['phase'] == 'Bound' and pvc['spec']['volumeName'] == 'pvc-b3f53180-5bce-4d84-ab9c-47460a1e3ad9', 'original_database_and_claim')
    need(d['spec']['replicas'] == 1 and d['status'].get('observedGeneration') == d['metadata']['generation']
         and all(d['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas']), 'ready_original_database')
    pv = get('pv', pvc['spec']['volumeName'])
    need(pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
         and pv['spec']['csi']['volumeHandle'] == pvc['spec']['volumeName'], 'original_database_longhorn_binding')
    pods = json.loads(call(['kubectl', '-n', 'wordpress', 'get', 'pods', '-l', 'app=wordpress-db', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_database_writer')
    p = pods[0]
    c = p['spec']['containers'][0]
    need(not p['metadata'].get('deletionTimestamp') and len(p['spec']['containers']) == 1
         and p['status']['containerStatuses'][0]['ready']
         and c['image'] == 'mysql:5.7@sha256:4bc6bc963e6d8443453676cae56536f4b8156d78bae03c0145cbe47c2aad73bb'
         and c['envFrom'] == [{'secretRef': {'name': 'wordpress-db-runtime'}}], 'unchanged_ready_original_mysql')
    owner = [o for o in p['metadata'].get('ownerReferences', []) if o.get('controller')]
    need(len(owner) == 1 and owner[0]['kind'] == 'ReplicaSet', 'database_replicaset_owner')
    rs = get('replicaset', owner[0]['name'])
    need(rs['metadata']['uid'] == owner[0]['uid'] and any(o.get('controller') and o['uid'] == d['metadata']['uid'] for o in rs['metadata']['ownerReferences']), 'original_database_owner_chain')
    need(any(v.get('persistentVolumeClaim', {}).get('claimName') == pvc['metadata']['name'] and v['name'] == 'data-0' for v in p['spec']['volumes'])
         and any(v['name'] == 'data-0' and v['mountPath'] == '/var/lib/mysql' and not v.get('subPath') for v in c['volumeMounts'])
         and p['status']['containerStatuses'][0]['imageID'].rsplit('@', 1)[-1] in [c['image'].rsplit('@', 1)[-1], 'sha256:dab0a802b44617303694fb17d166501de279c3031ddeb28c56ecf7fcab5ef0da'], 'original_database_runtime_and_mount')
    return {'wordpress_uid': wp['metadata']['uid'], 'wordpress_generation': wp['metadata']['generation'],
            'database_uid': d['metadata']['uid'], 'database_claim_uid': pvc['metadata']['uid'],
            'database_pv_uid': pv['metadata']['uid'],
            'database_pod': p['metadata']['name'], 'database_pod_uid': p['metadata']['uid'],
            'database_image_id': p['status']['containerStatuses'][0]['imageID']}


CLIENT = r'''set -eu
case "$MYSQL_USER" in ''|*[!A-Za-z0-9_.-]*) exit 1;; esac
case "$MYSQL_DATABASE" in ''|*[!A-Za-z0-9_]*) exit 1;; esac
test -n "$MYSQL_PASSWORD"
export MYSQL_PWD="$MYSQL_PASSWORD"
# Bash process substitution is a pipe, not a plaintext credentials file.
exec 3< <(printf '[client]\nuser=%s\n[mysql]\ndatabase=%s\n' "$MYSQL_USER" "$MYSQL_DATABASE")
'''
PREFLIGHT = CLIENT + r'''mysql --defaults-file=/proc/self/fd/3 --batch --skip-column-names <<'SQL'
SELECT COUNT(*),SUM(ENGINE<>'InnoDB') FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE';
SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE();
SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE();
SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME IN ('mysql','sys');
SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME NOT IN ('information_schema','performance_schema','mysql','sys') AND SCHEMA_NAME<>DATABASE();
SQL
'''
DUMP = CLIENT + r'''exec mysqldump --defaults-file=/proc/self/fd/3 --databases "$MYSQL_DATABASE" --single-transaction --quick --skip-lock-tables --no-tablespaces --hex-blob --triggers --events --skip-comments --set-gtid-purged=OFF --default-character-set=utf8mb4 --order-by-primary
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    need(a.apply and os.name == 'posix', 'explicit_native_backup')
    os.umask(0o077)
    need(a.output_dir.is_absolute() and a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(a.output_dir.stat().st_uid == os.getuid() and not a.output_dir.stat().st_mode & 0o077, 'private_output_mode')
    folder = a.output_dir / ('wordpress-sql-' + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    record = {'status': 'started', 'application': 'wordpress', 'kind': 'transactional-logical-database-backup',
              'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'restorationDrillPerformed': False,
              'writerScaledOrDatabaseMutated': False, 'plaintextWrittenToDisk': False, 'credentialsLeaveDatabasePod': False}
    children = []
    pins = [(f, shared.protected(f, f == shared.IDENTITY)) for f in [shared.AGE, shared.IDENTITY, shared.RECIPIENT]]
    source_sha = shared.file_hash(Path(__file__))
    def save():
        tmp = folder / ('receipt-' + uuid.uuid4().hex + '.tmp')
        tmp.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
        tmp.replace(folder / 'receipt.json')
    def expired(_signum, _frame):
        raise TimeoutError('bounded_logical_backup_deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(360)
    save()
    try:
        need(shared.file_hash(shared.AGE) == shared.AGE_SHA256, 'pinned_age')
        before = fence()
        record['writer'] = before
        args = ['kubectl', '-n', 'wordpress', 'exec', '-i', before['database_pod'], '--', 'bash', '-s']
        preflight = call(args, PREFLIGHT.encode()).decode().splitlines()
        need(preflight == ['12\t0', '0', '0', '0', '0'], 'twelve_innodb_tables_no_routines_events_or_other_databases')
        source = subprocess.Popen(shared.SSH + [shlex.join(args)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(source)
        source.stdin.write(DUMP.encode())
        source.stdin.close()
        cipher = folder / 'wordpress-complete-visible-database.sql.age'
        plaintext_sha = hashlib.sha256()
        total = 0
        create_tables = 0
        insert_statements = 0
        with cipher.open('xb') as out:
            encryptor = subprocess.Popen([str(shared.AGE), '-R', str(shared.RECIPIENT)], stdin=subprocess.PIPE, stdout=out, stderr=subprocess.DEVNULL)
            children.append(encryptor)
            for block in iter(lambda: source.stdout.readline(8 * 1024 ** 2 + 1), b''):
                need(len(block) <= 8 * 1024 ** 2, 'bounded_sql_statement_line')
                total += len(block)
                need(total <= 512 * 1024 ** 2, 'bounded_sql_snapshot')
                plaintext_sha.update(block)
                encryptor.stdin.write(block)
                create_tables += block.startswith(b'CREATE TABLE ')
                insert_statements += block.startswith(b'INSERT INTO ')
            encryptor.stdin.close()
            need(total > 1024 and source.wait(timeout=30) == 0 and encryptor.wait(timeout=30) == 0, 'complete_mysql_dump_and_encryption')
            need(create_tables == 12 and insert_statements >= 8, 'complete_twelve_table_schema_and_original_content')
            out.flush()
            os.fsync(out.fileno())
        verify = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(verify)
        verified_sha = hashlib.sha256()
        verified_bytes = 0
        for block in iter(lambda: verify.stdout.read(1024 ** 2), b''):
            verified_bytes += len(block)
            need(verified_bytes <= total, 'authenticated_sql_size')
            verified_sha.update(block)
        need(verify.wait(timeout=30) == 0 and verified_bytes == total and verified_sha.digest() == plaintext_sha.digest(), 'full_sql_authenticated_eof_and_hash')
        need(fence() == before and shared.file_hash(Path(__file__)) == source_sha, 'same_quiesced_app_database_and_source')
        for f, identity in pins:
            need(shared.protected(f, f == shared.IDENTITY) == identity, 'crypto_identity_unchanged')
        record.update(status='completed', archive=str(cipher), archiveBytes=cipher.stat().st_size, archiveSHA256=shared.file_hash(cipher),
                      plaintextBytes=total, fullAuthenticatedRoundTrip=True, visibleApplicationTables=12,
                      routinesAndEventsAbsent=True, sourceSHA256=source_sha)
        record.update(createTableStatements=create_tables, insertStatements=insert_statements)
    except Exception as error:
        record.update(status='failed', failure=str(error) if isinstance(error, ValueError) else type(error).__name__)
    finally:
        signal.alarm(0)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
        record['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    out = folder / 'receipt.json'
    print(json.dumps({'status': record['status'], 'receipt': str(out), 'receiptSHA256': shared.file_hash(out)}))
    return 0 if record['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
