"""Read-only outcome of an already-submitted native retirement; never retries.

The original failed receipt stays failed. No unlink, prune, removal, GC trigger,
service action or reference-guard relaxation is performed by this observer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
REMOTE=r'''
import hashlib,json,os,pathlib,stat,subprocess,sys
request=json.load(sys.stdin);q=request['qualification'];rows=q['profile']['mappedCandidates']
assert os.geteuid()==0 and 1<=len(rows)<=71
ctr=pathlib.Path('/opt/containerd-k8s/bin/ctr')
def sha(p):
 value=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):value.update(block)
 return value.hexdigest()
assert sha(ctr)=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
raw=subprocess.check_output([str(ctr),'--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io','images','list'],stdin=subprocess.DEVNULL,timeout=30)
assert hashlib.sha256(raw).hexdigest()==q['profile']['nativeInventory']['imageRecordsSHA256']
for b in q['verifiedOriginalBlobs']:
 p=pathlib.Path(b['path']);assert p.resolve()==p and p.is_relative_to('/var/lib/containerd-k8s/io.containerd.content.v1.content/blobs/sha256')
 s=p.lstat();actual={k:getattr(s,'st_'+k) for k in b['identity']}
 assert actual==b['identity'] and sha(p)==b['digest'][7:]
absent=[];retained=[]
for row in rows:
 p=pathlib.Path(row['path']);assert p.resolve()==p and p.parent==pathlib.Path('/var/lib/containerd-k8s/io.containerd.snapshotter.v1.overlayfs/snapshots')
 d={k:row[k] for k in ['key','path','allocatedBytes']}
 if p.exists():retained.append(dict(d,reason='Native API already handled; filesystem cleanup still present. No resubmission or raw deletion.'))
 else:absent.append(d)
s=os.statvfs('/')
print(json.dumps({'originalFailureReclassified':False,'observationOnly':True,'nativeRemoveResubmitted':False,'originalImagesAndCompletePayloadsPreserved':True,'absent':absent,'absentQualifiedAllocatedBytes':sum(x['allocatedBytes'] for x in absent),'retained':retained,'filesystem':{'capacity':s.f_blocks*s.f_frsize,'free':s.f_bfree*s.f_frsize,'usable':s.f_bavail*s.f_frsize}}))
'''

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--qualification',type=Path,required=True);p.add_argument('--journal',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--node',choices=['masternode','workernode2'],default='masternode');a=p.parse_args()
 assert os.geteuid()==1000 and F.is_mount()
 raw=sys.stdin.buffer.readline(130).removesuffix(b'\n');assert 0<len(raw)<=128 and not any(x in raw for x in (b'\r',b'\n',b'\0'))
 for path in [a.qualification,a.journal,a.receipt]:assert path.resolve()==path and path.parent==H
 assert not a.receipt.exists()
 qdata=a.qualification.read_bytes();journal=a.journal.read_bytes();q=json.loads(qdata);assert q['node']==a.node
 events=[json.loads(x) for x in journal.splitlines()];intent={x['intent'] for x in events if 'intent' in x};ack={x['removed'] for x in events if x.get('nativeRemoveCompleted')}
 assert ack<=intent
 address={'masternode':'192.168.0.4','workernode2':'192.168.0.5'}[a.node]
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@'+address,shlex.join(['sudo','-S','-k','-p','','python3','-B','-c',REMOTE])],input=raw+b'\n'+json.dumps({'qualification':q}).encode(),capture_output=True,timeout=180);raw=None
 assert r.returncode==0,('Read-only observation failed',r.stderr[-1000:].decode())
 value=json.loads(r.stdout);value.update(qualificationSHA256=hashlib.sha256(qdata).hexdigest(),journalSHA256=hashlib.sha256(journal).hexdigest(),originalNativeIntentCount=len(intent),originalAcknowledgedCount=len(ack),sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 os.umask(0o077)
 with a.receipt.open('x') as out:json.dump(value,out,indent=2)
 print(json.dumps({k:v for k,v in value.items() if k not in ['absent','retained']}|{'absentCount':len(value['absent']),'retainedCount':len(value['retained'])}))

if __name__=='__main__':main()
