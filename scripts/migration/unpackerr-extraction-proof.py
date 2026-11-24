#!/usr/bin/env python3
"""Extract an owned ZIP with the exact deployed image on the existing SMB CSI claim."""
import datetime,hashlib,json,pathlib,subprocess,time,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args,body=None):return subprocess.check_output(k+args,input=body)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S');folder='.migration-unpackerr-proof-'+stamp;name='unpackerr-proof-'+stamp
payload=b'Kubernetes migration extraction acceptance\n'*256;expected=hashlib.sha256(payload).hexdigest()
code='import pathlib,zipfile;p=pathlib.Path('+repr('/downloads/'+folder)+');(p/"input"/"fixture").mkdir(parents=True,exist_ok=False);(p/"output").mkdir();z=zipfile.ZipFile(p/"input"/"fixture"/"fixture.zip","w",compression=zipfile.ZIP_DEFLATED);z.writestr("acceptance.payload",'+repr(payload)+');z.close();print("owned fixture created")'
run(['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],code.encode())
values=yaml.safe_load((ROOT/'k8s-rewrite/charts/media-stack/unpackerr/values.yaml').read_text())
env={'UN_FOLDER_0_PATH':'/acceptance/input','UN_FOLDER_0_INTERVAL':'2s','UN_FOLDER_0_EXTRACT_PATH':'/acceptance/output','UN_FOLDER_0_DELETE_AFTER':'0s','UN_FOLDER_0_DELETE_ORIGINAL':'false','UN_FOLDER_0_DELETE_FILES':'false','UN_FOLDER_0_MOVE_BACK':'false','UN_START_DELAY':'1s','UN_RETRY_DELAY':'1s','UN_FOLDERS_INTERVAL':'2s','UN_DEBUG':'true'}
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'plex'},'spec':{'nodeName':'masternode','automountServiceAccountToken':False,'restartPolicy':'Never','securityContext':{'runAsUser':1000,'runAsGroup':1000,'fsGroup':1000},'containers':[{'name':'extractor','image':values['image'],'env':[{'name':key,'value':value} for key,value in env.items()],'volumeMounts':[{'name':'fixture','mountPath':'/acceptance','subPath':folder},{'name':'config','mountPath':'/config'}],'resources':{'requests':{'cpu':'25m','memory':'64Mi'},'limits':{'memory':'128Mi'}}}],'volumes':[{'name':'fixture','persistentVolumeClaim':{'claimName':'unpackerr-data-0'}},{'name':'config','emptyDir':{}}]}}
run(['create','-f','-'],json.dumps(pod).encode());run(['wait','pod/'+name,'-n','plex','--for=condition=Ready','--timeout=90s'])
trigger=code.replace('"fixture"','"fixture-live"').replace('(p/"output").mkdir();','')
run(['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],trigger.encode())
probe='import hashlib,json,pathlib;root=pathlib.Path('+repr('/downloads/'+folder)+');files=list((root/"output").rglob("acceptance.payload"));print(json.dumps({"files":len(files),"sha256":hashlib.sha256(files[0].read_bytes()).hexdigest() if files else None,"source_archive_retained":(root/"input"/"fixture"/"fixture.zip").exists()}))'
result=None
for attempt in range(90):
 result=json.loads(run(['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],probe.encode()))
 if result['sha256']==expected:break
 time.sleep(2)
else:
 logs=run(['logs',name,'-n','plex']);diagnostic=RUNTIME/'unpackerr-extraction.diagnostic';diagnostic.write_bytes(logs);diagnostic.chmod(0o600);raise RuntimeError('Owned archive extraction not proven; isolated Pod/fixture retained')
if not result['source_archive_retained']:raise RuntimeError('Acceptance archive must remain retained')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deployed_image':values['image'],'existing_smb_csi_claim':'unpackerr-data-0','owned_fixture_subdirectory':folder,'actual_archive_extracted':True,'extracted_sha256_equal':True,'source_archive_retained':True,'production_configuration_unchanged':True,'real_arr_api_checks':'evidence/private-unpackerr.json','test_scope':'isolated folder mode, not a completed real download/import'}
(ROOT/'evidence/unpackerr-extraction-proof.json').write_text(json.dumps(report,indent=2)+'\n');run(['delete','pod',name,'-n','plex','--wait=true','--timeout=60s']);print(json.dumps(report))
