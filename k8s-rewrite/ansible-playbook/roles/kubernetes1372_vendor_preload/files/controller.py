#!/usr/bin/env python3
"""Four official Kubernetes1.37.2 images; aggregate observation then original per-image native guards."""
import hashlib,inspect,json,os,runpy,stat,sys,types,urllib.request
from pathlib import Path
ORIGINAL_SHA='0082325f8db7db2f7822bf3fbadb72d0b2d95b6db697fe84441eead3773b5e93'
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028/kubernetes1372-prestage'
SCAN=H.parent/'kubernetes1372-full-scan'
PINS={'kube-apiserver': {'repository': 'registry.k8s.io/kube-apiserver', 'root': 'sha256:3e563afb5cb5b72a10bac7012698dd09f5a42bde7d22de8d7d3c12e654df86b4', 'measurementSHA256': 'fa2b5556fbfaca91e084026aeffa8cad4b40b915ea847a1d7ea3cacaa9c4cc08', 'wholePeak': 227098647, 'layers': 15}, 'kube-controller-manager': {'repository': 'registry.k8s.io/kube-controller-manager', 'root': 'sha256:28e62daf706ed815a8bd1dd27b03294ba09421b2e1674e9a83bbac38e24ceb0c', 'measurementSHA256': 'fa2b5556fbfaca91e084026aeffa8cad4b40b915ea847a1d7ea3cacaa9c4cc08', 'wholePeak': 210015822, 'layers': 15}, 'kube-scheduler': {'repository': 'registry.k8s.io/kube-scheduler', 'root': 'sha256:028c847fc321b8a7f9787f7b1c0840f832d6b68439be2e5c09279ffb14203d6b', 'measurementSHA256': 'fa2b5556fbfaca91e084026aeffa8cad4b40b915ea847a1d7ea3cacaa9c4cc08', 'wholePeak': 175221577, 'layers': 15}, 'kube-proxy': {'repository': 'registry.k8s.io/kube-proxy', 'root': 'sha256:b2e075697d7ab4f0878775dff9e5dccf818b67644437175210ce72fc1ec70551', 'measurementSHA256': 'fa2b5556fbfaca91e084026aeffa8cad4b40b915ea847a1d7ea3cacaa9c4cc08', 'wholePeak': 206278705, 'layers': 3}}
BINDINGS={'kube-apiserver': {'index': 0, 'receipt': 'fb0cb71de5c13eeac59942d8a915bbad60510fbf71662b9a67f487f89ffb84db', 'results': 'e567af4b2a91e6176ba44237ecb5f182a5449b151d8e41939fe7e8a79ce89c45', 'severityCounts': {'HIGH': 5, 'LOW': 3, 'MEDIUM': 7, 'UNKNOWN': 6}, 'targetCount': 3, 'packageCount': 145, 'amd64': 'sha256:f3916d65eddfe52b6d21ff4a17abdf4c52589c8ef62ec7e0c17204f276cd8db6', 'config': 'sha256:7a918dfe486968064a41f0376e29517b68ae6fe75b78138941c7ba6607af5fe5'}, 'kube-controller-manager': {'index': 1, 'receipt': '021cda2700b7c863cfb525b8365df769624636c1c2450067417f126ae4297f72', 'results': '76ed2c54d36d52dfd65377ed353ecc361c39bab33611d426011edc05932ca3fe', 'severityCounts': {'HIGH': 5, 'LOW': 3, 'MEDIUM': 7, 'UNKNOWN': 6}, 'targetCount': 4, 'packageCount': 167, 'amd64': 'sha256:07fccf8e84f4cdc72c8e59f1a50da68f15acf1299e455004a944610aecac60c4', 'config': 'sha256:2db038c9db5097c8fd95b9fa1152b5d87642f987fe53612af5e93c2392f010b4'}, 'kube-scheduler': {'index': 2, 'receipt': '965ba4c14e3288616b200e221d36d9d997f5e397af0ad06856b1e6fefad3d90a', 'results': 'fd0379fc5a67c5c823fe3e5962fe5293573f1f514e9769f158079fccf0fbda93', 'severityCounts': {'HIGH': 5, 'LOW': 3, 'MEDIUM': 7, 'UNKNOWN': 6}, 'targetCount': 4, 'packageCount': 133, 'amd64': 'sha256:e5438c1bb8c569c41ad556d8a1e8eba44fc5b3cfe4da3adf2a17168102434074', 'config': 'sha256:20824b0c11f7d70ed7e6dd1c716d5cf88874ad77bebaa97c1fcd8bb0761045ff'}, 'kube-proxy': {'index': 3, 'receipt': 'c44eeb5667f9e6aa16b210bba7876710fb03357c81645333c4b093ce65255d6f', 'results': 'c44262d93235b243d36f4424e71a0039f66530e17dde2f5542f97f2bacd72852', 'severityCounts': {'HIGH': 6, 'LOW': 22, 'MEDIUM': 26, 'UNKNOWN': 6}, 'targetCount': 4, 'packageCount': 168, 'amd64': 'sha256:8c355aac6f4397e98a5462d4bb47b55386df688e6e1e46c67bf374155ac02c45', 'config': 'sha256:55b428162aa8c6cdde556e76ddc0b24cf733398fe215a833cbd0bf38738494e8'}}
FILES={'oci-metadata.json': '9f9c9741c4969f98dbfe5017925de02997dc5e044520670185c6269f1830e25b', 'oci-staging-budget.json': 'fa2b5556fbfaca91e084026aeffa8cad4b40b915ea847a1d7ea3cacaa9c4cc08', 'measure-oci.py': '8103926a9884cef25f6e28a1570020a712123d5c69c3e0b78f80d86f52e787d9', 'qualification-summary.json': 'eb07f6dd3a5475829112e537013a66211ab728a6fd11cefb0f79075187677831'}

