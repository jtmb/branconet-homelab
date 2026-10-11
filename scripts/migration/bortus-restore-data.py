"""Bounded independent restore data composition; no CLI, API or Node launcher."""
import copy
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import stat
import subprocess
import sys
import time
from typing import NamedTuple
import uuid


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Callers construct Collector/SourceSnapshot through these exact exposed interfaces.
watch = load('bortus_data_watch', 'bortus-restore-watch.py')
health = load('bortus_data_health', 'bortus-restored-consumer-fence.py')
archive = load('bortus_data_archive', 'bortus-sqlite-archive.py')
normalization = load('bortus_data_normalization', 'normalize-bortus-sqlite-archive.py')
comparison = load('bortus_data_comparison', 'compare-bortus-databases.py')
MAX_RECORD = 65536
ARCHIVE_NAME = 'restored-sqlite.age'
FAILURES = ('prerequisite', 'source', 'health', 'identity_drift', 'capture',
            'normalization', 'comparison', 'cleanup', 'deadline', 'ownership', 'durability')


class DataRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in FAILURES else 'prerequisite'
        super().__init__('Independent restored data refused: ' + self.code)


def need(condition, code):
    if not condition:
        raise DataRefused(code)


def failure_code(error, stage):
    if type(error) is DataRefused:
        return error.code
    if type(error) is watch.WatchRefused:
        return 'prerequisite'
    return stage if stage in FAILURES else 'durability'


class SourceSnapshot(NamedTuple):
    """Fresh independently validated source metadata, never an authorization boolean."""
    checkpoint_journal_sha256: str
    original_ciphertext_sha256: str
    claim: health.Identity
    pv: health.Identity
    volume: health.Identity
    backup: health.Identity


class DataResult(NamedTuple):
    run_id: str
    artifact_basename: str
    ciphertext_bytes: int
    recovery_rows_equal: bool = True
    exact_tmpfs_copies_cleaned: bool = True
    overall_live_restore_acceptance: bool = False
    image_runtime_admission_acceptance: bool = False


def identity_dict(ident):
    need(type(ident) is health.Identity, 'identity')
    health.identity({'metadata': {'name': ident.name, 'uid': ident.uid,
        'namespace': ident.namespace, 'resourceVersion': ident.resource_version}}, ident.namespace)
    return ident._asdict()


def health_record(value):
    return {key: [identity_dict(r) for r in value.replicas] if key == 'replicas'
            else identity_dict(getattr(value, key)) for key in
            ('claim', 'pv', 'volume', 'backup', 'holder', 'engine', 'replicas', 'node')}


def same_identities(before, after):
    for key in before:
        a, b = before[key], after[key]
        if type(a) is list:
            need(len(a) == len(b), 'identity_drift')
            for left, right in zip(a, b):
                need(all(left[k] == right[k] for k in ('name', 'uid', 'namespace')), 'identity_drift')
        else:
            need(all(a[k] == b[k] for k in ('name', 'uid', 'namespace')), 'identity_drift')


