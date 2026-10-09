#!/usr/bin/env python3
"""Deploy the delivered app privately after infrastructure/Secret preflight."""
import datetime
import json
import pathlib
import subprocess
import tempfile
import shutil
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    distribution=json.loads((ROOT/'evidence/bortus-image-distribution.json').read_text())
    if len(distribution['nodes'])!=3 or not all(n['tag_present_in_runtime'] for n in distribution['nodes']):raise SystemExit('Three-node image verification required')
    if len({n['runtime_manifest_digest'] for n in distribution['nodes']})!=1:raise SystemExit('Runtime image digests differ')
    storage=json.loads((ROOT/'evidence/storage-proof.json').read_text())
    if not all(storage[k] for k in ['luks_header_verified','cross_node_reattachment_passed','older_snapshot_content_verified']):raise SystemExit('Storage proof required')
    imported=json.loads((ROOT/'evidence/native-secret-import.json').read_text())
    if not imported['executed'] or not all(s['readback_equal'] for s in imported['secrets']):raise SystemExit('Native import verification required')
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    helm=[str(RUNTIME/'bin/helm'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    with tempfile.TemporaryDirectory(prefix='bortus-staging-') as work:
        chart=pathlib.Path(work)/'chart'
        shutil.copytree(ROOT/'k8s-rewrite/charts/apps/bortus',chart)
        arguments=['--set','enabled=true,migration.staging=true,replicaCount=1']
        rendered=subprocess.run([*helm,'template','bortus',str(chart),'-n','bortus',*arguments],capture_output=True,text=True,check=True)
        resources=[r for r in yaml.safe_load_all(rendered.stdout) if r]
        if any(r['kind'] in {'Ingress','IngressRoute'} for r in resources):raise SystemExit('Staging must remain private')
        subprocess.run([*kube,'apply','--dry-run=server','-f','-'],input=rendered.stdout,text=True,capture_output=True,check=True)
        result=subprocess.run([*helm,'upgrade','--install','bortus',str(chart),'-n','bortus',*arguments,'--wait','--timeout','8m'],capture_output=True,text=True)
        report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release':'bortus','namespace':'bortus','staging_only':True,'public_ingress':False,'application_accepted':False,'server_dry_run_passed':True,'helm_exit_code':result.returncode}
        (ROOT/'evidence/bortus-staging.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
        if result.returncode:raise SystemExit('BORTUS staging did not become ready; inspect events/probes without exposing credentials')

if __name__=='__main__':main()
