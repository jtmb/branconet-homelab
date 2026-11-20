"""Update only existing libc slice files and its package-version record."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
s=importlib.util.spec_from_file_location('libc_layer_input',Path(__file__).with_name('prepare-bortus-runtime-security.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args()
 root=m.OUT/'libc';receipt=json.loads((root/'receipt.json').read_bytes());m.need(receipt['repository_signature_verified'] and receipt['version']=='2.44-1ubuntu2.1');source=root/'package';target=root/'patch';m.need(not (root/'patch.json').exists())
 if args.resume:
  m.need(target.is_dir() and not target.is_symlink())
  for p in target.rglob('*'):
   if p.is_dir():continue
   src=source/p.relative_to(target);m.need((p.is_symlink() and src.is_symlink() and os.readlink(p)==os.readlink(src))or(p.is_file() and not p.is_symlink() and src.is_file() and not src.is_symlink() and m.sha(p)==m.sha(src)))
 else:m.need(not target.exists())
 files=[]
 for parent,dirs,names in os.walk(source,followlinks=False):
  for name in names+[d for d in dirs if (Path(parent)/d).is_symlink()]:files.append(str((Path(parent)/name).relative_to(source)))
 js="const fs=require('fs'),crypto=require('crypto'),out={};for(const p of JSON.parse(process.argv[1])){try{const s=fs.lstatSync('/'+p);out[p]={file:s.isFile(),link:s.isSymbolicLink(),target:s.isSymbolicLink()?fs.readlinkSync('/'+p):null,sha256:s.isFile()?crypto.createHash('sha256').update(fs.readFileSync('/'+p)).digest('hex'):null}}catch(e){if(e.code!=='ENOENT')throw e}}console.log(JSON.stringify(out));"
 existing=json.loads(subprocess.check_output(['docker','exec','bortus-review-cc319fb','node','-e',js,json.dumps(files)],timeout=30));target.mkdir(mode=0o700,exist_ok=args.resume);changed=[]
 for name,before in existing.items():
  src=source/name;dest=target/name;m.need(before['file']==(src.is_file() and not src.is_symlink()) and before['link']==src.is_symlink())
  if src.is_symlink():
   if before['target']==os.readlink(src):continue
   dest.parent.mkdir(parents=True,exist_ok=True);os.symlink(os.readlink(src),dest);changed.append({'path':name,'link':os.readlink(src)})
  else:
   digest=m.sha(src)
   if before['sha256']==digest:continue
   dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);dest.chmod(src.stat().st_mode&0o777);changed.append({'path':name,'before':before['sha256'],'after':digest})
 status=subprocess.check_output(['docker','exec','bortus-review-cc319fb','node','-e',"process.stdout.write(require('fs').readFileSync('/var/lib/dpkg/status'))"],timeout=15).decode();paragraphs=status.split('\n\n');matches=[n for n,p in enumerate(paragraphs)if p.startswith('Package: libc6\n')];m.need(len(matches)==1 and '\nVersion: 2.44-1ubuntu2\n' in paragraphs[matches[0]]);paragraphs[matches[0]]=paragraphs[matches[0]].replace('\nVersion: 2.44-1ubuntu2\n','\nVersion: 2.44-1ubuntu2.1\n');dest=target/'var/lib/dpkg/status';dest.parent.mkdir(parents=True);dest.write_text('\n\n'.join(paragraphs));dest.chmod(0o644)
 m.need(any(x['path'].endswith('/libc.so.6')for x in changed) and any('ld-linux' in x['path']for x in changed))
 result={'state':'prepared','package_version':'2.44-1ubuntu2.1','changed_existing_paths':changed,'package_record_updated':True,'new_optional_package_components_added':False,'no_maintainer_scripts_executed':True};(root/'patch.json').write_text(json.dumps(result));print(json.dumps({'libc_patch_prepared':True,'existing_files_updated':len(changed),'version':receipt['version']}))
if __name__=='__main__':main()
