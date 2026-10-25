#!/usr/bin/env python3
"""Compare cold Plex library-section rows in memory; never export private values."""
import argparse
import datetime
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
IMAGE = 'docker.io/library/plex-security-20261023@sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397'
DATABASE = 'data-0/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db'


def need(value, reason):
    if not value:
        raise ValueError(reason)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--receipt-sha256', required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    need(BASE in a.receipt.parents and a.receipt.resolve() == a.receipt and
         hashlib.sha256(a.receipt.read_bytes()).hexdigest() == a.receipt_sha256, 'original_cold_receipt')
    r = json.loads(a.receipt.read_bytes())
    need(r['application'] == 'plex' and r['status'] == 'completed' and r['cold_archive_verified']
         and r['temporary_pod_deleted'], 'completed_authenticated_cold_archive')
    archive = Path(r['archive_path']); need(archive.parent == a.receipt.parent and not archive.stat().st_mode & 0o077, 'private_archive')
    age = BASE / 'bin/age'
    need(hashlib.sha256(age.read_bytes()).hexdigest() == 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c', 'pinned_age')
    digest = hashlib.sha256()
    with archive.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''): digest.update(b)
    need(digest.hexdigest() == r['archive_sha256'], 'cold_archive_sha256')
    child = subprocess.Popen([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(archive)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    manifest = None; seen = set(); total = 0; database = None
    try:
        with tarfile.open(fileobj=child.stdout, mode='r|') as bundle:
            for m in bundle:
                name = m.name.rstrip('/'); need(name not in seen and len(seen) <= 131072, 'bounded_unique_members'); seen.add(name)
                if name == 'manifest.json':
                    need(len(seen) == 1 and m.isfile() and m.size <= 64*1024**2, 'first_manifest')
                    manifest = json.load(bundle.extractfile(m)); continue
                need(manifest is not None and name in manifest['entries'], 'complete_manifest_member')
                row = manifest['entries'][name]
                need((m.uid, m.gid, m.mode) == (row['uid'], row['gid'], row['mode']), 'member_metadata')
                if row['kind'] == 'directory': need(m.isdir(), 'directory'); continue
                if row['kind'] == 'symlink': need(m.issym() and m.linkname == row['link'], 'symlink'); continue
                need(m.isfile() and m.size == row['bytes'], 'file_length')
                selected = name == DATABASE
                if selected: need(m.size <= 512*1024**2, 'bounded_in_memory_database')
                h = hashlib.sha256(); chunks = []
                stream = bundle.extractfile(m)
                for b in iter(lambda: stream.read(1024**2), b''):
                    total += len(b); need(total <= 16*1024**3, 'complete_archive_data_bound'); h.update(b)
                    if selected: chunks.append(b)
                need(h.hexdigest() == row['sha256'], 'every_complete_file_hash')
                if selected: database = b''.join(chunks)
        for b in iter(lambda: child.stdout.read(65536), b''): need(not any(b), 'archive_padding')
        need(child.wait(timeout=30) == 0 and seen == {'manifest.json'} | set(manifest['entries'])
             and total == manifest['total_file_bytes'] and database is not None, 'whole_archive_authentication')
    finally:
        if child.poll() is None: child.kill(); child.wait(timeout=10)
    spec = importlib.util.spec_from_file_location('plex_qualifier', Path(__file__).with_name('qualify-plex.py'))
    q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
    # sqlite3_deserialize cannot use a WAL-mode header. Only the private RAM copy
    # changes its two format bytes, after proving the cold archive has no WAL
    # frames or journal to recover. Never touch the archive or live database.
    # https://www.sqlite.org/c3ref/deserialize.html
    for suffix in ['-wal', '-journal']:
        entry = manifest['entries'].get(DATABASE + suffix)
        need(entry is None or entry['kind'] == 'file' and entry['bytes'] == 0, 'no_cold_wal_or_journal_frames')
    need(database[:16] == b'SQLite format 3\x00' and database[18:20] in [b'\x01\x01', b'\x02\x02'], 'sqlite_format')
    database = database[:18] + b'\x01\x01' + database[20:]
    connection = sqlite3.connect(':memory:'); connection.deserialize(database); connection.execute('PRAGMA query_only=ON')
    columns = [x[1] for x in connection.execute('PRAGMA table_info(library_sections)')]
    original = [dict(zip(columns, x)) for x in connection.execute('SELECT * FROM library_sections ORDER BY id')]
    connection.close(); del database
    writer = q.fence(IMAGE)
    live = json.loads(q.call(['kubectl', '-n', 'plex', 'exec', writer['pod'], '--',
                '/usr/lib/plexmediaserver/Plex SQLite', '-readonly', '-json',
                q.CONFIG + '/Plug-in Support/Databases/com.plexapp.plugins.library.db',
                'SELECT * FROM library_sections ORDER BY id;']))
    need(len(original) == len(live) and [x['id'] for x in original] == [x['id'] for x in live]
         and all(set(x) == set(columns) for x in live), 'all_original_rows_columns_and_ids')
    differences = {str(x['id']): [k for k in columns if x[k] != y[k]] for x,y in zip(original,live)}
    differences = {k:v for k,v in differences.items() if v}
    key = (a.output_dir / 'observation.key').read_bytes(); need(len(key) == 32, 'existing_private_observation_key')
    def seal(value): return hmac.new(key,json.dumps(value,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
    report = {'observedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'wholeColdArchiveAuthenticated': True,
              'originalColdReceiptSHA256': a.receipt_sha256, 'rows': len(original), 'columns': columns,
              'changedColumnsByRow': differences, 'coldColumnsHMAC': {k:seal([x[k] for x in original]) for k in columns},
              'liveColumnsHMAC': {k:seal([x[k] for x in live]) for k in columns},
              'privateValuesExported': False, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    need(q.fence(IMAGE) == writer, 'stable_original_writer')
    out = a.output_dir / ('plex-library-bookkeeping-' + uuid.uuid4().hex + '.json')
    with out.open('x') as f: json.dump(report,f,indent=2,sort_keys=True)
    out.chmod(0o600)
    print(json.dumps({'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(), 'changedColumnsByRow':differences}))


if __name__ == '__main__':
    main()
