#!/usr/bin/env python3
"""Read-only original static-site, native binding and HTTP preservation proof."""
import argparse
import copy
from decimal import Decimal
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import resource
import shlex
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

OLD='jtmb92/jtmb-dev@sha256:d46e9aeb8222d60b6778b6aa2202359b0982da76a69b2d4f01a5d58bc5a309a2'
NEW='docker.io/library/jtmb-dev-security-20261023@sha256:6432c71889d843c7efb381a4321e4fba07a52a0cfb50171921b6315bddf1b295'
NS='website-stack'
BASELINE_SOURCE='27e03fa18b0c83e4e202f318c9d5ea2262b958644ba5cb064331d5bb941eaab0'
TOUCHED_CONFIG={'etc/nginx/conf.d','etc/nginx/conf.d/default.conf'}

def files_equal(old,new):
    if set(old)!=set(new):return False
    for path,left in old.items():
        right=new[path]
        if left==right:continue
        if path not in TOUCHED_CONFIG:return False
        if {k:v for k,v in left.items() if k!='mtime'}!={k:v for k,v in right.items() if k!='mtime'}:return False
        before,after=Decimal(left['mtime']),Decimal(right['mtime'])
        if not (before.is_finite() and after.is_finite() and before<=after<=Decimal(str(time.time()+60))):return False
    return True

def need(ok):
    if not ok:raise ValueError('Static-site preservation refused')

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()

def kube(*args):
    p=subprocess.run(['kubectl','--request-timeout=25s','-n',NS,*args],capture_output=True,timeout=120)
    need(p.returncode==0 and len(p.stdout)<=32*1024**2);return p.stdout

