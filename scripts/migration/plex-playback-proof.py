#!/usr/bin/env python3
"""Decode real Plex media through the standard service with a local token-hiding proxy."""
import base64,datetime,http.server,json,pathlib,subprocess,threading,urllib.request,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
secret=json.loads(subprocess.check_output(k+['get','secret','plex-api-access','-n','plex','-o','json']));token=base64.b64decode(secret['data']['token']).decode();base='http://192.168.0.4:32400'
def open_(path,headers=None):return urllib.request.urlopen(urllib.request.Request(base+path,headers={'X-Plex-Token':token,**(headers or {})}),timeout=30)
with open_('/library/sections') as response:sections=ET.fromstring(response.read())
sample=None
for section in sections.findall('Directory'):
 with open_('/library/sections/'+section.get('key')+'/all?X-Plex-Container-Start=0&X-Plex-Container-Size=1') as response:page=ET.fromstring(response.read())
 part=page.find('.//Part')
 if part is not None and part.get('key'):sample=part.get('key');break
if not sample:raise RuntimeError('No real media part for playback')
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_HEAD(self):self.serve(False)
 def do_GET(self):self.serve(True)
 def serve(self,body):
  try:
   with open_(sample,{'Range':self.headers['Range']} if self.headers.get('Range') else None) as response:
    self.send_response(response.status)
    for key in ['Content-Type','Content-Length','Content-Range','Accept-Ranges']:
     if response.headers.get(key):self.send_header(key,response.headers[key])
    self.end_headers()
    if body:
     while True:
      chunk=response.read(1024*1024)
      if not chunk:break
      self.wfile.write(chunk)
  except (BrokenPipeError,ConnectionResetError):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
binaries=list(pathlib.Path('/mnt/c/Users/james/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg_*/**/ffmpeg.exe'))
if len(binaries)!=1:raise RuntimeError('Expected installed FFmpeg client')
try:
 result=subprocess.run([str(binaries[0]),'-hide_banner','-loglevel','error','-nostdin','-i','http://127.0.0.1:'+str(server.server_address[1])+'/media','-t','10','-map','0:v:0','-an','-progress','pipe:1','-f','null','-'],capture_output=True,timeout=150)
 if result.returncode:
  diagnostic=RUNTIME/'plex-playback.diagnostic';diagnostic.write_bytes(result.stderr);diagnostic.chmod(0o600);raise RuntimeError('FFmpeg network playback failed; protected diagnostic saved')
 progress={line.split('=',1)[0]:line.split('=',1)[1].strip() for line in result.stdout.decode().splitlines() if '=' in line};frames=int(progress.get('frame','0'))
 if frames<1 or progress.get('progress')!='end':raise RuntimeError('No completed video decode')
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'client':'Installed FFmpeg','standard_service_address':'192.168.0.4:32400','real_plex_media_video_decoded':True,'decoded_frames':frames,'requested_playback_seconds':10,'secret_only_in_proxy_memory':True,'titles_and_secret_values_reported':False}
 (ROOT/'evidence/plex-playback-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:server.shutdown();server.server_close()
