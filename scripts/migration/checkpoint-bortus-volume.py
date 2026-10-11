#!/usr/bin/env python3
"""Fenced BORTUS-only encrypted SQLite/Longhorn checkpoint. No native Secret reads."""
import argparse
import datetime
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import uuid
import urllib.parse

loader = importlib.util.spec_from_file_location('bortus_preflight',
    pathlib.Path(__file__).with_name('inspect-bortus-checkpoint.py'))
preflight = importlib.util.module_from_spec(loader)
loader.loader.exec_module(preflight)
require = preflight.require
identity = preflight.identity
RUNTIME = preflight.RUNTIME
RESOURCES = {
    'deployment': ('deployment', 'bortus', 'bortus', 'replicas'),
    'helmrelease': ('helmrelease', 'bortus', 'flux-system', 'suspend'),
    'kustomization': ('kustomization', 'migration-releases', 'flux-system', 'suspend')}


def archive_sqlite(checkpoint):
    spec = importlib.util.spec_from_file_location('bortus_sqlite_archive',
        pathlib.Path(__file__).with_name('bortus-sqlite-archive.py'))
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)
    return archive.capture(checkpoint)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def same_id(actual, expected):
    return all(identity(actual)[key] == expected[key] for key in ('name', 'namespace', 'uid'))


def valid_digest(image):
    # Accept OCI registry ports, but reject schemes, tags and incomplete digests.
    return bool(re.fullmatch(
        r'(?:(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)(?::[0-9]{1,5})?/)?'
        r'[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*'
        r'@sha256:[0-9a-f]{64}', image))


