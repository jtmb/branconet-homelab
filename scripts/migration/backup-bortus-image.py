#!/usr/bin/env python3
"""Protect the exact deployed local image export for recovery without a worktree."""
import datetime,hashlib,json,os,pathlib,subprocess,tarfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
record=json.loads((ROOT/'evidence/bortus-image-distribution.json').read_text())
archive=pathlib.Path(record['operator_archive'])

def checksum(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

if checksum(archive)!=record['archive_sha256']:raise RuntimeError('Existing image archive differs from the deployed export')
with tarfile.open(archive) as contents:
    manifest=json.load(contents.extractfile('manifest.json'))
    item=next(m for m in manifest if record['image_tag'] in m.get('RepoTags',[]))
    config=contents.extractfile(item['Config']).read()
    if 'sha256:'+hashlib.sha256(config).hexdigest()!=record['source_image_id']:raise RuntimeError('Restored image configuration ID differs from the deployed build')
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
target=RUNTIME/'recovery'/('bortus-image-'+stamp+'.tar.age')
fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
recipient=(pathlib.Path.home()/'.ssh/id_ed25519.pub').read_text().strip()
with os.fdopen(fd,'wb') as output:
    subprocess.run([str(RUNTIME/'bin/age'),'-r',recipient,str(archive)],stdout=output,stderr=subprocess.PIPE,check=True)
process=subprocess.Popen([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
digest=hashlib.sha256()
for chunk in iter(lambda:process.stdout.read(1024*1024),b''):digest.update(chunk)
process.wait()
if process.returncode or digest.hexdigest()!=record['archive_sha256']:raise RuntimeError('Authenticated image recovery differs from deployed export')
nas='/mnt/container-backups/k8s-migration-20261009/'+target.name
subprocess.run(['scp','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-P','2002',str(target),'james@192.168.0.4:'+nas],capture_output=True,check=True)
nas_digest=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','sha256sum',nas]).decode().split()[0]
encrypted_digest=checksum(target)
if nas_digest!=encrypted_digest:raise RuntimeError('NAS image backup checksum differs')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_tag':record['image_tag'],'source_image_id':record['source_image_id'],'verified_runtime_manifest_digest':record['nodes'][0]['runtime_manifest_digest'],'operator_encrypted_copy':str(target),'nas_encrypted_copy':nas,'ciphertext_sha256':encrypted_digest,'decrypted_export_sha256':record['archive_sha256'],'image_config_digest_verified':True,'authenticated_full_decryption_equal':True,'nas_ciphertext_byte_equal':True,'separate_worktree_required_for_restore':False,'live_image_or_app_changed':False,'restore_scope':'Exact export already imported on all three nodes; authenticated recovered bytes match that export. No new image import or full disaster rebuild performed.'}
(ROOT/'evidence/bortus-image-recovery.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
