#!/usr/bin/env python3
"""Validate individual Helm packages, activation gates and staged manifests."""
import argparse
import json
import pathlib
import subprocess
import shutil
import tempfile
import hashlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--helm',default=str(pathlib.Path.home()/'.local/share/branconet-migration/bin/helm'))
    parser.add_argument('--allow-incomplete',action='store_true')
    args=parser.parse_args()
    results=[]
    temporary=tempfile.TemporaryDirectory(prefix='branconet-chart-validation-')
    for chart in sorted((ROOT/'k8s-rewrite/charts').rglob('Chart.yaml')):
        source=chart.parent
        directory=pathlib.Path(temporary.name)/source.relative_to(ROOT/'k8s-rewrite/charts')
        shutil.copytree(source,directory)
        fingerprint=hashlib.sha256()
        for file in sorted(directory.rglob('*')):
            if file.is_file():fingerprint.update(str(file.relative_to(directory)).encode()+b'\0'+file.read_bytes())
        values=yaml.safe_load((directory/'values.yaml').read_text())
        name=yaml.safe_load(chart.read_text())['name']
        lint=subprocess.run([args.helm,'lint',str(directory)],capture_output=True,text=True)
        blocked=subprocess.run([args.helm,'template',name,str(directory),'--set','enabled=true,migration.verified=false,migration.staging=false'],capture_output=True,text=True)
        rendered=subprocess.run([args.helm,'template',name,str(directory),'--set','enabled=true,migration.verified=true,replicaCount=0'],capture_output=True,text=True)
        objects=list(yaml.safe_load_all(rendered.stdout)) if rendered.returncode==0 else []
        objects=[o for o in objects if o]
        replicas_valid=all(isinstance(o['spec']['replicas'],int) for o in objects if o['kind'] in {'Deployment','StatefulSet'})
        identities=[(o['kind'],o['metadata'].get('namespace'),o['metadata']['name']) for o in objects]
        unique_resources=len(identities)==len(set(identities))
        unique_pod_lists=True
        for obj in objects:
            if obj['kind'] not in {'Deployment','StatefulSet','DaemonSet'}:continue
            pod=obj['spec']['template']['spec']
            volumes=[v['name'] for v in pod.get('volumes',[])]
            unique_pod_lists &= len(volumes)==len(set(volumes))
            for container in pod.get('containers',[])+pod.get('initContainers',[]):
                paths=[m['mountPath'] for m in container.get('volumeMounts',[])]
                unique_pod_lists &= len(paths)==len(set(paths))
        active_empty=not values['resources']
        private=subprocess.run([args.helm,'template',name,str(directory),'--set','enabled=true,migration.verified=false,migration.staging=true,replicaCount=0'],capture_output=True,text=True)
        private_objects=[o for o in yaml.safe_load_all(private.stdout) if o] if not private.returncode else []
        private_valid=private.returncode==0 and all(o['kind'] not in {'Ingress','IngressRoute'} and (o['kind']!='Service' or (o['spec'].get('type','ClusterIP')=='ClusterIP' and not o['spec'].get('externalIPs'))) for o in private_objects)
        result={'chart':str(source.relative_to(ROOT)), 'input_sha256':fingerprint.hexdigest(), 'lint_passed':lint.returncode==0,
                'activation_gate_enforced':blocked.returncode!=0, 'staged_render_passed':rendered.returncode==0,
                'replica_types_valid':replicas_valid, 'unique_resource_identities':unique_resources,
                'unique_pod_lists':unique_pod_lists, 'rendered_objects':len(objects),
                'implementation_incomplete':active_empty,
                'private_staging_without_external_routes_passed':private_valid,
                'application_accepted':False}
        results.append(result)
    temporary.cleanup()
    packaging=all(r['lint_passed'] and r['activation_gate_enforced'] and r['staged_render_passed'] and r['replica_types_valid'] and r['private_staging_without_external_routes_passed'] and r['unique_resource_identities'] and r['unique_pod_lists'] for r in results)
    complete=all(not r['implementation_incomplete'] for r in results)
    report={'packaging_passed':packaging,'all_manifests_implemented':complete,'application_acceptance':False,'charts':results}
    output=ROOT/'evidence/chart-validation.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'packaging_passed':packaging,'all_manifests_implemented':complete,'charts':len(results),'evidence':str(output)}))
    raise SystemExit(0 if packaging and (complete or args.allow_incomplete) else 1)

if __name__=='__main__':main()
