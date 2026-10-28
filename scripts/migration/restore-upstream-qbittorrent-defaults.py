#!/usr/bin/env python3
"""Restore only the source-proven libtorrent-dependent disk-queue default."""
import argparse,datetime,hashlib,json,os,shlex,stat,subprocess,uuid
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'upstream-qbittorrent-20261026'
PROGRAM=r'''
import types,base64,hashlib,hmac,json,urllib.request,urllib.parse,socket
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
need(socket.gethostname().split('.')[0].lower()=='masternode','actual_master')
request=json.loads(sys.stdin.buffer.read(4*1024**2));key=bytes.fromhex(request['key']);need(len(key)==32,'private_key');mac=lambda v:hmac.new(key,canonical(v),hashlib.sha256).hexdigest()
args=types.SimpleNamespace(expected_image='ghcr.io/linuxserver/qbittorrent:5.3.0_v2.1.2-ls485@sha256:75ecbb1c89ab7b0a21c4bde40b4820e4f1649d2d56d83b91913422155e8d2a5f',expected_runtime='sha256:236a7a3a81a3706182ae1f12ee55aa3781c753963e680b2d9c8e55541686d0ce')
before,runtime,pod,base=identity(args,mac);baseline=request['baseline'];need(baseline['passed']and baseline['key_binding']==mac('qbittorrent-observer-v1'),'exact_original_baseline');need(baseline['observation']['preferences']['disk_queue_size']==mac(1048576),'original_one_MiB_preference_fingerprint')
s=obj('secret','qbittorrent-runtime');user=base64.b64decode(s['data']['QBITTORRENT_USERNAME']).decode();password=base64.b64decode(s['data']['QBITTORRENT_PASSWORD']).decode();api=API(base,user,password);del s,user,password;prefs=api.get('app/preferences');need(prefs['disk_queue_size']in [1048576,104857600],'exact_source_default_transition');changed=prefs['disk_queue_size']!=1048576
if changed:
    payload=urllib.parse.urlencode({'json':json.dumps({'disk_queue_size':1048576},separators=(',',':'))}).encode()
    with api.client.open(urllib.request.Request(base+'/api/v2/app/setPreferences',data=payload,headers={'Referer':base},method='POST'),timeout=10)as response:need(response.status in [200,204]and len(response.read(65537))<=65536,'native_preference_write')
after=api.get('app/preferences');expected=dict(prefs);expected['disk_queue_size']=1048576;need(after==expected,'only_original_disk_queue_restored');need(identity(args,mac)[:2]==(before,runtime),'native_wiring_and_writer_unchanged')
print(json.dumps({'passed':True,'changed':changed,'onlyPreference':'disk_queue_size','previousBytes':prefs['disk_queue_size'],'restoredBytes':1048576,'originalBaselineFingerprintVerified':True,'credentialsOrOtherPreferencesChanged':False,'writerUID':runtime['pod_uid'],'nativeSecretsOrImagesChanged':False}))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args();assert a.apply and os.getuid()==1000;os.umask(0o077)
 for path in [OUT/'baseline.json',OUT/'observation.key']:
  info=path.lstat();assert path.resolve()==path and stat.S_ISREG(info.st_mode)and info.st_uid==1000 and not info.st_mode&0o077
 baseline=json.loads((OUT/'baseline.json').read_text());source=Path(__file__).with_name('qualify-upstream-qbittorrent.py');code=source.read_text();request={'key':(OUT/'observation.key').read_text(),'baseline':baseline};program="__name__='qbittorrent_guarded_repair'\n"+code+'\n'+PROGRAM
 ssh=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4'];r=subprocess.run(ssh+[shlex.join(['python3','-B','-c',program])],input=json.dumps(request).encode(),capture_output=True,timeout=120);assert len(r.stdout)<=65536
 try:result=json.loads(r.stdout)
 except Exception:result={'passed':False,'reason':'raw_details_suppressed','exitCode':r.returncode}
 result.update(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),observerSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),baselineSHA256=hashlib.sha256((OUT/'baseline.json').read_bytes()).hexdigest());target=OUT/('disk-queue-repair-'+uuid.uuid4().hex+'.json');target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'receipt':str(target),'changed':result.get('changed'),'restoredBytes':result.get('restoredBytes')}));return 0 if r.returncode==0 and result['passed']else 1
if __name__=='__main__':raise SystemExit(main())