class Sidecar:
    """A new file under the borrowed WatchJournal, never a watch/journal ABI extension."""
    def __init__(self, collector):
        self.collector, self.journal = collector, collector.journal
        self.inode = self.digest = None
        self.state = {'abi': 1, 'state': 'pending', 'failure': None,
            'run_id': self.journal.record['run_id'], 'lease_id': collector.state['lease_id'],
            'checkpoint_journal_sha256': self.journal.record['checkpoint_journal_sha256'],
            'proposal_sha256': self.journal.record['reviewed_proposal_sha256'],
            'module_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            'artifact_basename': ARCHIVE_NAME, 'ciphertext_bytes': None,
            'source_before': None, 'source_after': None, 'health_before': None, 'health_after': None,
            'watch_before': None, 'watch_after': None, 'tmpfs_cleanup': [],
            'recovery_rows_equal': False, 'overall_live_restore_acceptance': False,
            'image_runtime_admission_acceptance': False}
        self.keys = set(self.state)
        with self.journal.watch_lock:
            self.journal._owned()
            fd = os.open('data.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                         0o600, dir_fd=self.journal.fd)
            try:
                info = os.fstat(fd)
                self.inode = (info.st_dev, info.st_ino)
            finally:
                os.close(fd)
            self.save()  # A failed flush retains an existing unaccepted file; no replay.

    def check(self):
        self.journal._owned()
        fd = os.open('data.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.journal.fd)
        try:
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                 stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1 and
                 info.st_size <= MAX_RECORD and (info.st_dev, info.st_ino) == self.inode, 'ownership')
            raw = os.read(fd, MAX_RECORD + 1)
            need(len(raw) <= MAX_RECORD and (self.digest is None or
                 hashlib.sha256(raw).hexdigest() == self.digest), 'ownership')
        finally:
            os.close(fd)

    def save(self):
        with self.journal.watch_lock:
            self.check()
            self.validate()
            raw = (json.dumps(self.state, separators=(',', ':')) + '\n').encode()
            need(len(raw) <= MAX_RECORD, 'durability')
            name = 'data-' + uuid.uuid4().hex + '.next'
            fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                         0o600, dir_fd=self.journal.fd)
            try:
                with os.fdopen(fd, 'wb', closefd=False) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(fd)
                    info = os.fstat(fd)
                    new_inode = (info.st_dev, info.st_ino)
            finally:
                os.close(fd)
            self.check()
            os.replace(name, 'data.json', src_dir_fd=self.journal.fd, dst_dir_fd=self.journal.fd)
            # Pin the exact owned replacement even if its directory flush fails.
            # The caller may then retain a refused outcome, never replay source IO.
            self.inode, self.digest = new_inode, hashlib.sha256(raw).hexdigest()
            os.fsync(self.journal.fd)
            self.check()

    def validate(self):
        need(type(self.state) is dict and set(self.state) == self.keys and
             type(self.state['abi']) is int and self.state['abi'] == 1 and
             self.state['run_id'] == self.journal.record['run_id'] and
             self.state['lease_id'] == self.collector.state['lease_id'] and
             self.state['checkpoint_journal_sha256'] == self.journal.record['checkpoint_journal_sha256'] and
             self.state['proposal_sha256'] == self.journal.record['reviewed_proposal_sha256'] and
             type(self.state['module_sha256']) is str and
             re.fullmatch('[0-9a-f]{64}', self.state['module_sha256']) and
             self.state['artifact_basename'] == ARCHIVE_NAME and
             self.state['state'] in ('pending', 'confirmed', 'refused') and
             self.state['failure'] in (None,) + FAILURES and
             self.state['overall_live_restore_acceptance'] is False and
             self.state['image_runtime_admission_acceptance'] is False, 'durability')
        for key in ('source_before', 'source_after', 'health_before', 'health_after'):
            record = self.state[key]
            if record is None:
                continue
            keys = {'claim', 'pv', 'volume', 'backup'} if key.startswith('source') else {
                'claim', 'pv', 'volume', 'backup', 'holder', 'engine', 'replicas', 'node'}
            need(type(record) is dict and set(record) == keys, 'durability')
            for name, identities in record.items():
                if name == 'replicas':
                    need(type(identities) is list and len(identities) == 2, 'durability')
                else:
                    identities = [identities]
                for ident in identities:
                    need(type(ident) is dict and set(ident) == set(health.Identity._fields), 'durability')
                    identity_dict(health.Identity(**ident))
        for key in ('watch_before', 'watch_after'):
            proof = self.state[key]
            if proof is not None:
                need(type(proof) is dict and set(proof) == {'lease_id', 'collection_resource_version',
                    'sequence', 'durable_record_sha256'} and proof['lease_id'] == self.state['lease_id'] and
                    type(proof['sequence']) is int and 0 <= proof['sequence'] <= watch.MAX_WATCH_FRAMES and
                    type(proof['durable_record_sha256']) is str and
                    re.fullmatch('[0-9a-f]{64}', proof['durable_record_sha256']) and
                    type(proof['collection_resource_version']) is str, 'durability')
                health.text(proof['collection_resource_version'])
        cleaned = self.state['tmpfs_cleanup']
        need(type(cleaned) is list and len(cleaned) <= 2 and all(type(v) is bool for v in cleaned) and
             type(self.state['recovery_rows_equal']) is bool, 'durability')
        size = self.state['ciphertext_bytes']
        need(size is None or (type(size) is int and 0 < size <= archive.MAX_TOTAL * 2), 'durability')
        if self.state['state'] == 'confirmed':
            need(self.state['failure'] is None and cleaned == [True, True] and size is not None and
                 self.state['recovery_rows_equal'] is True and all(self.state[k] is not None for k in
                 ('source_before', 'source_after', 'health_before', 'health_after',
                  'watch_before', 'watch_after')), 'durability')
        else:
            need(self.state['recovery_rows_equal'] is False and (self.state['failure'] is not None
                 if self.state['state'] == 'refused' else self.state['failure'] is None), 'durability')


