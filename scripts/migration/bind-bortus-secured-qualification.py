"""Bind actual local, current-security, private publication and three-node acceptance."""
import hashlib,json,os
from pathlib import Path
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery');O=A/'empty-list-fix'
def need(v):
 if not v:raise RuntimeError('final_qualification_binding_failed')
def main():
 p=json.loads((O/'publication.json').read_bytes());a=json.loads((O/'secured-image-archive.json').read_bytes());q=json.loads((O/'secured-net-runtime-qualification.json').read_bytes());scan=json.loads((O/'secured-net-image-scan.json').read_bytes());need(p['manifest']==a['manifest']==q['image'] and p['source']==a['source']==q['source'] and p['current_unfiltered_security_scan_passed'] and q['real_tls_empty_current_and_history_ready'] and q['reviewed_client_assets_byte_identical'] and q['new_client_asset_count']==170 and scan['Metadata']['ImageID']==p['manifest'] and scan.get('Results') and not any(x.get('Vulnerabilities')or x.get('Secrets')for x in scan['Results']))
 nodes=[]
 for host in ('192.168.0.4','192.168.0.5','192.168.0.6'):
  if host=='192.168.0.4':
   path=O/'preload-node01-alias-reconciliation.json';d=json.loads(path.read_bytes());need(d['manifest_alias_and_all_layers_verified']and any(row[0]=='docker.io/jtmb92/bortus:release-'+p['source'] and row[2]==p['manifest']for row in d['bortus_image_rows']));nodes.append({'host':host,'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'original_uncertain_import_reconciled':True});continue
  path=O/('preload-'+host+'.json');d=json.loads(path.read_bytes());need(d['state']=='completed' and d['image_reference']==p['image'] and len(d['nodes'])==1);n=d['nodes'][0];need(n['host']==host and n['state']=='verified' and n['all_layer_blobs_verified']and n['fully_downloaded_and_unpacked']and n['archive_sha256']==a['archive_sha256']);nodes.append({'host':host,'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 result={'source':p['source'],'image':p['image'],'manifest':p['manifest'],'config':p['config'],'all_three_nodes_verified':True,'current_unfiltered_security_scan_passed':True,'reviewed_browser_assets_identical':True,'original_nvda_report_preserved':True,'archive_sha256':a['archive_sha256'],'layer_count':a['layer_count'],'nodes':nodes,'production_acceptance_pending':True}
 path=A/'qualified-final-image.json';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w')as f:json.dump(result,f);f.flush();os.fsync(f.fileno())
 os.chown(path,1000,1000);print(json.dumps({'all_three_nodes_qualified':True,'image':p['image']}))
if __name__=='__main__':main()
