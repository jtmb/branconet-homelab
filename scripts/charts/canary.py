#!/usr/bin/env python3
"""Prove the separate repository's gated chart push and rollback end to end."""
import argparse
import datetime
import hashlib
import http.client
import json
import pathlib
import socket
import ssl
import subprocess
import time
import yaml

RUNTIME = pathlib.Path.home()/'.local/share/branconet-migration'
K = [str(RUNTIME/'bin/kubectl'), '--kubeconfig', str(RUNTIME/'admin.conf')]
GIT = '/mnt/c/Program Files/Git/cmd/git.exe'
MARKER = 'branconet.io/charts-repository-canary'
OUT = RUNTIME/'charts-separation/canary.json'

def command(argv, cwd=None):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{pathlib.Path(argv[0]).name} request failed; output withheld')
    return result.stdout

def get(kind, name=None, namespace='http-echo'):
    return json.loads(command(K+['get', kind]+([name] if name else [])+['-n', namespace, '-o', 'json']))

def capture():
    deploy = get('deployment', 'http-echo')
    pods = [p for p in get('pods')['items'] if p['metadata'].get('labels', {}).get('app') == 'http-echo'
            and not p['metadata'].get('deletionTimestamp')
            and any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', []))]
    if len(pods) != 1: raise RuntimeError('One Ready HTTP echo Pod is required')
    claim = get('pvc', 'http-echo-data-pvc')
    with ssl._create_unverified_context().wrap_socket(socket.create_connection(('192.168.0.4', 443), timeout=15),
                                                     server_hostname='http-echo.branconet.local') as conn:
        conn.sendall(b'GET / HTTP/1.1\r\nHost: http-echo.branconet.local\r\nConnection: close\r\n\r\n')
        response = http.client.HTTPResponse(conn)
        response.begin()
        body = response.read()
    if response.status != 200: raise RuntimeError('HTTP echo route failed')
    hr = get('helmrelease', 'http-echo', 'flux-system')
    kust = get('kustomization', 'migration-releases', 'flux-system')
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    return {'pod_uid': pods[0]['metadata']['uid'], 'deployment_uid': deploy['metadata']['uid'],
            'claim_uid': claim['metadata']['uid'], 'volume': claim['spec']['volumeName'],
            'image': deploy['spec']['template']['spec']['containers'][0]['image'],
            'http_status': response.status, 'body_sha256': hashlib.sha256(body).hexdigest(),
            'tls_validation': 'Existing LAN certificate unverified for noncredential health probe',
            'canary': deploy['spec']['template']['metadata'].get('annotations', {}).get(MARKER),
            'source_revision': source['status']['artifact']['revision'],
            'kustomization_revision': kust['status']['lastAppliedRevision'],
            'helmrelease_revision': hr['status']['lastAttemptedRevision'],
            'helmrelease_source': hr['spec']['chart']['spec']['sourceRef']['name'],
            'helmrelease_generation': hr['metadata']['generation'],
            'helmrelease_observed_generation': hr['status']['observedGeneration']}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repository', type=pathlib.Path)
    args = parser.parse_args()
    root = args.repository.resolve()
    if OUT.exists(): raise RuntimeError('A canary record exists; inspect it before repetition')
    if command([GIT, 'status', '--porcelain'], root).strip(): raise RuntimeError('Clean chart worktree required')
    chart = root/'charts/http-echo/values.yaml'
    original = chart.read_bytes()
    values = yaml.safe_load(original)
    deployment = next(o for o in values['resources'] if o['kind'] == 'Deployment')
    annotations = deployment['spec']['template']['metadata'].setdefault('annotations', {})
    if MARKER in annotations: raise RuntimeError('Canary annotation already exists')
    report = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'HTTP echo Pod template annotation only; native data and images untouched',
              'baseline': capture(), 'phases': []}
    def save(): OUT.write_text(json.dumps(report, indent=2)+'\n')
    def publish(message):
        command([GIT, 'add', 'charts/http-echo/values.yaml'], root)
        command([GIT, 'commit', '-m', message], root)
        sha = command([GIT, 'rev-parse', 'HEAD'], root).strip()
        command([GIT, 'push', 'origin', 'main'], root)
        print(json.dumps({'commit': sha, 'waiting_for': 'Chart validation and source promotion'}), flush=True)
        run = None
        for attempt in range(120):
            runs = json.loads(command(['/usr/bin/gh', 'run', 'list', '--repo', 'jtmb/branconet-charts',
                                       '--workflow', 'charts.yml', '--limit', '8', '--json', 'databaseId,headSha,status,conclusion']))
            run = next((r for r in runs if r['headSha'] == sha), None)
            if run and run['status'] == 'completed': break
            time.sleep(5)
        if not run or run['conclusion'] != 'success': raise RuntimeError('Chart CI did not succeed')
        command([str(RUNTIME/'bin/flux'), '--kubeconfig', str(RUNTIME/'admin.conf'), 'reconcile',
                 'kustomization', 'migration-releases', '-n', 'flux-system', '--with-source', '--timeout=240s'])
        state = capture()
        if not state['source_revision'].endswith(sha) or not state['kustomization_revision'].endswith(sha):
            raise RuntimeError('Flux did not consume the exact successful CI commit')
        if sha[:12] not in state['helmrelease_revision'] or state['helmrelease_source'] != 'branconet-charts':
            raise RuntimeError('HTTP echo HelmRelease did not observe the exact chart source revision')
        if state['helmrelease_generation'] != state['helmrelease_observed_generation']:
            raise RuntimeError('HTTP echo HelmRelease generation is not reconciled')
        return {'commit': sha, 'ci_run': run['databaseId'], 'state': state}
    save()
    canary = None
    try:
        annotations[MARKER] = 'accepted-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
        chart.write_text(yaml.safe_dump(values, sort_keys=False))
        canary = publish('Prove chart push deploys through validation and Flux')
        report['phases'].append({'phase': 'canary', **canary})
        save()
        if not canary['state']['canary'] or canary['state']['pod_uid'] == report['baseline']['pod_uid']:
            raise RuntimeError('Canary must replace the actual Pod')
    finally:
        chart.write_bytes(original)
        rollback = publish('Revert the chart repository deployment canary')
        report['phases'].append({'phase': 'rollback', **rollback})
        save()
    for phase in report['phases']:
        for field in ['claim_uid', 'volume', 'deployment_uid', 'image', 'body_sha256']:
            if phase['state'][field] != report['baseline'][field]:
                raise RuntimeError('Canary preservation failed: '+field)
    if not canary or rollback['state']['canary'] or rollback['state']['pod_uid'] == canary['state']['pod_uid']:
        raise RuntimeError('Rollback must remove the annotation and replace the actual Pod')
    report.update({'passed': True, 'actual_pod_rollout_and_rollback': True,
                   'same_claim_volume_image_and_response': True,
                   'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    save()
    print(json.dumps(report), flush=True)

if __name__ == '__main__': main()
