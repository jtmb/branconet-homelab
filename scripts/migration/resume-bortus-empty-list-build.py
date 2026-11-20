"""Reuse the exact failed build context/cache with missing locked build dependencies."""
import argparse,hashlib,importlib.util,io,json,os,subprocess,tarfile
from pathlib import Path
s=importlib.util.spec_from_file_location('empty_build_recipe',Path(__file__).with_name('build-bortus-empty-list-fix.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--reason',choices=['missing-tailwind','missing-npm','changed-lock'],default='missing-tailwind');args=parser.parse_args();reason=args.reason
 m.need(os.geteuid()==0);out=m.OUT;original=json.loads((out/'manifest.json').read_bytes());m.need(original['source']==m.COMMIT and original['context_sha256']==hashlib.sha256((out/'context.tar').read_bytes()).hexdigest())
 marker={'missing-tailwind':"Cannot find module 'tailwindcss'",'missing-npm':'npm: command not found','changed-lock':'added 309 packages'}[reason]
 m.need(json.loads((out/'result.json').read_bytes())['exit_code']!=0 and '# pass 1' in (out/'build.log').read_text() and marker in (out/'build.log').read_text())
 m.need(not (out/('build-'+reason+'.log')).exists())
 for old,new in [('build.log','build-'+reason+'.log'),('result.json','result-'+reason+'.json'),('manifest.json','manifest-'+reason+'.json')]:os.rename(out/old,out/new)
 with tarfile.open(out/'context.tar','r') as source,tarfile.open(out/'context.next.tar','w') as target:
  for member in source:
   data=source.extractfile(member).read()
   if member.name=='Dockerfile':
    (out/('recipe-'+reason+'.Dockerfile')).write_bytes(data);data=m.DOCKERFILE.encode();member.size=len(data)
   target.addfile(member,io.BytesIO(data))
 os.replace(out/'context.next.tar',out/'context.tar')
 (out/'manifest.json').write_text(json.dumps({'source':m.COMMIT,'source_inventory':'manifest-first.json' if (out/'manifest-first.json').exists() else 'manifest-missing-tailwind.json','parent_manifest':'manifest-'+reason+'.json','context_sha256':hashlib.sha256((out/'context.tar').read_bytes()).hexdigest(),'recipe_sha256':hashlib.sha256(m.DOCKERFILE.encode()).hexdigest(),'reuses_compatible_cached_stages':True,'runtime_dependencies_unchanged':True}))
 with (out/'context.tar').open('rb') as context,(out/'build.log').open('wb') as log:
  result=subprocess.run(['docker','build','--pull=false','--tag',m.TAG,'-'],stdin=context,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,DOCKER_BUILDKIT='0'),timeout=1200)
 (out/'result.json').write_text(json.dumps({'exit_code':result.returncode,'source':m.COMMIT,'tag':m.TAG,'production_deployed':False}));m.need(result.returncode==0)
 image=json.loads(subprocess.check_output(['docker','image','inspect',m.TAG]))[0];(out/'image.json').write_text(json.dumps({'id':image['Id'],'size':image['Size'],'rootfs_layers':image['RootFS']['Layers']}));print(json.dumps({'built':True,'source':m.COMMIT,'image':image['Id']}))
if __name__=='__main__':main()
