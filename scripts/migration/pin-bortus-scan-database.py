"""Verify the exact scan database against an immutable public OCI blob before retirement."""
import hashlib,json,pathlib,tarfile,urllib.request
O=pathlib.Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
BASE='https://mirror.gcr.io/v2/aquasec/trivy-db/'
def need(v):
 if not v:raise RuntimeError('scan_database_origin_not_equivalent_preserve_local_snapshot')
def main():
 need(not(O/'scan-database-origin.json').exists());expected=json.loads((O/'scanner-cache/db/metadata.json').read_bytes())
 with (O/'scanner-cache/db/trivy.db').open('rb')as f:db_sha=hashlib.file_digest(f,'sha256').hexdigest()
 request=urllib.request.Request(BASE+'manifests/2',headers={'Accept':'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
 with urllib.request.urlopen(request,timeout=30)as response:raw=response.read(1024*1024+1)
 need(len(raw)<1024*1024);manifest=json.loads(raw);need(manifest.get('schemaVersion')==2 and len(manifest.get('layers',[]))==1);layer=manifest['layers'][0];need(layer['mediaType'].endswith('tar+gzip'))
 class Hashed:
  def __init__(self,source):self.source=source;self.hash=hashlib.sha256();self.count=0
  def read(self,size=-1):
   block=self.source.read(size);self.hash.update(block);self.count+=len(block);need(self.count<=layer['size']);return block
 observed={}
 with urllib.request.urlopen(BASE+'blobs/'+layer['digest'],timeout=120)as response:
  hashed=Hashed(response)
  with tarfile.open(fileobj=hashed,mode='r|gz')as archive:
   for member in archive:
    name=member.name.removeprefix('./');need(member.isfile()or member.isdir())
    if member.isfile():
     source=archive.extractfile(member)
     if name=='trivy.db':
      h=hashlib.sha256()
      for block in iter(lambda:source.read(1024*1024),b''):h.update(block)
      observed['db_sha256']=h.hexdigest();observed['db_bytes']=member.size
     elif name=='metadata.json':observed['metadata']=json.loads(source.read(65536))
     else:raise RuntimeError('unexpected_database_layer_payload')
  while hashed.read(1024*1024):pass
  need(hashed.count==layer['size']and'sha256:'+hashed.hash.hexdigest()==layer['digest'])
 need(observed['db_sha256']==db_sha and observed['metadata']['Version']==expected['Version']and observed['metadata']['UpdatedAt']==expected['UpdatedAt'])
 record={'state':'verified','immutable_repository':'mirror.gcr.io/aquasec/trivy-db@sha256:'+hashlib.sha256(raw).hexdigest(),'manifest':manifest,'layer_digest':layer['digest'],'db_sha256':db_sha,'db_bytes':observed['db_bytes'],'metadata':observed['metadata'],'local_download_metadata':expected,'regenerate':'GET '+BASE+'blobs/'+layer['digest']+'; verify compressed layer digest; stream gzip tar and restore trivy.db/metadata.json; verify recorded database SHA256 before scanning'}
 with(O/'scan-database-origin.json').open('x')as f:json.dump(record,f)
 print(json.dumps({'exact_scan_database_origin_verified':True,'immutable_repository':record['immutable_repository'],'db_sha256':db_sha}))
if __name__=='__main__':main()
