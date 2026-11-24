"""Publish the qualified transport-only derivative to the existing private repository."""
import hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 b=load('publish_fix_build','build-bortus-empty-list-fix.py');p=load('publish_fix_registry','publish-qualified-bortus-image.py');out=b.OUT
 b.need(os.geteuid()==0 and not (out/'publication.json').exists())
 build=json.loads((out/'secured-net-build.json').read_bytes());source=build['source'];tag=build['tag'];b.need(build['state']=='built')
 q=json.loads((out/'secured-net-runtime-qualification.json').read_bytes());b.need(q['state']=='completed' and q['real_tls_empty_current_and_history_ready'] and q['reviewed_client_assets_byte_identical'] and q['native_runtime_security_patches_applied'])
 current=json.loads((out/'secured-net-image-scan.json').read_bytes());b.need(current['ArtifactName']==tag and current.get('Results') and not any(r.get('Vulnerabilities') or r.get('Secrets') for r in current.get('Results',[])))
 archive=json.loads((out/'secured-image-archive.json').read_bytes());b.need(archive['allowed_runtime_paths_only'] and archive['all_blob_hashes_verified'])
 image=json.loads(p.command(['docker','image','inspect',tag]))[0];b.need(image['Id']==q['image']==archive['manifest'] and image['Config']['Labels']['org.opencontainers.image.revision']==source)
 b.need(current['Metadata']['ImageID'] in (image['Id'],archive['config']))
 helper=ROOT/'windows-docker-credential-bortus.py';p.verify_private_repository(helper);token=p.registry_token(helper);prior=p.document(token,'release-'+source,missing=True)
 b.need(prior is None)
 client=out/'publication-client';b.need(not client.exists());(client/'bin').mkdir(parents=True,mode=0o700);(client/'config').mkdir(mode=0o700);(client/'tmp').mkdir(mode=0o700)
 try:
  windows=p.command(['wslpath','-w',str(helper)]).decode().strip();launcher=client/'bin/docker-credential-bortus-windows'
  launcher.write_text('#!/usr/bin/python3\nimport subprocess,sys\np=subprocess.run('+repr([p.PYTHON,'-I','-B',windows])+'+sys.argv[1:],input=sys.stdin.buffer.read(4097),stdout=sys.stdout.buffer,stderr=subprocess.DEVNULL)\nraise SystemExit(p.returncode)\n');launcher.chmod(0o700);p.write(client/'config/config.json',{'credsStore':'bortus-windows'})
  env=dict(os.environ,DOCKER_CONFIG=str(client/'config'),PATH=str(client/'bin')+':/usr/local/bin:/usr/bin:/bin',TMPDIR=str(client/'tmp'))
  with (out/'private-push.log').open('xb') as log:result=subprocess.run(['docker','push',tag],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
  b.need(result.returncode==0);token=p.registry_token(helper);remote=p.document(token,'release-'+source);descriptor=remote['value'];config=p.document(token,descriptor['config']['digest'],kind='blobs')
  b.need(config['value']['config']['Labels']==image['Config']['Labels'] and config['value']['rootfs']['diff_ids']==image['RootFS']['Layers'] and config['value']['os']=='linux' and config['value']['architecture']=='amd64')
  parent=p.document(token,b.BASE.split('@')[1]);parent_config=p.document(token,parent['value']['config']['digest'],kind='blobs');parent_diff=parent_config['value']['rootfs']['diff_ids'];b.need(config['value']['rootfs']['diff_ids'][:len(parent_diff)]==parent_diff)
  receipt={'state':'published-private','source':source,'image':'docker.io/jtmb92/bortus@'+remote['digest'],'manifest':remote['digest'],'config':descriptor['config']['digest'],'layers':descriptor['layers'],'parent':b.BASE,'local_image':image['Id'],'remote_config_and_graph_verified':True,'private_readback':True,'credentials_persisted':False,'production_deployed':False,'current_unfiltered_security_scan_passed':True,'vulnerabilities':0,'secrets':0,'earlier_failed_scan_preserved':'image-scan.json'}
  p.write(out/'publication.json',receipt);print(json.dumps({k:receipt[k] for k in ('state','source','image','config')}))
 finally:
  b.need(client.resolve().parent==out and not client.is_symlink());shutil.rmtree(client)
if __name__=='__main__':main()
