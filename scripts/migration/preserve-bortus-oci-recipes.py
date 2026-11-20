"""Prove byte-exact OCI export regeneration from small framing and private registry blobs."""
import argparse,base64,hashlib,importlib.util,json,os,tarfile,urllib.parse,urllib.request
from pathlib import Path
S=Path(__file__).parent;STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files');O=STORE/'bortus-operator-recovery/empty-list-fix'
def need(v):
 if not v:raise RuntimeError('lossless_oci_recipe_verification_failed')
class RegistryRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,*args,**kwargs):
  redirected=super().redirect_request(request,*args,**kwargs)
  if redirected is not None and urllib.parse.urlsplit(request.full_url).netloc!=urllib.parse.urlsplit(redirected.full_url).netloc:redirected.remove_header('Authorization')
  return redirected
def publisher():
 s=importlib.util.spec_from_file_location('recipe_registry',S/'publish-qualified-bortus-image.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p);return p
def stream(recipe,token,output=None):
 total=0;overall=hashlib.sha256()
 def emit(block):
  nonlocal total
  total+=len(block);need(total<=recipe['archive_bytes']);overall.update(block)
  if output:output.write(block)
 for segment in recipe['segments']:
  if 'literal'in segment:emit(base64.b64decode(segment['literal'],validate=True));continue
  digest=segment['blob'];need(digest.startswith('sha256:')and len(digest)==71);h=hashlib.sha256();count=0
  request=urllib.request.Request('https://registry-1.docker.io/v2/jtmb92/bortus/blobs/'+digest,headers={'Authorization':'Bearer '+token})
  with urllib.request.build_opener(RegistryRedirect()).open(request,timeout=120)as response:
   while block:=response.read(1024*1024):count+=len(block);need(count<=segment['bytes']);h.update(block);emit(block)
  need(count==segment['bytes']and'sha256:'+h.hexdigest()==digest)
 need(total==recipe['archive_bytes']and overall.hexdigest()==recipe['archive_sha256']);return total
def prepare(path,expected,allowed):
 before=path.stat();need(path.resolve()==path and path.is_file())
 with path.open('rb')as f:need(hashlib.file_digest(f,'sha256').hexdigest()==expected)
 recipe={'schema':1,'archive_path':str(path),'archive_bytes':before.st_size,'archive_sha256':expected,'registry':'docker.io/jtmb92/bortus','segments':[],'device':before.st_dev,'inode':before.st_ino}
 with tarfile.open(path)as archive,path.open('rb')as source:
  pos=0
  for member in archive:
   need(member.offset_data>=pos and member.offset_data-pos<1024*1024);source.seek(pos);gap=source.read(member.offset_data-pos)
   if gap:recipe['segments'].append({'literal':base64.b64encode(gap).decode()})
   if member.size>65536:
    need(member.isfile()and member.name.startswith('blobs/sha256/'));digest='sha256:'+member.name.rsplit('/',1)[1];need(digest in allowed);recipe['segments'].append({'blob':digest,'bytes':member.size})
   elif member.size:recipe['segments'].append({'literal':base64.b64encode(source.read(member.size)).decode()})
   pos=member.offset_data+member.size
  source.seek(pos);tail=source.read();need(len(tail)<1024*1024);recipe['segments'].append({'literal':base64.b64encode(tail).decode()})
 after=path.stat();need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns));return recipe
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--restore',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args();p=publisher();helper=S/'windows-docker-credential-bortus.py';p.verify_private_repository(helper);token=p.registry_token(helper)
 if args.restore:
  need(args.output is not None and STORE in args.output.resolve().parents and not args.output.exists());recipe=json.loads(args.restore.read_bytes())
  with args.output.open('xb')as target:stream(recipe,token,target)
  print(json.dumps({'restored':str(args.output),'sha256':recipe['archive_sha256']}));return
 publication=json.loads((O/'publication.json').read_bytes());allowed={x['digest']for x in publication['layers']}
 inputs=[('original',STORE/'release-v2-12dce115-inputs/candidate-pod-summary-root.oci.tar','cf0d950a263b4ae63911f51560980fdce2211f7836852495bc2f189523e934dc'),('transport',O/'image.oci.tar','0403b0d7bb7726993180f2cb241322e44358fe51ba04baeeff535a1f59332a1a'),('final',O/'secured-image.oci.tar','21344ae4891f47adfbf071ed45b4288bc0738d10f8569c4de617d7dfe2f1d983')]
 for name,path,expected in inputs:
  target=O/('lossless-'+name+'-oci-recipe.json');need(not target.exists());recipe=prepare(path,expected,allowed);stream(recipe,token);recipe['private_registry_regeneration_verified']=True
  with target.open('x')as f:json.dump(recipe,f,separators=(',',':'))
  target.chmod(0o600);print(json.dumps({'archive':str(path),'byte_exact_regeneration_verified':True,'recipe':str(target),'recipe_bytes':target.stat().st_size}),flush=True)
if __name__=='__main__':main()
