"""Retire one of two completed transfer duplicates; never prune runtime images."""
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
PROFILES={
    'seerr':(NAME,SHA,SIZE,DIGEST,ALIAS),
    'ytptube':('ytptube-security-20261023-ci40052586445.oci.tar',
        'c1d4130b64aa71629e5ead6ac0c37d17194dff2cf644ae5e4f8115f5559de5c3',461156352,
        'sha256:7c637f7e9cadf6f7def2243b517ff6101354287e17f9aebed8b0aa386fd1b754',
        'docker.io/library/ytptube-security-20261023@sha256:7c637f7e9cadf6f7def2243b517ff6101354287e17f9aebed8b0aa386fd1b754')}
PROFILES.update({'flaresolverr': ('flaresolverr-security-20261023-ci40058492329.oci.tar', 'db6315339f46a96d02d80bac4687de6929b1b900b640d1c9a146e54570209a7e', 478848000, 'sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7', 'docker.io/library/flaresolverr-security-20261023@sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7'), 'wordpress': ('wordpress-security-20261023.oci.tar', '1beae8accc1979992c256bf2b2274e93d0f0b61253a64bb0c0ea1ff7fc173889', 278253056, 'sha256:fe0f66b827b865026a5ffcf0ee28b34f8e2d2cc9fb6c85bd3faace75987a9bf0', 'docker.io/library/wordpress-security-20261023@sha256:fe0f66b827b865026a5ffcf0ee28b34f8e2d2cc9fb6c85bd3faace75987a9bf0'), 'phpmyadmin': ('phpmyadmin-security-20261023.oci.tar', '983b0c04a75cfc5cb52eec40833f66ba4c77c2b91fa11a58327a26a744eb1c1a', 198543872, 'sha256:f52ba34cdf0d98b6b25cf4654fa6da3d69371651dbaab092a92129e6824403f2', 'docker.io/library/phpmyadmin-security-20261023@sha256:f52ba34cdf0d98b6b25cf4654fa6da3d69371651dbaab092a92129e6824403f2'), 'tautulli': ('tautulli-security-20261023-ci40068021890.oci.tar', 'e2e9fe4ce25fddf7b6944f6b00212c256a80ad9df66cda70dfbb36585a687d40', 108427776, 'sha256:769aa67e07e35bdfe714a486591eb1a34c9ad9bd6cf2da89da130dcdab9de05a', 'docker.io/library/tautulli-security-20261023@sha256:769aa67e07e35bdfe714a486591eb1a34c9ad9bd6cf2da89da130dcdab9de05a'), 'vaultwarden': ('vaultwarden-security-20261023-ci40060033423.oci.tar', 'ad0c9750afb40816382c33b669e7250c294adf7cda841566f94abbe19036c949', 92899840, 'sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d', 'docker.io/library/vaultwarden-security-20261023@sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d'), 'coredns': ('coredns-security-20261023.oci.tar', 'c499e924e0f59a95ef79326bb8014e1a143f25fad8db25684342d115e77500bf', 69998592, 'sha256:014e9ae348d5dcf3ed5451a5490a29bb6e51477f5b3291e31804c74fe6b557d9', 'docker.io/library/coredns-security-20261023@sha256:014e9ae348d5dcf3ed5451a5490a29bb6e51477f5b3291e31804c74fe6b557d9'), 'nginx': ('nginx-security-20261023.oci.tar', '9a73ec166398aefcd56871869f04c382cd1dd1487d5077ae47210e43d3f26e56', 65977856, 'sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3', 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3')})

PROFILES.update({'mealie': ('mealie-security-20261023-r2.oci.tar', 'bd04589000b777dea02d7967669d332fdbdffb2ad9d0c0783e544e6e76d63cfe', 627191296, 'sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9', 'docker.io/library/mealie-security-20261023@sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9'), 'xteve': ('xteve-security-20261023-r1.oci.tar', 'b36f04e79afedf1f89ab84013af36d9a6cabc556d0dbf2c15327227394a2579a', 220521984, 'sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656', 'docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'), 'jtmb-dev': ('jtmb-dev-security-20261023-r1.oci.tar', 'c40750f4c164e57a754aa631e1fba01f1e899cd623678891f4eb56bd4af16958', 66908160, 'sha256:6432c71889d843c7efb381a4321e4fba07a52a0cfb50171921b6315bddf1b295', 'docker.io/library/jtmb-dev-security-20261023@sha256:6432c71889d843c7efb381a4321e4fba07a52a0cfb50171921b6315bddf1b295'), 'plex': ('plex-security-20261023.oci.tar', '5dd3a6748713c4d33e1130ac04ca6fff2a3130e9fbbea83051b57a7cc6ec9e61', 395109888, 'sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397', 'docker.io/library/plex-security-20261023@sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397'), 'qbittorrent-current': ('qbittorrent-current-security-20261023.oci.tar', '4a103e0632f0c53fe14ac1a3202abc103d37b11899f06661f777dac95c72f278', 102375424, 'sha256:9e546e0ac277ef9b241cb383bfa9157e47df3269e62481348a63f4d19b87adf8', 'docker.io/library/qbittorrent-current-security-20261023@sha256:9e546e0ac277ef9b241cb383bfa9157e47df3269e62481348a63f4d19b87adf8')})
PROFILES.update({
    'radarr': ('radarr-security-20261023-r1.oci.tar', 'cd2d2f1daab143fbb12db7e55d3c4e00e39d16fbb703724ca3a316fe2eb54cf7', 141429760,
               'sha256:b79e4e0e3bec790e4f8a48cca83fd5b34e1267f672e27496cf1b95e732fed83c',
               'docker.io/library/radarr-security-20261023@sha256:b79e4e0e3bec790e4f8a48cca83fd5b34e1267f672e27496cf1b95e732fed83c'),
    'sonarr': ('sonarr-security-20261023-r1.oci.tar', '0799041fc3e9f06811c7fc8d42ebded9aaa9901f04539383a8389533cc2e58b3', 134134784,
               'sha256:7d297bbadfd74dd2c346b48d32530d6fa632bc902739d4f7aaadbd898375f593',
               'docker.io/library/sonarr-security-20261023@sha256:7d297bbadfd74dd2c346b48d32530d6fa632bc902739d4f7aaadbd898375f593'),
    'bazarr': ('bazarr-security-20261023-r2.oci.tar', 'dca662b128f93e203be25119c6417af893265c8cfe3f41a68c9eb74e67868407', 154896896,
               'sha256:bcf9a782f3381b4182bed0985e0d38df79da0218ead2ca47c577595e9dafe21b',
               'docker.io/library/bazarr-security-20261023@sha256:bcf9a782f3381b4182bed0985e0d38df79da0218ead2ca47c577595e9dafe21b'),
    'whoami': ('whoami-security-20261023-r1.oci.tar', '4085fbdf0551290c784ead0916e3db71c20cf2225c8bbc36c9d1c6866f77a8d5', 10252288,
               'sha256:cb42c3577ddf0d7eae9c88f6ff2a99fbe217d92d4e44ae88a92f0a372000dcb1',
               'docker.io/library/whoami-security-20261023@sha256:cb42c3577ddf0d7eae9c88f6ff2a99fbe217d92d4e44ae88a92f0a372000dcb1'),
})
OFFLOADED_PROFILES={'mealie', 'plex', 'jtmb-dev', 'xteve', 'qbittorrent-current', 'radarr', 'sonarr', 'bazarr', 'whoami'}


def need(ok):
    if not ok:raise ValueError('Completed Seerr transfer retention check refused')

def fingerprint(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1024**2),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['controller','inventory','retire']);p.add_argument('--service',choices=sorted(PROFILES),default='seerr');a=p.parse_args()
    NAME,SHA,SIZE,DIGEST,ALIAS=PROFILES[a.service]
    controller=a.phase=='controller'
    need(os.geteuid()==(pwd.getpwnam('brajam').pw_uid if controller else 0))
    parent=Path('/home/brajam' if controller else '/home/james')/'.local/share/branconet-migration/application-artifacts-20261023'
    if controller and a.service in OFFLOADED_PROFILES:
        mount=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
        need(mount.is_mount() and mount.resolve()==mount and mount.stat().st_dev!=os.stat('/').st_dev)
        need(subprocess.check_output(['findmnt','-n','-o','UUID,FSTYPE','--target',str(mount)],timeout=10).decode().split()==['3c792469-ea0e-4a2c-98e8-1185b141607b','ext4'])
        parent=mount/'application-artifacts-20261023'
    need(parent.resolve()==parent and parent.is_dir())
    need(parent.stat().st_uid==pwd.getpwnam('brajam' if controller else 'james').pw_uid and stat.S_IMODE(parent.stat().st_mode)==0o700)
    if not controller:need(socket.gethostname().split('.')[0] in ['masternode','workernode2','workernode1'])
    path=parent/NAME
    if not path.exists():
        need(a.phase!='controller');print(json.dumps({'changed':False,'already_absent':True,'path':str(path)}));return
    before=path.lstat();need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==SIZE and stat.S_IMODE(before.st_mode) in ((0o400,0o600) if controller else (0o600,)))
    need(before.st_uid==pwd.getpwnam('brajam' if controller else 'james').pw_uid and path.resolve()==path)
    need(sha(path)==SHA and fingerprint(path.stat())==fingerprint(before))
    result={'phase':a.phase,'service':a.service,'path':str(path),'archive_sha256':SHA,'logical_bytes':SIZE,'allocated_bytes':before.st_blocks*512,'changed':False,'images_pruned':False,'volumes_changed':False,'controller_copy_retained':True}
    if controller:print(json.dumps(result));return
    ctr=['/opt/containerd-k8s/bin/ctr','--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
    listing=subprocess.check_output(ctr+['images','list'],timeout=30).decode().splitlines()
    images={p[0]:p[2] for line in listing if len(p:=line.split())>=3 and p[2].startswith('sha256:')}
    need(ALIAS not in images or images[ALIAS]==DIGEST)
    # Kubelet may already have garbage-collected this unused image on a node.
    # This file is a reproducible transfer, not the retained rollback archive:
    # the role hashes the full controller archive before AND after removal.
    # Never recreate/prune a runtime image merely to remove a transfer copy.
    cached=ALIAS in images
    docs=[];seen=set()
    if cached:
        manifest=subprocess.check_output(ctr+['content','get',DIGEST],timeout=30)
        need('sha256:'+hashlib.sha256(manifest).hexdigest()==DIGEST)
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
    result['cached_alias_present']=cached
    result['regeneration']='copy the exact SHA256-verified controller archive to this path'
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