def cas_patch(obj, expected, field, old, new):
    require(same_id(obj, expected), 'Resource identity changed')
    spec = obj.get('spec', {})
    actual = spec.get(field, False if field == 'suspend' else None)
    require(type(actual) is type(old) and actual == old, 'Controlled field changed')
    operations = [
        {'op': 'test', 'path': '/metadata/uid', 'value': expected['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion',
         'value': identity(obj)['resourceVersion']}]
    if field in spec:
        operations.append({'op': 'test', 'path': '/spec/' + field, 'value': old})
    operations.append({'op': 'add', 'path': '/spec/' + field, 'value': new})
    return operations


class Client(preflight.Client):
    def request(self, args, body):
        # Bodies (including delete preconditions) go over stdin, never argv.
        argv = [str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'),
                '--request-timeout=20s', *args]
        result = subprocess.run(argv, input=json.dumps(body).encode(), capture_output=True,
                                timeout=25)
        require(result.returncode == 0 and len(result.stdout) <= 8 * 1024 * 1024,
                'API mutation result unavailable; do not replay')
        try:
            obj = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise RuntimeError('API mutation result unavailable; do not replay') from None
        require(isinstance(obj, dict), 'Invalid API mutation reply')
        return obj

    def change(self, kind, name, ns, patch):
        return self.request(['patch', kind, name, '-n', ns, '--type=json',
                             '--patch-file=/dev/stdin', '-o', 'json'], patch)

    def create(self, body, dry_run=False):
        return self.request(['create', '-f', '-', '-o', 'json'] +
                            (['--dry-run=server'] if dry_run else []), body)

    def delete_holder(self, obj):
        meta = identity(obj)
        require(meta['namespace'] == 'bortus' and
                re.fullmatch(r'bortus-cold-[0-9a-f]{12}', meta['name']), 'Invalid holder identity')
        return self.request(['delete', '--raw', '/api/v1/namespaces/bortus/pods/' + meta['name'],
                             '-f', '-'], {
            'apiVersion': 'v1', 'kind': 'DeleteOptions',
            'preconditions': {'uid': meta['uid'], 'resourceVersion': meta['resourceVersion']}})


class Journal:
    def __init__(self, directory, record=None):
        self.directory = pathlib.Path(directory)
        self.path = self.directory / 'journal.json'
        self.lock = self.directory / 'active.lock'
        self.record = record
        self.opened = False
        self.locked = False

    def open(self, new):
        if new:
            self.directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        require(self.directory.is_dir() and not self.directory.is_symlink(), 'Invalid run directory')
        fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        self.locked = True
        with os.fdopen(fd, 'w', encoding='ascii') as out:
            out.write(str(os.getpid()) + '\n')
        if not new:
            require(self.path.is_file() and not self.path.is_symlink(), 'Missing retained journal')
            self.record = json.loads(self.path.read_text(encoding='utf-8'))
        else:
            require(not os.path.lexists(self.path), 'Journal already exists')
        self.opened = True
        self.save()
        return self

    def save(self):
        require(self.opened and self.locked, 'Journal is not exclusively open')
        self.record['updated_at_utc'] = now()
        target = self.directory / ('journal-' + uuid.uuid4().hex + '.next')
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(self.record, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(target, self.path)

    def close(self):
        # Only this process's exact lock, never a stale lock from another run.
        if self.locked and self.lock.is_file() and self.lock.read_text(encoding='ascii') == str(os.getpid()) + '\n':
            self.lock.unlink()
        self.locked = False


class Checkpoint:
    def __init__(self, client, journal, sleep=time.sleep, monotonic=time.monotonic, archive=archive_sqlite):
        self.client = client
        self.journal = journal
        self.r = journal.record
        self.sleep = sleep
        self.monotonic = monotonic
        self.archive = archive

    def wait(self, predicate, seconds):
        deadline = self.monotonic() + seconds
        while True:
            value = predicate()
            if value:
                return value
            require(self.monotonic() < deadline, 'Bounded checkpoint wait expired')
            self.sleep(2)

    def control(self, key, old, new):
        entry = self.r['controls'][key]
        kind, name, ns, field = RESOURCES[key]
        obj = self.client.get(kind, name, ns)
        patch = cas_patch(obj, entry['identity'], field, old, new)
        entry['intent'] = {'from': old, 'to': new, 'state': 'pending',
                           'resourceVersion': identity(obj)['resourceVersion']}
        self.journal.save()
        try:
            result = self.client.change(kind, name, ns, patch)
            require(same_id(result, entry['identity']) and
                    type(result.get('spec', {}).get(field)) is type(new) and
                    result['spec'][field] == new, 'Unexpected mutation reply')
        except Exception:
            # A timeout may have applied. Record uncertainty; never automatically replay.
            entry['intent']['state'] = 'uncertain'
            self.journal.save()
            raise
        entry['intent']['state'] = 'confirmed'
        entry['current'] = new
        self.journal.save()

    def storage(self):
        ids = self.r['baseline']['identities']
        claim = self.client.get('pvc', 'bortus-data', 'bortus')
        pv = self.client.get('pv', ids['pv']['name'])
        volume = self.client.get('volumes.longhorn.io', ids['longhorn_volume']['name'], 'longhorn-system')
        require(same_id(claim, ids['claim']) and same_id(pv, ids['pv']) and
                same_id(volume, ids['longhorn_volume']), 'Storage identity changed')
        require(claim.get('status', {}).get('phase') == 'Bound' and
                claim.get('spec', {}).get('volumeName') == ids['pv']['name'] and
                claim['metadata'].get('annotations', {}).get('helm.sh/resource-policy') == 'keep',
                'Original claim mapping or retention changed')
        pspec = pv.get('spec', {})
        ref = pspec.get('claimRef', {})
        require(ref.get('uid') == ids['claim']['uid'] and ref.get('namespace') == 'bortus' and
                ref.get('name') == 'bortus-data' and pspec.get('persistentVolumeReclaimPolicy') == 'Retain'
                and pspec.get('csi', {}).get('driver') == 'driver.longhorn.io' and
                pspec['csi'].get('volumeHandle') == ids['longhorn_volume']['name'], 'PV mapping changed')
        require(volume.get('spec', {}).get('encrypted') is True and
                type(volume['spec'].get('numberOfReplicas')) is int and
                volume['spec']['numberOfReplicas'] == 2 and
                volume.get('status', {}).get('robustness') == 'healthy', 'Longhorn safety changed')

    def holder(self):
        expected = self.r.get('holder_identity')
        require(expected is not None, 'Holder creation result unresolved')
        obj = self.client.get('pod', expected['name'], 'bortus')
        require(same_id(obj, expected) and not obj['metadata'].get('deletionTimestamp'), 'Holder identity changed')
        spec = obj.get('spec', {})
        proposal = self.r['holder_proposal']['spec']
        containers = spec.get('containers', [])
        proposed = proposal['containers'][0]
        require(len(containers) == 1 and
                all(containers[0].get(k) == v for k, v in proposed.items()) and
                not (set(containers[0]) - set(proposed) -
                     {'terminationMessagePath', 'terminationMessagePolicy'}) and
                spec.get('securityContext') == proposal['securityContext'], 'Holder execution changed')
        require(spec.get('nodeName') == proposal['nodeName'] and
                spec.get('automountServiceAccountToken') is False and
                spec.get('volumes') == proposal['volumes'] and
                spec.get('initContainers', []) == [] and spec.get('ephemeralContainers', []) == [],
                'Holder contract changed')
        # API defaults are allowed outside the bounded container/volume contract.
        return obj

    def consumers(self):
        return [p for p in self.client.get('pods', namespace='bortus').get('items', [])
                if preflight.uses_claim(p) and p.get('status', {}).get('phase') not in ('Succeeded', 'Failed')]

    def cold(self):
        self.storage()
        for key, desired in [('deployment', 0), ('helmrelease', True), ('kustomization', True)]:
            kind, name, ns, field = RESOURCES[key]
            obj = self.client.get(kind, name, ns)
            require(same_id(obj, self.r['controls'][key]['identity']) and
                    type(obj.get('spec', {}).get(field)) is type(desired) and
                    obj['spec'][field] == desired, 'Cold controller fence changed')
        holder = self.holder()
        active = self.consumers()
        require(all(identity(p)['uid'] in (identity(holder)['uid'], self.r['baseline']['writer']['uid'])
                    for p in active),
                'Unexpected claim consumer; cold capture refused')
        return len(active) == 1 and identity(active[0])['uid'] == identity(holder)['uid'] and \
            holder.get('status', {}).get('phase') == 'Running' and any(
            c.get('type') == 'Ready' and c.get('status') == 'True'
            for c in holder.get('status', {}).get('conditions', []))

    def writer_ready(self):
        self.storage()
        kind, name, ns, _ = RESOURCES['deployment']
        deployment = self.client.get(kind, name, ns)
        require(same_id(deployment, self.r['controls']['deployment']['identity']) and
                type(deployment.get('spec', {}).get('replicas')) is int and
                deployment['spec']['replicas'] == 1, 'Resume controller changed')
        h_uid = self.r.get('holder_identity', {}).get('uid')
        active = [p for p in self.consumers() if identity(p)['uid'] != h_uid]
        require(len(active) <= 1, 'Unexpected concurrent claim consumers')
        if not active:
            return False
        writer = active[0]
        require(not writer['metadata'].get('deletionTimestamp'), 'Unexpected terminating consumer')
        parents = [p for p in writer['metadata'].get('ownerReferences', []) if p.get('controller') is True]
        require(len(parents) == 1 and parents[0].get('kind') == 'ReplicaSet', 'Unknown writer owner')
        rs = self.client.get('replicaset', parents[0]['name'], 'bortus')
        require(identity(rs)['uid'] == parents[0].get('uid'), 'ReplicaSet identity changed')
        owners = [p for p in rs['metadata'].get('ownerReferences', []) if p.get('controller') is True]
        require(len(owners) == 1 and owners[0].get('kind') == 'Deployment' and
                owners[0].get('uid') == identity(deployment)['uid'] and owners[0].get('name') == 'bortus',
                'Unexpected resumed writer')
        return writer.get('status', {}).get('phase') == 'Running' and any(
            c.get('type') == 'Ready' and c.get('status') == 'True'
            for c in writer.get('status', {}).get('conditions', []))

    def resume(self):
        # Resume also serves an explicitly requested interrupted-run recovery.
        # Resolve pending outcomes by reads; do not repeat the original mutation.
        self.storage()
        for key in ('deployment', 'helmrelease', 'kustomization'):
            entry = self.r['controls'][key]
            intent = entry.get('intent')
            kind, name, ns, field = RESOURCES[key]
            obj = self.client.get(kind, name, ns)
            require(same_id(obj, entry['identity']), 'Resume identity changed')
            current = obj.get('spec', {}).get(field, False if field == 'suspend' else None)
            require(type(current) is type(entry['original']), 'Resume field type changed')
            if not intent:
                require(current == entry['original'], 'Untouched original field changed')
                if key == 'deployment':
                    self.wait(self.writer_ready, 180)
                continue
            if current == entry['original']:
                entry['current'] = current
                entry['intent']['state'] = 'original-observed'
                self.journal.save()
                if key == 'deployment':
                    self.wait(self.writer_ready, 180)
                continue
            require(current == intent['to'], 'Resume state is not the recorded intent')
            if key == 'deployment':
                def original_writer_gone():
                    holder_uid = self.r.get('holder_identity', {}).get('uid')
                    active = self.consumers()
                    require(all(identity(p)['uid'] in (holder_uid, self.r['baseline']['writer']['uid'])
                                for p in active), 'Unexpected consumer blocks writer resume')
                    return all(identity(p)['uid'] == holder_uid for p in active)

                self.wait(original_writer_gone, 180)
            self.control(key, current, entry['original'])
            if key == 'deployment':
                self.wait(self.writer_ready, 180)
        # Confirm actual readiness even when the deployment mutation was never applied.
        self.wait(self.writer_ready, 180)
        self.r['writer_resumed_ready'] = True
        self.r['reconcile_flags_restored'] = True
        self.journal.save()

    def create_owned(self, label, body):
        self.r[label + '_create_state'] = 'pending'
        self.journal.save()
        try:
            obj = self.client.create(body)
            meta = identity(obj)
            require(meta['name'] == body['metadata']['name'] and
                    meta['namespace'] == body['metadata']['namespace'], 'Created resource differs')
        except Exception:
            self.r[label + '_create_state'] = 'uncertain'
            self.journal.save()
            raise
        self.r[label + '_identity'] = meta
        self.r[label + '_create_state'] = 'confirmed'
        self.journal.save()
        return obj

    def capture(self):
        body = self.r['holder_proposal']
        # Qualify admission/schema before suspending controllers or stopping a writer.
        self.client.create(body, dry_run=True)
        self.create_owned('holder', body)
        self.wait(lambda: self.holder().get('status', {}).get('phase') == 'Running' and any(
            c.get('type') == 'Ready' and c.get('status') == 'True'
            for c in self.holder().get('status', {}).get('conditions', [])), 180)
        self.storage()
        active = self.consumers()
        require({identity(p)['uid'] for p in active} == {
            self.r['baseline']['writer']['uid'], self.r['holder_identity']['uid']},
            'Writer changed before suspension')
        try:
            for key in ('kustomization', 'helmrelease'):
                original = self.r['controls'][key]['original']
                if not original:
                    self.control(key, False, True)
            self.control('deployment', 1, 0)
            self.wait(self.cold, 180)
            self.r['sqlite_archive_state'] = 'pending'
            self.r['database_byte_read_attempted'] = True
            self.r['database_or_secret_reads'] = None
            self.journal.save()
            result = self.archive(self)
            require(result.get('authenticated_decryption_equal') is True and
                    result.get('nas_ciphertext_equal') is True and result.get('plaintext_persisted') is False,
                    'Encrypted SQLite archive not verified')
            self.r['sqlite_archive'] = result
            self.r['sqlite_archive_state'] = 'confirmed'
            self.r['database_byte_reads'] = True
            self.r['database_or_secret_reads'] = len(result['files'])
            self.journal.save()
            snapshot = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'Snapshot',
                'metadata': {'name': self.r['snapshot_name'], 'namespace': 'longhorn-system',
                             'labels': {'bortus-checkpoint': self.r['run_id']}},
                'spec': {'volume': self.r['baseline']['identities']['longhorn_volume']['name'],
                         'createSnapshot': True, 'labels': {'bortus-consistency': 'cold-writer-stopped'}}}
            self.create_owned('snapshot', snapshot)

            def snapshot_ready():
                require(self.cold(), 'Cold holder not Ready')
                obj = self.client.get('snapshots.longhorn.io', self.r['snapshot_name'], 'longhorn-system')
                require(same_id(obj, self.r['snapshot_identity']) and
                        all(obj.get('spec', {}).get(k) == v for k, v in snapshot['spec'].items()),
                        'Snapshot identity or source changed')
                require(not obj.get('status', {}).get('error'), 'Snapshot controller failed')
                return obj.get('status', {}).get('readyToUse') is True

            self.wait(snapshot_ready, 300)
            self.r['cold_snapshot_ready'] = True
            self.journal.save()
        finally:
            # Attempt only conditional restoration of recorded fields. On ambiguity,
            # identity drift or a competing consumer, leave the journal for inspection.
            self.resume()
        backup = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'Backup',
            'metadata': {'name': self.r['backup_name'], 'namespace': 'longhorn-system',
                'labels': {'backup-volume': self.r['baseline']['identities']['longhorn_volume']['name'],
                           'backup-target': 'default', 'bortus-checkpoint': self.r['run_id']}},
            'spec': {'snapshotName': self.r['snapshot_name'], 'backupMode': 'full',
                     'labels': {'bortus-consistency': 'cold-writer-stopped'}}}
        self.create_owned('backup', backup)

        def backup_done():
            obj = self.client.get('backups.longhorn.io', self.r['backup_name'], 'longhorn-system')
            require(same_id(obj, self.r['backup_identity']) and
                    all(obj.get('spec', {}).get(k) == backup['spec'][k]
                        for k in ('snapshotName', 'backupMode')) and
                    obj.get('spec', {}).get('labels', {}).get('bortus-consistency') == 'cold-writer-stopped',
                    'Backup identity or source changed')
            status = obj.get('status', {})
            require(not status.get('error') and status.get('state') != 'Error', 'Backup controller failed')
            if status.get('state') != 'Completed':
                return False
            require(isinstance(status.get('url'), str), 'Completed backup URL missing')
            url = urllib.parse.urlsplit(status['url'])
            try:
                query = urllib.parse.parse_qs(url.query, strict_parsing=True,
                                             keep_blank_values=True, max_num_fields=2)
            except ValueError:
                raise RuntimeError('Expected credential-free completed NAS backup URL') from None
            require(url.scheme == 'cifs' and url.hostname == '192.168.0.8' and
                    url.username is None and url.password is None and url.port is None and not url.fragment and
                    url.path.rstrip('/') == '/container_backups/k8s-migration-20261009/longhorn' and
                    query == {'backup': [self.r['backup_name']], 'volume': [
                        self.r['baseline']['identities']['longhorn_volume']['name']]},
                    'Expected credential-free completed NAS backup URL')
            self.r['backup_url'] = status['url']
            return True

        self.wait(backup_done, 1800)
        self.r['encrypted_nas_backup_complete'] = True
        self.journal.save()
        holder = self.holder()
        self.client.delete_holder(holder)
        self.r['holder_delete_accepted'] = True
        self.wait(lambda: all(identity(p)['uid'] != self.r['holder_identity']['uid']
                             for p in self.client.get('pods', namespace='bortus').get('items', [])), 120)
        self.r['owned_holder_removed'] = True
        self.r['completed_at_utc'] = now()
        self.journal.save()


