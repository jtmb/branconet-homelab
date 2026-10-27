"""Verify native Longhorn NAS bundle bytes, YAML and exact storage bindings."""
import pathlib,json,hashlib,io,zipfile,datetime,stat,subprocess,os
F=pathlib.Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025');O=F/'platform-upstream-review-20261027/longhorn-system-backup';C=F/'operator-control'
plan=json.loads((O/'plan.json').read_text());name=plan['manifest']['metadata']['name'];nas=pathlib.Path(r'\\TRUENAS\container_backups\k8s-migration-20261009\longhorn\backupstore\system-backups\v1.12.1')/name
cfg=nas/'system-backup.cfg';archive=nas/'system-backup.zip';assert cfg.is_file()and archive.is_file()and cfg.stat().st_size<=65536 and archive.stat().st_size<=16*1024**2
first={};members=[]
for path in [cfg,archive]:
 before=path.stat();data=path.read_bytes();after=path.stat();assert(before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)and len(data)==after.st_size;first[path.name]={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 if path==cfg:configuration=json.loads(data)
 else:raw=data
with zipfile.ZipFile(io.BytesIO(raw))as z:
 assert z.testzip()is None and len(z.infolist())<=256;names=set();total=0
 for m in z.infolist():
  assert m.filename not in names and not m.filename.startswith('/')and '..'not in pathlib.PurePosixPath(m.filename).parts;names.add(m.filename);assert pathlib.PurePosixPath(m.filename).parts[0]==name
  assert not stat.S_ISLNK(m.external_attr>>16)
  if m.is_dir():continue
  total+=m.file_size;assert total<=16*1024**2 and m.file_size<=4*1024**2;data=z.read(m);members.append({'name':m.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 assert any(m['name']==name+'/metadata.yaml'for m in members)
for row in first.values():
 with pathlib.Path(row['path']).open('rb')as f:assert hashlib.file_digest(f,'sha256').hexdigest()==row['sha256']
assert configuration['Name']==name and configuration['LonghornVersion']=='v1.12.1'and configuration['Checksum']==first['system-backup.zip']['sha256']
assert os.name=='nt';os.environ.update(TEMP=str(C/'tmp'),TMP=str(C/'tmp'))
validator=pathlib.Path(__file__).resolve().parents[2]/'k8s-rewrite/ansible-playbook/roles/longhorn_system_backup/files/verify_bundle.py'
assert validator.is_file()and str(validator).startswith('C:\\')
linux='/mnt/c/'+validator.as_posix()[3:]
args=['wsl','-d','Ubuntu','-u','root','--cd','/home/brajam','--exec','/usr/sbin/runuser','-u','brajam','--','/usr/bin/env','TMPDIR=/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/operator-control/tmp','/home/brajam/.local/share/branconet-migration/venv/bin/python3.12','-B',linux,'--name',name,'--plan','/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/longhorn-system-backup/plan.json']
run=subprocess.run(args,input=raw,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
assert run.returncode==0,run.stderr[-1000:]
qualification=json.loads(run.stdout);assert qualification['zipSHA256']==first['system-backup.zip']['sha256']
result={'independentBundleQualification':qualification,'validatorSourceSHA256':hashlib.sha256(validator.read_bytes()).hexdigest(),'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'name':name,'nativeSystemBackupUID':json.loads((O/'submission.json').read_text())['uid'],'files':list(first.values()),'fullNASReadbacks':2,'zipCRCAllMembersPassed':True,'archiveMemberCount':len(members),'uncompressedBytes':total,'members':members,'nasConfigVersion':configuration.get('LonghornVersion'),'applicationDataBackupClaimed':False,'systemRestoreExecuted':False,'localPayloadCopiesCreated':False}
target=O/'nas-contents-qualification.json';assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='members'}))