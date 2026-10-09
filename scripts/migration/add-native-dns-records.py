#!/usr/bin/env python3
"""Append native management/repository DNS names without altering existing records."""
import datetime,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def exec_(args):return subprocess.check_output(k+['exec','-n','pihole','deployment/pihole','--']+args,text=True)
def records():return [v.strip() for v in exec_(['pihole-FTL','--config','dns.hosts']).strip().strip('[]').split(',') if v.strip()]
before=records();after=list(before)
for name in ['bortus.branconet.lan','http-echo.branconet.local','echo.branconet.local','jtmb-dev.branconet.local']:
 if not any(name in line.split()[1:] for line in after):after.append('192.168.0.4 '+name)
exec_(['pihole-FTL','--config','dns.hosts',json.dumps(after)]);exec_(['pihole','restartdns'])
actual=records()
if set(actual)!=set(after) or not set(before).issubset(actual):raise RuntimeError('DNS records differ after append')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_existing_records_preserved':True,'added_records':[v for v in after if v not in before],'native_pihole_configuration_on_retained_claim':True}
(ROOT/'evidence/native-dns-records.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