def obj(kind,name,ns=NS):return json.loads(kube('-n',ns,'get',kind,name,'-o','json'))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','after','restart']);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--previous-after',type=Path);a=p.parse_args()
    need(socket.gethostname().split('.')[0]=='masternode');resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.umask(0o077)
    key=bytes.fromhex(sys.stdin.read(67).strip());need(len(key)==32)
    mac=lambda domain,value:hmac.new(key,canonical([domain,value]),hashlib.sha256).hexdigest()
    need(a.receipt.is_absolute() and a.receipt.resolve()==a.receipt and not a.receipt.exists() and not a.receipt.parent.stat().st_mode&0o077)
    image=OLD if a.mode=='baseline' else NEW
    def fence():
        dep=obj('deployment','jtmb-dev');hr=obj('helmrelease','jtmb-dev','flux-system');service=obj('service','jtmb-dev')
        need(dep['spec']['replicas']==1 and dep['status'].get('observedGeneration',0)>=dep['metadata']['generation'])
        need(all(dep['status'].get(k)==1 for k in ['replicas','readyReplicas','availableReplicas','updatedReplicas']))
        need(not hr['spec'].get('suspend') and hr['spec']['values']['replicaCount']==1 and any(c['type']=='Ready' and c['status']=='True' for c in hr['status'].get('conditions',[])))
        spec=dep['spec']['template']['spec'];need(len(spec['containers'])==1 and spec['containers'][0]['image']==image)
        need(not spec.get('volumes') and not spec.get('initContainers'))
        pods=json.loads(kube('get','pods','-l','app=jtmb-dev','-o','json'))['items'];need(len(pods)==1)
        pod=pods[0];cs=pod['status']['containerStatuses'];need(not pod['metadata'].get('deletionTimestamp') and len(cs)==1 and cs[0]['ready'])
        need(pod['spec']['containers'][0]['image']==image and cs[0]['imageID'].rsplit('@',1)[-1]==image.rsplit('@',1)[-1])
        rs=next(o for o in pod['metadata']['ownerReferences'] if o.get('controller'));replica=obj('replicaset',rs['name'])
        need(rs['kind']=='ReplicaSet' and replica['metadata']['uid']==rs['uid'] and any(o['uid']==dep['metadata']['uid'] and o.get('controller') for o in replica['metadata']['ownerReferences']))
        normalized=copy.deepcopy(dep['spec']);normalized['template']['spec']['containers'][0]['image']='<maintenance-image>'
        annotations=normalized['template'].get('metadata',{}).get('annotations',{});annotations.pop('kubectl.kubernetes.io/restartedAt',None)
        if not annotations:normalized['template'].get('metadata',{}).pop('annotations',None)
        resources={'deployment':dep,'helmrelease':hr,'service':service}
        for n in ['jtmb-dev-ingress','jtmb-dev-https']:resources['ingress/'+n]=obj('ingress',n)
        stable={k:{'uid':v['metadata']['uid'],'spec_hmac':mac(k,normalized if k=='deployment' else v['spec'])} for k,v in resources.items()}
        writer={'pod_uid':pod['metadata']['uid'],'image':image,'runtime':cs[0]['imageID'],'restart_count':cs[0].get('restartCount',0)}
        return stable,writer,pod['metadata']['name'],service['spec']['clusterIP']
    stable,writer,pod,address=fence()
    if a.mode!='baseline':
        # The exact reviewed official hook touches default.conf before checking
        # its package checksum, and sed's replacement can touch its directory.
        hook=kube('exec',pod,'-c','jtmb-dev','--','sha256sum','/docker-entrypoint.d/10-listen-on-ipv6-by-default.sh').decode().split()
        need(hook==['91c84252278f74e5b22f9c573464994691bd4e0b2b7196315342979d49722f79','/docker-entrypoint.d/10-listen-on-ipv6-by-default.sh'])
    raw=kube('exec',pod,'-c','jtmb-dev','--','tar','--format=pax','--numeric-owner','-cf','-','-C','/','etc/nginx','usr/share/nginx/html')
    files={};paths=[];total=0
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for item in tar:
            name=item.name.rstrip('/');need(name not in files and '..' not in Path(name).parts and not name.startswith('/'))
            need(name in ['etc/nginx','usr/share/nginx/html'] or name.startswith(('etc/nginx/','usr/share/nginx/html/')))
            record={'uid':item.uid,'gid':item.gid,'mode':item.mode,'mtime':item.pax_headers.get('mtime',str(item.mtime))}
            if item.isfile():
                need(item.size<=8*1024**2);body=tar.extractfile(item).read();total+=len(body);need(total<=24*1024**2)
                record.update(kind='file',bytes=len(body),body_hmac=mac(['file',name],body.hex()))
                if name.startswith('usr/share/nginx/html/'):paths.append('/'+name[len('usr/share/nginx/html/'):])
            elif item.isdir():record['kind']='directory'
            elif item.issym():record.update(kind='symlink',target=item.linkname)
            else:raise ValueError('Unsupported site object')
            files[name]=record;need(len(files)<=1024)
    paths=['/']+sorted(paths)+['/__branconet_maintenance_missing_20261025__'];need(len(paths)<=256)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect());http={}
    for path in paths:
        request=urllib.request.Request('http://'+address+urllib.parse.quote(path,safe='/'),headers={'Host':'jtmb-dev.branconet.local','Accept-Encoding':'identity'})
        try:r=opener.open(request,timeout=10)
        except urllib.error.HTTPError as error:r=error
        with r:
            body=r.read(8*1024**2+1);need(len(body)<=8*1024**2)
            if path=='/__branconet_maintenance_missing_20261025__' and r.code==404:
                version=b'nginx/1.27.5' if a.mode=='baseline' else b'nginx/1.30.6'
                need(body.count(b'<center>'+version+b'</center>')==1)
                body=body.replace(b'<center>'+version+b'</center>',b'<center>nginx/<maintenance-version></center>')
            http[path]={'status':r.code,'body_hmac':mac(['HTTP',path],body.hex()),'headers':{k:r.headers.get(k) for k in ['Content-Type','Cache-Control','ETag','Last-Modified','Location']}}
    need(http['/']['status']==200);need(fence()[:2]==(stable,writer))
    receipt={'mode':a.mode,'passed':True,'stable':stable,'writer':writer,'files':files,'http':http,'file_bytes':total,'routes_checked':len(http),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'personal_login_verified':False,'browser_verified':False,'failures':[]}
    def read(path,mode):
        value=json.loads(path.read_bytes());signature=value.pop('receipt_hmac');need(hmac.compare_digest(signature,mac('receipt',value)) and value['mode']==mode and value['passed']);return value
    if a.mode!='baseline':
        old=read(a.baseline,'baseline');need(old['source_sha256'] in [receipt['source_sha256'],BASELINE_SOURCE])
        for label in ['stable','http']:
            if old[label]!=receipt[label]:receipt['failures'].append(label)
        if not files_equal(old['files'],receipt['files']):receipt['failures'].append('files')
        receipt['source_proven_runtime_timestamps']=[n for n in TOUCHED_CONFIG if old['files'][n]!=receipt['files'][n]]
        receipt['baseline_sha256']=hashlib.sha256(a.baseline.read_bytes()).hexdigest()
        if a.mode=='restart':
            previous=read(a.previous_after,'after');need(previous['baseline_sha256']==receipt['baseline_sha256'])
            if previous['writer']['pod_uid']==writer['pod_uid'] and writer['restart_count']<=previous['writer']['restart_count']:receipt['failures'].append('restart-not-observed')
    receipt['passed']=not receipt['failures'];receipt['receipt_hmac']=mac('receipt',receipt)
    with os.fdopen(os.open(a.receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps({'passed':receipt['passed'],'routes_checked':len(http),'files':len(files),'failures':receipt['failures']}));return 0 if receipt['passed'] else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:raise SystemExit('Static-site preservation refused; raw values suppressed')
