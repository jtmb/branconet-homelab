#!/usr/bin/env python3
"""Turn existing manifests into individually reviewable, gated Helm charts.

Never activates releases or copies environment values from Docker into Git.
Live images are taken from the sanitized pre-maintenance inventory. Missing
applications remain explicit scaffolds until their manifests are implemented.
"""
import json
import pathlib
import re
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHARTS = ROOT / 'k8s-rewrite/charts'
TEMPLATE = '''{{- if .Values.enabled }}
{{- if not .Values.migration.verified }}
{{- fail "Migration storage, secrets and cutover checks must be verified before activation" }}
{{- end }}
{{- range .Values.resources }}
{{- if or (eq .kind "Deployment") (eq .kind "StatefulSet") }}
{{- $_ := set .spec "replicas" (int $.Values.replicaCount) }}
{{- end }}
---
{{ tpl (toYaml .) $ }}
{{- end }}
{{- end }}
'''

def main():
    register = json.loads((ROOT / 'evidence/service-register.json').read_text())
    grouped = {}
    for entry in register['entries']:
        chart = entry.get('chart')
        if chart and not chart.startswith('@'):
            grouped.setdefault(chart, []).append(entry)
    report = []
    for relative, entries in sorted(grouped.items()):
        directory = CHARTS / relative
        if (directory / 'Chart.yaml').exists():
            report.append({'chart': relative, 'result': 'existing-chart-preserved'})
            continue
        directory.mkdir(parents=True, exist_ok=True)
        resources = []
        for path in sorted(directory.glob('*.yaml')):
            if path.name in {'kustomization.yaml', 'namespace.yaml', 'values.yaml'}:
                continue
            resources.extend(o for o in yaml.safe_load_all(path.read_text()) if o)
        live = next((e for e in entries if e['source_type'] in {'swarm', 'standalone'}), None)
        live_image = (live or {}).get('source_image') or (live or {}).get('source_instance', {}).get('image')
        source_keys = (live or {}).get('environment_keys') or (live or {}).get('source_instance', {}).get('environment_keys', [])
        name = re.sub('[^a-z0-9-]', '-', directory.name.lower())
        namespace = entries[0].get('namespace') or name
        for obj in resources:
            if obj.get('kind') not in {'Deployment', 'StatefulSet', 'DaemonSet'}:
                continue
            if obj['kind'] != 'DaemonSet':
                obj['spec']['replicas'] = 0
            containers = obj['spec']['template']['spec']['containers']
            if live_image and len(containers) == 1:
                containers[0]['image'] = '{{ .Values.image }}'
                if source_keys:
                    # Runtime env is imported into Kubernetes, never persisted here.
                    containers[0].pop('env', None)
                    containers[0]['envFrom'] = [{'secretRef': {'name': '{{ .Values.environmentSecret }}'}}]
        values = {
            'enabled': False, 'replicaCount': 0,
            'image': live_image or '', 'environmentSecret': name + '-runtime',
            'migration': {
                'verified': False,
                'state': 'manifest-review-pending' if resources else 'manifest-implementation-required',
                'sources': [e['source'] for e in entries],
                'requiredEnvironmentKeys': source_keys,
                'storageSizingVerified': False,
                'nativeSecretsImported': False,
                'applicationChecksPassed': False,
            },
            'resources': resources,
        }
        (directory / 'Chart.yaml').write_text(yaml.safe_dump({'apiVersion':'v2', 'name':name, 'description':'Individual migration chart; inactive until verified', 'type':'application', 'version':'0.1.0'}, sort_keys=False))
        (directory / 'values.yaml').write_text(yaml.safe_dump(values, sort_keys=False))
        (directory / 'templates').mkdir(exist_ok=True)
        (directory / 'templates/resources.yaml').write_text(TEMPLATE)
        report.append({'chart':relative, 'manifest_count':len(resources), 'state':values['migration']['state'], 'live_image_pinned':bool(live_image)})
    output = ROOT / 'evidence/chart-preparation.json'
    output.write_text(json.dumps({'charts':report, 'deployed':False}, indent=2)+'\n')
    print(json.dumps({'charts':len(report), 'evidence':str(output), 'deployed':False}))

if __name__ == '__main__':
    main()
