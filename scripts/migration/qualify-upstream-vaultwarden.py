#!/usr/bin/env python3
"""Vaultwarden exact native identities, binary/API/config and route acceptance."""
import argparse,datetime,hashlib,hmac,http.client,json,os,shlex,socket,ssl,subprocess,uuid
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'upstream-vaultwarden-20261026'
OLD='docker.io/library/vaultwarden-security-20261023@sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d'
NEW='docker.io/vaultwarden/server:1.37.4-alpine@sha256:19ea2b669945d842dadc3d500f2d6a795866a003330f59a47b9634658bae98bb'
CHILD='sha256:7d90670a4e2531e752f014e58f7283b9d197847b6f073bf84e99598f49d80ffd'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']


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

def get(kind, name, namespace='vaultwarden'):
    return json.loads(call(['kubectl', '-n', namespace, 'get', kind, name, '-o', 'json']))

def fence(image, revision, key):
    d, h, pvc = get('deployment', 'vaultwarden'), get('helmrelease', 'vaultwarden', 'flux-system'), get('pvc', 'vaultwarden-data-0')
    assert d['metadata']['uid'] == '668bb3cd-e382-48b0-910f-7440351bc7d1'
    assert h['metadata']['uid'] == '3022a586-c52e-4dcd-850b-149f6b38b603'
    assert pvc['metadata']['uid'] == '0fb0e918-ea61-43f5-af95-662c12f8ffe8' and pvc['status']['phase'] == 'Bound'
    assert d['spec']['replicas'] == 1 and all(d['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'availableReplicas', 'readyReplicas'])
    assert d['status']['observedGeneration'] == d['metadata']['generation']
    assert h['status']['observedGeneration'] == h['metadata']['generation'] and h['spec']['values']['replicaCount'] == 1
    assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status']['conditions'])
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    assert source['status']['artifact']['revision'] == 'validated@sha1:' + revision
    assert h['status']['lastAttemptedRevision'].endswith('+' + revision[:12])
    spec = json.loads(json.dumps(d['spec']));containers = spec['template']['spec']['containers']
    assert len(containers) == 1 and containers[0]['image'] == image
    assert containers[0]['envFrom'] == [{'secretRef': {'name': 'vaultwarden-runtime'}}]
    assert containers[0]['resources'] == {'requests': {'cpu': '25m', 'memory': '64Mi'}}
    assert containers[0]['imagePullPolicy']==('Never' if image==OLD else 'IfNotPresent')
    containers[0]['imagePullPolicy']='<immutable-image-policy>'
    containers[0]['image'] = '<maintained-image>'
    spec['template']['metadata']['annotations'].pop('maintenance.branconet.lan/restart-proof',None)
    pods = get('pods', '-l=app=vaultwarden')['items'];assert len(pods) == 1
    pod = pods[0];assert not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running'
    cs = pod['status']['containerStatuses'][0];assert cs['ready'] and cs.get('restartCount', 0) == 0
    assert pod['spec']['containers'][0]['image'] == image
    assert cs['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[-1], CHILD if image == NEW else image.rsplit('@', 1)[-1]]
    owners = [r for r in pod['metadata']['ownerReferences'] if r.get('controller')];assert len(owners) == 1 and owners[0]['kind'] == 'ReplicaSet'
    rs = get('replicaset', owners[0]['name']);assert rs['metadata']['uid'] == owners[0]['uid']
    assert any(r.get('controller') and r['uid'] == d['metadata']['uid'] for r in rs['metadata']['ownerReferences'])
    secret, pv = get('secret', 'vaultwarden-runtime'), get('pv', pvc['spec']['volumeName'])
    assert pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
    stable = {'deployment': mac(key, spec), 'pvc': mac(key, pvc['spec']), 'pvUID': pv['metadata']['uid'], 'pv': mac(key, pv['spec']),
              'secretUID': secret['metadata']['uid'], 'secretRV': secret['metadata']['resourceVersion'],
              'secret': mac(key, {'type': secret['type'], 'data': secret.get('data', {})})}
    for kind, names in [('service', ['vaultwarden', 'vaultwarden-published']), ('ingress', ['vaultwarden-http', 'vaultwarden-https'])]:
        for name in names:
            r = get(kind, name);stable[kind + '/' + name] = {'uid': r['metadata']['uid'], 'spec': mac(key, r['spec']), 'annotations': mac(key, r['metadata'].get('annotations', {}))}
    return {'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'], 'imageID': cs['imageID'], 'stable': stable}

def request(host, port, path):
    tls = port == 443;trusted = True;fingerprint = None
    if tls:
        try:
            with socket.create_connection((host, port), timeout=5) as raw:
                with ssl.create_default_context().wrap_socket(raw, server_hostname='vault.branconet.lan'):pass
            context = ssl.create_default_context()
        except ssl.SSLCertVerificationError as error:
            assert error.verify_code == 18;trusted = False;context = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname='vault.branconet.lan') as stream:der = stream.getpeercert(binary_form=True)
            cert = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-noout', '-subject', '-issuer', '-nameopt', 'RFC2253'], input=der, capture_output=True, timeout=10)
            assert cert.returncode == 0 and cert.stdout.decode().splitlines() == ['subject=CN=TRAEFIK DEFAULT CERT', 'issuer=CN=TRAEFIK DEFAULT CERT']
            fingerprint = hashlib.sha256(der).hexdigest()
        connection = http.client.HTTPSConnection(host, port, context=context, timeout=15)
    else:connection = http.client.HTTPConnection(host, port, timeout=15)
    try:
        connection.request('GET', path, headers={'Host': 'vault.branconet.lan'})
        response = connection.getresponse();body = response.read(1024**2 + 1);assert len(body) <= 1024**2
        if path in ['/api/sync','/api/accounts/profile']:assert response.status==401
        else:assert response.status==200
        if path=='/':assert b'<html' in body.lower() and (b'Vaultwarden' in body or b'Bitwarden'in body)
        if path=='/api/config':
            data=json.loads(body);assert isinstance(data,dict)and 'version'in data
        return {'status':response.status,'authenticatedTLS':trusted if tls else None,'certificateSHA256':fingerprint,'config':json.loads(body)if path=='/api/config'else None}
    finally:connection.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['baseline','after','restart'],required=True);p.add_argument('--revision',required=True);a=p.parse_args();assert os.getuid()==1000 and len(a.revision)==40;os.umask(0o077)
    key=(OUT/'verification.key').read_bytes();assert len(key)==64;image=OLD if a.phase=='baseline'else NEW;target=OUT/(a.phase+'-runtime.json');assert not target.exists();before=fence(image,a.revision,key)
    version=call(['kubectl','-n','vaultwarden','exec',before['pod'],'--','/vaultwarden','--version']).decode().strip().splitlines();assert version==['Vaultwarden 1.37.4','Web-Vault 2026.7.0']
    guard='case "${DATABASE_URL:-}" in ""|data/db.sqlite3|/data/db.sqlite3|sqlite:/data/db.sqlite3) ;; *) exit 41;; esac; if [ -f /data/config.json ] && grep -q \'"database_url"\' /data/config.json; then exit 42; fi; printf %s sqlite-confirmed'
    assert call(['kubectl','-n','vaultwarden','exec',before['pod'],'--','/bin/sh','-c',guard])==b'sqlite-confirmed'
    routes={};configs=[]
    for host in ['192.168.0.4','192.168.0.5','192.168.0.6']:
        for port in [8096,80,443]:
            for path in ['/alive','/api/config','/','/api/sync','/api/accounts/profile']:
                result=request(host,port,path);config=result.pop('config')
                if config is not None:configs.append(config)
                routes[host+':'+str(port)+path]=result
    assert all(config==configs[0]for config in configs);stable_config=mac(key,configs[0]);assert fence(image,a.revision,key)==before
    if a.phase!='baseline':
        original=json.loads((OUT/'baseline-runtime.json').read_text());assert before['stable']==original['writer']['stable'] and stable_config==original['canonicalPublicConfigHMAC']
        if a.phase=='restart':assert before['podUID']!=json.loads((OUT/'after-runtime.json').read_text())['writer']['podUID']
    result={'passed':True,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':a.phase,'revision':a.revision,'writer':before,'binaryVersion':version,'databaseBackendSQLiteVerified':True,'canonicalPublicConfigHMAC':stable_config,'routes':routes,'personalLoginOrClientSyncVerified':False,'productionChangedByObserver':False,'sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with target.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'phase':a.phase,'podUID':before['podUID'],'routes':len(routes),'binaryVersion':version}))
if __name__=='__main__':main()
