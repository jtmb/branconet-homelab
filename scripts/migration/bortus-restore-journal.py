#!/usr/bin/env python3
"""Exclusive durable ownership ledger for the future independent restore executor."""
import copy
import datetime
import json
import os
import pathlib
import re
import stat
import uuid


def require(value):
    if not value:
        raise RuntimeError('Restore ownership journal invalid; inspect without replay')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def utc(value):
    require(isinstance(value, str) and len(value) <= 40 and
            re.fullmatch(r'[0-9:T.+-]+', value))
    try:
        require(datetime.datetime.fromisoformat(value).utcoffset() == datetime.timedelta(0))
    except ValueError:
        raise RuntimeError('Restore ownership timestamp invalid') from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def identity(obj):
    meta = obj.get('metadata', {})
    require(isinstance(meta, dict))
    result = {k: meta.get(k) for k in ('name', 'namespace', 'uid', 'resourceVersion')}
    for k in ('name', 'uid', 'resourceVersion'):
        require(isinstance(result[k], str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,253}', result[k]))
    require(result['namespace'] is None or result['namespace'] == 'bortus')
    return result


ACTIONS = {'storageclass_create': ('StorageClass', None),
           'claim_create': ('PersistentVolumeClaim', 'bortus'),
           'holder_create': ('Pod', 'bortus'), 'holder_delete': ('Pod', 'bortus')}


def seed(run_id, checkpoint_sha256, proposal_sha256):
    require(isinstance(run_id, str) and re.fullmatch(r'[0-9a-f]{12}', run_id))
    require(all(isinstance(x, str) and re.fullmatch(r'[0-9a-f]{64}', x)
                for x in (checkpoint_sha256, proposal_sha256)))
    return {'scope': 'Independent BORTUS restore ownership; no restore acceptance',
            'run_id': run_id, 'target_name': 'bortus-restore-' + run_id,
            'checkpoint_journal_sha256': checkpoint_sha256,
            'reviewed_proposal_sha256': proposal_sha256, 'started_at_utc': now(),
            'operations': {}, 'independent_restore_proven': False,
            'whole_row_preservation_proven': False}


def validate_record(record):
    require(isinstance(record, dict))
    expected = seed(record.get('run_id'), record.get('checkpoint_journal_sha256'),
                    record.get('reviewed_proposal_sha256'))
    require(set(record) in (set(expected), set(expected) | {'updated_at_utc'}))
    for key in set(expected) - {'started_at_utc', 'operations'}:
        require(type(record[key]) is type(expected[key]) and record[key] == expected[key])
    for key in ('started_at_utc', 'updated_at_utc'):
        if key in record:
            utc(record[key])
    operations = record['operations']
    require(isinstance(operations, dict) and set(operations) <= set(ACTIONS))
    for action, entry in operations.items():
        kind, namespace = ACTIONS[action]
        require(isinstance(entry, dict) and
                set(entry) <= {'state', 'kind', 'name', 'namespace', 'started_at_utc',
                               'finished_at_utc', 'identity', 'preconditions'} and
                entry.get('state') in ('pending', 'confirmed', 'uncertain') and
                entry.get('kind') == kind and entry.get('namespace') == namespace and
                entry.get('name') == record['target_name'])
        for key in ('started_at_utc', 'finished_at_utc'):
            if key in entry:
                utc(entry[key])
        require('started_at_utc' in entry)
        if action == 'holder_delete':
            created = operations.get('holder_create', {})
            require(created.get('state') == 'confirmed' and 'identity' in created and
                    'preconditions' in entry and 'identity' not in entry)
            owned = identity({'metadata': entry['preconditions']})
            require(owned == entry['preconditions'] and all(
                owned[k] == created['identity'][k] for k in ('name', 'namespace', 'uid')))
        elif entry['state'] == 'confirmed':
            owned = identity({'metadata': entry.get('identity', {})})
            require(owned == entry['identity'] and owned['name'] == record['target_name'] and
                    owned['namespace'] == namespace and 'preconditions' not in entry)
        else:
            require('identity' not in entry and 'preconditions' not in entry)


class Journal:
    """Never auto-replay confirmed, pending or uncertain operations on reopening."""
    def __init__(self, directory):
        self.directory = pathlib.Path(directory)
        self.fd = None
        self.parent_fd = None
        self.record = None
        self.lock_inode = None
        self.journal_inode = None

    def _file(self, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                    stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 1024 * 1024)
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                return stream.read(1024 * 1024 + 1), (info.st_dev, info.st_ino)
        finally:
            os.close(fd)

    def open(self, record=None):
        require(os.name == 'posix' and self.fd is None and self.parent_fd is None)
        if record is not None:
            # Validate only the narrow metadata seed before creating anything.
            validate_record(record)
            require(record['operations'] == {} and 'updated_at_utc' not in record)
        try:
            self.parent_fd = os.open(self.directory.parent,
                                     os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            parent = os.fstat(self.parent_fd)
            require(parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700)
            self.parent_inode = (parent.st_dev, parent.st_ino)
            if record is not None:
                os.mkdir(self.directory.name, mode=0o700, dir_fd=self.parent_fd)
            self.fd = os.open(self.directory.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=self.parent_fd)
            info = os.fstat(self.fd)
            require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700)
            self.directory_inode = (info.st_dev, info.st_ino)
            if record is not None:
                os.fsync(self.parent_fd)  # Persist the newly created run-directory entry.
            lock_fd = os.open('active.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              0o600, dir_fd=self.fd)
            try:
                info = os.fstat(lock_fd)
                self.lock_inode = (info.st_dev, info.st_ino)
                self.lock_value = (str(os.getpid()) + ':' + uuid.uuid4().hex + '\n').encode('ascii')
                os.write(lock_fd, self.lock_value)
                os.fsync(lock_fd)
            finally:
                os.close(lock_fd)
            os.fsync(self.fd)
            if record is None:
                raw, self.journal_inode = self._file('journal.json')
                self.record = json.loads(raw, object_pairs_hook=unique_object)
                validate_record(self.record)
            else:
                self.record = copy.deepcopy(record)
                self.save()
            return self
        except Exception:
            self.close()
            raise RuntimeError('Restore ownership journal unavailable; inspect without replay') from None

    def _owned(self):
        require(self.fd is not None and self.parent_fd is not None and self.lock_inode is not None)
        parent = self.directory.parent.lstat()
        require((parent.st_dev, parent.st_ino) == self.parent_inode and
                stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
                stat.S_IMODE(parent.st_mode) == 0o700)
        current = self.directory.lstat()
        require((current.st_dev, current.st_ino) == self.directory_inode and
                stat.S_ISDIR(current.st_mode) and current.st_uid == os.getuid() and
                stat.S_IMODE(current.st_mode) == 0o700)
        value, inode = self._file('active.lock')
        require(inode == self.lock_inode and value == self.lock_value)
        if self.journal_inode is not None:
            _, inode = self._file('journal.json')
            require(inode == self.journal_inode)
        else:
            try:
                os.stat('journal.json', dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                require(False)

    def save(self):
        self._owned()
        self.record['updated_at_utc'] = now()
        validate_record(self.record)
        data = (json.dumps(self.record, indent=2) + '\n').encode('utf-8')
        require(len(data) <= 1024 * 1024)
        temp = 'journal-' + uuid.uuid4().hex + '.next'
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(fd)
                info = os.fstat(fd)
                new_inode = (info.st_dev, info.st_ino)
        finally:
            os.close(fd)
        # Recheck the owned lock/directory/journal before replacing the last record.
        self._owned()
        os.replace(temp, 'journal.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)
        _, inode = self._file('journal.json')
        require(inode == new_inode)
        self.journal_inode = inode

    def perform(self, action, mutate, validate, delete_identity=None):
        """Caller supplies live guard/source/spec validation; this is not an executor."""
        require(action in ACTIONS and callable(mutate) and callable(validate))
        operations = self.record['operations']
        require(action not in operations)
        kind, namespace = ACTIONS[action]
        intent = {'state': 'pending', 'kind': kind, 'name': self.record['target_name'],
                  'namespace': namespace, 'started_at_utc': now()}
        if action == 'holder_delete':
            created = operations.get('holder_create', {})
            require(created.get('state') == 'confirmed' and isinstance(created.get('identity'), dict))
            current = identity({'metadata': delete_identity})
            require(current == delete_identity and all(
                current[k] == created['identity'][k] for k in ('name', 'namespace', 'uid')))
            intent['preconditions'] = current
        else:
            require(delete_identity is None)
        operations[action] = intent
        self.save()  # Both file and directory fsync precede the API mutation.
        try:
            result = mutate(copy.deepcopy(intent))
            validate(result)  # Full live/spec fence belongs to the caller.
            if action != 'holder_delete':
                require(isinstance(result, dict) and result.get('kind') == kind)
                owned = identity(result)
                require(owned['name'] == intent['name'] and owned['namespace'] == namespace and
                        result['metadata'].get('labels', {}).get('bortus-restore') == self.record['run_id'])
                intent['identity'] = owned
            intent['state'] = 'confirmed'
            intent['finished_at_utc'] = now()
            self.save()
        except Exception:
            intent.pop('identity', None)
            intent['state'] = 'uncertain'
            try:
                self.save()
            except Exception:
                pass  # Durable prior pending state also forbids replay.
            raise RuntimeError('Restore mutation outcome unresolved; inspect without replay') from None
        return copy.deepcopy(intent)

    def close(self):
        if self.fd is not None:
            try:
                if self.lock_inode is not None:
                    value, inode = self._file('active.lock')
                    if inode == self.lock_inode and value == self.lock_value:
                        os.unlink('active.lock', dir_fd=self.fd)
                        os.fsync(self.fd)
            except (OSError, RuntimeError):
                pass  # Preserve any foreign/replaced lock for inspection.
            finally:
                os.close(self.fd)
                self.fd = None
                self.lock_inode = None
        if self.parent_fd is not None:
            os.close(self.parent_fd)
            self.parent_fd = None
