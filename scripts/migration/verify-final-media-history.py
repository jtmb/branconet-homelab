#!/usr/bin/env python3
"""Read-only original cold Seerr history delta, authenticated archive entirely in RAM."""
import collections
import hashlib
import io
import json
from pathlib import Path
import shlex
import sqlite3
import struct
import subprocess
import tarfile

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'platform-upstream-review-20261027/final-media-state-20261028'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519', '-p2002', 'james@192.168.0.4']

def remote(args, body=None):
    p = subprocess.run(SSH + [shlex.join(args)], input=body, capture_output=True, timeout=90)
    assert p.returncode == 0, 'remote_read_failed'
    assert len(p.stdout) < 8 * 1024**2, 'response_limit'
    return p.stdout

def overlay(db, wal):
    """Validate SQLite WAL checksum chain and apply only the last committed prefix."""
    assert db[:16] == b'SQLite format 3\x00'
    assert len(wal) >= 32
    magic, version, size, seq, salt1, salt2, c1, c2 = struct.unpack('>8I', wal[:32])
    assert magic in (0x377f0682, 0x377f0683) and version == 3007000
    assert size in [1 << n for n in range(9, 17)]
    dbsize = struct.unpack('>H', db[16:18])[0]
    assert size == (65536 if dbsize == 1 else dbsize)
    endian = '<' if magic == 0x377f0682 else '>'
    def checksum(data, s=(0, 0)):
        assert len(data) % 8 == 0
        a, b = s
        for x, y in struct.iter_unpack(endian + 'II', data):
            a = (a + x + b) & 0xffffffff
            b = (b + y + a) & 0xffffffff
        return a, b
    assert checksum(wal[:24]) == (c1, c2), 'wal_header_checksum'
    assert (len(wal) - 32) % (size + 24) == 0
    frames = []
    committed = None
    checks = (c1, c2)
    for offset in range(32, len(wal), size + 24):
        head = wal[offset:offset + 24]
        page, count, s1, s2, x, y = struct.unpack('>6I', head)
        # SQLite reset leaves old checkpointed frames after the active prefix.
        # https://www.sqlite.org/fileformat2.html#wal_reset
        if (s1, s2) != (salt1, salt2):
            break
        assert page > 0, 'wal_frame_identity'
        data = wal[offset + 24:offset + 24 + size]
        checks = checksum(data, checksum(head[:8], checks))
        assert checks == (x, y), 'wal_frame_checksum'
        frames.append((page, data))
        if count:
            assert count * size <= 128 * 1024**2
            committed = (len(frames), count)
    assert committed is not None, 'wal_commit_missing'
    n, count = committed
    merged = bytearray(db[:count * size])
    merged.extend(bytes(max(0, count * size - len(merged))))
    for page, data in frames[:n]:
        if page <= count:
            merged[(page - 1)*size:page*size] = data
    # In-memory deserialize has no WAL sidecar: materialized committed pages use
    # rollback journal format flags. Source bytes/archive are never changed.
    merged[18:20] = b'\x01\x01'
    return bytes(merged), {'validatedFrames': len(frames), 'committedFrames': n, 'databasePages': count, 'pageSize': size, 'staleSaltTailFrames': (len(wal)-32)//(size+24)-len(frames)}

def main():
    archive = ROOT / 'upstream-seerr-20261025/cold/seerr-cold-5899f5a32cd94dcea29b12790de0577a/seerr-complete-config.tar.age'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'b70eb9a319fda964a445fb4e8d11a9b38abacf7fd8e46a0ca28f95310e19cdce'
    p = subprocess.run(['/home/brajam/.local/share/branconet-migration/bin/age', '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(archive)], capture_output=True, timeout=90)
    assert p.returncode == 0 and len(p.stdout) <= 128 * 1024**2, 'authenticated_archive'
    with tarfile.open(fileobj=io.BytesIO(p.stdout), mode='r:') as t:
        files = {m.name: t.extractfile(m).read() for m in t if m.name in ['data-0/db/db.sqlite3', 'data-0/db/db.sqlite3-wal'] and m.isfile()}
    db, evidence = overlay(files['data-0/db/db.sqlite3'], files['data-0/db/db.sqlite3-wal'])
    c = sqlite3.connect(':memory:')
    c.deserialize(db)
    c.execute('PRAGMA query_only=ON')
    assert c.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    columns = {'media_request': ['id','status','updatedAt'], 'media': ['id','status','updatedAt','lastSeasonChange','mediaAddedAt','ratingKey'], 'season': ['id','status','updatedAt']}
    old = {name: c.execute('SELECT ' + ','.join(cols) + ' FROM ' + name + ' ORDER BY id').fetchall() for name, cols in columns.items()}
    c.close()
    identity = json.loads((OUT / 'seerr-current.json').read_bytes())['identity']
    def fence():
        v=json.loads(remote(['kubectl','-n','plex','get','pod',identity['pod'],'-o','json']))
        assert v['metadata']['uid']==identity['podUID'] and not v['metadata'].get('deletionTimestamp')
        assert v['spec']['containers'][0]['image']==identity['image']
        return v['metadata']['uid'], v['status']['containerStatuses'][0]['restartCount']
    before=fence()
    js="""const fs=require('fs'),sqlite=require('/app/node_modules/sqlite3');const columns=JSON.parse(fs.readFileSync(0));let db=new sqlite.Database('/app/config/db/db.sqlite3',sqlite.OPEN_READONLY);const all=s=>new Promise((r,j)=>db.all(s,(e,v)=>e?j(e):r(v)));(async()=>{await all('PRAGMA query_only=ON');await all('BEGIN');let out={};for(const [t,c] of Object.entries(columns)){if(!['media_request','media','season'].includes(t)||c.some(v=>!/^\\w+$/.test(v)))throw Error('schema');out[t]=(await all('SELECT '+c.join(',')+' FROM '+t+' ORDER BY id')).map(r=>c.map(k=>r[k]));}await all('ROLLBACK');db.close();process.stdout.write(JSON.stringify(out));})().catch(()=>{process.exitCode=1;db.close();});"""
    current=json.loads(remote(['kubectl','-n','plex','exec','-i',identity['pod'],'-c','overseerr','--','node','-e',js],json.dumps(columns).encode()))
    assert before==fence()
    result={'archiveSHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'wal':evidence,'quickCheck':'ok','identity':identity,'tables':{},'exactOriginalComparisonPassed':False,'interpretation':'Native lifecycle provenance remains a separate review gate; no changed fields excluded from literal comparison.'}
    for name, cols in columns.items():
        prior=old[name]; now=current[name]
        assert [r[0] for r in prior]==[r[0] for r in now]
        deltas=[{'id':a[0],'changes':{col:{'old':a[i],'new':b[i]} for i,col in enumerate(cols) if a[i]!=b[i]}} for a,b in zip(prior,now) if list(a)!=b]
        result['tables'][name]={'count':len(now),'idsPreserved':True,'oldStatuses':dict(collections.Counter(str(r[1]) for r in prior)),'newStatuses':dict(collections.Counter(str(r[1]) for r in now)),'changedRows':len(deltas),'deltas':deltas}
    result['sourceSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    target=OUT/'seerr-history-deltas.json'
    with target.open('x') as f:json.dump(result,f,indent=2)
    target.chmod(0o600)
    print(json.dumps({name:{k:v for k,v in data.items() if k!='deltas'} for name,data in result['tables'].items()}))

if __name__=='__main__':main()
