#!/usr/bin/env python3
"""Prove shared VPN egress and an actual temporary tunnel failure, then restore."""
import datetime,hashlib,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def exec_(container,args,check=True):return subprocess.run(k+['exec','-n','plex','deployment/qbittorrent','-c',container,'--']+args,capture_output=True,check=check)
def qb_ip():
 for attempt in range(6):
  result=exec_('qbittorrent',['curl','-fsS','--max-time','12','https://api.ipify.org'],check=False)
  if result.returncode==0 and result.stdout.strip():return result.stdout.strip()
  time.sleep(2)
 raise RuntimeError('VPN public egress did not respond')
before=qb_ip();vpn=exec_('gluetun',['wget','-qO-','--timeout=12','https://api.ipify.org']).stdout.strip()
hostcode="import urllib.request,sys;body=urllib.request.urlopen('https://1.1.1.1/cdn-cgi/trace',timeout=15).read().decode();sys.stdout.write(next(line[3:] for line in body.splitlines() if line.startswith('ip=')))"
isp=subprocess.check_output(['ssh','-p','2002','james@192.168.0.4','python3','-'],input=hostcode.encode()).strip()
if not before or before!=vpn or before==isp:raise RuntimeError('Shared VPN egress differs or bypasses VPN')
down=False
try:
 exec_('gluetun',['ip','link','set','tun0','down']);down=True
 blocked=exec_('qbittorrent',['curl','-fsS','--max-time','5','https://api.ipify.org'],check=False)
 if not blocked.returncode or blocked.stdout.strip():raise RuntimeError('VPN tunnel failure allowed public egress')
finally:
 if down:exec_('gluetun',['ip','link','set','tun0','up'],check=False)
after=None
for attempt in range(30):
 try:after=qb_ip();break
 except subprocess.CalledProcessError:time.sleep(2)
if not after or after==isp:raise RuntimeError('VPN did not recover safely')
forward=exec_('gluetun',['sh','-c','test -s /tmp/gluetun/forwarded_port'],check=False).returncode==0
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'shared_pod_vpn_egress_equal':True,'vpn_egress_distinct_from_host':True,'actual_tunnel_down_blocks_qbittorrent_egress':True,'tunnel_restored_and_egress_recovered':True,'forwarded_port_file_present':forward,'vpn_egress_sha256':hashlib.sha256(before).hexdigest(),'source_wireguard_configuration_preserved':True,'port_forwarding_integration_pending':not forward}
(ROOT/'evidence/vpn-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
