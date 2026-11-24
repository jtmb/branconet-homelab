"""Bind the fixed OCI export and bound its Next-only incremental node footprint."""
import hashlib,importlib.util,json,tarfile
from pathlib import Path
s=importlib.util.spec_from_file_location('fixed_archive_build',Path(__file__).with_name('build-bortus-empty-list-fix.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def main():
 p=b.OUT/'image.oci.tar';hashed=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):hashed.update(block)
 with tarfile.open(p) as t:
  def blob(d):
   raw=t.extractfile('blobs/sha256/'+d.split(':')[1]).read();b.need('sha256:'+hashlib.sha256(raw).hexdigest()==d);return raw
  index=json.load(t.extractfile('index.json'));b.need(len(index['manifests'])==1);digest=index['manifests'][0]['digest'];manifest=json.loads(blob(digest));config=json.loads(blob(manifest['config']['digest']));b.need(config['config']['Labels']['org.opencontainers.image.revision']==b.COMMIT)
  base=json.loads((b.OUT/'image.json').read_bytes());b.need(base['id']==digest and config['rootfs']['diff_ids']==base['rootfs_layers'])
  layers=manifest['layers'];b.need(len(layers)==11);allocated=0;entries=0
  for n,layer in enumerate(layers):
   f=t.extractfile('blobs/sha256/'+layer['digest'].split(':')[1]);h=hashlib.sha256();count=0
   for data in iter(lambda:f.read(1024**2),b''):count+=len(data);h.update(data)
   b.need(count==layer['size'] and 'sha256:'+h.hexdigest()==layer['digest'])
   if n<9:continue
   with tarfile.open(fileobj=t.extractfile('blobs/sha256/'+layer['digest'].split(':')[1]),mode='r|*') as delta:
    for member in delta:
     name=member.name.removeprefix('./').rstrip('/');b.need(name in ('','app','app/.next','app/.wh..next') or name.startswith('app/.next/'))
     b.need(member.isdir() or member.isfile());entries+=1;allocated+=4096+((member.size+4095)//4096)*4096
  peak=allocated+sum(x['size'] for x in layers[9:])+128*1024**2;b.need(peak<512*1024**2)
  receipt={'source':b.COMMIT,'manifest':digest,'config':manifest['config']['digest'],'archive_sha256':hashed.hexdigest(),'archive_bytes':p.stat().st_size,'layer_count':len(layers),'all_blob_hashes_verified':True,'only_next_output_changed':True,'incremental_entries':entries,'incremental_allocated_bound':allocated,'import_peak_bound':peak,'parent_runtime_required':b.BASE,'parent_layer_count':9}
  (b.OUT/'image-archive.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
if __name__=='__main__':main()
