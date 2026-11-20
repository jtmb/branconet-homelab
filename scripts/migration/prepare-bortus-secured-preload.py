"""Specialize the proven sealed-memory receiver without altering original provenance."""
import hashlib,json,os,re
from pathlib import Path
S=Path(__file__).parent
O=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
def need(v):
 if not v:raise RuntimeError('secured_receiver_preparation_failed')
def main():
 a=json.loads((O/'secured-image-archive.json').read_bytes());p=json.loads((O/'publication.json').read_bytes());need(a['all_blob_hashes_verified'] and a['allowed_runtime_paths_only'] and p['manifest']==a['manifest'] and p['config']==a['config'] and p['state']=='published-private')
 node=(S/'bortus-qualified-preload-node.py').read_text()
 for key,value in {'SOURCE':a['source'],'MANIFEST':a['manifest'],'CONFIG':a['config'],'ARCHIVE_SHA':a['archive_sha256'],'ARCHIVE_BYTES':a['archive_bytes'],'MAX_IMPORT_BYTES':a['import_peak_bound']}.items():
  node,count=re.subn(r'^'+key+r' = .+$',key+' = '+repr(value),node,flags=re.M);need(count==1)
 node=node.replace("== 9)","== "+str(a['layer_count'])+")").replace('all_nine_layer_blobs_verified','all_layer_blobs_verified')
 node=node.replace('        if existing is None:\n', '''        if existing is None:
            parent_ref = 'docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
            need(parent_ref in metadata(['images', 'check', '--quiet']).decode().splitlines())
            parent = content(parent_ref.split('@')[1])
            need(parent['config']['digest'] == 'sha256:42e3a1a9e6fe5cd3c9912262b0cbeaca9a8cdff7b7b1891392eb100127d84698' and len(parent['layers']) == 9)
''')
 node=node.replace('Receive only the published 12dce115 image','Receive only the qualified secured image').replace('then the original OCI archive','then the verified secured OCI archive')
 launcher=(S/'preload-qualified-bortus-image.py').read_text().replace('bortus-qualified-preload-node.py','bortus-secured-preload-node.py').replace("ROOT = publisher.ROOT",'ROOT = Path('+repr(str(O))+')').replace("ARCHIVE = ROOT.parents[1] / 'release-v2-12dce115-inputs/candidate-pod-summary-root.oci.tar'","ARCHIVE = ROOT / 'secured-image.oci.tar'").replace('all_nine_layer_blobs_verified','all_layer_blobs_verified')
 old="""    need(publication.get('digest') == node.MANIFEST and
         publication.get('state') == 'published-private-immutable-artifact' and
         publication.get('remote_config_verified') is True and
         publication.get('remote_layer_digests_verified') is True)"""
 new="""    need(publication.get('manifest') == node.MANIFEST and
         publication.get('state') == 'published-private' and
         publication.get('remote_config_and_graph_verified') is True and
         publication.get('current_unfiltered_security_scan_passed') is True)"""
 need(old in launcher);launcher=launcher.replace(old,new)
 for name,text in [('bortus-secured-preload-node.py',node),('preload-secured-bortus-image.py',launcher)]:
  compile(text,name,'exec');path=S/name;need(not path.exists());path.write_text(text)
 (O/'secured-preload-source.json').write_text(json.dumps({'source':a['source'],'manifest':a['manifest'],'layer_count':a['layer_count'],'import_peak_bound':a['import_peak_bound'],'original_provenance_files_unchanged':True,'files':{n:hashlib.sha256((S/n).read_bytes()).hexdigest()for n in ['bortus-secured-preload-node.py','preload-secured-bortus-image.py']}}))
 print(json.dumps({'prepared':True,'layer_count':a['layer_count'],'import_peak_bound':a['import_peak_bound']}))
if __name__=='__main__':main()