def prepare(client, expected, image, run_id):
    require(valid_digest(image), 'Exact tagless holder digest required')
    require(expected.get('checks_passed') is True and expected.get('mutations') == 0,
            'Read-only prerequisite report required')
    baseline = client.inspect(expected['identities']['claim']['uid'], image)
    for key in ('claim', 'pv', 'longhorn_volume', 'deployment', 'helmrelease', 'kustomization'):
        require(all(baseline['identities'][key][p] == expected['identities'][key][p]
                    for p in ('name', 'namespace', 'uid')), 'Expected prerequisite identity changed')
    require(baseline['writer']['uid'] == expected['writer']['uid'], 'Expected writer changed')
    proposal = baseline.pop('holder_proposal')
    proposal['metadata'].pop('generateName')
    proposal['metadata']['name'] = 'bortus-cold-' + run_id
    proposal['metadata']['labels'] = {'bortus-checkpoint': run_id}
    controls = {key: {'identity': baseline['identities'][key], 'original': value,
                      'current': value} for key, value in (
        ('deployment', 1), ('helmrelease', baseline['preserve_reconcile_state']['helmrelease_suspend']),
        ('kustomization', baseline['preserve_reconcile_state']['kustomization_suspend']))}
    require(all(type(controls[k]['original']) is bool for k in ('helmrelease', 'kustomization')),
            'Invalid reconciliation flag type')
    return {'scope': 'BORTUS-only cold Longhorn checkpoint; independent recovery remains pending',
        'run_id': run_id, 'started_at_utc': now(), 'baseline': baseline, 'controls': controls,
        'holder_proposal': proposal, 'snapshot_name': 'bortus-cold-' + run_id,
        'backup_name': 'backup-' + run_id, 'cold_snapshot_ready': False,
        'encrypted_nas_backup_complete': False, 'writer_resumed_ready': False,
        'reconcile_flags_restored': False, 'database_or_secret_reads': 0,
        'database_byte_reads': False, 'native_secret_reads': 0,
        'database_byte_read_attempted': False,
        'independent_restore_proven': False, 'sqlite_preservation_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    capture = modes.add_parser('capture')
    capture.add_argument('--preflight-report', type=pathlib.Path, required=True)
    capture.add_argument('--holder-image', required=True)
    resume = modes.add_parser('resume')
    resume.add_argument('--run-id', required=True)
    args = parser.parse_args()
    journal = None
    try:
        require(os.name == 'posix', 'Run only in the operator WSL environment')
        directory = RUNTIME / 'recovery/bortus-checkpoints'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        client = Client()
        if args.mode == 'capture':
            expected = json.loads(args.preflight_report.read_text(encoding='utf-8'))
            run_id = uuid.uuid4().hex[:12]
            record = prepare(client, expected, args.holder_image, run_id)
            journal = Journal(directory / run_id, record)
            journal.open(new=True)
            Checkpoint(client, journal).capture()
        else:
            require(bool(re.fullmatch(r'[0-9a-f]{12}', args.run_id)), 'Invalid run identity')
            journal = Journal(directory / args.run_id)
            journal.open(new=False)
            require(journal.record.get('run_id') == args.run_id, 'Retained run identity differs')
            Checkpoint(client, journal).resume()
        print(json.dumps({'operation': args.mode, 'run_id': journal.record['run_id'],
                          'writer_resumed_ready': journal.record['writer_resumed_ready'],
                          'independent_recovery_pending': True}))
        return 0
    except Exception:
        if journal and journal.opened and journal.record:
            journal.record['last_operation_failed'] = True
            try:
                journal.save()
            except Exception:
                pass
        print('BORTUS checkpoint operation failed; inspect the retained journal and controller state. '
              'Private API output withheld; do not blindly repeat capture.', file=sys.stderr)
        return 1
    finally:
        if journal:
            journal.close()


if __name__ == '__main__':
    raise SystemExit(main())
