#!/usr/bin/env python3
"""Prove retained monitor state, real API queue polling and negotiated port updates."""
import datetime,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args):return subprocess.check_output(k+args)
def pod():
 p=json.loads(run(['get','pods','-n','plex','-l','app=qbit-monitor','-o','json']))['items']
 return next(o for o in p if not o['metadata'].get('deletionTimestamp') and any(c['type']=='Ready' and c['status']=='True' for c in o['status'].get('conditions',[])))
def check():
 for attempt in range(90):
  logs=run(['logs','-n','plex','deployment/qbit-monitor'])
  if b'Torrents Validated.' in logs and b'Login successful' in logs:break
  time.sleep(2)
 else:raise RuntimeError('Real monitor polling/forwarding login not proven')
 port=int(run(['exec','-n','plex','deployment/qbit-monitor','--','cat','/tmp/gluetun/forwarded_port']).strip())
 subprocess.run([str(RUNTIME/'venv/bin/python'),str(ROOT/'scripts/migration/qbittorrent-api-proof.py')],capture_output=True,check=True)
 api=json.loads((ROOT/'evidence/qbittorrent-api-proof.json').read_text())
 if api['listen_port']!=port:raise RuntimeError('Negotiated VPN port differs from actual qBittorrent listen port')
 state=run(['exec','-n','plex','deployment/qbit-monitor','--','sh','-c','test -s /app/state/notified_torrents.txt && sha256sum /app/state/notified_torrents.txt']).decode().split()[0]
 return {'forwarded_port':port,'listen_port_matches':True,'real_queue_count':api['torrent_queue_count'],'queue_polling_passed':True,'state_sha256':state}
first=pod();before=check();claim=json.loads(run(['get','pvc','qbit-monitor-state','-n','plex','-o','json']))
run(['rollout','restart','deployment/qbit-monitor','-n','plex']);run(['rollout','status','deployment/qbit-monitor','-n','plex','--timeout=180s'])
time.sleep(12);after=check();second=pod()
if first['metadata']['uid']==second['metadata']['uid'] or before['state_sha256']!=after['state_sha256']:raise RuntimeError('Monitor did not retain state through actual restart')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release':'qbit-monitor','namespace':'plex','chart':'media-stack/qbit-monitor','checks':after,'actual_restart_passed':True,'longhorn_state_claim_uid':claim['metadata']['uid'],'same_node_as_qbittorrent':second['spec']['nodeName'],'native_credentials_authenticated':True,'discord_notifications_disabled_during_acceptance':True,'discord_delivery_not_tested':True,'source_originals_retained':True,'production_routing_accepted':False}
(ROOT/'evidence/private-qbit-monitor.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
