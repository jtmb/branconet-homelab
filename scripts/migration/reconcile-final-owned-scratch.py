"""Retire four terminal zero-byte locks and the regenerable final etcdutl copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import stat
import subprocess

BASE='/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
REL='platform-upstream-review-20261027/final-owned-scratch-20261028'
COHORTS=['master-cache-capacity-20261028','retired-web-cache-masternode-20261028','retired-platform-cache-workernode2-20261028','retired-mysql-cache-workernode2-20261028']
GUARD_SHA='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
TOOL_SHA='e3bd459308395080493488003f8cd4498db7ad4237584881b00f948a47950d2f'
REPO=Path(__file__).resolve().parents[2]

def sha(p):
    with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def ident(p):
    s=p.lstat();return {k:getattr(s,'st_'+k)for k in ['dev','ino','mode','uid','gid','nlink','size','mtime_ns','ctime_ns','blocks']}

def save(p,d):
    with p.open('x')as f:json.dump(d,f,indent=2)
    if os.name!='nt':os.chown(p,1000,1000)

def windows(h,root):
    import ctypes
    from ctypes import wintypes
    plan=json.loads((h/'plan.json').read_text());k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];k.CreateFileW.restype=wintypes.HANDLE;k.CloseHandle.argtypes=[wintypes.HANDLE]
    handles=[]
    try:
        for row in plan['targets']:
            p=root/row['relative'];v=k.CreateFileW(str(p),0x80000000,0,None,3,0x02000000 if row['directory']else 0,None)
            assert v not in (None,ctypes.c_void_p(-1).value),('native_windows_reference_check_failed_protect_exact_target',str(p),ctypes.get_last_error())
            handles.append(v)
    finally:
        for v in handles:k.CloseHandle(v)
    save(h/'windows.json',{'planSHA256':sha(h/'plan.json'),'exclusiveHandlesClosed':len(handles)});print(json.dumps({'exclusiveHandlesClosed':len(handles)}))

def regeneration(root,h):
    lib=runpy.run_path(str(REPO/'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
    old=root/'platform-upstream-review-20261027/etcd-restore-qualification/cp-e90319b39ff741ab9dbc9f7d09cc6187-reuse-installed-tool-ctr.py'
    import ast
    tree=ast.parse(old.read_bytes());node=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='REMOTE'for t in n.targets))
    code=ast.literal_eval(node.value)
    assert code.count("['ctr',")==1
    code=code.replace("['ctr',","['/opt/containerd-k8s/bin/ctr',")
    code=code.replace('cid=sys.argv[1];',"assert hashlib.sha256(open('/opt/containerd-k8s/bin/ctr','rb').read()).hexdigest()=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'\ncid=sys.argv[1];")
    def source():
        p=lib['get']('pods','etcd-masternode','kube-system');c=next(c for c in p['status']['containerStatuses']if c['name']=='etcd')
        assert c['ready']and c['imageID']=='registry.k8s.io/etcd:3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910'
        return {'podUID':p['metadata']['uid'],'containerID':c['containerID'],'imageID':c['imageID']}
    before=source();password=runpy.run_path(str(REPO/'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))['privilege_input']()
    try:
        p=subprocess.run(lib['SSH']+[shlex.join(['sudo','-S','-p','','--','python3','-B','-c',code,before['containerID'].removeprefix('containerd://')])],input=password+b'\n',capture_output=True,timeout=90)
        assert p.returncode==0 and len(p.stdout)==16601250 and hashlib.sha256(p.stdout).hexdigest()==TOOL_SHA and source()==before
        save(h/'regeneration.json',{'source':before,'sha256':TOOL_SHA,'completeBytesRead':len(p.stdout),'noPayloadFileWritten':True,'originalRecipeSHA256':sha(old),'executedReaderSHA256':hashlib.sha256(code.encode()).hexdigest(),'regenerate':'Read exact usr/local/bin/etcdutl from verified pinned etcd native container, using preserved original reader and native ctr path correction; verify exact bytes/hash before writing an explicit future owned tools destination.'})
    finally:password=None

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['inventory','windows','apply']);a=p.parse_args()
    root=Path(r'\\?\UNC\wsl.localhost\Ubuntu'+BASE.replace('/','\\'))if os.name=='nt'else Path(BASE);h=root/REL
    if a.mode=='windows':windows(h,root);return
    assert os.geteuid()==0 and root.is_mount() and root.resolve()==root
    assert subprocess.check_output(['findmnt','-n','-o','UUID','-T',str(root)]).decode().strip()=='3c792469-ea0e-4a2c-98e8-1185b141607b'
    for q in [root,Path('/mnt/c')]:assert os.statvfs(q).f_bavail*os.statvfs(q).f_frsize>=15*1024**3+32*1024**2
    o=root/'platform-upstream-review-20261027';q=o/'post-upgrade-control-plane-checkpoint-20261028';op=json.loads((q/'operator.json').read_bytes());assert op['status']=='completed'
    restore=o/'etcd-restore-qualification'/('cp-'+op['runID']+'-restore-result.json');r=json.loads(restore.read_bytes());assert r['status']=='completed'and r['completeAgeAuthentication']and r['offlineSnapshotRestoreExecuted']and r['keyValueHistoryHashUnchanged']
    tools=o/'etcd-restore-qualification/tools';target=tools/'etcdutl'
    paths=[o/n/'retirement.lock'for n in COHORTS]+[target,tools]
    if a.mode=='inventory':
        assert not h.exists();h.mkdir(mode=0o700);os.chown(h,1000,1000)
        save(h/'ownership.json',{'owner':'01a12045-bf7e-73b3-8557-752d17c72ffd','root':BASE,'generatedPaths':[str(h)],'completePeakBytes':32*1024**2,'protected':'All source, lockfiles, ciphertexts, original receipts, failed safety targets, image/data and unrelated workloads','endCondition':'Only metadata receipts retained; exact inactive generated targets removed after regeneration/Linux/Windows proof'})
        regeneration(root,h)
    proof=json.loads((h/'regeneration.json').read_bytes());assert proof['sha256']==TOOL_SHA and proof['completeBytesRead']==16601250
    assert list(tools.iterdir())==[target]and sha(target)==TOOL_SHA
    guard=root/'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py';assert sha(guard)==GUARD_SHA
    lib={'__name__':'final_owned_inactive_guard'};exec(compile(guard.read_bytes(),str(guard),'exec'),lib);lib.update(BASE=root,ATTEMPTS=tuple(str(x.relative_to(root))for x in paths));refs=lib['idle']()
    rows=[]
    for path in paths:
        assert path.resolve()==path and path.is_relative_to(root)and not path.is_symlink()and not path.is_mount()and not os.listxattr(path)
        i=ident(path);assert i['dev']==root.stat().st_dev and i['uid']==1000
        directory=stat.S_ISDIR(i['mode']);assert directory or(stat.S_ISREG(i['mode'])and i['nlink']==1)
        if path.name=='retirement.lock':assert i['size']==i['blocks']==0
        rows.append({'relative':str(path.relative_to(root)),'directory':directory,'identity':i,'sha256':None if directory else sha(path)})
    protected={str(x.relative_to(root)):sha(x)for x in [q/'operator.json',restore,REPO/'scripts/migration/reconcile-final-owned-scratch.py']if x.is_relative_to(root)}
    if a.mode=='inventory':save(h/'plan.json',{'targets':rows,'references':refs,'protected':protected,'regenerationProofSHA256':sha(h/'regeneration.json')});print(json.dumps({'targets':len(rows),'allocatedBytes':sum(x['identity']['blocks']*512 for x in rows)}));return
    plan=json.loads((h/'plan.json').read_bytes());win=json.loads((h/'windows.json').read_bytes());assert rows==plan['targets']and win['planSHA256']==sha(h/'plan.json')and win['exclusiveHandlesClosed']==len(rows)and protected==plan['protected']
    removed=[]
    for row in rows:
        path=root/row['relative'];now=ident(path)
        assert all(now[k]==row['identity'][k]for k in (['dev','ino','mode','uid','gid']if row['directory']else now))
        if row['directory']:assert not any(path.iterdir());path.rmdir()
        else:assert sha(path)==row['sha256'];path.unlink()
        removed.append({'path':str(path),'allocatedBytes':now['blocks']*512})
    save(h/'receipt.json',{'status':'completed','removed':removed,'removedAllocatedLinuxBytes':sum(x['allocatedBytes']for x in removed),'WindowsRecoveryClaimed':False,'regenerationProofSHA256':sha(h/'regeneration.json')});print(json.dumps({'removedAllocatedLinuxBytes':sum(x['allocatedBytes']for x in removed),'paths':len(removed)}))

if __name__=='__main__':main()
