#!/usr/bin/env python3
"""Preserve inspected legacy published ports in native Services; retain source specs."""
import concurrent.futures,datetime,hashlib,json,pathlib,socket,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';NODES=['192.168.0.4','192.168.0.5','192.168.0.6'];k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
if (ROOT/'evidence/application-port-cutover.json').exists():raise RuntimeError('Inspect the recorded cutover and rollback before repeating')
def run(args,body=None):return subprocess.check_output(k+args,input=json.dumps(body).encode() if body is not None else None)
def docker(args):
 code='import subprocess,sys;r=subprocess.run('+repr(['docker']+args)+',capture_output=True);sys.stdout.buffer.write(r.stdout);sys.exit(r.returncode)'
 result=subprocess.run(['ssh','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True)
 if result.returncode:raise RuntimeError('Source published-port operation failed')
 return result.stdout
entries=json.loads((ROOT/'evidence/service-register.json').read_text())['entries'];selected=[]
for entry in entries:
 chart=entry.get('chart')
 if entry['source_type']!='swarm' or not chart or chart.startswith('@') or entry['source']=='pi_pihole':continue
 name=chart.rsplit('/',1)[-1];ports=entry.get('source_ports',[])
 if not (ROOT/'evidence'/('private-'+name+'.json')).exists():raise RuntimeError('Private evidence required for '+name)
 if not ports:continue
 d=json.loads(run(['get','deployment',name,'-n',entry['namespace'],'-o','json']))
 if d.get('status',{}).get('readyReplicas',0)!=1:raise RuntimeError('One Ready native replacement required for '+name)
 selected.append((entry,name,d))
sources=json.loads(docker(['service','inspect',*[entry['source'] for entry,_,_ in selected]]))
raw=json.dumps(sources).encode();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');target=RUNTIME/'recovery'/('application-port-rollback-'+stamp+'.json.age');recipient=(pathlib.Path.home()/'.ssh/id_ed25519.pub').read_text().strip()
encrypted=subprocess.check_output([str(RUNTIME/'bin/age'),'-r',recipient],input=raw);target.write_bytes(encrypted);target.chmod(0o600)
if subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),str(target)])!=raw:raise RuntimeError('Rollback archive authentication failed')
nas='/mnt/container-backups/k8s-migration-20261009/'+target.name
subprocess.run(['scp','-P','2002',str(target),'james@192.168.0.4:'+nas],capture_output=True,check=True)
if subprocess.check_output(['ssh','-p','2002','james@192.168.0.4','sha256sum',nas]).decode().split()[0]!=hashlib.sha256(encrypted).hexdigest():raise RuntimeError('Rollback NAS archive differs')
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rollback_operator_copy':str(target),'rollback_nas_copy':nas,'source_data_retained':True,'services':[]};path=ROOT/'evidence/application-port-cutover.json'
for entry,name,d in selected:
 source=next(o for o in sources if o['Spec']['Name']==entry['source']);ports=source['Spec'].get('EndpointSpec',{}).get('Ports',[])
 args=['service','update','--detach','--replicas','0']
 for port in ports:args+=['--publish-rm',str(port['TargetPort'])+'/'+port['Protocol']]
 docker(args+[entry['source']])
 service={'apiVersion':'v1','kind':'Service','metadata':{'name':name+'-published','namespace':entry['namespace'],'labels':{'app.kubernetes.io/managed-by':'Helm'},'annotations':{'meta.helm.sh/release-name':name,'meta.helm.sh/release-namespace':entry['namespace']}},'spec':{'type':'ClusterIP','externalIPs':NODES,'selector':d['spec']['selector']['matchLabels'],'ports':[{'name':'p'+str(p['PublishedPort'])+'-'+p['Protocol'],'port':p['PublishedPort'],'targetPort':p['TargetPort'],'protocol':p['Protocol'].upper()} for p in entry['source_ports']]}}
 run(['apply','-f','-'],service)
 values_path=ROOT/'k8s-rewrite/charts'/entry['chart']/'values.yaml';values=yaml.safe_load(values_path.read_text());values['resources']=[o for o in values['resources'] if (o['kind'],o['metadata']['name'])!=('Service',service['metadata']['name'])]+[service];values_path.write_text(yaml.safe_dump(values,sort_keys=False))
 release_path=ROOT/'k8s-rewrite/flux/migration-releases'/(name+'.yaml');release=yaml.safe_load(release_path.read_text());release['spec']['values']['migration']['routingReviewed']=True;release_path.write_text(yaml.safe_dump(release,sort_keys=False))
 report['services'].append({'source':entry['source'],'release':name,'namespace':entry['namespace'],'source_original_replicas':source['Spec']['Mode']['Replicated']['Replicas'],'published_ports':[p['PublishedPort'] for p in entry['source_ports']],'source_ports_removed':True,'source_spec_and_data_retained':True});path.write_text(json.dumps(report,indent=2)+'\n')
def probe(pair):
 host,port=pair
 try:
  with socket.create_connection((host,port),timeout=4):return {'node':host,'port':port,'tcp_open':True}
 except OSError:return {'node':host,'port':port,'tcp_open':False}
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:report['tcp_checks']=list(pool.map(probe,[(host,p['PublishedPort']) for entry,_,_ in selected for p in entry['source_ports'] if p['Protocol']=='tcp' for host in NODES]))
report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['application_content_not_established_by_tcp_probe']=True;path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'services_transferred':len(selected),'tcp_checks':len(report['tcp_checks']),'closed_ports':[o for o in report['tcp_checks'] if not o['tcp_open']],'original_data_retained':True}))
