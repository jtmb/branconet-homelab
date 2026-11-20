#!/usr/bin/env python3
"""Validate/approve one node's Pending kubelet-serving CSR using strict parsing.

Manual use enrolls the explicitly selected live node for this invocation.
Unattended callers must supply a previously reviewed --enrollment-file; they
must never build that file from an incoming CSR. --check-only never approves.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import time
from kubelet_csr_policy import approval_patch, validate_csr

RUNTIME = '/home/brajam/.local/share/branconet-migration'
KUBECTL = [RUNTIME + '/bin/kubectl', '--kubeconfig', RUNTIME + '/admin.conf', '--request-timeout=20s']


def kubectl(*args, data=None):
    return subprocess.run([*KUBECTL, *args], input=data, capture_output=True, check=True, timeout=30).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--enrollment-file', type=Path)
    args = parser.parse_args()
    node = json.loads(kubectl('get', 'node', args.node, '-o', 'json'))
    if args.enrollment_file:
        if args.enrollment_file.stat().st_size > 65536:
            raise ValueError("enrollment_file_too_large")
        enrollment = json.loads(args.enrollment_file.read_text())
        if enrollment.get('name') != args.node:
            raise ValueError("enrollment_node_mismatch")
    else:
        enrollment = {
            'name': args.node, 'uid': node['metadata']['uid'],
            'ips': [a['address'] for a in node['status']['addresses'] if a['type'] == 'InternalIP'],
            'dns': sorted({a['address'] for a in node['status']['addresses'] if a['type'] == 'Hostname'} | {args.node}),
        }
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        for csr in json.loads(kubectl('get', 'csr', '-o', 'json'))['items']:
            spec, status = csr['spec'], csr.get('status', {})
            if spec.get('signerName') != 'kubernetes.io/kubelet-serving' or status.get('conditions'):
                continue
            if spec.get('username') != 'system:node:' + args.node:
                continue
            # Fetch exact current objects before validation; no approval of a stale list snapshot.
            name = csr['metadata']['name']
            current = json.loads(kubectl('get', 'csr', name, '-o', 'json'))
            node = json.loads(kubectl('get', 'node', args.node, '-o', 'json'))
            failures = validate_csr(current, node, enrollment)
            if failures:
                print(json.dumps({'csr': name, 'approved': False, 'failed_checks': failures}))
                return 1
            if args.check_only:
                print(json.dumps({'csr': name, 'approved': False, 'eligible': True, 'node': args.node}))
                return 0
            patch = approval_patch(current, dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z'))
            kubectl('patch', 'csr', name, '--subresource=approval', '--type=json',
                    '--patch-file=/dev/stdin', data=json.dumps(patch).encode())
            print(json.dumps({'csr': name, 'approved': True, 'node': args.node,
                              'installed_verified': False}))
            return 0
        time.sleep(3)
    print(json.dumps({'node': args.node, 'approved': False, 'reason': 'no_pending_kubelet_serving_csr'}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
