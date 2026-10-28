#!/usr/bin/env python3
"""Run the exact vendor migration on a copy; report every table/field difference."""
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-mealie-20261026'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def database(path, key):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert db.execute('PRAGMA foreign_key_check').fetchone() is None
        tables = {}
        for name, sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [x[1] for x in db.execute('PRAGMA table_xinfo(' + quoted + ')')]
            rows = db.execute('SELECT *FROM ' + quoted).fetchall()
            assert len(rows) <= 1000000
            def cell(value):
                if isinstance(value, bytes):
                    return ['bytes', value.hex()]
                return [type(value).__name__, value]
            fields = {column: sorted(hmac.new(key, canonical(cell(r[i])), hashlib.sha256).hexdigest() for r in rows)
                      for i, column in enumerate(columns)}
            row_hmacs = sorted(hmac.new(key, canonical([cell(v) for v in row]), hashlib.sha256).hexdigest() for row in rows)
            tables[name] = {'rows': len(rows), 'columns': columns, 'fields': fields,
                            'rowHMACs': row_hmacs, 'schema': sql}
        return tables
    finally:
        db.close()


def main():
    retry = sys.argv[1:] == ['--apply', '--retry-empty-mountpoint']
    assert (retry or sys.argv[1:] == ['--apply']) and os.getuid() == 1000
    cg = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    suffix = 'migrate-r2' if retry else 'migrate'
    assert cg.endswith('/branconet-mealie-copy-' + suffix + '-20261026.service')
    group = Path('/sys/fs/cgroup') / cg.lstrip('/')
    assert (group / 'memory.max').read_text().strip() == str(1024**3)
    assert (group / 'memory.swap.max').read_text().strip() == '0'
    assert not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK)
    os.umask(0o077)
    prepared = json.loads((OUT / 'prepare.json').read_text())
    snapshot = json.loads((OUT / 'db-copy/source.json').read_text())
    assert prepared['passed'] and snapshot['passed'] and not snapshot['productionChanged']
    source = OUT / 'vendor-rootfs/opt/mealie/lib/python3.14/site-packages/mealie/db/init_db.py'
    assert sha(source) == prepared['installedMigrationSourceSHA256']
    key = (OUT / 'db-copy/observation.key').read_bytes()
    assert len(key) == 32
    original = OUT / 'db-copy/sqlite-original.db'
    before_hash = sha(original)
    before = database(original, key)
    data = OUT / 'migration-data'
    assert data.is_dir() and data.resolve() == data
    copy = OUT / 'db-copy/sqlite-migration.db'
    target = data / 'mealie.db'
    if retry:
        previous = json.loads((OUT / 'migration.json').read_text())
        assert previous['vendorMigrationExit'] == 1 and previous['originalCopyUnchanged'] and not previous['productionChanged']
        assert (OUT / 'migration.stderr').read_text() == "bwrap: Can't mkdir /app/data: Read-only file system\n"
        assert not copy.exists() and set(data.iterdir()) == {target}
        mountpoint = OUT / 'vendor-rootfs/app/data'
        assert not mountpoint.exists() and mountpoint.parent.resolve() == mountpoint.parent
        mountpoint.mkdir(mode=0o755)
    else:
        assert not list(data.iterdir())
        assert copy.is_file() and copy.resolve() == copy and not copy.is_symlink()
        assert copy.stat().st_uid == 1000 and copy.stat().st_dev == data.stat().st_dev
        os.rename(copy, target)
    assert database(target, key) == before
    cmd = ['/usr/bin/bwrap', '--unshare-all', '--new-session', '--die-with-parent', '--cap-drop', 'ALL',
           '--ro-bind', str(OUT / 'vendor-rootfs'), '/', '--proc', '/proc', '--dev', '/dev',
           '--bind', str(data), '/app/data', '--bind', str(OUT / 'migration-tmp'), '/tmp', '--chdir', '/app',
           '--clearenv', '--setenv', 'PATH', '/opt/mealie/bin:/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
           '--setenv', 'TMPDIR', '/tmp', '--setenv', 'TEMP', '/tmp', '--setenv', 'TMP', '/tmp',
           '--setenv', 'PRODUCTION', 'true', '--setenv', 'TESTING', 'false', '--setenv', 'DATA_DIR', '/app/data',
           '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', '--', '/opt/mealie/bin/python', '-I', '-B', '-c',
           'from mealie.db.init_db import main; main()']
    prefix = 'migration-r2' if retry else 'migration'
    with (OUT / (prefix + '.stdout')).open('xb') as stdout, (OUT / (prefix + '.stderr')).open('xb') as stderr:
        run = subprocess.run(cmd, stdout=stdout, stderr=stderr, timeout=180)
    report = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'vendorMigrationExit': run.returncode, 'networkDisabled': True,
              'productionChanged': False, 'migrationAcceptance': False, 'sourceSHA256': sha(Path(__file__)),
              'originalCopyUnchanged': sha(original) == before_hash, 'image': prepared['image']}
    assert report['originalCopyUnchanged']
    if run.returncode == 0:
        after = database(target, key)
        rows = []
        for name in sorted(before.keys() | after.keys()):
            a, b = before.get(name), after.get(name)
            row = {'table': name, 'beforeRows': a['rows'] if a else None, 'afterRows': b['rows'] if b else None}
            if a and b:
                row.update(addedColumns=sorted(set(b['columns']) - set(a['columns'])),
                           removedColumns=sorted(set(a['columns']) - set(b['columns'])),
                           changedCommonFields=sorted(k for k in a['fields'].keys() & b['fields'].keys()
                                                      if a['fields'][k] != b['fields'][k]),
                           exactRowsAndSchemaEqual=a == b)
            rows.append(row)
        report.update(beforeTableCount=len(before), afterTableCount=len(after), differences=rows,
                      criticalCounts={name: {'before': before[name]['rows'], 'after': after.get(name, {}).get('rows')}
                                      for name in ['users', 'groups', 'recipes']},
                      copiedDatabaseIntegrityAndForeignKeys=True)
        with (OUT / ('copy-state-private-r2.json' if retry else 'copy-state-private.json')).open('x') as stream:
            json.dump({'before': before, 'after': after}, stream)
    with (OUT / (prefix + '.json')).open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != 'differences'}))
    return int(run.returncode != 0)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'failureCategory': type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
