#!/usr/bin/env python3
"""Extract tracked live chart packages and Flux composition without app history."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
GIT = '/mnt/c/Program Files/Git/cmd/git.exe' if str(ROOT).startswith('/mnt/c/') else 'git'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=pathlib.Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise RuntimeError('Destination must be new; never overwrite another repository')
    files = subprocess.check_output([GIT, 'ls-files'], cwd=ROOT, text=True).splitlines()
    helmreleases = []
    for file in files:
        if file.startswith('k8s-rewrite/flux/migration-releases/') and file.endswith('.yaml'):
            helmreleases.extend(o for o in yaml.safe_load_all((ROOT/file).read_text())
                                if o and o.get('kind') == 'HelmRelease' and 'chart' in o['spec'])
    if len(helmreleases) != 33:
        raise RuntimeError('Expected the 33 current application packages')
    destination.mkdir()
    packages = []
    for release in sorted(helmreleases, key=lambda o: o['metadata']['name']):
        old = release['spec']['chart']['spec']['chart'].removeprefix('./')
        name = release['metadata']['name']
        new = f'charts/{name}'
        digests = {}
        for file in files:
            if not file.startswith(old+'/'):
                continue
            relative = file[len(old)+1:]
            data = (ROOT/file).read_bytes()
            target = destination/new/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            digests[relative] = hashlib.sha256(data).hexdigest()
        if 'Chart.yaml' not in digests or 'values.yaml' not in digests:
            raise RuntimeError(f'Missing chart/values for {name}')
        packages.append({'name': name, 'source_path': old, 'path': new, 'copied_files_sha256': digests})
    for file in files:
        prefix = 'k8s-rewrite/flux/migration-releases/'
        if not file.startswith(prefix):
            continue
        target = destination/'flux/releases'/file[len(prefix):]
        target.parent.mkdir(parents=True, exist_ok=True)
        objects = list(yaml.safe_load_all((ROOT/file).read_text()))
        changed = False
        for obj in objects:
            if not obj or obj.get('kind') != 'HelmRelease' or 'chart' not in obj['spec']:
                continue
            obj['spec']['chart']['spec']['chart'] = './charts/'+obj['metadata']['name']
            obj['spec']['chart']['spec']['sourceRef']['name'] = 'branconet-charts'
            changed = True
        target.write_text(yaml.safe_dump_all(objects, sort_keys=False) if changed else (ROOT/file).read_text())
    (destination/'evidence').mkdir()
    record = {'source_repository': 'https://github.com/jtmb/branconet-homelab',
              'source_commit': subprocess.check_output([GIT, 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'application_packages': packages, 'chart_count': len(packages),
              'excluded': ['ets2', 'minecraft-exporter'],
              'application_source_copied': False, 'history_copied': False}
    (destination/'evidence/extraction.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({'destination': str(destination), 'chart_count': len(packages), 'source_commit': record['source_commit']}))

if __name__ == '__main__':
    main()
