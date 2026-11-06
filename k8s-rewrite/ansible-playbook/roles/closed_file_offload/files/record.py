"""Exclusive durable public receipt writer for the finite offload role."""
import argparse,json,os,re
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/autonomous-hardening-20261028/closed-file-offload')
p=argparse.ArgumentParser();p.add_argument('--path',required=True);a=p.parse_args()
t=Path(a.path)
if t.parent not in (ROOT/'masternode',ROOT/'workernode2') or t.parent.resolve()!=t.parent or not re.fullmatch(r'[a-z0-9-]+[.]json',t.name):raise ValueError('fixed_receipt_scope')
import sys
raw=sys.stdin.buffer.read(4*1024*1024+1)
if len(raw)>4*1024*1024:raise ValueError('receipt_bound')
json.loads(raw)
fd=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
fd=os.open(t.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:os.fsync(fd)
finally:os.close(fd)
