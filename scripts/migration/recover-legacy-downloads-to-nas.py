"""Copy two legacy media files to their intended NAS paths; never delete sources.

Windows operator uses the existing WSL SSH identity and authenticated NAS share.
All control/evidence stays in the existing task root; no local media staging.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
NAS = Path(r'\\TRUENAS\plex_smb_share\downloads')
SIZES = {3447044670, 2192493059}
FLOOR = 15 * 1024**3
PREFIX = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec',
          '/usr/sbin/runuser', '-u', 'brajam', '--', '/usr/bin/ssh', '-o', 'BatchMode=yes',
          '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10', '-o',
          'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', '-i',
          '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, category):
    if not ok:
        raise ValueError(category)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def remote(body):
    return PREFIX + [shlex.join(['python3', '-B', '-c', body])]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', required=True, type=Path)
    p.add_argument('--run-id', required=True)
    args = p.parse_args()
    need(os.name == 'nt' and uuid.UUID(args.run_id).hex == args.run_id, 'fixed_windows_operator')
    need(args.inventory.resolve().is_relative_to((F / 'node-cleanup-20261027').resolve()), 'owned_inventory')
    need(F.is_dir() and NAS.is_dir(), 'existing_destinations')
    need(shutil.disk_usage('C:\\').free >= FLOOR and shutil.disk_usage(F).free >= FLOOR + 128 * 1024**2, 'controller_free_space')
    need(shutil.disk_usage(NAS).free >= FLOOR + sum(SIZES), 'nas_free_space')
    os.environ.update(TEMP=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'))
    original = json.loads(args.inventory.read_text())['nodes']['192.168.0.4']['files']
    selected = [x for x in original if x['size'] in SIZES]
    need(len(selected) == 2 and {x['size'] for x in selected} == SIZES, 'exact_two_legacy_media_sizes')
    need(all(Path(x['relative']).name == x['relative'] and x['relative'].endswith('.mkv') and not x['symlink'] for x in selected), 'basename_media_allowlist')
    run = F / 'node-cleanup-20261027' / ('legacy-media-recovery-' + args.run_id)
    run.mkdir(mode=0o700)
    children = []
    events = run / 'events.jsonl'
    def event(name, **fields):
        with events.open('a', encoding='utf8') as out:
            out.write(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'event': name, **fields}) + '\n')
            out.flush()
            os.fsync(out.fileno())
    ownership = {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F), 'run': str(run),
                 'physicalVolume': 'F-backed ext4 3c792469-ea0e-4a2c-98e8-1185b141607b',
                 'generatedPaths': [str(events), str(run / 'receipt.json'), str(run / 'ownership.json')], 'nasRuntimeDestination': str(NAS),
                 'protectedSources': '/mnt/plex_smb_share/downloads; original files and .metube state',
                 'sourceDeleted': False, 'localMediaStaging': False}
    (run / 'ownership.json').write_text(json.dumps(ownership, indent=2) + '\n')
    result = dict(ownership, status='started', files=[])
    try:
        # Reject collisions before reading or writing any media.
        for index, item in enumerate(selected):
            target = NAS / item['relative']
            partial = NAS / ('.branconet-migration-' + args.run_id + '-' + str(index) + '.partial')
            need(not target.exists() and not partial.exists(), 'existing_nas_file_preserved')
        inventory_code = '''from pathlib import Path
import hashlib,json,os,stat
root=Path('/mnt/plex_smb_share')/'downloads'
names=REPLACE_NAMES
out=[]
for name in names:
 p=root/name;s=p.lstat();assert p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_nlink==1
 h=hashlib.sha256()
 with p.open('rb')as stream:
  for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
 t=p.lstat();assert(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns)
 out.append({'name':name,'sha256':h.hexdigest(),'identity':{k:getattr(t,'st_'+k)for k in ['dev','ino','size','mode','uid','gid','nlink','mtime_ns','ctime_ns','blocks']}})
print(json.dumps(out))
'''.replace('REPLACE_NAMES', repr([x['relative'] for x in selected]))
        event('source_inventory_started')
        inventory = subprocess.run(remote(inventory_code), capture_output=True, timeout=240)
        need(inventory.returncode == 0 and len(inventory.stdout) < 8192, 'source_inventory')
        files = json.loads(inventory.stdout)
        need({f['identity']['size'] for f in files} == SIZES, 'source_size_changed')
        event('source_inventory_complete', files=files)
        for index, item in enumerate(files):
            target = NAS / item['name']
            partial = NAS / ('.branconet-migration-' + args.run_id + '-' + str(index) + '.partial')
            need(not target.exists() and not partial.exists(), 'destination_race')
            event('copy_started', source=item, target=str(target), partial=str(partial))
            body = '''from pathlib import Path
import hashlib,os,stat,sys
item=REPLACE_ITEM
p=Path('/mnt/plex_smb_share')/'downloads'/item['name']
def ident(s):return {k:getattr(s,'st_'+k)for k in item['identity']}
assert p.resolve()==p and ident(p.lstat())==item['identity']
fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);h=hashlib.sha256();count=0
with os.fdopen(fd,'rb')as src:
 assert ident(os.fstat(src.fileno()))==item['identity']
 for block in iter(lambda:src.read(1024**2),b''):
  h.update(block);count+=len(block);sys.stdout.buffer.write(block)
 assert ident(os.fstat(src.fileno()))==item['identity']
sys.stdout.buffer.flush()
assert count==item['identity']['size']and h.hexdigest()==item['sha256']and ident(p.lstat())==item['identity']
'''.replace('REPLACE_ITEM', repr(item))
            child = subprocess.Popen(remote(body), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            children.append(child)
            h = hashlib.sha256()
            count = 0
            with partial.open('xb') as output:
                for block in iter(lambda: child.stdout.read(1024**2), b''):
                    count += len(block)
                    need(count <= item['identity']['size'] and shutil.disk_usage(NAS).free >= FLOOR, 'copy_size_or_space')
                    output.write(block)
                    h.update(block)
                output.flush()
                os.fsync(output.fileno())
            need(child.wait(timeout=60) == 0 and count == item['identity']['size'] and h.hexdigest() == item['sha256'], 'source_stream_integrity')
            need(partial.stat().st_size == count, 'nas_partial_size')
            # Preserve source modification time as closely as SMB exposes it;
            # the exact original numeric ownership/mode/time remains in receipt.
            os.utime(partial, ns=(item['identity']['mtime_ns'], item['identity']['mtime_ns']))
            need(not target.exists(), 'final_name_collision')
            partial.rename(target)
            need(target.stat().st_size == count and sha(target) == item['sha256'], 'published_nas_full_readback')
            result['files'].append({'source': item, 'nasPath': str(target), 'nasBytes': count, 'nasSHA256': item['sha256'], 'nasMtimeNs': target.stat().st_mtime_ns})
            event('file_verified', index=index, bytes=count, sha256=item['sha256'])
        check = subprocess.run(remote(inventory_code), capture_output=True, timeout=240)
        need(check.returncode == 0 and json.loads(check.stdout) == files, 'original_source_changed')
        result.update(status='completed', originalSourcesUnchanged=True, sourceDeleted=False)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__, sourceDeleted=False)
        raise
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=30)
        (run / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
        event('finished', status=result['status'], sourceDeleted=False)
        print(json.dumps({'status': result['status'], 'receipt': str(run / 'receipt.json'), 'filesVerified': len(result['files']), 'sourceDeleted': False}))


if __name__ == '__main__':
    main()
