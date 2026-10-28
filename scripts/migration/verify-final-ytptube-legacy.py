#!/usr/bin/env python3
"""Hash exactly seven original files in the existing pod; no writes or NAS walk."""
import hashlib
import argparse
import json
from pathlib import Path
import runpy
import subprocess

SOURCE = Path(__file__).resolve()
REPO = SOURCE.parents[2]
ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'platform-upstream-review-20261027/final-media-state-20261028'
REMOTE = r'''
import hashlib,json,pathlib,sys,os,stat
manifest=json.load(sys.stdin);out={}
assert len(manifest)==7
for name,row in manifest.items():
 parts=pathlib.PurePosixPath(name).parts
 assert len(parts)==2 and parts[0] in ('data-0','data-1') and parts[1] not in ('.','..')
 root=pathlib.Path('/state' if parts[0]=='data-0' else '/tmp_dir');path=root/parts[1]
 assert root.is_dir() and not root.is_symlink() and not path.is_symlink()
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(fd);assert stat.S_ISREG(before.st_mode) and before.st_size==row['bytes']
  h=hashlib.sha256();size=0
  while True:
   block=os.read(fd,1048576)
   if not block:break
   h.update(block);size+=len(block)
  after=os.fstat(fd)
  assert (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
  out[name]={'bytes':size,'sha256':h.hexdigest(),'matches':size==row['bytes'] and h.hexdigest()==row['sha256']}
 finally:os.close(fd)
print(json.dumps(out))
'''

def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--security-refresh',action='store_true')
    args=parser.parse_args()
    transport=runpy.run_path(str(SOURCE.with_name('verify-final-media-history.py')))
    op=runpy.run_path(str(SOURCE.with_name('qualify-ytptube.py')))
    if args.security_refresh:
        OUT=ROOT/'platform-upstream-review-20261027/upstream-security-refresh-20261028'
        image='ghcr.io/arabcoders/ytptube:v2.7.6@sha256:a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86'
        op['UPSTREAM_IMAGE']=image
    def kube(*args,body=None,timeout=30):
        return transport['remote'](['kubectl','-n','plex',*args],body)
    op['writer'].__globals__['kubectl']=kube
    oldreader=REPO/'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py'
    reader=runpy.run_path(str(oldreader))
    receipt_path=Path('/home/brajam/.local/share/branconet-migration/metube-state-20261024/metube-backup-1cd7f75fb44d4e4495afdcd223fb2b2d/receipt.json')
    assert reader['file_hash'](receipt_path)=='1be3ce258c6753ecaf39af11d226326cfb87f443298fa20a7043dcadf9eb1a3c'
    baseline=json.loads(receipt_path.read_bytes())
    assert baseline['status']=='completed' and baseline['cold_archive_verified'] is True and baseline['file_count']==7
    archive=Path(baseline['archive_path'])
    assert reader['file_hash'](archive)==baseline['archive_sha256']
    assert reader['file_hash'](reader['AGE'])==reader['AGE_SHA256']
    process=subprocess.Popen([str(reader['AGE']),'-d','-i',str(reader['IDENTITY']),str(archive)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        manifest=reader['verify_archive'](process.stdout)
        trailing=0
        for block in iter(lambda:process.stdout.read(65536),b''):
            trailing+=len(block);assert trailing<=1024**2 and not any(block)
        assert process.wait(timeout=30)==0
    finally:
        process.stdout.close()
        if process.poll() is None:process.kill();process.wait()
    assert hashlib.sha256(reader['canonical'](manifest)).hexdigest()==baseline['manifest_sha256']
    files={name:row for name,row in manifest['entries'].items() if row['kind']=='file'}
    assert len(files)==7 and sum(v['bytes'] for v in files.values())==618241982
    before=op['writer'](op['UPSTREAM_IMAGE'])
    assert before['deployment_uid']==baseline['deployment_uid']
    assert {v['name']:v['uid'] for v in before['claims'].values()}=={v['name']:v['uid'] for v in baseline['claims']}
    def mount_fence():
        pod=json.loads(kube('get','pod',before['pod'],'-o','json'))
        mounts={m['mountPath']:m for c in pod['spec']['containers'] if c['name']=='ytdl' for m in c['volumeMounts']}
        volumes={v['name']:v for v in pod['spec']['volumes']}
        for target,claim in [('/state','ytdl-data-0'),('/tmp_dir','ytdl-data-1')]:
            mount=mounts[target];assert not mount.get('subPath') and not mount.get('subPathExpr')
            assert volumes[mount['name']]['persistentVolumeClaim']['claimName']==claim
        return pod['metadata']['uid'],pod['spec']['nodeName']
    mount_before=mount_fence()
    observed=json.loads(kube('exec','-i',before['pod'],'-c','ytdl','--','/opt/python/bin/python','-B','-c',REMOTE,body=json.dumps(files).encode()))
    assert before==op['writer'](op['UPSTREAM_IMAGE']) and mount_before==mount_fence()
    result={'passed':all(v['matches'] for v in observed.values()),'writer':before,'podUID':mount_before[0],'node':mount_before[1],'files':observed,'baselineReceiptSHA256':reader['file_hash'](receipt_path),'archiveSHA256':baseline['archive_sha256'],'manifestSHA256':baseline['manifest_sha256'],'authenticatedCompleteArchiveRead':True,'fileCount':len(observed),'totalBytes':sum(v['bytes'] for v in observed.values()),'sourceSHA256':reader['file_hash'](SOURCE),'readerSHA256':reader['file_hash'](oldreader),'newDownloads':False,'newMounts':False,'filesystemWalk':False,'plaintextExtractedToFilesystem':False}
    op['save_new'](OUT/'ytptube-seven-original-files.json',result)
    print(json.dumps({'passed':result['passed'],'fileCount':len(observed),'totalBytes':result['totalBytes'],'podUID':mount_before[0]}))

if __name__=='__main__':main()
