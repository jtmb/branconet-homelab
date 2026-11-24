#!/usr/bin/env python3
"""Preserve effective source launch arguments in native Secrets; audit host dependencies."""
import base64
import datetime
import json
import pathlib
import re
import subprocess
import urllib.parse
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    register=json.loads((ROOT/'evidence/service-register.json').read_text())
    inventory=json.loads((ROOT/'evidence/live-inventory.json').read_text())
    configurations={}
    backup=json.loads((ROOT/'evidence/config-backups.json').read_text())
    for host in backup['hosts']:
        raw=subprocess.run([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),host['operator_copy']],capture_output=True,check=True).stdout
        configurations[host['host']]=json.loads(raw)
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def run(args,body=None):
        result=subprocess.run([*kube,*args],input=json.dumps(body) if body is not None else None,capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Launch integration API operation failed')
        return result.stdout
    hostmap={};entries=[]
    for entry in register['entries']:
        chart=entry.get('chart')
        if not chart or chart.startswith('@') or entry['source_type'] not in {'swarm','standalone'}:continue
        source=entry.get('source_instance') or next(iter(entry.get('source_instances',[])),None)
        if not source:continue
        host=entry['source'].split('/')[0] if entry['source_type']=='standalone' else source['host']
        directory=ROOT/'k8s-rewrite/charts'/chart
        name=yaml.safe_load((directory/'Chart.yaml').read_text())['name'];ns=entry['namespace']
        aliases={entry['source']}
        if entry['source_type']=='swarm':
            aliases.add(entry['source'].split('_',1)[-1])
            for network in next(s for s in inventory['nodes'][host]['services'] if s['name']==entry['source']).get('networks',[]):aliases.update(network.get('Aliases') or [])
        for alias in aliases:
            if '/' not in alias:hostmap[(ns,alias)]=name+'.'+ns+'.svc.cluster.local'
        entries.append((entry,source,host,directory,name,ns))
    results=[];dependencies=[];seen=set()
    for entry,source,host,directory,name,ns in entries:
        if entry['chart'] in seen:continue
        seen.add(entry['chart']);values=yaml.safe_load((directory/'values.yaml').read_text())
        if entry['source_type']=='swarm':
            spec=next(s for s in configurations[host]['services'] if s['Spec']['Name']==entry['source'])['Spec']['TaskTemplate']['ContainerSpec']
            command=spec.get('Command') or [];args=spec.get('Args') or []
        else:
            original=next(c for c in configurations[host]['containers'] if c['Name'].lstrip('/')==source['name'])
            command=original['Config'].get('Entrypoint') or [];args=original['Config'].get('Cmd') or []
        deployment=next((o for o in values['resources'] if o['kind'] in {'Deployment','StatefulSet'}),None)
        if deployment:container=deployment['spec']['template']['spec']['containers'][0]
        elif name=='gluetun':
            torrent_path=ROOT/'k8s-rewrite/charts/media-stack/qbittorrent/values.yaml';torrent=yaml.safe_load(torrent_path.read_text())
            container=next(o for o in torrent['resources'] if o['kind']=='Deployment')['spec']['template']['spec']['initContainers'][0]
        else:raise RuntimeError('Missing effective container for '+name)
        if '@sha256:' not in values['image']:
            digests=inventory['nodes'][host]['images'][source['image_id']]['repo_digests']
            if not digests:raise RuntimeError('Source image digest missing for '+name)
            values['image']=digests[0]
            if name=='gluetun':container['image']=digests[0]
        launch={}
        container['env']=[item for item in container.get('env',[]) if not item['name'].startswith(('MIGRATION_COMMAND_','MIGRATION_ARGS_'))]
        for field,items in [('command',command),('args',args)]:
            if items:
                container[field]=[]
                for index,value in enumerate(items):
                    key=field+'-'+str(index);env='MIGRATION_'+field.upper()+'_'+str(index)
                    launch[key]=value;container[field].append('$('+env+')')
                    container.setdefault('env',[]).append({'name':env,'valueFrom':{'secretKeyRef':{'name':name+'-launch','key':key}}})
        if launch:
            desired={'apiVersion':'v1','kind':'Secret','metadata':{'name':name+'-launch','namespace':ns},'type':'Opaque','stringData':launch}
            existing=subprocess.run([*kube,'get','secret',name+'-launch','-n',ns,'--ignore-not-found','-o','json'],capture_output=True,text=True,check=True).stdout
            if existing:
                actual=json.loads(existing)
                if {k:base64.b64decode(v).decode() for k,v in actual.get('data',{}).items()}!=launch:raise RuntimeError('Existing launch Secret differs; explicit review required')
            else:run(['create','-f','-'],desired)
        runtime=json.loads(run(['get','secret',values['environmentSecret'],'-n',ns,'-o','json']))
        changes=[]
        for key,encoded in runtime.get('data',{}).items():
            if not re.search(r'(^|_)(HOST|HOSTNAME|URL|ADDRESS|ADDR|ENDPOINT_IP)$',key,re.I):continue
            value=base64.b64decode(encoded).decode()
            try:
                parsed=urllib.parse.urlsplit(value if '://' in value else '//'+value)
                hostname=parsed.hostname;port=parsed.port
            except ValueError:continue  # Lists are reviewed separately; never report their raw value.
            if not hostname:continue
            replacement=hostmap.get((ns,hostname))
            if replacement:
                changed=value.replace(hostname,replacement,1)
                runtime['data'][key]=base64.b64encode(changed.encode()).decode();changes.append({'key':key,'source_hostname':hostname,'destination_hostname':replacement})
            dependencies.append({'chart':entry['chart'],'key':key,'hostname':replacement or hostname,'port':port,'rewritten':bool(replacement)})
        if changes:run(['replace','-f','-'],runtime)
        values['migration']['sourceCommandArgumentsRequireReview']=False
        values['migration']['nativeSecretsImported']=True
        values['migration']['launchSecretKeys']=sorted(launch)
        if deployment:
            container.setdefault('resources',{'requests':{'cpu':'25m','memory':'64Mi'}})
        (directory/'values.yaml').write_text(yaml.safe_dump(values,sort_keys=False))
        if name=='gluetun':torrent_path.write_text(yaml.safe_dump(torrent,sort_keys=False))
        results.append({'chart':entry['chart'],'source':entry['source'],'image':values['image'],'command_count':len(command),'argument_count':len(args),'native_launch_secret':name+'-launch' if launch else None,'environment_host_rewrites':changes,'application_accepted':False})
    report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'launches':results,'environment_dependencies':dependencies,'values_reported':False}
    (ROOT/'evidence/live-launch-integration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'charts_reviewed':len(results),'environment_dependencies':dependencies,'values_reported':False}),flush=True)

if __name__=='__main__':main()
