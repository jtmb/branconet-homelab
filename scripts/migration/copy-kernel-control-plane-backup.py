"""Copy only the authenticated kernel-maintenance ciphertext to the existing NAS.

Complete independent readback binds the NAS bytes to the authenticated producer;
this does not claim an independent etcd restore or write any plaintext/config.
"""
import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

BASE='/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
ROOT=Path(r'\\?\UNC\wsl.localhost\Ubuntu'+BASE.replace('/','\\'))
H=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028'
NAS=Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')

def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--qualify-existing',action='store_true',help='Read-only qualification of the exact completed ciphertext after an interrupted proof; never overwrite a partial target')
 parser.add_argument('--generation',choices=['kernel','concurrent-ingenium','kubernetes1372','kubernetes1372-current-ingenium'],default='kernel')
 args=parser.parse_args()
 assert os.name=='nt' and H.is_dir() and NAS.is_dir()
 assert shutil.disk_usage('C:\\').free>=15*1024**3
 choices=list((H/(args.generation+'-control-plane-backup')).glob('control-plane-*/receipt.json'));assert len(choices)==1
 receipt=choices[0];data=json.loads(receipt.read_text())
 assert data['status']=='completed' and data['authenticated_archive_verified'] and data['snapshot_footer_verified'] and data['snapshot_status_verified'] and not data['remote_plaintext_retained']
 source=receipt.with_name('control-plane.tar.age');before=source.stat();authority=sha(receipt)
 assert before.st_size==data['archive_bytes'] and sha(source)==data['archive_sha256']
 target=NAS/('sha256-'+data['archive_sha256']+'.age');proof=H/(args.generation+'-control-plane-nas-proof.json')
 assert not proof.exists()
 if args.qualify_existing:
  assert target.is_file(), 'The exact prior ciphertext must exist; incomplete bytes remain protected'
 else:
  assert not target.exists() and shutil.disk_usage(NAS).free>=15*1024**3+before.st_size
  with source.open('rb') as src,target.open('xb') as dst:
   while block:=src.read(1024**2):dst.write(block)
   dst.flush();os.fsync(dst.fileno())
 assert target.stat().st_size==before.st_size and sha(target)==data['archive_sha256']
 after=source.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns) and sha(source)==data['archive_sha256'] and sha(receipt)==authority
 result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceReceiptSHA256':authority,'archiveSHA256':data['archive_sha256'],'bytes':before.st_size,'NASPath':str(target),'fullIndependentReadback':True,'ciphertextMatchesAuthenticatedProducer':True,'plaintextWritten':False,'independentEtcdRestore':False,'sourceUnchanged':True}
 with proof.open('x') as out:json.dump(result,out,indent=2)
 print(json.dumps(result))

if __name__=='__main__':main()
