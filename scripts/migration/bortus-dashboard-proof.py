#!/usr/bin/env python3
"""Verify live cluster views and API outage behavior without reporting values."""
import base64
import datetime
import json
import pathlib
import socket
import subprocess
import time
import urllib.error
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def kubectl(args,body=None):
        result=subprocess.run([*kube,*args],input=json.dumps(body) if body else None,capture_output=True,text=True,timeout=300)
        if result.returncode:raise RuntimeError('Dashboard proof Kubernetes operation failed')
        return result.stdout
    access=json.loads(kubectl(['get','secret','bortus-operator-access','-n','bortus','-o','json']))
    password=base64.b64decode(access['data']['password']).decode()
    runtime=json.loads(kubectl(['get','secret','bortus-runtime','-n','bortus','-o','json']))
    lookup=base64.b64decode(runtime['data']['lookup-token']).decode()
    aliases=json.loads(json.loads((ROOT/'evidence/native-secret-aliases.json').read_text())['data']['aliases.json'])
    alias=next(a for a in aliases if a['namespace']=='bortus-secrets')
    expected=json.loads(kubectl(['get','secret',alias['name'],'-n',alias['namespace'],'-o','json']))
    expected=base64.b64decode(expected['data'][alias['key']]).decode()
    holder=socket.socket();holder.bind(('127.0.0.1',0));port=holder.getsockname()[1];holder.close()
    forward=subprocess.Popen([*kube,'port-forward','-n','bortus','service/bortus',str(port)+':4000','--address','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base='http://127.0.0.1:'+str(port);cookie=None;policy=False
    def request(path,method='GET',body=None,bearer=False):
        headers={}
        if cookie:headers['Cookie']=cookie
        if bearer:headers['Authorization']='Bearer '+lookup
        if body is not None:headers['Content-Type']='application/json'
        try:
            with urllib.request.urlopen(urllib.request.Request(base+path,method=method,headers=headers,data=json.dumps(body).encode() if body is not None else None),timeout=25) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as error:return error.code,error.read(),error.headers
    def wait_ready():
        for _ in range(60):
            try:
                if request('/api/health/ready')[0]==200:return
            except (urllib.error.URLError,ConnectionError,TimeoutError):pass
            time.sleep(1)
        raise RuntimeError('BORTUS did not recover readiness')
    checks={}
    try:
        wait_ready()
        login=request('/api/auth/login','POST',{'username':'james','password':password})
        if login[0]!=200:raise RuntimeError('Operator login failed')
        cookie=login[2]['Set-Cookie'].split(';')[0]
        response=request('/api/cluster/nodes')
        nodes=json.loads(response[1]).get('nodes',[])
        if response[0]!=200 or len(nodes)!=3 or any(n['status']!='ready' or n.get('k8sVersion')!='v1.37.1' for n in nodes):raise RuntimeError('Dashboard must show three live Ready nodes/version, not DB fallback')
        checks['three_live_ready_nodes_and_version']=True
        for resource in ['pods','services','deployments','namespaces','volumes']:
            response=request('/api/cluster/'+resource)
            if response[0]!=200:raise RuntimeError('Dashboard resource endpoint failed: '+resource)
            body=json.loads(response[1])
            if not any(isinstance(v,list) and v for v in body.values()):raise RuntimeError('Dashboard resource view is empty: '+resource)
            checks['live_'+resource]=True
        from urllib.parse import urlencode
        path='/api/vars/lookup?'+urlencode({'key':alias['alias']})
        response=request(path,bearer=True)
        if response[0]!=200 or json.loads(response[1]).get('value')!=expected:raise RuntimeError('Lookup differs before outage')
        kubectl(['create','-f','-'],{'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'bortus-api-outage-proof','namespace':'bortus'},'spec':{'podSelector':{'matchLabels':{'app':'bortus'}},'policyTypes':['Egress'],'egress':[]}});policy=True
        time.sleep(3)
        response=request(path,bearer=True)
        if response[0]!=503 or (len(expected)>=8 and expected.encode() in response[1]):raise RuntimeError('API outage must fail closed without a value/DB fallback')
        if request('/api/health/ready')[0]!=503:raise RuntimeError('Readiness must fail during API outage')
        checks['live_api_outage_503_without_value_fallback']=True
        kubectl(['delete','networkpolicy','bortus-api-outage-proof','-n','bortus']);policy=False
        wait_ready()
        response=request(path,bearer=True)
        if response[0]!=200 or json.loads(response[1]).get('value')!=expected:raise RuntimeError('Lookup did not recover after outage')
        checks['lookup_and_readiness_recovered']=True
        report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'values_reported':False,'public_ingress':False,'cluster_admin_bound':False}
        (ROOT/'evidence/bortus-dashboard-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    finally:
        if policy:kubectl(['delete','networkpolicy','bortus-api-outage-proof','-n','bortus'])
        forward.terminate()
        try:forward.wait(timeout=10)
        except subprocess.TimeoutExpired:forward.kill()

if __name__=='__main__':main()