def need(ok,reason):
 if not ok:raise ValueError(reason)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pinned(p,d):
 need(p.resolve()==p and sha(p)==d,'pinned_evidence:'+p.name);return json.loads(p.read_bytes())
def measurement(service,live_registry=True):
 need(service in PINS and live_registry,'finite_official_kubernetes_live_registry_required')
 pin=PINS[service];binding=BINDINGS[service];n=binding['index']
 allmeta=pinned(SCAN/'oci-metadata.json',FILES['oci-metadata.json']);allbudget=pinned(SCAN/'oci-staging-budget.json',FILES['oci-staging-budget.json'])
 approved=allmeta['images'][n];budget=allbudget['images'][n]
 receipt=pinned(SCAN/('apps-kubernetes1372-current-r5-'+str(n))/'receipt.json',binding['receipt']);results=pinned(SCAN/('apps-kubernetes1372-current-r5-'+str(n))/'results.json',binding['results'])
 qualification=pinned(SCAN/'qualification-summary.json',FILES['qualification-summary.json']);need(qualification['allComplete'] and len(qualification['images'])==4,'all_four_complete_scans')
 need(sha(SCAN/'measure-oci.py')==FILES['measure-oci.py']==allbudget['sourceSHA256'] and allbudget['metadataSHA256']==FILES['oci-metadata.json'],'measurement_source_authority')
 image=pin['repository']+'@'+pin['root']
 need(receipt['image']==image and receipt['scanComplete'] and receipt['scannerExitCode']==0 and receipt['inputHashesReverifiedAfterScan'] and not receipt['suppressionUsed'] and not receipt['containerCreated'] and receipt['resultsSHA256']==binding['results'],'complete_bound_unsuppressed_scan')
 need(receipt['knownExploitedCVEs']==[] and receipt['severityCounts']==binding['severityCounts'],'exact_reviewed_remaining_findings')
 need(isinstance(results,list) and len(results)==binding['targetCount'] and sum(len(x.get('Packages') or []) for x in results)==binding['packageCount'],'complete_package_targets')
 need(approved['name']==budget['name']==service and budget['allCompressedDigestsAndDiffIDsVerified'] and budget['image']==image and budget['amd64']==binding['amd64'] and len(budget['layers'])==pin['layers'],'complete_full_diffid_measurement')
 need(approved['rootDigest']==pin['root'] and approved['amd64Digest']==binding['amd64'] and approved['configDigest']==binding['config'],'approved_root_manifest_config')
 need(budget['additionalFilesystemReserveBytes']==67108864 and budget['singleCopyContentAndUnpackBudgetBytes']+16777216==pin['wholePeak'],'original_full_staging_bound')
 previous='';layers=[]
 for i,row in enumerate(budget['layers']):
  need(row['compressedBytes']>0 and row['fullUncompressedTarBytes']>0 and row['regularFilesRounded4KiB']>=row['regularPayloadBytes'] and row['metadataReserve4KiBPerMember']==row['members']*4096,'all_original_per_layer_bounds')
  need(row['diffID']==approved['config']['rootfs']['diff_ids'][i] and row['compressedDigest']==approved['manifest']['layers'][i]['digest'] and row['compressedBytes']==approved['manifest']['layers'][i]['size'],'exact_compressed_and_diffid_descriptors')
  chain=row['diffID'] if not previous else 'sha256:'+hashlib.sha256((previous+' '+row['diffID']).encode()).hexdigest();need(chain==budget['chainIDs'][i],'original_chain_identity')
  upper=row['regularFilesRounded4KiB']+row['metadataReserve4KiBPerMember']+(67108864 if i==len(budget['layers'])-1 else 0)
  layers.append({'digest':row['compressedDigest'],'compressedBytes':row['compressedBytes'],'diffID':row['diffID'],'chainID':chain,'parent':previous,'unpackedUpperBytes':upper});previous=chain
 need(sum(x['compressedBytes'] for x in layers)==budget['compressedContentBytes'],'full_compressed_budget')
 need(sum(x['unpackedUpperBytes'] for x in layers)==budget['allLayersUnpackedConservative4KiBBytes']+67108864,'full_allocation_budget')
 need(sum(x['compressedBytes']+x['unpackedUpperBytes'] for x in layers)+16777216==pin['wholePeak'],'unchanged_full_peak_plus_native_metadata_allowance')
 headers={'Accept':'application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json'};metadata=[];base='https://registry.k8s.io/v2/'+service
 for route,digest,expected in [('/manifests/',pin['root'],approved['index']),('/manifests/',binding['amd64'],approved['manifest']),('/blobs/',binding['config'],approved['config'])]:
  with urllib.request.urlopen(urllib.request.Request(base+route+digest,headers=headers),timeout=30) as response:raw=response.read(1024**2+1)
  need(len(raw)<=1024**2 and 'sha256:'+hashlib.sha256(raw).hexdigest()==digest and json.loads(raw)==expected,'live_exact_official_metadata');metadata.append({'digest':digest,'compressedBytes':len(raw)})
 need(sum(x['compressedBytes'] for x in metadata)<=1024**2,'metadata_inside_fixed_allowance')
 need(approved['config']['architecture']=='amd64' and approved['config']['os']=='linux','linux_amd64_configuration')
 return {'service':service,'image':image,'root':pin['root'],'manifest':binding['amd64'],'config':binding['config'],'layers':layers,'measurementSHA256':FILES['oci-staging-budget.json'],'measurementSourceSHA256':FILES['measure-oci.py'],'metadataSHA256':FILES['oci-metadata.json'],'registryMetadataVerified':True,'metadataBlobs':metadata,'wholePeakBytes':pin['wholePeak'],'scanReceiptSHA256':binding['receipt'],'scanResultsSHA256':binding['results'],'remainingFindingsAcceptedAsZero':False}

