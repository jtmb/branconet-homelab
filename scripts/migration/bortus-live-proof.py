#!/usr/bin/env python3
"""Live native-provider/auth/restart acceptance; credentials never leave memory/API."""
import base64
import datetime
import http.cookiejar
import json
import pathlib
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def kubectl(args,body=None):
        result=subprocess.run([*kube,*args],input=json.dumps(body) if body is not None else None,capture_output=True,text=True,timeout=300)
        if result.returncode:raise RuntimeError('Live proof Kubernetes operation failed: '+args[0])
        return result.stdout
    def get_secret(name):return json.loads(kubectl(['get','secret',name,'-n','bortus','-o','json']))
    credential_check=subprocess.run([*kube,'get','secret','bortus-operator-access','-n','bortus','--ignore-not-found','-o','json'],capture_output=True,text=True,check=True)
    if credential_check.stdout.strip():
        access=json.loads(credential_check.stdout);password=base64.b64decode(access['data']['password']).decode()
    else:
        password=secrets.token_urlsafe(40)
        kubectl(['create','-f','-'],{'apiVersion':'v1','kind':'Secret','metadata':{'name':'bortus-operator-access','namespace':'bortus'},'type':'Opaque','stringData':{'username':'james','password':password}})
    holder=socket.socket();holder.bind(('127.0.0.1',0));port=holder.getsockname()[1];holder.close()
    forward=subprocess.Popen([*kube,'port-forward','-n','bortus','service/bortus',str(port)+':4000','--address','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base='http://127.0.0.1:'+str(port)
    writer_cookie=None;reader_cookie=None
    def request(path,method='GET',body=None,cookie=None,bearer=None):
        headers={}
        if body is not None:headers['Content-Type']='application/json'
        if cookie:headers['Cookie']=cookie
        if bearer:headers['Authorization']='Bearer '+bearer
        operation=urllib.request.Request(base+path,method=method,headers=headers,data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(operation,timeout=30) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as error:return error.code,error.read(),error.headers
    def expect(path,status=200,**kwargs):
        response=request(path,**kwargs)
        if response[0]!=status:raise RuntimeError('Live BORTUS check failed: '+path.split('?')[0]+' expected '+str(status)+' got '+str(response[0]))
        return response
    def connect():
        for _ in range(60):
            try:
                if request('/api/health/ready')[0]==200:return
            except (urllib.error.URLError,TimeoutError,ConnectionError):pass
            time.sleep(1)
        raise RuntimeError('BORTUS staging did not become HTTP ready')
    checks={}
    try:
        connect();checks['readiness_passed']=True
        expect('/api/secrets',401);expect('/api/vars/lookup?key=not-mapped',401);checks['unauthenticated_denied']=True
        registered=request('/api/auth/register','POST',{'username':'james','password':password})
        if registered[0]==201:writer_cookie=registered[2]['Set-Cookie'].split(';')[0]
        else:
            login=expect('/api/auth/login',method='POST',body={'username':'james','password':password});writer_cookie=login[2]['Set-Cookie'].split(';')[0]
        expect('/api/settings',method='PATCH',body={'key':'allow_registration','value':'true'},cookie=writer_cookie)
        try:
            reader_password=secrets.token_urlsafe(40)
            username='migration_reader_'+secrets.token_hex(3)
            reader=expect('/api/auth/register',201,method='POST',body={'username':username,'password':reader_password})
            reader_cookie=reader[2]['Set-Cookie'].split(';')[0]
        finally:expect('/api/settings',method='PATCH',body={'key':'allow_registration','value':'false'},cookie=writer_cookie)
        expect('/api/secrets',cookie=reader_cookie)
        expect('/api/secrets',403,method='POST',body={},cookie=reader_cookie)
        expect('/api/secrets?namespace=bortus&name=bortus-runtime&key=lookup-token',403,cookie=reader_cookie)
        checks['readonly_metadata_and_value_write_denial']=True
        runtime=get_secret('bortus-runtime');lookup_token=base64.b64decode(runtime['data']['lookup-token']).decode()
        aliases=json.loads((ROOT/'evidence/native-secret-aliases.json').read_text())
        if isinstance(aliases,dict):aliases=json.loads(aliases['data']['aliases.json'])
        vault_aliases=[a for a in aliases if a['namespace']=='bortus-secrets']
        if len(vault_aliases)<43:raise RuntimeError('Vault alias coverage is incomplete')
        for alias in vault_aliases:
            secret=json.loads(kubectl(['get','secret',alias['name'],'-n',alias['namespace'],'-o','json']))
            expected=base64.b64decode(secret['data'][alias['key']]).decode()
            response=expect('/api/vars/lookup?'+urllib.parse.urlencode({'key':alias['alias']}),bearer=lookup_token)
            if json.loads(response[1]).get('value')!=expected:raise RuntimeError('Imported Vault alias value differs')
        checks['imported_vault_aliases_readback_equal']=len(vault_aliases)
        target={'namespace':'bortus','name':'migration-acceptance-'+secrets.token_hex(3),'key':'proof_key'}
        marker=secrets.token_urlsafe(24)
        expect('/api/secrets',201,method='POST',body={**target,'value':marker,'mode':'create'},cookie=writer_cookie)
        current=get_secret(target['name']);version=current['metadata']['resourceVersion']
        current.setdefault('metadata',{}).setdefault('annotations',{})['branconet.io/proof']='preserve'
        current['data']['other_key']=base64.b64encode(b'other-proof').decode()
        kubectl(['replace','-f','-'],current)
        expect('/api/secrets',409,method='POST',body={**target,'value':'stale-write','mode':'update','resourceVersion':version},cookie=writer_cookie)
        current=get_secret(target['name']);version=current['metadata']['resourceVersion']
        updated=secrets.token_urlsafe(24)
        expect('/api/secrets',method='POST',body={**target,'value':updated,'mode':'update','resourceVersion':version},cookie=writer_cookie)
        current=get_secret(target['name'])
        if base64.b64decode(current['data'][target['key']]).decode()!=updated or current['data']['other_key']!=base64.b64encode(b'other-proof').decode() or current['metadata']['annotations']['branconet.io/proof']!='preserve':raise RuntimeError('Native CRUD preservation check failed')
        checks['native_create_update_conflict_metadata_preservation']=True
        kubectl(['rollout','restart','deployment/bortus','-n','bortus']);kubectl(['rollout','status','deployment/bortus','-n','bortus','--timeout=240s'])
        forward.terminate();forward.wait(timeout=10)
        forward=subprocess.Popen([*kube,'port-forward','-n','bortus','service/bortus',str(port)+':4000','--address','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        connect()
        response=expect('/api/secrets?'+urllib.parse.urlencode(target),cookie=writer_cookie)
        if json.loads(response[1]).get('value')!=updated:raise RuntimeError('Secret changed after app restart')
        if get_secret('bortus-runtime')['data']!=runtime['data']:raise RuntimeError('Signing/lookup runtime changed after restart')
        checks['restart_native_secret_user_session_and_stable_runtime']=True
        current=get_secret(target['name'])
        expect('/api/secrets',method='DELETE',body={**target,'resourceVersion':current['metadata']['resourceVersion']},cookie=writer_cookie)
        current=get_secret(target['name'])
        if target['key'] in current['data'] or 'other_key' not in current['data']:raise RuntimeError('Native key deletion did not preserve other keys')
        expect('/api/secrets',403,method='DELETE',body={**target,'resourceVersion':current['metadata']['resourceVersion']},cookie=reader_cookie)
        checks['key_delete_preserves_object_and_other_key']=True
        report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'values_reported':False,'operator_account':'james','operator_credential_reference':'bortus/bortus-operator-access','registration_locked':True,'public_ingress':False,'outage_live_check_pending':True,'dashboard_acceptance_pending':True}
        (ROOT/'evidence/bortus-live-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    finally:
        forward.terminate()
        try:forward.wait(timeout=10)
        except subprocess.TimeoutExpired:forward.kill()

if __name__=='__main__':main()