def execute(collector, expected_health, original_archive, original_ciphertext_sha256, *, age,
            recipient_file, identity_file, source_fence, read_metadata, launch_reader, deadline):
    """Compose trusted fresh callbacks; never infer a live gate from their fixture success.

    launch_reader(holder Identity, deadline) returns an owned Popen with PIPE stdin/stdout
    and suppressed private stderr. This function sends the exact immutable NODE_READER.
    The caller owns the Collector and must close it in its outer finally, after any
    separate fresh UID/RV holder-delete transaction. This function never deletes a Pod.
    """
    sidecar = source = None
    copies = []
    failure = 'prerequisite'
    first_source = first_health = None
    try:
        now = time.monotonic()
        need(type(deadline) in (int, float) and math.isfinite(deadline) and
             now < deadline <= now + 300, 'deadline')
        need(type(collector) is watch.Collector and type(collector.journal) is watch.WatchJournal and
             deadline <= collector.deadline and all(callable(c) for c in
                 (source_fence, read_metadata, launch_reader)), 'prerequisite')
        health.bounded(expected_health)
        expected = copy.deepcopy(expected_health)
        with collector.lock:
            collector.prerequisite()
            need(collector.state['metadata_eligible'] is True and collector.expected is not None,
                 'prerequisite')
            holder = collector.journal.record['operations'].get('holder_create', {})
            need(holder.get('state') == 'confirmed' and
                 all(holder['identity'][key] == expected['holder'][key]
                     for key in ('name', 'namespace', 'uid')) and
                 'holder_delete' not in collector.journal.record['operations'], 'prerequisite')
            cs = collector.source
            need(cs.original_claim_uid == expected['original_claim']['uid'] and
                 cs.original_pv_uid == expected['original_pv']['uid'] and
                 cs.original_volume_uid == expected['original_volume']['uid'] and
                 cs.original_volume_handle == expected['original_volume']['name'] and
                 cs.backup.name == expected['backup']['name'] and cs.backup.uid == expected['backup']['uid'] and
                 cs.backup_url == expected['backup_url'] and
                 collector.expected.volume_uid == expected['volume']['uid'] and
                 collector.expected.volume_name == expected['volume']['name'], 'prerequisite')
        failure = 'durability'
        sidecar = Sidecar(collector)

        def live():
            need(time.monotonic() < deadline, 'deadline')
            with collector.lock:
                proof = collector.prerequisite()
                need(collector.state['metadata_eligible'] is True and
                     proof.lease_id == sidecar.state['lease_id'] and
                     'holder_delete' not in collector.journal.record['operations'], 'prerequisite')
                sidecar.check()
            return {'lease_id': proof.lease_id, 'collection_resource_version': proof.collection_resource_version,
                    'sequence': proof.sequence, 'durable_record_sha256': proof.durable_record_sha256}

        def fences():
            nonlocal first_source, first_health, failure
            live()
            failure = 'source'
            snapshot = source_fence(deadline)
            need(type(snapshot) is SourceSnapshot and snapshot.checkpoint_journal_sha256 ==
                 collector.journal.record['checkpoint_journal_sha256'] and
                 type(original_ciphertext_sha256) is str and
                 re.fullmatch('[0-9a-f]{64}', original_ciphertext_sha256) and
                 snapshot.original_ciphertext_sha256 == original_ciphertext_sha256, 'source')
            sr = {key: identity_dict(getattr(snapshot, key)) for key in ('claim', 'pv', 'volume', 'backup')}
            for key in sr:
                trusted = expected['backup' if key == 'backup' else 'original_' + key]
                need(all(sr[key][field] == trusted[field] for field in ('name', 'uid', 'namespace')), 'source')
            live()
            failure = 'health'
            eligible = health.evaluate(expected, read_metadata(deadline))
            hr = health_record(eligible)
            if first_source is None:
                first_source, first_health = sr, hr
            else:
                same_identities(first_source, sr)
                same_identities(first_health, hr)
            live()
            return sr, hr, eligible

        sr, hr, eligible = fences()
        sidecar.state.update(source_before=sr, health_before=hr, watch_before=live())
        sidecar.save()
        live()
        failure = 'capture'
        launched = launch_reader(eligible.holder, deadline)
        need(type(launched) is subprocess.Popen, 'capture')
        source = launched
        need(source.stdin is not None and source.stdout is not None and source.stderr is None, 'capture')
        writer = archive.Pipe(source.stdin, deadline, False)
        try:
            writer.write(archive.NODE_READER.encode())
            source.stdin.close()
        finally:
            writer.close()
        captured = archive.encrypt_source(source, collector.journal.directory / ARCHIVE_NAME, age,
            recipient_file, identity_file, deadline, directory_fd=collector.journal.fd)
        cipher_stamp = os.stat(ARCHIVE_NAME, dir_fd=collector.journal.fd, follow_symlinks=False)

        def ciphertext_unchanged():
            info = os.stat(ARCHIVE_NAME, dir_fd=collector.journal.fd, follow_symlinks=False)
            need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and
                 info.st_uid == os.getuid() and info.st_nlink == 1 and
                 all(getattr(info, field) == getattr(cipher_stamp, field) for field in
                     ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'ownership')
            return info
        fences()
        live()
        failure = 'normalization'
        for path, digest in ((original_archive, original_ciphertext_sha256),
                             (collector.journal.directory / ARCHIVE_NAME, captured['ciphertext_sha256'])):
            live()
            info = pathlib.Path(path).lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                 stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'normalization')
            result = normalization.normalize(path, digest, identity_file, age=age,
                                             seconds=300, deadline=deadline)
            copies.append(result)
            live()
        failure = 'comparison'
        live()
        compared = comparison.compare(pathlib.Path(copies[0]['database_path']),
            pathlib.Path(copies[1]['database_path']), 'recovery', deadline=deadline)
        need(compared['passed'] is True, 'comparison')
        live()
        sr, hr, _ = fences()
        sidecar.state.update(source_after=sr, health_after=hr, watch_after=live())
        failure = None
    except Exception as error:
        failure = failure_code(error, failure)
    finally:
        cleanup_failed = False
        for result in copies:
            try:
                normalization.cleanup(result['temporary_directory'], result['temporary_directory_identity'])
                if sidecar: sidecar.state['tmpfs_cleanup'].append(True)
            except Exception:
                cleanup_failed = True
                if sidecar: sidecar.state['tmpfs_cleanup'].append(False)
        if source is not None:
            try:
                archive.stop_owned(source)
            except Exception:
                cleanup_failed = True
            for stream in (source.stdin, source.stdout, source.stderr):
                try:
                    if stream and not stream.closed:
                        stream.close()
                except Exception:
                    cleanup_failed = True
        if cleanup_failed:
            failure = 'cleanup'
    if sidecar is None:
        raise DataRefused(failure or 'prerequisite') from None
    try:
        if failure is None:
            # Actual lease and fresh source/health fences still apply AFTER cleanup.
            sr, hr, _ = fences()
            sidecar.state.update(source_after=sr, health_after=hr, watch_after=live())
            info = ciphertext_unchanged()
            sidecar.state.update(state='confirmed', ciphertext_bytes=info.st_size,
                                 recovery_rows_equal=True, failure=None)
            live()
            failure = None
        else:
            sidecar.state.update(state='refused', failure=failure, recovery_rows_equal=False)
        sidecar.save()
    except Exception as error:
        # A durable prior pending record also refuses replay; never return acceptance.
        final_failure = failure_code(error, failure)
        try:
            sidecar.state.update(state='refused', failure=final_failure, recovery_rows_equal=False)
            sidecar.save()
        except Exception:
            pass
        # Leave the handler before exposing a fixed refusal: `from None` alone
        # hides display but still retains the private callback in __context__.
        failure = final_failure
    if failure is not None:
        raise DataRefused(failure) from None
    return DataResult(sidecar.state['run_id'], ARCHIVE_NAME, sidecar.state['ciphertext_bytes'])
