#!/usr/bin/env python3
"""Prove the fixed official CoreDNS binary/tag in a no-data, isolated Pod."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import os
import re
import shlex
import subprocess
import time
import urllib.request
import uuid

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-coredns-20261026'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def kube(args, data=None):
    p = subprocess.run(SSH + [shlex.join(['kubectl', '--request-timeout=30s', '-n', 'kube-system', *args])], input=data, capture_output=True, timeout=45)
    assert p.returncode == 0 and len(p.stdout) <= 1024**2
    return p.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    assert parser.parse_args().apply and ROOT.is_mount()
    os.umask(0o077)
    assert not (OUT / 'version-probe-r2-request.json').exists()
    image = json.loads((OUT / 'vendor-image-inspection.json').read_text())['image']
    assert image['reference'] == 'docker.io/coredns/coredns:1.15.0@sha256:0a9d8c8ddf34347eb59aad9a8784f0710de88d6d112726d11d271f9bc6daca26'
    baseline = json.loads((OUT / 'baseline.json').read_text())
    security = baseline['deployment']['spec']['template']['spec']['containers'][0]['securityContext']
    assert security['capabilities'] == {'add': ['NET_BIND_SERVICE'], 'drop': ['ALL']}
    assert security['allowPrivilegeEscalation'] is False and security['readOnlyRootFilesystem'] is True
    current = json.loads(kube(['get', 'deployment', 'coredns', '-o', 'json']))
    assert current['metadata']['uid'] == baseline['deploymentUID'] and current['spec'] == baseline['deployment']['spec']
    node = json.loads(kube(['get', 'node', 'workernode1', '-o', 'json']))
    assert node['metadata']['uid'] == 'e8d4555f-7cea-445f-b84f-6416964045a9' and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])
    name = 'coredns-upstream-version-' + uuid.uuid4().hex[:10]
    labels = {'upstream-version-probe': name}
    policy = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': {'name': name, 'namespace': 'kube-system'}, 'spec': {'podSelector': {'matchLabels': labels}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'kube-system', 'labels': labels}, 'spec': {'nodeName': 'workernode1', 'restartPolicy': 'Never', 'activeDeadlineSeconds': 180, 'automountServiceAccountToken': False, 'enableServiceLinks': False, 'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'runAsGroup': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [{'name': 'version', 'image': image['reference'], 'command': ['/coredns'], 'args': ['-version'], 'resources': {'requests': {'cpu': '10m', 'memory': '16Mi'}, 'limits': {'cpu': '100m', 'memory': '96Mi'}}, 'securityContext': copy.deepcopy(security)}]}}
    (OUT / 'version-probe-r2-request.json').write_text(json.dumps({'pod': pod, 'policy': policy, 'securityMatchesProduction': True, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + '\n')
    owned = []
    for obj in [policy, pod]:
        actual = json.loads(kube(['create', '-f', '-', '-o', 'json'], json.dumps(obj).encode()))
        owned.append({'kind': actual['kind'], 'name': name, 'uid': actual['metadata']['uid']})
    (OUT / 'version-probe-r2-owned-resources.json').write_text(json.dumps(owned, indent=2) + '\n')
    deadline = time.monotonic() + 210
    while time.monotonic() < deadline:
        p = json.loads(kube(['get', 'pod', name, '-o', 'json']))
        assert p['metadata']['uid'] == owned[1]['uid']
        if p['status']['phase'] in ['Failed', 'Succeeded']:
            break
        time.sleep(2)
    logs = kube(['logs', name]).decode()
    assert len(logs) < 4096
    (OUT / 'version-probe-r2-observation.json').write_text(json.dumps({'pod': p, 'logs': logs}, indent=2) + '\n')
    assert p['status']['phase'] == 'Succeeded' and 'CoreDNS-1.15.0' in logs and 'go1.27.3' in logs and 'a6fde3f' in logs
    image_id = p['status']['containerStatuses'][0]['imageID']
    assert image_id.rsplit('@', 1)[-1] in [image['rootDigest'], image['amd64Manifest']]
    url = 'https://api.github.com/repos/coredns/coredns/git/ref/tags/v1.15.0'
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read(65537)
    assert len(raw) <= 65536
    tag = json.loads(raw)['object']
    assert tag['type'] == 'commit' and re.fullmatch('[a-f0-9]{40}', tag['sha']) and tag['sha'].startswith('a6fde3fe339c')
    result = {'passed': True, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'image': image['reference'], 'imageID': image_id, 'podUID': p['metadata']['uid'], 'releaseTagURL': url, 'releaseCommit': tag['sha'], 'runtimeVersionOutput': logs, 'version': '1.15.0', 'goVersion': '1.27.3', 'volumesOrSecretsMounted': False, 'productionChanged': False}
    (OUT / 'vendor-runtime-version.json').write_text(json.dumps(result, indent=2) + '\n')
    for item in reversed(owned):
        api = '/api/v1/namespaces/kube-system/pods/' if item['kind'] == 'Pod' else '/apis/networking.k8s.io/v1/namespaces/kube-system/networkpolicies/'
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': item['uid']}}
        kube(['delete', '--raw', api + name, '-f', '-'], json.dumps(options).encode())
        kube(['wait', item['kind'] + '/' + name, '--for=delete', '--timeout=30s'])
    result['probeAndPolicyRetiredByUID'] = True
    (OUT / 'version-probe-retirement.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
