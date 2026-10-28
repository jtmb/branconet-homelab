#!/usr/bin/env python3
"""Pi-hole exact native resource, FTL version and web authorization routes."""
import argparse,datetime,hashlib,hmac,http.client,importlib.util,json,os,shlex,socket,ssl,subprocess,uuid
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025');OUT=ROOT/'upstream-pihole-20261026'
OLD='docker.io/library/pihole-security-20261023@sha256:05ededd91f4f497f527502a4e16960f98d62d1651fc9a34a44740a41e89c7e49'
NEW='docker.io/pihole/pihole:2026.10.0@sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']
spec=importlib.util.spec_from_file_location('pihole_upstream_state',Path(__file__).with_name('verify-upstream-pihole-state.py'));state=importlib.util.module_from_spec(spec);spec.loader.exec_module(state)


def mac(key, value):
    return hmac.new(key, json.dumps(value, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()

def call(args, payload=None):
    result = subprocess.run(SSH + [shlex.join(args)], input=payload, capture_output=True, timeout=240)
    if result.returncode != 0:
        failure = OUT / ('failed-read-' + uuid.uuid4().hex)
        if 'exec' in args:
            for suffix, data in [('stdout', result.stdout), ('stderr', result.stderr)]:
                with Path(str(failure) + '.' + suffix).open('xb') as stream:stream.write(data)
        else:
            with failure.with_suffix('.json').open('x') as stream:
                json.dump({'exitCode': result.returncode, 'metadataResponseNotPersisted': True}, stream)
    assert result.returncode == 0 and len(result.stdout) <= 8 * 1024**2
    return result.stdout

def request(host, port, path):
    tls = port == 443;trusted = True;fingerprint = None
    if tls:
        try:
            with socket.create_connection((host, port), timeout=5) as raw:
                with ssl.create_default_context().wrap_socket(raw, server_hostname='pi.branconet.lan'):pass
            context = ssl.create_default_context()
        except ssl.SSLCertVerificationError as error:
            assert error.verify_code == 18;trusted = False;context = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname='pi.branconet.lan') as stream:der = stream.getpeercert(binary_form=True)
            cert = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-noout', '-subject', '-issuer', '-nameopt', 'RFC2253'], input=der, capture_output=True, timeout=10)
            assert cert.returncode == 0 and cert.stdout.decode().splitlines() == ['subject=CN=TRAEFIK DEFAULT CERT', 'issuer=CN=TRAEFIK DEFAULT CERT']
            fingerprint = hashlib.sha256(der).hexdigest()
        connection = http.client.HTTPSConnection(host, port, context=context, timeout=15)
    else:connection = http.client.HTTPConnection(host, port, timeout=15)
    try:
        connection.request('GET', path, headers={'Host': 'pi.branconet.lan'})
        response = connection.getresponse();body = response.read(1024**2 + 1);assert len(body) <= 1024**2
        if path=='/api/groups':assert response.status==401
        elif path=='/admin/':assert response.status==302 and response.getheader('Location')=='/admin/login'
        else:assert response.status==200 and b'<html'in body.lower() and b'Pi-hole'in body
        return {'status':response.status,'authenticatedTLS':trusted if tls else None,'certificateSHA256':fingerprint}
    finally:connection.close()

def fence(image,revision,key):
    binding=state.fence('verify',image);d=state.get('deployment','pihole');h=state.get('helmrelease','pihole','flux-system');source=state.get('gitrepository','branconet-charts','flux-system')
    assert source['status']['artifact']['revision']=='validated@sha1:'+revision and h['status']['lastAttemptedRevision'].endswith('+'+revision[:12])
    ds=json.loads(json.dumps(d['spec']));container=ds['template']['spec']['containers'][0]
    assert container['resources']=={'requests':{'cpu':'25m','memory':'64Mi'}}and container['imagePullPolicy']==('Never'if image==OLD else'IfNotPresent')
    container['image']='<maintained-image>';container['imagePullPolicy']='<immutable-image-policy>';ds['template']['metadata']['annotations'].pop('branconet.lan/security-restart',None)
    secret=state.get('secret','pihole-runtime');stable={'deployment':mac(key,ds),'secretUID':secret['metadata']['uid'],'secretRV':secret['metadata']['resourceVersion'],'secret':mac(key,{'type':secret['type'],'data':secret.get('data',{})})}
    for alias,target in state.cold.CLAIMS.items():
        pvc=state.get('pvc',target['name']);pv=state.get('pv',pvc['spec']['volumeName']);stable[alias]={'pvcUID':pvc['metadata']['uid'],'pvc':mac(key,pvc['spec']),'pvUID':pv['metadata']['uid'],'pv':mac(key,pv['spec'])}
    for kind,names in [('service',['pihole','pihole-public']),('ingress',['pihole-http','pihole-https'])]:
        for name in names:
            resource=state.get(kind,name)
            if kind=='ingress':assert [r['host']for r in resource['spec']['rules']]==['pi.branconet.lan']
            stable[kind+'/'+name]={'uid':resource['metadata']['uid'],'spec':mac(key,resource['spec']),'annotations':mac(key,resource['metadata'].get('annotations',{}))}
    return {'pod':binding['pod_name'],'podUID':binding['pod_uid'],'stable':stable,'image':image,'restarts':binding['restart_count']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['baseline','after','restart'],required=True);p.add_argument('--revision',required=True);a=p.parse_args();assert os.getuid()==1000 and len(a.revision)==40;os.umask(0o077)
    key=(OUT/'verification.key').read_bytes();assert len(key)==64;image=OLD if a.phase=='baseline'else NEW;target=OUT/(a.phase+'-runtime.json');assert not target.exists();before=fence(image,a.revision,key)
    version=call(['kubectl','-n','pihole','exec',before['pod'],'--','pihole-FTL','--version']).decode().strip();assert version=='v6.8'
    routes={}
    for host in ['192.168.0.4','192.168.0.5','192.168.0.6']:
        for port in [8079,80,443]:
            for path in ['/admin/','/admin/login','/api/groups']:routes[host+':'+str(port)+path]=request(host,port,path)
    assert fence(image,a.revision,key)==before
    if a.phase!='baseline':
        original=json.loads((OUT/'baseline-runtime.json').read_text());assert before['stable']==original['writer']['stable']
        if a.phase=='restart':assert before['podUID']!=json.loads((OUT/'after-runtime.json').read_text())['writer']['podUID']
    result={'passed':True,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':a.phase,'revision':a.revision,'writer':before,'FTLVersion':version,'routes':routes,'personalBrowserLoginVerified':False,'productionChangedByObserver':False,'sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with target.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'phase':a.phase,'podUID':before['podUID'],'routes':len(routes),'FTLVersion':version}))
if __name__=='__main__':main()
