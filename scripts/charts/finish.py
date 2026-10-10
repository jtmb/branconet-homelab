#!/usr/bin/env python3
"""Deactivate the old source after proven rollback; check preservation and routes."""
import concurrent.futures
import datetime
import hashlib
import http.client
import json
import pathlib
import socket
import ssl
import subprocess
import sys

CHARTS = pathlib.Path('/mnt/c/Users/james/.codex/worktrees/8cdf/branconet-charts')
sys.path.insert(0, str(CHARTS/'scripts'))
from checkpoint import K, RUNTIME, capture, compare
OUT = RUNTIME/'charts-separation'

def execute(argv, body=None):
    result = subprocess.run(argv, input=body, capture_output=True, text=True)
    if result.returncode: raise RuntimeError(f'{pathlib.Path(argv[0]).name} request failed; output withheld')
    return result.stdout

def probe(host, address):
    path = ('/dashboard/' if host == 'proxy.branconet.lan' else
            '/auth/login' if host == 'bortus.branconet.lan' else
            '/admin/' if host == 'pi.branconet.lan' else '/')
    context = ssl._create_unverified_context() if host.endswith(('.lan', '.local')) else ssl.create_default_context()
    try:
        with context.wrap_socket(socket.create_connection((address, 443), timeout=15), server_hostname=host) as conn:
            request = f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0 Branconet-route-check\r\nConnection: close\r\n\r\n'
            conn.sendall(request.encode())
            response = http.client.HTTPResponse(conn)
            response.begin()
            body = response.read()
        return {'host': host, 'address': address, 'path': path, 'status': response.status,
                'body_sha256': hashlib.sha256(body).hexdigest(),
                'certificate_verified': not host.endswith(('.lan', '.local')),
                'passed': response.status in {200, 301, 302, 303, 307, 308, 401}}
    except Exception as error:
        return {'host': host, 'address': address, 'passed': False, 'error_type': type(error).__name__}

def main():
    canary = json.loads((OUT/'canary.json').read_text())
    if canary.get('passed') is not True: raise RuntimeError('A proven rollout AND rollback is required first')
    current = capture()
    preserved = compare(json.loads((OUT/'before.json').read_text()), current)
    if not preserved['preservation_passed']:
        raise RuntimeError('Preservation must pass before old source deactivation: '+','.join(preserved['differences']))
    if len(current['kustomizations']) != 1 or any(v['source']['name'] != 'branconet-charts' for v in current['kustomizations'].values()):
        raise RuntimeError('One Kustomization owned by the new source is required')
    if any(v['source'] and v['source']['name'] != 'branconet-charts' for v in current['helmreleases'].values()):
        raise RuntimeError('All application charts must use the new source')
    patch = {'spec': {'suspend': True, 'ref': {'branch': None, 'commit': '373a1e513e1bfb8b13ed5212ccc1b0f57a5ff301'}}}
    execute(K+['patch', 'gitrepository', 'migration-validated', '-n', 'flux-system', '--type=merge', '--patch-file=/dev/stdin'], json.dumps(patch))
    ingresses = json.loads(execute(K+['get', 'ingresses', '-A', '-o', 'json']))['items']
    hosts = sorted({rule['host'] for o in ingresses for rule in o['spec'].get('rules', []) if rule.get('host')})
    pairs = [(host, address) for host in hosts for address in ['192.168.0.4', '192.168.0.5', '192.168.0.6']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        routes = list(pool.map(lambda pair: probe(*pair), pairs))
    after = capture()
    (OUT/'after.json').write_text(json.dumps(after, indent=2)+'\n')
    report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'preservation': compare(json.loads((OUT/'before.json').read_text()), after),
              'old_source_suspended_and_pinned': True, 'one_kustomization': len(after['kustomizations']) == 1,
              'all_application_source_refs_new': True, 'hostnames': len(hosts),
              'route_probes': len(routes), 'route_probes_passed': sum(r['passed'] for r in routes), 'routes': routes}
    report['passed'] = report['preservation']['preservation_passed'] and all(r['passed'] for r in routes)
    (OUT/'final.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'routes'}))
    if not report['passed']:
        print(json.dumps({'failed_routes': [r for r in routes if not r['passed']]}))
        raise SystemExit(1)

if __name__ == '__main__': main()
