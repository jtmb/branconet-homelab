#!/usr/bin/env python3
"""Exact official Bazarr native prestage; observe by default, no archives or credentials persisted."""
import hashlib,json,os,runpy,stat,sys,types,urllib.request
from pathlib import Path
ORIGINAL_SHA='0082325f8db7db2f7822bf3fbadb72d0b2d95b6db697fe84441eead3773b5e93'
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028/bazarr-prestage'
SCAN=H.parent/'bazarr-full-scan'
PIN={'repository':'ghcr.io/hotio/bazarr','root':'sha256:86b76c5c66a839ca6f6dd15ddb16b43f074dc71d41907b720e176bdede4b6562','measurementSHA256':'c3d1a751467c12a1944dbf7078bfdaa63a2b24454eb3e9b01d72700353779263','wholePeak':771870091,'layers':11}
BINDINGS={'metadata':'6550906025b0b460ef6ded8ae79adf2c316254d33bc99f9a681e704b88115236','receipt':'c0308f9314aee62d8621f61196321ba8e367af1c5462ea101c4f56df29b7cdb4','results':'24dd3da1c7069beee4fb6c4f003d21c6e49ecc0417829b4007ef13786cb84110','measurementSource':'50c96833e56b4a265e7de8a471b9cccd6a9ad715741f66a1146ad17adc5235ae'}
AMD64='sha256:ff7b10937c15036b011b33b1d524b92ead2415564bf1ab5415268b915d4b71f9'
CONFIG='sha256:a1cd55d365bb6cf370d6404df11576214ecd75c5135dd2cc3b0401252949f736'
def need(ok,reason):
 if not ok:raise ValueError(reason)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pinned(p,d):
 need(p.resolve()==p and sha(p)==d,'pinned_evidence:'+p.name);return json.loads(p.read_bytes())
def measurement(service,live_registry=True):
 need(service=='bazarr' and live_registry,'one_official_bazarr_live_registry_required')
 budget=pinned(SCAN/'oci-staging-budget.json',PIN['measurementSHA256'])
 receipt=pinned(SCAN/'apps-bazarr-current-r5-0/receipt.json',BINDINGS['receipt'])
 results=pinned(SCAN/'apps-bazarr-current-r5-0/results.json',BINDINGS['results'])
 approved=pinned(H/'approved-metadata.json',BINDINGS['metadata'])
 need(sha(SCAN/'measure-oci.py')==BINDINGS['measurementSource']==budget['sourceSHA256'],'measurement_source_authority')
 image=PIN['repository']+'@'+PIN['root']
 need(receipt['image']==image and receipt['scanComplete'] and receipt['scannerExitCode']==0 and receipt['inputHashesReverifiedAfterScan'] and not receipt['suppressionUsed'] and not receipt['containerCreated'] and receipt['resultsSHA256']==BINDINGS['results'],'complete_bound_unsuppressed_scan')
 need(receipt['knownExploitedCVEs']==[] and receipt['severityCounts']=={'HIGH':6,'MEDIUM':7,'CRITICAL':1},'exact_reviewed_remaining_findings')
 need(isinstance(results,list) and len(results)==2 and sum(len(x.get('Packages',[])) for x in results)==349,'complete_package_targets')
 need(budget['allCompressedDigestsAndDiffIDsVerified'] and budget['image']==PIN['root'] and budget['amd64']==AMD64 and len(budget['layers'])==PIN['layers'],'complete_full_diffid_measurement')
 need(approved['rootDigest']==PIN['root'] and approved['amd64ManifestDigest']==AMD64 and approved['configurationDigest']==CONFIG,'approved_root_manifest_config')
 need(budget['additionalFilesystemReserveBytes']==67108864 and budget['singleCopyContentAndUnpackBudgetBytes']==755092875,'original_full_staging_bound')
 previous='';layers=[]
 for i,row in enumerate(budget['layers']):
  need(row['compressedBytes']>0 and row['fullUncompressedTarBytes']>0 and row['regularFilesRounded4KiB']>=row['regularPayloadBytes'] and row['metadataReserve4KiBPerMember']==row['members']*4096,'all_original_per_layer_bounds')
  need(row['diffID']==approved['configuration']['rootfs']['diff_ids'][i] and row['compressedDigest']==approved['amd64Manifest']['layers'][i]['digest'] and row['compressedBytes']==approved['amd64Manifest']['layers'][i]['size'],'exact_compressed_and_diffid_descriptors')
  chain=row['diffID'] if not previous else 'sha256:'+hashlib.sha256((previous+' '+row['diffID']).encode()).hexdigest()
  upper=row['regularFilesRounded4KiB']+row['metadataReserve4KiBPerMember']+(budget['additionalFilesystemReserveBytes'] if i==len(budget['layers'])-1 else 0)
  layers.append({'digest':row['compressedDigest'],'compressedBytes':row['compressedBytes'],'diffID':row['diffID'],'chainID':chain,'parent':previous,'unpackedUpperBytes':upper});previous=chain
 need(sum(x['compressedBytes'] for x in layers)==budget['compressedContentBytes'],'full_compressed_budget')
 need(sum(x['unpackedUpperBytes'] for x in layers)==budget['allLayersUnpackedConservative4KiBBytes']+67108864,'full_allocation_budget')
 need(sum(x['compressedBytes']+x['unpackedUpperBytes'] for x in layers)+16777216==PIN['wholePeak'],'unchanged_full_peak_plus_native_metadata_allowance')
 base='https://ghcr.io/v2/hotio/bazarr';token_url='https://ghcr.io/token?service=ghcr.io&scope=repository:hotio/bazarr:pull'
 with urllib.request.urlopen(token_url,timeout=30) as response:raw=response.read(1024**2+1)
 need(len(raw)<=1024**2,'bounded_public_token');token=json.loads(raw)['token']
 headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json'};metadata=[]
 for route,digest,expected in [('/manifests/',PIN['root'],approved['rootManifest']),('/manifests/',AMD64,approved['amd64Manifest']),('/blobs/',CONFIG,approved['configuration'])]:
  with urllib.request.urlopen(urllib.request.Request(base+route+digest,headers=headers),timeout=30) as response:raw=response.read(1024**2+1)
  need(len(raw)<=1024**2 and 'sha256:'+hashlib.sha256(raw).hexdigest()==digest and json.loads(raw)==expected,'live_exact_official_metadata')
  metadata.append({'digest':digest,'compressedBytes':len(raw)})
 token=headers=None
 need(sum(x['compressedBytes'] for x in metadata)<=1024**2,'metadata_inside_fixed_allowance')
 need(approved['configuration']['architecture']=='amd64' and approved['configuration']['os']=='linux','linux_amd64_configuration')
 return {'service':'bazarr','image':image,'root':PIN['root'],'manifest':AMD64,'config':CONFIG,'layers':layers,'measurementSHA256':PIN['measurementSHA256'],'measurementSourceSHA256':BINDINGS['measurementSource'],'metadataSHA256':BINDINGS['metadata'],'registryMetadataVerified':True,'metadataBlobs':metadata,'wholePeakBytes':PIN['wholePeak'],'scanReceiptSHA256':BINDINGS['receipt'],'scanResultsSHA256':BINDINGS['results'],'remainingFindingsAcceptedAsZero':False}
