#!/usr/bin/env python3
"""Observe the exact Flare derivative and fetch one public page; no workload writes."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
import uuid

IMAGE = 'docker.io/library/flaresolverr-security-20261023@sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7'
DEP_UID = '7a6239d9-8a48-40ec-9480-dd4e8667f695'
HELM_UID = 'b556d097-1352-49b5-9253-d70657d70330'
ROOT = Path('/home/james/.local/share/branconet-migration/flaresolverr-acceptance-20261024')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def command(args):
    p = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=35)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024 ** 2, 'bounded_command_failed')
    return p.stdout


def kube(*args):
    return json.loads(command(['kubectl', '--request-timeout=25s', *args, '-o', 'json']))


def api(host, body=None):
    url = 'http://' + host + ':8191/' + ('v1' if body is not None else '')
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json'})
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with client.open(request, timeout=80 if body else 15) as response:
        need(response.status == 200 and response.url == url, 'unexpected_api_route')
        raw = response.read(4 * 1024 ** 2 + 1)
    need(len(raw) <= 4 * 1024 ** 2, 'api_response_limit')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-pod-uid', required=True)
    args = parser.parse_args()
    need(re.fullmatch('[0-9a-f-]{36}', args.previous_pod_uid), 'previous_pod_uid')
    os.umask(0o077)
    need(ROOT.parent.resolve() == ROOT.parent, 'output_parent_identity')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    need(ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.getuid()
         and ROOT.stat().st_mode & 0o077 == 0, 'output_identity')
    record = {'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'image': IMAGE, 'workloadWrites': False, 'passed': False}
    try:
        dep = kube('get', 'deployment', 'flaresolverr', '-n', 'plex')
        hr = kube('get', 'helmrelease', 'flaresolverr', '-n', 'flux-system')
        need(dep['metadata']['uid'] == DEP_UID and hr['metadata']['uid'] == HELM_UID, 'owner_identity')
        need(dep['spec']['replicas'] == 1 and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation']
             and all(dep['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']), 'deployment_not_ready')
        need(any(c['type'] == 'Ready' and c['status'] == 'True' and c.get('observedGeneration') == hr['metadata']['generation']
                 for c in hr.get('status', {}).get('conditions', [])), 'flux_release_not_ready')
        containers = dep['spec']['template']['spec']['containers']
        need(len(containers) == 1, 'container_identity')
        c = containers[0]
        need(c['image'] == IMAGE and c.get('imagePullPolicy') == 'Never' and not c.get('envFrom'), 'image_environment_contract')
        need(c.get('resources') == {'requests': {'cpu': '25m', 'memory': '64Mi'}}, 'resource_contract')
        env = c.get('env', [])
        need({v['name'] for v in env} == {'LOG_LEVEL', 'TZ'} and len(env) == 2, 'environment_scope')
        need(all(v.get('valueFrom') == {'secretKeyRef': {'name': 'flaresolverr-runtime', 'key': v['name']}} for v in env), 'native_secret_references')
        need(dep['spec']['template']['spec']['volumes'] == [{'emptyDir': {}, 'name': 'data-0'}], 'disposable_storage_contract')
        pods = kube('get', 'pods', '-n', 'plex', '-l', 'app=flaresolverr')['items']
        pods = [p for p in pods if not p['metadata'].get('deletionTimestamp')]
        need(len(pods) == 1, 'single_live_pod')
        pod = pods[0]
        need(pod['metadata']['uid'] != args.previous_pod_uid and pod['status']['phase'] == 'Running', 'new_pod_required')
        statuses = pod['status'].get('containerStatuses', [])
        need(len(statuses) == 1 and statuses[0]['ready'] and statuses[0].get('restartCount') == 0
             and statuses[0].get('imageID', '').endswith(IMAGE.split('@')[1]), 'runtime_digest_or_readiness')
        program = "import json,subprocess,importlib.metadata,os;print(json.dumps({'uid':os.getuid(),'chromium':subprocess.check_output(['/usr/bin/chromium','--version'],text=True).strip(),'driver':subprocess.check_output(['/app/chromedriver','--version'],text=True).strip(),'pythonPackages':{n:importlib.metadata.version(n) for n in ['certifi','urllib3','setuptools']}}))"
        runtime = json.loads(command(['kubectl', '--request-timeout=25s', 'exec', '-n', 'plex', pod['metadata']['name'], '--', '/usr/local/bin/python', '-c', program]))
        need(runtime['uid'] != 0 and runtime['pythonPackages'] == {'certifi': '2026.10.19', 'urllib3': '2.8.0', 'setuptools': '83.0.0'}, 'nonroot_python_contract')
        browser = re.search(r'\b(\d+\.\d+\.\d+\.\d+)\b', runtime['chromium'])
        driver = re.search(r'\b(\d+\.\d+\.\d+\.\d+)\b', runtime['driver'])
        need(browser and driver and browser[1] == driver[1]
             and tuple(map(int, browser[1].split('.'))) >= (156, 0, 8078, 47), 'browser_driver_pair')
        routes = []
        for host in ['192.168.0.4', '192.168.0.5', '192.168.0.6']:
            value = api(host)
            need(value.get('version') == '3.5.2', 'api_version')
            routes.append({'host': host, 'httpStatus': 200, 'version': value['version']})
        value = api('192.168.0.4', {'cmd': 'request.get', 'url': 'https://example.com/', 'maxTimeout': 60000})
        solution = value.get('solution', {})
        need(value.get('status') == 'ok' and solution.get('status') == 200
             and solution.get('url') == 'https://example.com/' and 'Example Domain' in solution.get('response', ''), 'real_browser_retrieval_failed')
        record.update(passed=True, deploymentUID=DEP_UID, helmReleaseUID=HELM_UID,
                      podUID=pod['metadata']['uid'], previousPodUID=args.previous_pod_uid,
                      node=pod['spec']['nodeName'], imageID=statuses[0]['imageID'], runtime=runtime,
                      routes=routes, browserRequest={'url': 'https://example.com/', 'status': 200,
                      'bodySHA256': hashlib.sha256(solution['response'].encode()).hexdigest(),
                      'expectedPageFound': True, 'cookiesRetained': False})
    except Exception as exc:
        record['failureCategory'] = str(exc) if isinstance(exc, ValueError) and re.fullmatch('[a-z_]+', str(exc)) else 'qualification_failed_diagnostics_withheld'
    record['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = ROOT / ('observation-' + uuid.uuid4().hex + '.json')
    raw = json.dumps(record, indent=2).encode()
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({'passed': record['passed'], 'failureCategory': record.get('failureCategory'),
                      'receipt': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
