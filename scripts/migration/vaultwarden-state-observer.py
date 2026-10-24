#!/usr/bin/env python3
"""Bounded read-only Vaultwarden SQL/file fingerprints; no application imports."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

MAX_SQLITE = 128 * 1024 ** 2
MAX_VALUE = 1024 ** 2
MAX_ENCODED = 32 * 1024 ** 2
MAX_ROWS = 250000
NEW_VERSIONS = {'20260309005927', '20260425120000', '20260505120000', '20260902120000'}
# Diesel splits the upstream 2024-03-13_170000_sso_userscascade directory at
# its first underscore, so its retained version is the opaque ID 20240313.
LEGACY_VERSIONS = {'20240313'}
NEW_COLUMNS = {'sso_auth': ['binding_hash', 'code_response_error'], 'users': ['key_id']}
DATABASE_FILES = {'db.sqlite3', 'db.sqlite3-wal', 'db.sqlite3-shm'}


def check(ok):
    if not ok:
        raise ValueError('vaultwarden_state_refused')


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def mac(key, domain, value):
    return hmac.new(key, compact(['vaultwarden-state-v1', domain, value]), hashlib.sha256).hexdigest()


def quoted(value):
    return '"' + value.replace('"', '""') + '"'


def cell(value):
    if value is None:
        return ['null']
    if isinstance(value, int):
        return ['int', str(value)]
    if isinstance(value, float):
        return ['float', value.hex()]
    if isinstance(value, str):
        check(len(value.encode()) <= MAX_VALUE)
        return ['text', value]
    if isinstance(value, bytes):
        check(len(value) <= MAX_VALUE)
        return ['blob', base64.b64encode(value).decode()]
    raise ValueError('vaultwarden_value_type')


def fingerprint(path, key, domain, selected=None, live=False):
    deadline = time.monotonic() + 90
    source = sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True, timeout=5, isolation_level=None)
    memory = None
    try:
        source.execute('PRAGMA query_only=ON')
        source.execute('PRAGMA busy_timeout=5000')
        source.execute('PRAGMA temp_store=MEMORY')
        source.execute('BEGIN')
        source.execute('SELECT count(*) FROM sqlite_master').fetchone()
        page_size = source.execute('PRAGMA page_size').fetchone()[0]
        pages = source.execute('PRAGMA page_count').fetchone()[0]
        check(page_size * pages <= MAX_SQLITE)
        connection = source
        if live:
            memory = sqlite3.connect(':memory:', isolation_level=None)
            def progress(status, remaining, total):
                check(time.monotonic() < deadline and total * page_size <= MAX_SQLITE)
            source.backup(memory, pages=64, progress=progress, sleep=0.05)
            source.rollback()
            source.close()
            source = None
            connection = memory
            connection.execute('PRAGMA query_only=ON')
            connection.execute('PRAGMA temp_store=MEMORY')
            connection.execute('BEGIN')
        connection.set_progress_handler(lambda: 1 if time.monotonic() >= deadline else 0, 10000)
        check(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
        names = sorted(r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
        check(0 < len(names) <= 256 and {'users', 'sso_auth', '__diesel_schema_migrations'} <= set(names))
        if selected is None:
            check('archives' not in names)
        else:
            check(set(names) == set(selected['tables']) | {'archives'})
            info = connection.execute('PRAGMA table_info(archives)').fetchall()
            check(info == [(0, 'user_uuid', 'CHAR(36)', 1, None, 1),
                           (1, 'cipher_uuid', 'CHAR(36)', 1, None, 2),
                           (2, 'archived_at', 'DATETIME', 1, 'CURRENT_TIMESTAMP', 0)])
            check(connection.execute('SELECT count(*) FROM archives').fetchone()[0] == 0)
            links = connection.execute('PRAGMA foreign_key_list(archives)').fetchall()
            check({(v[2], v[3], v[4], v[5], v[6]) for v in links} ==
                  {('users', 'user_uuid', 'uuid', 'NO ACTION', 'CASCADE'),
                   ('ciphers', 'cipher_uuid', 'uuid', 'NO ACTION', 'CASCADE')})
            names.remove('archives')
        tables = {}
        encoded = total_rows = 0
        versions = [r[0] for r in connection.execute('SELECT version FROM __diesel_schema_migrations ORDER BY version')]
        check(all(isinstance(v, str) and v.isdecimal()
                  and (len(v) == 14 or v in LEGACY_VERSIONS) for v in versions))
        if selected is None:
            check(not set(versions) & NEW_VERSIONS)
        else:
            check(set(versions) == set(selected['migration_versions']) | NEW_VERSIONS
                  and len(versions) == len(selected['migration_versions']) + 4)
        for name in names:
            check(time.monotonic() < deadline)
            info = [list(r) for r in connection.execute('PRAGMA table_xinfo(' + quoted(name) + ')')]
            all_columns = [r[1] for r in info]
            check(0 < len(info) <= 256 and len(set(all_columns)) == len(all_columns))
            if selected is None:
                columns = all_columns
                original_info = info
                if name in NEW_COLUMNS:
                    check(not set(all_columns) & set(NEW_COLUMNS[name]))
            else:
                original = selected['tables'][name]
                columns = original['columns']
                original_info = original['table_info']
                additions = NEW_COLUMNS.get(name, [])
                check(all_columns == columns + additions and info[:len(columns)] == original_info)
                check(info[len(columns):] == [[len(columns) + i, col, 'TEXT', 0, None, 0, 0]
                                             for i, col in enumerate(additions)])
                for col in additions:
                    check(connection.execute('SELECT count(*) FROM ' + quoted(name) + ' WHERE ' + quoted(col) + ' IS NOT NULL').fetchone()[0] == 0)
            where, params = '', []
            if selected is not None and name == '__diesel_schema_migrations':
                where = ' WHERE version NOT IN (?,?,?,?)'
                params = sorted(NEW_VERSIONS)
            sql = 'SELECT ' + ','.join(quoted(c) for c in columns) + ' FROM ' + quoted(name) + where
            sql += ' ORDER BY ' + ','.join(quoted(c) for c in columns)
            rows = connection.execute(sql, params)
            aggregate = hmac.new(key, compact(['table', domain, name, columns]), hashlib.sha256)
            per_column = {c: hmac.new(key, compact(['column', domain, name, c]), hashlib.sha256) for c in columns}
            count = 0
            for row in rows:
                values = [cell(v) for v in row]
                raw = compact(values)
                encoded += len(raw)
                count += 1
                total_rows += 1
                check(encoded <= MAX_ENCODED and total_rows <= MAX_ROWS and time.monotonic() < deadline)
                aggregate.update(len(raw).to_bytes(8, 'big') + raw)
                for column, value in zip(columns, values):
                    raw_cell = compact(value)
                    per_column[column].update(len(raw_cell).to_bytes(8, 'big') + raw_cell)
            tables[name] = {'columns': columns, 'table_info': original_info, 'count': count,
                            'all_rows_hmac': aggregate.hexdigest(),
                            'per_column_hmac': {c: h.hexdigest() for c, h in per_column.items()}}
        return {'quick_check': 'ok', 'tables': tables,
                'migration_versions': selected['migration_versions'] if selected is not None else versions,
                'key_binding': mac(key, domain, 'key-binding'), 'sqlite_version': sqlite3.sqlite_version,
                'snapshot_page_count': pages, 'live_backup_to_memory': live,
                'four_exact_additive_migrations': selected is not None}
    finally:
        if source is not None:
            source.close()
        if memory is not None:
            memory.close()


def files_from_manifest(manifest, key, domain):
    check(manifest['schema_version'] == 1 and not manifest['excluded_new_paths'])
    entries = {}
    count = size = 0
    for name, row in manifest['entries'].items():
        check(name == 'data-0' or name.startswith('data-0/'))
        relative = name.removeprefix('data-0').lstrip('/')
        if relative in DATABASE_FILES:
            check(row['kind'] == 'file')
            continue
        fields = ['kind', 'mode', 'uid', 'gid']
        if row['kind'] == 'file':
            fields += ['bytes', 'sha256']
            count += 1
            size += row['bytes']
        elif row['kind'] == 'symlink':
            fields += ['link']
        else:
            check(row['kind'] == 'directory')
        entries[mac(key, domain, ['path', relative])] = mac(key, domain, ['entry', relative, {k: row[k] for k in fields}])
    return {'entries_hmac': entries, 'non_database_file_count': count, 'non_database_file_bytes': size}


def live_files(root, key, domain):
    """Hash the complete non-DB tree without emitting paths or following links."""
    root = Path(root)
    check(root.resolve() == root and root.is_dir())
    device = root.stat().st_dev
    pending = [('data-0', root)]
    entries = {}
    total = 0
    deadline = time.monotonic() + 120
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    while pending:
        check(time.monotonic() < deadline and len(entries) <= 4096)
        name, path = pending.pop()
        info = path.lstat()
        check(info.st_dev == device)
        relative = name.removeprefix('data-0').lstrip('/')
        if relative in DATABASE_FILES:
            check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
            continue
        row = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
        if stat.S_ISDIR(info.st_mode):
            row['kind'] = 'directory'
            pending += [(name + '/' + p.name, p) for p in sorted(path.iterdir())]
        elif stat.S_ISLNK(info.st_mode):
            row.update(kind='symlink', link=os.readlink(path))
        else:
            check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
            total += info.st_size
            check(total <= 4 * 1024 ** 3)
            digest = hashlib.sha256()
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                check(identity(os.fstat(stream.fileno())) == identity(info))
                for block in iter(lambda: stream.read(1024 ** 2), b''):
                    check(time.monotonic() < deadline)
                    digest.update(block)
                check(identity(os.fstat(stream.fileno())) == identity(path.lstat()) == identity(info))
            row.update(kind='file', bytes=info.st_size, sha256=digest.hexdigest())
        entries[name] = row
    check(len(entries) <= 4096)
    return files_from_manifest({'schema_version': 1, 'entries': entries, 'excluded_new_paths': []}, key, domain)