def main():
 path=Path(__file__).resolve();repository=path.parents[5];original=path.parents[2]/'official_vendor_preload/files/controller.py'
 need(sha(original)==ORIGINAL_SHA,'unchanged_original_prestager_authority')
 original_source=original.read_text();core=runpy.run_path(str(original));g=core['main'].__globals__
 original_dispatch=core['dispatch'];original_save=core['save'];original_runpy=runpy.run_path
 need(core['CTR_SHA']=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743' and core['METADATA_ALLOWANCE']==16777216,'original_native_binary_and_allowance')
 stdin_requested='--password-stdin' in sys.argv
 if stdin_requested:sys.argv.remove('--password-stdin')
 def acquire_privilege_input():
  names=[x for x in ['BAZARR_PRELOAD_SUDO_PASSWORD','ANSIBLE_BECOME_PASSWORD'] if x in os.environ]
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
 prepared_input = stdin_requested or any(name in os.environ for name in ['BAZARR_PRELOAD_SUDO_PASSWORD','ANSIBLE_BECOME_PASSWORD'])
 pending_input = [acquire_privilege_input()] if prepared_input else []
 def privilege_input():
  if prepared_input:
   need(len(pending_input)==1,'protected_input_consumed_once')
   return pending_input.pop()
  return acquire_privilege_input()
 helper=repository/'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'
 def run_path(p):
  need(Path(p)==helper,'only_original_privilege_helper_adapter');return {'privilege_input':privilege_input}
 remote_source=original_source+'\nPINS = '+repr({'bazarr':PIN})+'\n'
 def dispatch(source,alias,phase,request,password):
  return original_dispatch(remote_source,alias,phase,request,password)
 def save(name,value):
  value={**value,'originalControllerSHA256':ORIGINAL_SHA,'bazarrEvidenceBindings':BINDINGS}
  if name=='ownership.json':value.update(owner='bazarr_vendor_preload',runtimeConsumer='Exact official Bazarr1.6.2 security refresh; no unrelated images')
  return original_save(name,value)
 g.update(PINS={'bazarr':PIN},H=H,__file__=str(path),measurement=measurement,dispatch=dispatch,save=save,runpy=types.SimpleNamespace(run_path=run_path))
 try:
  return core['main']()
 finally:
  pending_input.clear()
if __name__=='__main__':raise SystemExit(main())