def main():
 path=Path(__file__).resolve();repository=path.parents[5];original=path.parents[2]/'official_vendor_preload/files/controller.py'
 need(sha(original)==ORIGINAL_SHA,'unchanged_original_prestager_authority')
 original_source=original.read_text();core=runpy.run_path(str(original));g=core['main'].__globals__
 # This finite successor runs AFTER the verified kernel202 maintenance. Keep
 # the hash-pinned original and every cluster guard; advance only its exact
 # kernel equality, never accept an arbitrary version or weaken disk checks.
 cluster_source=inspect.getsource(core['cluster'])
 need(cluster_source.count("'5.15.0-198-generic'")==1,'exact_original_kernel_equality')
 exec(compile(cluster_source.replace("'5.15.0-198-generic'","'5.15.0-202-generic'"),str(path)+':kernel202-cluster','exec'),g)
 core['cluster']=g['cluster']
 original_dispatch=core['dispatch'];original_save=core['save'];original_runpy=runpy.run_path
 need(core['CTR_SHA']=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743' and core['METADATA_ALLOWANCE']==16777216,'original_native_binary_and_allowance')
 stdin_requested='--password-stdin' in sys.argv
 if stdin_requested:sys.argv.remove('--password-stdin')
 def acquire_privilege_input():
  names=[x for x in ['KUBERNETES1372_PRELOAD_SUDO_PASSWORD','ANSIBLE_BECOME_PASSWORD'] if x in os.environ]
  need(len(names)<=1 and not(stdin_requested and names),'one_privilege_input_source')
  if stdin_requested:
   need(not sys.stdin.isatty(),'protected_pipe_or_file_stdin_required')
   mode=os.fstat(sys.stdin.fileno());need(stat.S_ISFIFO(mode.st_mode) or (stat.S_ISREG(mode.st_mode) and mode.st_uid==os.getuid() and not mode.st_mode&0o077),'protected_stdin_permissions')
   raw=sys.stdin.buffer.readline(130).removesuffix(b'\n')
  elif names:raw=os.environ.pop(names[0]).encode()
  else:return original_runpy(str(repository/'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))['privilege_input']()
  need(0<len(raw)<=128 and b'\n' not in raw and b'\r' not in raw and b'\0' not in raw,'bounded_privilege_input');return raw
 # SSH GETs in the preserved controller inherit stdin. Consume the protected
 # line before those subprocesses can drain it; also remove env input before
 # child processes inherit the environment. Never store input outside RAM.
 prepared_input = stdin_requested or any(name in os.environ for name in ['KUBERNETES1372_PRELOAD_SUDO_PASSWORD','ANSIBLE_BECOME_PASSWORD'])
 pending_input = [acquire_privilege_input()] if prepared_input else []
 def privilege_input():
  if prepared_input:
   need(len(pending_input)==1,'protected_input_consumed_once')
   return pending_input.pop()
  return acquire_privilege_input()
 helper=repository/'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'
 def run_path(p):
  need(Path(p)==helper,'only_original_privilege_helper_adapter');return {'privilege_input':privilege_input}
 remote_source=original_source+'\nPINS = '+repr(PINS)+'\n'
 aggregate_checked=[False]
 def dispatch(source,alias,phase,request,password):
  if not aggregate_checked[0]:
   need(phase=='observe','aggregate_observation_before_any_stage')
   plans={service:measurement(service) for service in PINS}
   live=core['cluster']();need(core['same_controls'](request['cluster'],live),'aggregate_original_cluster_controls')
   nodes={}
   for node in core['NODES']:
    observations={service:original_dispatch(remote_source,node,'observe',{'node':node,'plan':plan,'cluster':live},password) for service,plan in plans.items()}
    values=list(observations.values());first=values[0]
    need(all(x['continuity']==first['continuity'] and x['rootUUID']==first['rootUUID'] and x['capacityBytes']==first['capacityBytes'] for x in values),'aggregate_same_node_runtime_and_filesystem')
    peak=sum(x['missingPeakBytes'] for x in values)
    free=min(x['freeBytes'] for x in values);available=min(x['availableBytes'] for x in values);floor=max(x['floorAndMarginBytes'] for x in values)
    nodes[node]={'observations':observations,'conservativeMissingPeakBytes':peak,'freeBytes':free,'availableBytes':available,'floorAndMarginBytes':floor,'fits':free>=floor+peak and available>=core['AVAILABLE_FLOOR']+peak}
   after=core['cluster']();need(core['same_controls'](live,after),'aggregate_cluster_controls_preserved')
   name='aggregate-four-images-'+core['uuid'].uuid4().hex+'.json'
   save(name,{'plans':plans,'nodes':nodes,'clusterBefore':live,'clusterAfter':after,'allFit':all(x['fits'] for x in nodes.values()),'deduplicationDiscountUsed':False})
   need(all(x['fits'] for x in nodes.values()),'aggregate_all_four_images_all_three_nodes_fit_before_any_pull')
   aggregate_checked[0]=True
  return original_dispatch(remote_source,alias,phase,request,password)
 def save(name,value):
  value={**value,'originalControllerSHA256':ORIGINAL_SHA,'kubernetes1372EvidenceBindings':BINDINGS}
  if name=='ownership.json':value.update(owner='kubernetes1372_vendor_preload',runtimeConsumer='Four exact official Kubernetes1.37.2 images; no unrelated images')
  return original_save(name,value)
 g.update(PINS=PINS,H=H,__file__=str(path),measurement=measurement,dispatch=dispatch,save=save,runpy=types.SimpleNamespace(run_path=run_path))
 try:
  return core['main']()
 finally:
  pending_input.clear()
if __name__=='__main__':raise SystemExit(main())
