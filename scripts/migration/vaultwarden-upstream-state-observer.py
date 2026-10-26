#!/usr/bin/env python3
"""Same-release complete typed Vaultwarden SQL and file preservation observer."""
import base64,hashlib,hmac,json,os,sqlite3,stat,time
from pathlib import Path
MAX_SQLITE=128*1024**2
MAX_VALUE=1024**2
MAX_ENCODED=32*1024**2
MAX_ROWS=250000
DATABASE_FILES={'db.sqlite3','db.sqlite3-wal','db.sqlite3-shm'}


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


def fingerprint(path,key,domain,selected=None,live=False):
    path=Path(path);check(path.is_file() and not path.is_symlink() and path.stat().st_size<=MAX_SQLITE)
    deadline=time.monotonic()+90;source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5,isolation_level=None);memory=None
    try:
        source.execute('PRAGMA query_only=ON');source.execute('PRAGMA busy_timeout=5000');source.execute('PRAGMA temp_store=MEMORY');source.execute('BEGIN')
        pages=source.execute('PRAGMA page_count').fetchone()[0];page_size=source.execute('PRAGMA page_size').fetchone()[0];check(pages*page_size<=MAX_SQLITE)
        connection=source
        if live:
            memory=sqlite3.connect(':memory:',isolation_level=None)
            def progress(status,remaining,total):check(time.monotonic()<deadline and total*page_size<=MAX_SQLITE)
            source.backup(memory,pages=64,progress=progress,sleep=0.05);source.rollback();source.close();source=None;connection=memory;connection.execute('PRAGMA temp_store=MEMORY')
        connection.set_progress_handler(lambda:int(time.monotonic()>=deadline),10000)
        check(connection.execute('PRAGMA quick_check').fetchall()==[('ok',)])
        check(connection.execute('PRAGMA foreign_key_check').fetchone()is None)
        schema=connection.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        names=[r[1]for r in schema if r[0]=='table'];check(0<len(names)<=256 and {'users','ciphers','devices','archives','__diesel_schema_migrations'}<=set(names))
        tables={};total_rows=encoded=0
        for name in names:
            info=[list(r)for r in connection.execute('PRAGMA table_xinfo('+quoted(name)+')')];columns=[r[1]for r in info];check(0<len(columns)<=256 and len(set(columns))==len(columns))
            hashes=[];column_hashes={c:hmac.new(key,compact(['same-release-column',domain,name,c]),hashlib.sha256)for c in columns}
            for row in connection.execute('SELECT * FROM '+quoted(name)):
                check(len(row)==len(columns));values=[cell(v)for v in row];body=compact(values);encoded+=len(body);total_rows+=1;check(encoded<=MAX_ENCODED and total_rows<=MAX_ROWS and time.monotonic()<deadline)
                hashes.append(mac(key,domain,['same-release-row',name,values]))
                # Explicit SQL ordering below is not needed for the sorted full
                # row multiset; per-column multisets preserve duplicates too.
            for c in columns:
                values=sorted(mac(key,domain,['same-release-cell',name,c,cell(r[0])])for r in connection.execute('SELECT '+quoted(c)+' FROM '+quoted(name)))
                column_hashes[c]=mac(key,domain,['same-release-column',name,c,values])
            tables[name]={'columns':columns,'table_info':info,'count':len(hashes),'all_rows_hmac':mac(key,domain,['same-release-table',name,sorted(hashes)]),'per_column_hmac':column_hashes}
        versions=[r[0]for r in connection.execute('SELECT version FROM __diesel_schema_migrations ORDER BY version')]
        result={'quick_check':'ok','foreign_keys_ok':True,'schema_hmac':mac(key,domain,['same-release-schema',schema]),'tables':tables,'migration_versions':versions,'key_binding':mac(key,domain,'same-release-key-binding'),'same_release_schema_and_all_cells':True}
        if selected is not None:check(result==selected)
        return result
    finally:
        if source is not None:source.close()
        if memory is not None:memory.close()


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
