"""Verify every exported blob and bound the exact reviewed runtime delta."""
import hashlib,importlib.util,json,tarfile
from pathlib import Path
s=importlib.util.spec_from_file_location('secured_archive_base',Path(__file__).with_name('build-bortus-empty-list-fix.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)

def main():
 p=b.OUT/'secured-image.oci.tar';build=json.loads((b.OUT/'secured-net-build.json').read_bytes())
 with p.open('rb') as f: archive_sha=hashlib.file_digest(f,'sha256').hexdigest()
 expected={x['path']:x['after'] for x in json.loads((b.OUT/'security-tools/libc/patch.json').read_bytes())['changed_existing_paths'] if 'after'in x}
 expected.update({'usr/local/bin/kubectl':'744a0c245731fc11fb7e4f78062603c7198da7bec11da93201378084e2e5e8c7','opt/bortus-scanner/trivy':'a25985fd9bb36728754332b5fadd8d632a9038f292760a02d7a338838e623454','app/scripts/scanner-inputs.json':'942921ce0018614ebef28ea1a8d8ecbd50fb12565f0e5ce0a67fbd4485628714'})
 expected['usr/local/bin/kubectl']=build['kubectl_sha256']
 status=(b.OUT/'security-tools/libc/patch/var/lib/dpkg/status').read_bytes();b.need(b'Package: libc6\n'in status and b'Version: 2.44-1ubuntu2.1\n'in status)
 expected['var/lib/dpkg/status']=hashlib.sha256(status).hexdigest()
 parents={str(y) for x in expected for y in Path(x).parents};parents.add('.')
 seen={};allocated=entries=0
 with tarfile.open(p) as t:
  def blob(d):
   raw=t.extractfile('blobs/sha256/'+d.split(':')[1]).read();b.need('sha256:'+hashlib.sha256(raw).hexdigest()==d);return raw
  index=json.load(t.extractfile('index.json'));b.need(len(index['manifests'])==1);digest=index['manifests'][0]['digest'];manifest=json.loads(blob(digest));config=json.loads(blob(manifest['config']['digest']))
  b.need(digest==build['image'] and config['config']['Labels']['org.opencontainers.image.revision']==build['source'])
  import subprocess
  image=json.loads(subprocess.check_output(['docker','image','inspect',build['tag']]))[0];base=json.loads(subprocess.check_output(['docker','image','inspect',b.BASE]))[0]
  b.need(config['rootfs']['diff_ids']==image['RootFS']['Layers'] and image['RootFS']['Layers'][:9]==base['RootFS']['Layers'] and len(base['RootFS']['Layers'])==9)
  layers=manifest['layers'];b.need(len(layers)==len(image['RootFS']['Layers']))
  for n,layer in enumerate(layers):
   f=t.extractfile('blobs/sha256/'+layer['digest'].split(':')[1]);h=hashlib.sha256();count=0
   for data in iter(lambda:f.read(1024**2),b''):count+=len(data);h.update(data)
   b.need(count==layer['size'] and 'sha256:'+h.hexdigest()==layer['digest'])
   if n<9:continue
   with tarfile.open(fileobj=t.extractfile('blobs/sha256/'+layer['digest'].split(':')[1]),mode='r|*') as delta:
    for member in delta:
     name=member.name.removeprefix('./').rstrip('/');b.need(not name.startswith('/') and '..'not in Path(name).parts)
     allowed=name in ('','app','app/.next','app/.wh..next') or name.startswith('app/.next/') or name in expected or (member.isdir() and name in parents)
     if not(allowed and (member.isdir() or member.isfile())):raise RuntimeError('unreviewed_runtime_layer_entry:'+str(n)+':'+name+':'+repr(member.type))
     if name in expected and member.isfile():seen[name]=hashlib.sha256(delta.extractfile(member).read()).hexdigest()
     entries+=1;allocated+=4096+((member.size+4095)//4096)*4096
  b.need(seen==expected)
  peak=allocated+sum(x['size'] for x in layers[9:])+128*1024**2;b.need(peak<2*1024**3)
  receipt={'source':build['source'],'manifest':digest,'config':manifest['config']['digest'],'archive_sha256':archive_sha,'archive_bytes':p.stat().st_size,'layer_count':len(layers),'all_blob_hashes_verified':True,'allowed_runtime_paths_only':True,'security_payload_hashes_verified':seen,'incremental_entries':entries,'incremental_allocated_bound':allocated,'import_peak_bound':peak,'parent_runtime_required':b.BASE,'parent_layer_count':9}
  (b.OUT/'secured-image-archive.json').write_text(json.dumps(receipt));print(json.dumps({k:v for k,v in receipt.items() if k!='security_payload_hashes_verified'}))
if __name__=='__main__':main()
