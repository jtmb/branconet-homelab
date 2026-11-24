#!/usr/bin/env python3
"""Verify retained Plex identity, libraries and a real media range without logging values."""
import datetime,hashlib,json,pathlib,subprocess,socket,time,urllib.request,urllib.error,xml.etree.ElementTree as ET,base64
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
prefs='/config/Library/Application Support/Plex Media Server/Preferences.xml'
original=subprocess.check_output(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-'],input=("import pathlib,sys;sys.stdout.buffer.write(pathlib.Path('/var/plex-stack/plex/config/Library/Application Support/Plex Media Server/Preferences.xml').read_bytes())").encode())
source=ET.fromstring(original);target=ET.fromstring(subprocess.check_output(k+['exec','-n','plex','deployment/plex','--','cat',prefs]))
if source.get('MachineIdentifier')!=target.get('MachineIdentifier'):raise SystemExit('Plex machine identity differs')
token=target.get('PlexOnlineToken')
if not token:raise SystemExit('Existing claimed Plex token required')
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'plex-api-access','namespace':'plex'},'type':'Opaque','stringData':{'token':token}}
existing=subprocess.run(k+['get','secret','plex-api-access','-n','plex','--ignore-not-found','-o','json'],capture_output=True,text=True,check=True).stdout
if existing:
 if base64.b64decode(json.loads(existing)['data']['token']).decode()!=token:raise SystemExit('Existing Plex API secret differs')
else:subprocess.run(k+['create','-f','-'],input=json.dumps(secret).encode(),capture_output=True,check=True)
s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();p=subprocess.Popen(k+['port-forward','-n','plex','svc/plex',str(port)+':32400'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 def request(path,headers=None):
  global p
  for attempt in range(180):
   if p.poll() is not None:p=subprocess.Popen(k+['port-forward','-n','plex','svc/plex',str(port)+':32400'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    r=urllib.request.Request('http://127.0.0.1:'+str(port)+path,headers={'X-Plex-Token':token,**(headers or {})})
    with urllib.request.urlopen(r,timeout=30) as response:return response.status,response.read()
   except (urllib.error.URLError,TimeoutError,ConnectionError):time.sleep(1)
  raise RuntimeError('Plex endpoint did not become ready')
 libraries=ET.fromstring(request('/library/sections')[1]);sections=[];sample=None
 for directory in libraries.findall('Directory'):
  key=directory.get('key');status,body=request('/library/sections/'+key+'/all?X-Plex-Container-Start=0&X-Plex-Container-Size=1');page=ET.fromstring(body)
  sections.append({'id':key,'type':directory.get('type'),'total_size':int(page.get('totalSize',page.get('size','0')))})
  if sample is None:
   part=page.find('.//Part')
   if part is not None and part.get('key'):sample=part.get('key')
 if not sections:raise SystemExit('No retained Plex libraries returned')
 if not sample:raise SystemExit('No playable media part found for range test')
 status,media=request(sample,{'Range':'bytes=0-1048575'})
 if status!=206 or len(media)!=1048576:raise SystemExit('Real media range/read test failed')
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'retained_machine_identity_equal':True,'claimed_library_api_access':True,'sections':sections,'real_media_range_status':status,'media_bytes_read':len(media),'media_range_sha256':hashlib.sha256(media).hexdigest(),'native_api_secret':'plex/plex-api-access','values_or_media_titles_reported':False,'client_playback_and_relocation_pending':True}
 (ROOT/'evidence/plex-library-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:p.terminate();p.wait(timeout=10)
