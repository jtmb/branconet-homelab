#!/usr/bin/env python3
"""Prove a harmless Git/CI/Flux rollout and rollback without touching application data."""
import datetime,hashlib,http.client,json,pathlib,socket,ssl,subprocess,time,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
chart=ROOT/'k8s-rewrite/charts/test-stack/http-echo/values.yaml';evidence=ROOT/'evidence/pipeline-rollback-proof.json';marker='branconet.io/pipeline-acceptance'
if evidence.exists():raise RuntimeError('Inspect the recorded pipeline proof before repeating')
if subprocess.check_output(['git','-c','core.autocrlf=false','status','--porcelain'],cwd=ROOT).strip():raise RuntimeError('Clean worktree required before owned canary commits')
original=chart.read_bytes();values=yaml.safe_load(original);d=next(o for o in values['resources'] if o['kind']=='Deployment');annotations=d['spec']['template']['metadata'].setdefault('annotations',{})
if marker in annotations:raise RuntimeError('Existing canary annotation must be reviewed')
def get(kind,name=None,ns='http-echo'):
 return json.loads(subprocess.check_output(k+['get',kind]+([name] if name else [])+['-n',ns,'-o','json']))
def capture():
 deploy=get('deploy','http-echo');pods=get('pods')['items'];ready=[p for p in pods if p['metadata'].get('labels',{}).get('app')=='http-echo' and not p['metadata'].get('deletionTimestamp') and any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[]))]
 if len(ready)!=1:raise RuntimeError('One Ready HTTP echo replacement required')
 claim=get('pvc','http-echo-data-pvc')
 with ssl._create_unverified_context().wrap_socket(socket.create_connection(('192.168.0.4',443),timeout=15),server_hostname='http-echo.branconet.local') as conn:
  conn.sendall(b'GET / HTTP/1.1\r\nHost: http-echo.branconet.local\r\nConnection: close\r\n\r\n');response=http.client.HTTPResponse(conn);response.begin();body=response.read()
 if response.status!=200:raise RuntimeError('HTTP echo endpoint failed')
 return {'pod_uid':ready[0]['metadata']['uid'],'claim_uid':claim['metadata']['uid'],'volume':claim['spec']['volumeName'],'http_status':response.status,'body_sha256':hashlib.sha256(body).hexdigest(),'canary_present':marker in deploy['spec']['template']['metadata'].get('annotations',{})}
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline':capture(),'test_scope':'Pod template annotation only; image/Secrets/PVC/body unchanged','phases':[]}
def save():evidence.write_text(json.dumps(report,indent=2)+'\n')
def commit_and_reconcile(message):
 subprocess.run(['git','-c','core.autocrlf=false','add',str(chart.relative_to(ROOT))],cwd=ROOT,capture_output=True,check=True)
 subprocess.run(['git','-c','core.autocrlf=false','commit','-m',message],cwd=ROOT,capture_output=True,check=True)
 sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();subprocess.run(['git','push','origin','codex/kubernetes-migration'],cwd=ROOT,capture_output=True,check=True);print(json.dumps({'commit':sha,'waiting_for':'CI validation'}),flush=True)
 run=None
 for attempt in range(90):
  runs=json.loads(subprocess.check_output(['/usr/bin/gh','run','list','--workflow','kubernetes-migration.yml','--limit','8','--json','databaseId,headSha,status,conclusion'],cwd=ROOT))
  run=next((r for r in runs if r['headSha']==sha),None)
  if run and run['status']=='completed':break
  time.sleep(2)
 if not run or run.get('conclusion')!='success':raise RuntimeError('Canary CI did not pass; no manual deployment override allowed')
 subprocess.run([str(RUNTIME/'bin/flux'),'--kubeconfig',str(RUNTIME/'admin.conf'),'reconcile','kustomization','migration-releases','-n','flux-system','--with-source','--timeout=180s'],capture_output=True,check=True)
 kust=get('kustomization','migration-releases','flux-system')
 if not kust['status']['lastAppliedRevision'].endswith(sha):raise RuntimeError('Flux must apply the CI-tested commit')
 return {'commit':sha,'ci_run':run['databaseId'],'flux_revision':kust['status']['lastAppliedRevision'],'state':capture()}
save()
try:
 annotations[marker]='canary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S');chart.write_text(yaml.safe_dump(values,sort_keys=False))
 canary=commit_and_reconcile('Test CI and Flux rollout with a data-preserving canary');report['phases'].append({'phase':'canary',**canary});save()
 if not canary['state']['canary_present'] or canary['state']['pod_uid']==report['baseline']['pod_uid']:raise RuntimeError('Canary did not perform a real rollout')
finally:
 chart.write_bytes(original)
 rollback=commit_and_reconcile('Revert the accepted CI and Flux canary');report['phases'].append({'phase':'rollback',**rollback});save()
for phase in report['phases']:
 for key in ['claim_uid','volume','body_sha256']:
  if phase['state'][key]!=report['baseline'][key]:raise RuntimeError('Canary/rollback changed application storage or endpoint content')
if rollback['state']['canary_present'] or rollback['state']['pod_uid']==canary['state']['pod_uid']:raise RuntimeError('Rollback did not remove the canary with an actual rollout')
report.update({'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'git_ci_flux_change_and_rollback_passed':True,'same_claim_and_volume':True,'same_http_body_after_each_rollout':True,'source_data_untouched':True});save();print(json.dumps(report),flush=True)
