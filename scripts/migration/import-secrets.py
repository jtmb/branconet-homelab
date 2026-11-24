#!/usr/bin/env python3
"""Import Vault and encrypted Docker runtime env directly into native Secrets.

Credentials and secret values remain in memory and pipe input. Existing unequal
Secrets cause a conflict rather than an overwrite. Values are never reported.
"""
import argparse
import base64
import datetime
import hashlib
import json
import pathlib
import re
import subprocess
import secrets
import sys
import time
import urllib.error
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--kubeconfig',required=True)
    args=parser.parse_args()
    request=json.load(sys.stdin)
    kubectl=str(RUNTIME/'bin/kubectl')
    def kube(arguments,body=None):
        result=subprocess.run([kubectl,'--kubeconfig',args.kubeconfig,*arguments],input=json.dumps(body) if body is not None else None,capture_output=True,text=True)
        return result
    def vault(path,method='GET',body=None):
        operation=urllib.request.Request('http://192.168.0.4:8200/v1/'+path,method=method,headers={'X-Vault-Token':request['root_token'],'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(operation,timeout=15) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            if path=='sys/health':return json.load(error)
            raise RuntimeError('Vault request failed: HTTP '+str(error.code)) from None
    health=vault('sys/health')
    if health.get('sealed'):vault('sys/unseal','PUT',{'key':request['unseal_key']})
    for _ in range(15):
        health=vault('sys/health')
        if not health.get('sealed') and not health.get('standby'):break
        time.sleep(1)
    else:raise SystemExit('Vault is not active')
    pending=[]
    def secret(namespace,name,values,annotations=None):
        encoded={key:base64.b64encode(value.encode()).decode() for key,value in values.items()}
        pending.append({'apiVersion':'v1','kind':'Secret','metadata':{'namespace':namespace,'name':name,'labels':{'branconet.io/migration':'native-secrets'},'annotations':annotations or {}},'type':'Opaque','data':encoded})
    records=json.loads((ROOT/'evidence/vault-restored-metadata.json').read_text())['records']
    for record in records:
        path=record['path'];fields=vault('kv/data/'+path)['data']['data']
        name='vault-'+re.sub('[^a-z0-9-]','-',path.lower()).strip('-')[:180]+'-'+hashlib.sha256(path.encode()).hexdigest()[:8]
        values={key:value if isinstance(value,str) else json.dumps(value,separators=(',',':')) for key,value in fields.items()}
        secret('bortus-secrets',name,values,{'branconet.io/vault-path':path,'branconet.io/vault-value-types':json.dumps({key:type(value).__name__ for key,value in fields.items()})})
    config_report=json.loads((ROOT/'evidence/config-backups.json').read_text())
    configurations=[]
    for host in config_report['hosts']:
        result=subprocess.run([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),host['operator_copy']],capture_output=True)
        if result.returncode:raise SystemExit('Encrypted runtime configuration recovery failed')
        configurations.append(json.loads(result.stdout))
    # Recover only the existing media-share credential reference from fstab.
    # Never substitute credentials from a different NAS share.
    media_credentials=None
    for configuration in configurations:
        files=configuration['files']
        fstab=base64.b64decode(files.get('/etc/fstab','')).decode(errors='replace')
        for line in fstab.splitlines():
            if line.lstrip().startswith('#') or '//192.168.0.8/plex_smb_share' not in line:continue
            reference=re.search(r'credentials=([^,\s]+)',line)
            if reference:
                if reference[1] not in files:continue
                raw=base64.b64decode(files[reference[1]]).decode()
                fields=dict(line.strip().split('=',1) for line in raw.splitlines() if '=' in line and not line.lstrip().startswith('#'))
            else:
                columns=line.split()
                if len(columns)<4:continue
                fields=dict(option.split('=',1) for option in columns[3].split(',') if '=' in option)
                fields={key:re.sub(r'\\([0-7]{3})',lambda match:chr(int(match[1],8)),value) for key,value in fields.items()}
            credentials={'username':fields.get('username',fields.get('user','')),'password':fields.get('password',fields.get('pass',''))}
            if fields.get('domain'):credentials['domain']=fields['domain']
            if credentials['username'] and credentials['password']:
                if media_credentials and media_credentials!=credentials:raise SystemExit('Conflicting media-share credentials require resolution')
                media_credentials=credentials
    smb_targets=set()
    import yaml
    for values_path in (ROOT/'k8s-rewrite/charts').rglob('values.yaml'):
        chart_values=yaml.safe_load(values_path.read_text())
        for obj in chart_values.get('resources',[]):
            csi=obj.get('spec',{}).get('csi',{})
            if csi.get('driver')=='smb.csi.k8s.io':
                reference=csi['nodeStageSecretRef'];smb_targets.add((reference['namespace'],reference['name']))
    if smb_targets and not media_credentials:raise SystemExit('Original media SMB credentials were not recovered')
    for namespace,name in sorted(smb_targets):secret(namespace,name,media_credentials,{'branconet.io/source-share':'//192.168.0.8/plex_smb_share'})
    register=json.loads((ROOT/'evidence/service-register.json').read_text())
    seen=set()
    for entry in register['entries']:
        chart=entry.get('chart')
        if not chart or chart.startswith('@') or chart in seen:continue
        seen.add(chart)
        values_path=ROOT/'k8s-rewrite/charts'/chart/'values.yaml'
        if not values_path.exists():continue
        import yaml
        chart_values=yaml.safe_load(values_path.read_text())
        source=None
        if entry['source_type']=='swarm':
            source=next((c['Config'] for cfg in configurations for c in cfg['containers'] if (c['Config'].get('Labels') or {}).get('com.docker.swarm.service.name')==entry['source']),None)
            if source is None:source=next((s['Spec']['TaskTemplate']['ContainerSpec'] for cfg in configurations for s in cfg['services'] if s['Spec']['Name']==entry['source']),None)
        elif entry['source_type']=='standalone':
            host,name=entry['source'].split('/',1)
            cfg=configurations[['192.168.0.4','192.168.0.5','192.168.0.6'].index(host)]
            source=next((c['Config'] for c in cfg['containers'] if c['Name'].lstrip('/')==name),None)
        if source:
            env=dict(item.split('=',1) for item in source.get('Env',[]) if '=' in item)
            secret(entry['namespace'],chart_values['environmentSecret'],env,{'branconet.io/docker-source':entry['source']})
    runtime_values=None
    if args.execute:
        existing_runtime=kube(['get','secret','bortus-runtime','-n','bortus','--ignore-not-found','-o','json'])
        if existing_runtime.returncode==0 and existing_runtime.stdout.strip():
            data=json.loads(existing_runtime.stdout).get('data',{})
            if set(data)!={'jwt-secret','lookup-token'}:raise SystemExit('BORTUS runtime Secret has unexpected keys')
            runtime_values={key:base64.b64decode(value).decode() for key,value in data.items()}
            if any(len(value)<32 for value in runtime_values.values()):raise SystemExit('BORTUS runtime key is too short')
    if runtime_values is None:runtime_values={'jwt-secret':secrets.token_urlsafe(48),'lookup-token':secrets.token_urlsafe(48)}
    secret('bortus','bortus-runtime',runtime_values)
    aliases=[]
    for obj in pending:
        ns=obj['metadata']['namespace'];name=obj['metadata']['name']
        path=obj['metadata']['annotations'].get('branconet.io/vault-path')
        for key in obj['data']:
            alias=(path+'/'+key) if path else 'secret_'+ns+'_'+name+'_'+key
            aliases.append({'alias':alias,'namespace':ns,'name':name,'key':key})
        if path and len(obj['data'])==1:
            aliases.append({'alias':path,'namespace':ns,'name':name,'key':next(iter(obj['data']))})
    if len({a['alias'] for a in aliases})!=len(aliases):raise SystemExit('Import alias collision requires explicit resolution')
    alias_config={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'bortus-secret-aliases','namespace':'bortus'},'data':{'aliases.json':json.dumps(aliases,separators=(',',':'))}}
    (ROOT/'evidence/native-secret-aliases.json').write_text(json.dumps(alias_config,indent=2)+'\n')
    results=[]
    for obj in pending:
        ns=obj['metadata']['namespace'];name=obj['metadata']['name']
        if args.execute:
            namespace=kube(['get','namespace',ns,'-o','json'])
            if namespace.returncode:
                created=kube(['create','-f','-'],{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}})
                if created.returncode:raise SystemExit('Namespace creation failed: '+ns)
            existing=kube(['get','secret',name,'-n',ns,'--ignore-not-found','-o','json'])
            if existing.returncode:raise SystemExit('Secret lookup failed: '+ns+'/'+name)
            if existing.stdout.strip():
                if json.loads(existing.stdout).get('data',{})!=obj['data']:raise SystemExit('Existing unequal Secret requires explicit conflict resolution: '+ns+'/'+name)
            else:
                created=kube(['create','-f','-'],obj)
                if created.returncode:raise SystemExit('Secret creation failed: '+ns+'/'+name)
            verified=kube(['get','secret',name,'-n',ns,'-o','json'])
            if verified.returncode or json.loads(verified.stdout).get('data',{})!=obj['data']:raise SystemExit('Secret readback mismatch: '+ns+'/'+name)
        results.append({'namespace':ns,'name':name,'keys':sorted(obj['data']),'annotations':obj['metadata']['annotations'],'readback_equal':args.execute})
    if args.execute:
        result=kube(['apply','-f','-'],alias_config)
        if result.returncode:raise SystemExit('BORTUS alias ConfigMap application failed')
    report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'executed':args.execute,'values_reported':False,'secrets':results,'bortus_integration_accepted':False}
    (ROOT/'evidence/native-secret-import.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'executed':args.execute,'secret_count':len(results),'values_reported':False}))

if __name__=='__main__':main()
