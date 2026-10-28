"""Existing-release sidecar-only Helm patch, with original NAS identity checks.

Reuse the pinned existing SMB chart compatibility/storage-reader primitives.
No install, owner adoption, driver replacement, PV change or raw Helm export.
"""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
BASE_SOURCE_SHA = '23f473dc1595fc155c9b1c33ca725b83d9034cbfd9339eb1d033b469bbce3226'
CHART_SHA = '27116d0a703d9b7dee87ae65a0ffc95d47dfa4092b0191f1bb7e7cab79abb7f0'
IMAGES = {
    'nodeDriverRegistrar': 'registry.k8s.io/sig-storage/csi-node-driver-registrar:v2.18.0@sha256:b7fefd08651f00ac4df1a196ed4c621c2451fbb899297fe9fad9e36c667af0c0',
    'livenessProbe': 'registry.k8s.io/sig-storage/livenessprobe:v2.20.0@sha256:19f2cf2f40e1987c7943945deca5f65cd4e4bf5cc0657fc78a5df131861578e8',
}
SUFFIX = r'''
OLD_SMB=SMB;OLD_RESIZER=RESIZER;OLD_HP=HP
pairs={
 'registry.k8s.io/sig-storage/csi-node-driver-registrar:v2.17.0':req['images']['nodeDriverRegistrar'],
 'registry.k8s.io/sig-storage/livenessprobe:v2.19.0':req['images']['livenessProbe']}
base_clean=clean;phase='before'
def clean(o,images=False):
 d=base_clean(o,images)
 if images:
  for c in sum([d.get('spec',{}).get('template',{}).get('spec',{}).get(k,[])for k in ['containers','initContainers']],[]):
   for old,new in pairs.items():
    if c['image']in [old,new]:c['image']='REVIEWED_SIDECAR:'+old
  if d['kind']=='DaemonSet':
   field='deprecated.daemonset.template.generation';expected='3'if phase=='after'else'2'
   need(d['metadata']['annotations'].get(field)==expected,'exact_daemonset_revision')
   d['metadata']['annotations'][field]='2'
 return d
def metadata():return json.loads(helm('get','metadata',RELEASE,'-n',NS,'-o','json'))
def deployment_revision():
 d=kube('deployment','csi-smb-controller',NS)
 return int(d['metadata']['annotations']['deployment.kubernetes.io/revision'])
def runtime_ids():
 pods=kube('pods',ns=NS)['items'];out=[]
 for p in pods:
  owners=p['metadata'].get('ownerReferences',[])
  if not any(o['kind']=='DaemonSet'and o['name']=='csi-smb-node'for o in owners)and not any(c['name']=='smb'for c in p['spec']['containers']):continue
  if p['metadata'].get('deletionTimestamp'):continue
  for c in p['spec']['containers']:
   if c['image']not in req['images'].values():continue
   s=next(x for x in p['status']['containerStatuses']if x['name']==c['name']);candidate=next(x for x in req['candidates']if x['reference']==c['image'])
   need(s['ready']and s['restartCount']==0,'sidecar_not_stable')
   need(s['imageID'].split('@')[-1]in [candidate['amd64ManifestDigest'],c['image'].split('@')[-1]],'sidecar_runtime_digest')
   out.append({'podUID':p['metadata']['uid'],'node':p['spec']['nodeName'],'container':c['name'],'image':c['image'],'imageID':s['imageID'],'ready':True,'restarts':0})
 need(len(out)==7,'exact_seven_replacement_sidecars');return out
try:
 receipt['key_id']=mac('key-id',b'smb-sidecars')
 meta=metadata();need(meta['version']=='1.20.4'and meta['status']=='deployed','existing_chart_version')
 need(meta['revision']==(3 if req['action']=='verify'else 2),'existing_revision')
 hrs=kube('helmreleases.helm.toolkit.fluxcd.io')['items']
 need(not any(h['spec'].get('releaseName',h['metadata']['name'])==RELEASE and h['spec'].get('targetNamespace',h['metadata']['namespace'])==NS for h in hrs),'competing_flux_owner')
 old=documents(helm('get','manifest',RELEASE,'-n',NS));values=json.loads(helm('get','values',RELEASE,'-n',NS,'-o','json'));effective=json.loads(helm('get','values',RELEASE,'-n',NS,'--all','-o','json'))
 need(effective['linux']['enabled']and effective['windows']['enabled']and effective['windows']['useHostProcessContainers'],'preserve_platforms')
 receipt['helmVersion']=helm('version','--short').decode().strip();need(receipt['helmVersion'].startswith('v4.3.0+'),'helm_version')
 if req['action']=='verify':
  phase='after';state,workloads,mounts=observe(old,expected_new=True);approved=req['approval']
  need(state==approved['baseline']['state'],'preserved_state_changed')
  need(mac('sidecar-values',values)==req['applied']['valuesAfterHMAC'],'values_after_changed')
  need(mac('sidecar-new-manifest',old)==approved['baseline']['newManifestHMAC'],'reviewed_manifest_changed')
  need(deployment_revision()==approved['baseline']['controllerRevision']+1,'controller_revision_increment')
  receipt.update(status='passed',state=state,workloads=workloads,mounts=mounts,runtime=runtime_ids(),revision=3)
 else:
  state,workloads,mounts=observe(old,expected_new=False)
  chart=base64.b64decode(req['chart']);need(hashlib.sha256(chart).hexdigest()==req['chart_sha256'],'chart_integrity')
  chart=compatibility_chart(chart);fd=os.memfd_create('public-existing-smb-chart',0);os.write(fd,chart);os.lseek(fd,0,0)
  command=[HELM,'upgrade',RELEASE,'/proc/self/fd/'+str(fd),'-n',NS,'--reuse-values']
  for name,image in req['images'].items():command+=['--set-string','image.'+name+'.tag='+image.split(':',1)[1]]
  preview=json.loads(run(command+['--dry-run=server','--output=json'],timeout=150,fds=(fd,)));need(not preview.get('hooks'),'unexpected_hook')
  new=documents(preview['manifest']);need(set(old)==set(new)and len(old)==12,'resource_inventory_changed');diffs=[]
  for rid in old:
   for path,a,b in changes(old[rid],new[rid]):
    need(path[:3]==('spec','template','spec')and path[3]in ['containers','initContainers']and path[-1]=='image'and pairs.get(a)==b,'unreviewed_delta')
    diffs.append({'resource':rid,'path':'/'.join(path),'old':a,'new':b})
  receipt['manifestDiff']=diffs
  need(len(diffs)==4,'exact_four_image_fields')
  baseline={'state':state,'valuesHMAC':mac('sidecar-values',values),'oldManifestHMAC':mac('sidecar-old-manifest',old),'newManifestHMAC':mac('sidecar-new-manifest',new),'controllerRevision':deployment_revision()}
  receipt.update(baseline=baseline,manifestDiff=diffs,workloadsBefore=workloads,mountsBefore=mounts,revisionBefore=2)
  if req['action']=='apply':
   approved=req['approval'];need(approved['status']=='passed'and approved['helper_sha256']==req['helper_sha256']and approved['key_id']==receipt['key_id']and approved['baseline']==baseline,'approved_baseline_changed')
   receipt['upgrade_attempted']=True
   upgraded=json.loads(run(command+['--rollback-on-failure','--wait=watcher','--timeout=10m','--output=json'],timeout=700,fds=(fd,)));need(upgraded['version']==3,'revision_after')
   phase='after';after,workloads,mountsAfter=observe(new,expected_new=True);need(after==state,'native_or_resource_change')
   actual=json.loads(helm('get','values',RELEASE,'-n',NS,'-o','json'));expected=copy.deepcopy(values)
   for name,image in req['images'].items():expected.setdefault('image',{}).setdefault(name,{})['tag']=image.split(':',1)[1]
   need(actual==expected,'unreviewed_values_change');need(deployment_revision()==baseline['controllerRevision']+1,'controller_revision_increment')
   need(mountsAfter['coverage_nodes']>=mounts['coverage_nodes'],'mount_sample_regression')
   receipt.update(after=after,workloadsAfter=workloads,mountsAfter=mountsAfter,valuesAfterHMAC=mac('sidecar-values',actual),runtime=runtime_ids(),revisionAfter=3)
  receipt['status']='passed'
except Exception as e:receipt['error']=str(e)if isinstance(e,RuntimeError)else type(e).__name__
print(json.dumps(receipt,sort_keys=True))
'''

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['preflight', 'apply', 'verify'])
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--approved-sha256', default='')
    a = ap.parse_args()
    os.umask(0o077)
    assert ROOT.is_mount() and a.output_dir.resolve().is_relative_to(ROOT) and not a.output_dir.is_symlink()
    assert shutil.disk_usage('/mnt/c').free >= 15 * 1024**3 and shutil.disk_usage(ROOT).free >= 15 * 1024**3 + 64 * 1024**2
    source = Path(__file__).resolve().parents[5] / 'scripts/migration/patch-smb-helm.py'
    assert sha(source) == BASE_SOURCE_SHA
    tree = ast.parse(source.read_text())
    remote = next(ast.literal_eval(x.value) for x in tree.body if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REMOTE' for t in x.targets))
    remote = remote[:remote.index('def preflight():')] + SUFFIX
    chart = ROOT / 'public-inputs/csi-driver-smb/csi-driver-smb-1.20.4.tgz'
    assert sha(chart) == CHART_SHA
    a.output_dir.mkdir(mode=0o700, exist_ok=True)
    target = a.output_dir / (a.mode + '.json')
    assert not target.exists(), 'single_use_receipt_exists'
    candidates = json.loads((ROOT / 'platform-upstream-review-20261027/platform-csi-upstream-candidates.json').read_text())['images']
    own_sha = sha(Path(__file__))
    request = {'action': a.mode, 'helper_sha256': own_sha, 'key': (ROOT / 'acceptance-smb-20261025/hmac-key.hex').read_text().strip(),
               'images': IMAGES, 'candidates': candidates, 'chart': base64.b64encode(chart.read_bytes()).decode(), 'chart_sha256': CHART_SHA}
    if a.mode != 'preflight':
        preflight = a.output_dir / 'preflight.json'
        assert sha(preflight) == a.approved_sha256
        request['approval'] = json.loads(preflight.read_text())
        if a.mode == 'apply':
            with (a.output_dir / 'apply-started.json').open('x') as f:
                json.dump({'sourceSHA256': own_sha, 'preflightSHA256': a.approved_sha256}, f)
        else:
            request['applied'] = json.loads((a.output_dir / 'apply.json').read_text())
            assert request['applied']['status'] == 'passed'
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4', shlex.join(['python3', '-B', '-c', remote])]
    p = subprocess.run(cmd, input=json.dumps(request).encode(), capture_output=True, timeout=1000)
    assert p.returncode == 0, 'SSH_failed_do_not_replay_apply'
    d = json.loads(p.stdout)
    d['baseSourceSHA256'] = BASE_SOURCE_SHA
    d['plaintextValuesStored'] = False
    target.write_text(json.dumps(d, indent=2) + '\n')
    print(json.dumps({'mode': a.mode, 'status': d['status'], 'error': d.get('error'), 'receipt': str(target)}))
    assert d['status'] == 'passed'

if __name__ == '__main__':
    main()
