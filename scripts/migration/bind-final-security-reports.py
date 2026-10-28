"""Bind current immutable runtime digests to complete hash-verified r5 reports."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
S=F/'security-review-20261026'
H=F/'platform-upstream-review-20261027/final-fleet-post-security-20261028'

def sha(p):
    with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    inventory=json.loads((H/'inventory.json').read_bytes())
    original=json.loads((S/'fleet-r5-final-coverage.json').read_bytes())
    scans={x['reference'].split('@')[-1]:x for x in original['images']}
    for i in range(2):
        p=S/('apps-vendor-candidates-r5-'+str(i))/'receipt.json';r=json.loads(p.read_bytes())
        assert r['scanComplete'] and r['scannerExitCode']==0 and r['inputHashesReverifiedAfterScan'] and r['databaseManifestDigest']==original['databaseManifestDigest']
        scans[r['image'].split('@')[-1]]={'reference':r['image'],'receipt':str(p),'receiptSHA256':sha(p),'results':str(p.with_name('results.json')),'resultsSHA256':r['resultsSHA256'],'severityCounts':r['severityCounts'],'knownExploitedCVEs':r['knownExploitedCVEs'],'coverage':'complete'}
    owners=collections.defaultdict(list)
    for p in inventory['pods']:
        if p['phase']!='Running' or p['deleting']:continue
        for c in p['containers']:
            assert c['imageID'], 'running_pod_container_without_runtime_identity'
            owners[c['imageID'].split('@')[-1]].append({'namespace':p['namespace'],'pod':p['name'],'podUID':p['uid'],'node':p['node'],'container':c['name'],'kind':c['kind'],'specification':c['image'],'runtimeImageID':c['imageID'],'ready':c['ready'],'restartCount':c['restartCount']})
    assert set(owners)<=set(scans), 'unscanned_new_runtime_digest'
    totals=collections.Counter();cves=set();images=[];kev=set()
    for digest,consumers in sorted(owners.items()):
        scan=scans[digest];p=Path(scan['receipt']);rp=Path(scan['results'])
        assert scan['coverage']=='complete' and sha(p)==scan['receiptSHA256'] and sha(rp)==scan['resultsSHA256']
        totals.update(scan['severityCounts']);kev.update(scan['knownExploitedCVEs'])
        rows=json.loads(rp.read_bytes())
        if isinstance(rows,dict):rows=rows.get('Results',[])
        cves.update(v['VulnerabilityID']for t in rows for v in t.get('Vulnerabilities',[])or [])
        images.append({k:scan[k]for k in ['reference','receipt','receiptSHA256','results','resultsSHA256','severityCounts','knownExploitedCVEs']}|{'runtimeDigest':digest,'currentOwners':consumers})
    unavailable=[c for c in inventory['controllers']if c['kind']in ['Deployment','StatefulSet','DaemonSet']and(c['replicasDesired']or c['desiredNumberScheduled']or 0)!=(c['readyReplicas']or c['numberReady']or 0)]
    assert not unavailable and len(inventory['nodes'])==3 and all(c['phase']=='Bound'for c in inventory['claims'])
    result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inventoryUTC':inventory['UTC'],'inventorySHA256':sha(H/'inventory.json'),'originalCoverageSHA256':sha(S/'fleet-r5-final-coverage.json'),'databaseManifestDigest':original['databaseManifestDigest'],'databaseNextUpdate':original['databaseNextUpdate'],'runtimeDigestCount':len(owners),'completeScans':len(images),'uncovered':[],'severityPackageRows':dict(totals),'uniqueCVECount':len(cves),'knownExploitedCVEs':sorted(kev),'images':images,'unavailableDesiredControllers':unavailable,'boundClaims':len(inventory['claims']),'SMBVolumes':sum(x['driver']=='smb.csi.k8s.io'for x in inventory['persistentVolumes']),'securityAcceptance':False,'absenceOfZeroDaysClaimed':False,'suppressionUsed':False,'scope':'Current runtime image bytes; mounted data and dependencies are separately checked, not inferred from image scans. Existing vendor and BORTUS owner exceptions remain.'}
    with (H/'security-bindings.json').open('x')as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items()if k not in ['images','scope']}))

if __name__=='__main__':main()
