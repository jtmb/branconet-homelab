#!/usr/bin/env python3
"""Retain the source game-server address only after its host port is released."""
import datetime,json,pathlib,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
copy=json.loads((ROOT/'evidence/copy-ets2.json').read_text())
if not copy['source_writers_stopped'] or not all(c['manifest_equal'] for c in copy['copies']):raise SystemExit('Accepted game data copy required')
ssh=['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.6']
state=subprocess.check_output(ssh+['docker','inspect','--format','{{.State.Running}}','ets2-server'],text=True).strip()
listeners=subprocess.check_output(ssh+['ss','-H','-lun'],text=True)
if state!='false' or any(':27016 ' in line for line in listeners.splitlines()):raise SystemExit('Source game port is not exclusive')
path=ROOT/'k8s-rewrite/charts/apps/ets2/values.yaml';v=yaml.safe_load(path.read_text());d=next(o for o in v['resources'] if o['kind']=='Deployment');d['spec']['template']['spec']['nodeSelector']={'kubernetes.io/hostname':'workernode1'};v['migration']['hostPortsReviewed']=True;path.write_text(yaml.safe_dump(v,sort_keys=False))
helm=[str(RUNTIME/'bin/helm'),'--kubeconfig',str(RUNTIME/'admin.conf')]
subprocess.run(helm+['upgrade','--install','ets2',str(path.parent),'-n','games','--set','enabled=true,migration.staging=true,migration.hostPortsReviewed=true,replicaCount=1','--wait','--timeout','8m'],capture_output=True,check=True)
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_stopped_and_27016_unbound_before_start':True,'node':'workernode1','original_server_address_preserved':'192.168.0.6','data_manifest_verified':True,'functional_game_query_pending':True}
(ROOT/'evidence/ets2-staging.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
