"""Copy an already authenticated BORTUS ciphertext to the existing NAS share."""
import argparse,hashlib,json,os,pathlib,re,shutil,sys
NAS=pathlib.Path('\\\\TRUENAS\\plex_smb_share\\Branconet-Recovery-Backups\\BORTUS')
PREFIX='\\\\wsl.localhost\\Ubuntu\\mnt\\h\\AgentArtifacts\\projects\\branconet\\builds\\wsl-artifact-store\\files\\bortus-operator-recovery\\recovery\\bortus-checkpoints'
AGE_HEADER=b'age-encryption.org/v1\n'
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--source',required=True);a.add_argument('--sha256',required=True);a.add_argument('--run-id',required=True);a.add_argument('--bytes',type=int,required=True);x=a.parse_args()
 assert os.name=='nt' and re.fullmatch('[0-9a-f]{12}',x.run_id) and re.fullmatch('[0-9a-f]{64}',x.sha256)
 assert str(pathlib.Path(x.source)).lower()==(PREFIX+'\\'+x.run_id+'\\sqlite-files.age').lower()
 size=x.bytes;assert 0<size<=513*1024**2 and shutil.disk_usage('C:/').free>15*1024**3 and shutil.disk_usage(NAS.parent).free>15*1024**3+size
 NAS.mkdir(exist_ok=True);assert not NAS.is_symlink();owner=NAS/'owner.json';identity={'purpose':'BORTUS encrypted cold checkpoints; original data preserved','project':'branconet-bortus'}
 if owner.exists():assert json.loads(owner.read_text())==identity
 else:
  with owner.open('x') as f:json.dump(identity,f)
 target=NAS/('bortus-sqlite-'+x.run_id+'.age');partial=target.with_suffix('.age.partial');assert target.parent==NAS
 existing=target.exists()
 if existing:assert target.stat().st_size==size and digest(target)==x.sha256
 retained_partial=not existing and partial.exists()
 if retained_partial:assert partial.stat().st_size==size and digest(partial)==x.sha256
 writer=None;h=hashlib.sha256();count=0;header=b''
 try:
  if not existing and not retained_partial:writer=partial.open('xb')
  while True:
   block=sys.stdin.buffer.read(min(1024*1024,size-count+1))
   if not block:break
   if len(header)<len(AGE_HEADER):header=(header+block)[:len(AGE_HEADER)]
   count+=len(block);assert count<=size;h.update(block)
   if writer:writer.write(block)
  assert count==size and h.hexdigest()==x.sha256 and header==AGE_HEADER
  if writer:writer.flush();os.fsync(writer.fileno())
 finally:
  if writer:writer.close()
 if not existing:assert digest(partial)==x.sha256;partial.rename(target)
 assert target.stat().st_size==size and digest(target)==x.sha256
 print(json.dumps({'nas_artifact':str(target),'nas_ciphertext_equal':True,'bytes':size,'plaintext_persisted':False}))
if __name__=='__main__':
 try:main()
 except Exception as error:
  tb=error.__traceback__
  while tb.tb_next:tb=tb.tb_next
  print('Encrypted BORTUS NAS copy failed; '+type(error).__name__+' at helper line '+str(tb.tb_lineno)+'; originals/partial retained.',file=sys.stderr);raise SystemExit(1)
