#!/usr/bin/env python3
"""Compare original WordPress files, accounts and routes across an upstream rollout."""
import argparse
import ast
import copy
import datetime
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OLD = 'docker.io/library/wordpress-security-20261023@sha256:fe0f66b827b865026a5ffcf0ee28b34f8e2d2cc9fb6c85bd3faace75987a9bf0'
NEW = 'docker.io/library/wordpress:7.1.3-php8.3-apache@sha256:e5a724ec7ad9055f48b2941ac1b674b08e77ed60edb8937a6254fb89ec45ddf7'
CHILD = 'sha256:806680ba62232c4c300fb9dcc9f89d08e9e8c2bfc59837a1f58716f8648306d5'
spec = importlib.util.spec_from_file_location('original_observer', Path(__file__).with_name('qualify-wordpress.py'))
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)

HTTP = r'''
import json,sys,http.client,hashlib,hmac
r=json.load(sys.stdin);key=bytes.fromhex(r['key']);rows={}
for address,port in [(r['serviceIP'],80)]+[(ip,8085)for ip in ['192.168.0.4','192.168.0.5','192.168.0.6']]:
 for path in ['/','/wp-login.php','/wp-json/']:
  c=http.client.HTTPConnection(address,port,timeout=20)
  try:
   c.request('GET',path,headers={'Host':'jtmb.cc','Accept-Encoding':'identity'});response=c.getresponse();body=response.read(2097153)
   assert len(body)<=2097152 and response.status in [200,301,302,401,403]
   if path=='/wp-login.php'and response.status==200:assert b'loginform'in body and b'wp-submit'in body
   rows[address+':'+str(port)+path]={'status':response.status,'bytes':len(body),'locationHMAC':hmac.new(key,response.getheader('Location','').encode(),hashlib.sha256).hexdigest(),'loginForm':path=='/wp-login.php'and response.status==200}
  finally:c.close()
print(json.dumps(rows))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['baseline', 'after', 'restart'])
    p.add_argument('--expected-revision', required=True)
    a = p.parse_args()
    out = ROOT / 'upstream-wordpress-20261026'
    assert ROOT.is_mount() and out.is_dir() and len(a.expected_revision) == 40
    os.umask(0o077)
    target = out / (a.phase + '.json')
    assert not target.exists()
    kp = out / 'observation.key'
    if a.phase == 'baseline':
        with kp.open('xb') as f:
            f.write(os.urandom(32))
    key = kp.read_bytes()
    assert len(key) == 32 and not kp.stat().st_mode & 0o077
    mac = lambda obj: hmac.new(key, json.dumps(obj, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    get = original.get
    def fence():
        d = get('deployment', 'wordpress')
        h = get('helmrelease', 'wordpress', 'flux-system')
        pvc = get('pvc', 'wordpress-data-0')
        assert d['metadata']['uid'] == 'c5b60268-c0d4-43f8-8014-4c04e427a122'
        assert h['metadata']['uid'] == '65ca0d62-fc47-4063-81a5-4ed59767e907'
        assert pvc['metadata']['uid'] == '90b7695b-3cbf-41d9-b6d1-1f9ee3fd5e2f' and pvc['status']['phase'] == 'Bound'
        assert d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 1 and d['status']['observedGeneration'] == d['metadata']['generation']
        assert all(d['status'].get(k, 0) == 1 for k in ['replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas'])
        assert h['status']['observedGeneration'] == h['metadata']['generation'] and not h['spec'].get('suspend')
        assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status']['conditions'])
        assert get('gitrepository', 'branconet-charts', 'flux-system')['status']['artifact']['revision'] == 'validated@sha1:' + a.expected_revision
        assert h['status']['lastAttemptedRevision'].endswith('+' + a.expected_revision[:12])
        pods = json.loads(original.call(['kubectl', '-n', 'wordpress', 'get', 'pods', '-l', 'app=wordpress', '-o', 'json']))['items']
        assert len(pods) == 1
        pod = pods[0]
        assert pod['status']['phase'] == 'Running' and not pod['metadata'].get('deletionTimestamp')
        assert len(pod['spec']['containers']) == 1 and pod['status']['containerStatuses'][0]['ready']
        image = OLD if a.phase == 'baseline' else NEW
        assert pod['spec']['containers'][0]['image'] == image
        assert pod['status']['containerStatuses'][0]['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[-1], CHILD if a.phase != 'baseline' else image.rsplit('@', 1)[-1]]
        normalized = copy.deepcopy(d['spec'])
        assert normalized['template']['spec']['containers'][0]['image'] == image
        normalized['template']['spec']['containers'][0]['image'] = '<maintained-image>'
        normalized['template']['metadata'].get('annotations', {}).pop('maintenance.branconet.lan/restart-proof', None)
        identity = {'deploymentUID': d['metadata']['uid'], 'releaseUID': h['metadata']['uid'], 'specHMAC': mac(normalized), 'claims': {}, 'services': {}, 'secretMetadata': {}}
        for name in ['wordpress-data-0', 'wordpress-db-data-0', 'wordpress-redis-data']:
            c = get('pvc', name)
            pv = get('pv', c['spec']['volumeName'])
            assert c['status']['phase'] == 'Bound' and pv['spec']['claimRef']['uid'] == c['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
            identity['claims'][name] = {'uid': c['metadata']['uid'], 'pvUID': pv['metadata']['uid'], 'specHMAC': mac([c['spec'], pv['spec']])}
        for name in ['wordpress', 'wordpress-published', 'wordpress-db', 'mysql-db', 'db', 'wordpress-redis']:
            s = get('service', name)
            identity['services'][name] = {'uid': s['metadata']['uid'], 'specHMAC': mac(s['spec'])}
        for name in ['wordpress-runtime', 'wordpress-db-runtime', 'wordpress-redis-runtime']:
            m = original.call(['kubectl', '-n', 'wordpress', 'get', 'secret', name, '-o', 'jsonpath={.metadata.uid}{" "}{.metadata.resourceVersion}']).decode().split()
            assert len(m) == 2
            identity['secretMetadata'][name] = {'uid': m[0], 'resourceVersion': m[1]}
        return identity, {'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'], 'image': image, 'imageID': pod['status']['containerStatuses'][0]['imageID'], 'restarts': pod['status']['containerStatuses'][0]['restartCount']}
    record = {'passed': False, 'phase': a.phase, 'revision': a.expected_revision, 'controllerSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'fullGoalComplete': False}
    try:
        before, writer = fence()
        data = json.loads(original.call(['kubectl', '-n', 'wordpress', 'exec', '-i', writer['pod'], '--', 'php', '-d', 'memory_limit=128M', '-r', original.PHP], key.hex().encode(), timeout=150))
        assert data['wordpressVersion'] == '7.1.3' and data['phpVersion'] == '8.3.36'
        routes = json.loads(original.call(['python3', '-B', '-c', HTTP], json.dumps({'key': key.hex(), 'serviceIP': get('service', 'wordpress')['spec']['clusterIP']}).encode(), timeout=300))
        if a.phase != 'baseline':
            baseline = json.loads((out / 'baseline.json').read_text())
            assert baseline['passed'] and before == baseline['identity'] and writer['podUID'] != baseline['writer']['podUID']
            old = baseline['observation']
            assert all(data[k] == old[k] for k in ['filesHMAC', 'fileEntries', 'fileBytes', 'plugins', 'wordpressVersion'])
            assert set(data['tables']) == set(old['tables']) and all(all(data['tables'][t][k] == old['tables'][t][k] for k in ['rows', 'hmac']) for t in old['tables'])
            assert set(routes) == set(baseline['routes']) and all(all(routes[n][k] == baseline['routes'][n][k] for k in ['status', 'locationHMAC', 'loginForm']) for n in routes)
            if a.phase == 'restart':
                previous = json.loads((out / 'after.json').read_text())
                assert previous['passed'] and writer['podUID'] != previous['writer']['podUID']
        assert fence() == (before, writer)
        record.update(passed=True, identity=before, writer=writer, observation=data, routes=routes, originalFileTreeAndSQLPreserved=a.phase != 'baseline', credentialsPrinted=False, personalLoginClaimed=False)
    except Exception as error:
        import traceback
        record.update(errorType=type(error).__name__, sourceLines=[f.lineno for f in traceback.extract_tb(error.__traceback__) if f.filename == __file__], rawDetailsSuppressed=True)
    record['UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    target.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'passed': record['passed'], 'phase': a.phase, 'receipt': str(target), 'errorType': record.get('errorType'), 'sourceLines': record.get('sourceLines')}))
    return int(not record['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
