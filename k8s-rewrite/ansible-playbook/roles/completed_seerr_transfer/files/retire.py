"""Retire one duplicate transfer file after Seerr acceptance; never prune images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess

NAME='seerr-security-20261023-ci40048938336.oci.tar'
SHA='d3fa13eee47afd2a6c83e5fc49796a02143c441513c36fd06aa9b21dff64b174'
SIZE=319832064
DIGEST='sha256:7bf03e8c4433460c0d93f789da56db457e3484412c448997102885af185db93c'
ALIAS='docker.io/library/seerr-security-20261023@'+DIGEST

def need(ok):
    if not ok:raise ValueError('Completed Seerr transfer retention check refused')

def fingerprint(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1024**2),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['controller','inventory','retire']);a=p.parse_args()
    controller=a.phase=='controller'
    need(os.geteuid()==(pwd.getpwnam('brajam').pw_uid if controller else 0))
    parent=Path('/home/brajam' if controller else '/home/james')/'.local/share/branconet-migration/application-artifacts-20261023'
    need(parent.resolve()==parent and parent.is_dir())
    need(parent.stat().st_uid==pwd.getpwnam('brajam' if controller else 'james').pw_uid and stat.S_IMODE(parent.stat().st_mode)==0o700)
    if not controller:need(socket.gethostname().split('.')[0]=='masternode')
    path=parent/NAME
    if not path.exists():
        need(a.phase!='controller');print(json.dumps({'changed':False,'already_absent':True,'path':str(path)}));return
    before=path.lstat();need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==SIZE and stat.S_IMODE(before.st_mode) in ((0o400,0o600) if controller else (0o600,)))
    need(before.st_uid==pwd.getpwnam('brajam' if controller else 'james').pw_uid and path.resolve()==path)
    need(sha(path)==SHA and fingerprint(path.stat())==fingerprint(before))
    result={'phase':a.phase,'path':str(path),'archive_sha256':SHA,'logical_bytes':SIZE,'allocated_bytes':before.st_blocks*512,'changed':False,'images_pruned':False,'volumes_changed':False,'controller_copy_retained':True}
    if controller:print(json.dumps(result));return
    ctr=['/opt/containerd-k8s/bin/ctr','--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
    listing=subprocess.check_output(ctr+['images','list'],timeout=30).decode().splitlines()
    images={p[0]:p[2] for line in listing if len(p:=line.split())>=3 and p[2].startswith('sha256:')}
    need(images.get(ALIAS)==DIGEST)
    manifest=subprocess.check_output(ctr+['content','get',DIGEST],timeout=30)
    need('sha256:'+hashlib.sha256(manifest).hexdigest()==DIGEST)
    # The same immutable image and all referenced content must remain available.
    docs=[json.loads(manifest)];seen={DIGEST}
    while docs:
        doc=docs.pop()
        for descriptor in doc.get('manifests',[]) + doc.get('layers',[]) + ([doc['config']] if 'config' in doc else []):
            digest=descriptor['digest']
            if digest in seen:continue
            seen.add(digest);need(len(seen)<=256 and descriptor['size']<=4*1024**3)
            child=subprocess.Popen(ctr+['content','get',digest],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            h=hashlib.sha256();count=0;small=[]
            for b in iter(lambda:child.stdout.read(1024**2),b''):
                count+=len(b);need(count<=descriptor['size']);h.update(b)
                if descriptor['mediaType'].endswith(('manifest.v1+json','index.v1+json')):small.append(b);need(count<=4*1024**2)
            need(child.wait(timeout=30)==0 and count==descriptor['size'] and 'sha256:'+h.hexdigest()==digest)
            if small:docs.append(json.loads(b''.join(small)))
    # No process, mount or loop may use the transfer file. Races disappearing
    # during /proc inspection are normal; an unreadable live FD is a refusal.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            fds=list((proc/'fd').iterdir())
        except (FileNotFoundError,ProcessLookupError):continue
        for fd in fds:
            try:info=fd.stat()
            except (FileNotFoundError,ProcessLookupError):continue
            need((info.st_dev,info.st_ino)!=(before.st_dev,before.st_ino))
    need(str(path) not in Path('/proc/self/mountinfo').read_text())
    for backing in Path('/sys/block').glob('loop*/loop/backing_file'):
        need(backing.read_text().strip()!=str(path))
    need(fingerprint(path.lstat())==fingerprint(before))
    result['cached_content_blobs_verified']=len(seen)
    result['free_bytes_before']=os.statvfs(parent).f_bavail*os.statvfs(parent).f_frsize
    if a.phase=='retire':
        parent_fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            need(fingerprint(os.stat(NAME,dir_fd=parent_fd,follow_symlinks=False))==fingerprint(before))
            os.unlink(NAME,dir_fd=parent_fd);os.fsync(parent_fd)
        finally:os.close(parent_fd)
        result['changed']=True
    result['free_bytes_after']=os.statvfs(parent).f_bavail*os.statvfs(parent).f_frsize
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
