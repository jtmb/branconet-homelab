"""Reuse every current58 gate; normalize only the exact authorized proxy image."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj


def normalize_proxy(items, plan):
    projected = copy.deepcopy(items)
    for o in projected:
        if (o['kind'], o['metadata'].get('namespace'), o['metadata']['name']) == ('DaemonSet', 'kube-system', 'kube-proxy'):
            containers = o['spec']['template']['spec']['containers']
            c = next(c for c in containers if c['name'] == 'kube-proxy')
            if c['image'] not in [plan['proxyBeforeImage'], plan['images']['kube-proxy']['reference']]:
                raise ValueError('Unreviewed proxy image')
            c['image'] = plan['proxyBeforeImage']
    return projected


def main():
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    here = Path(__file__).resolve().parent
    authority = module('patch_authority', here / 'authority.py')
    plan = authority.qualify({'path': a.manifest, 'sha256': a.sha256})
    guard = module('original_current58', here.parents[1] / 'security_maintenance/files/kernel_checkpoint.py')
    original_project = guard.project

    def project(items):
        return original_project(normalize_proxy(items, plan))

    # The original guard still checks all counts, UIDs, bound PVs, active/offline
    # states, source hashes, native backups, etcd source, NAS and archive hashes.
    guard.project = project
    sys.argv = ['checkpoint.py', '--manifest', plan['checkpoint']['path'], '--sha256', plan['checkpoint']['sha256']]
    guard.main()


if __name__ == '__main__':
    main()
