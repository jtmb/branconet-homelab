#!/usr/bin/env python3
"""Publish the unchanged qualified BORTUS image privately; never deploy it."""
import argparse,base64,datetime,fcntl,hashlib,json,os,re,shutil,subprocess,urllib.request,urllib.error
from pathlib import Path
REPOSITORY='jtmb92/bortus'
PYTHON='/mnt/c/Users/james/AppData/Local/Programs/Python/Python312/python.exe'
ACCEPT=', '.join(['application/vnd.oci.image.index.v1+json','application/vnd.oci.image.manifest.v1+json','application/vnd.docker.distribution.manifest.list.v2+json','application/vnd.docker.distribution.manifest.v2+json'])
ROOT=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/shared-docker-runtime/bortus-review')
EVIDENCE=Path('/mnt/h/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z')
SOURCE='12dce115006877fed2c674cad1ffd40805932974'
MANIFEST='sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'

def need(value, reason):
    if not value:
        raise RuntimeError(reason)

def command(args, **kwargs):
    r = subprocess.run(args, capture_output=True, timeout=kwargs.pop("timeout", 30), **kwargs)
    need(r.returncode == 0, "command_failed:" + Path(args[0]).name)
    return r.stdout

def write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

def registry_token(helper):
    # This stdout is consumed in memory only and never printed or persisted.
    windows = command(['wslpath', '-w', str(helper)]).decode().strip()
    raw = command([PYTHON, "-I", "-B", windows, "get"], input=b"https://index.docker.io/v1/\n")
    need(len(raw) <= 8192, "credential_response_bound")
    value = json.loads(raw)
    need(value.get("Username") == "jtmb92", "credential_account_changed")
    basic = base64.b64encode((value["Username"] + ":" + value["Secret"]).encode()).decode()
    req = urllib.request.Request("https://auth.docker.io/token?service=registry.docker.io&scope=repository:" + REPOSITORY + ":pull,push", headers={"Authorization": "Basic " + basic})
    with urllib.request.urlopen(req, timeout=30) as response:
        token = json.loads(response.read(65537))["token"]
    access = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))["access"]
    need(any(v["name"] == REPOSITORY and {"pull", "push"} <= set(v["actions"]) for v in access), "repository_push_grant_missing")
    return token

def document(token, name, kind="manifests", missing=False):
    req = urllib.request.Request("https://registry-1.docker.io/v2/" + REPOSITORY + "/" + kind + "/" + name, headers={"Authorization": "Bearer " + token, "Accept": ACCEPT})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(4 * 1024**2 + 1)
            need(len(raw) <= 4 * 1024**2, "registry_document_bound")
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            need(not response.headers.get("Docker-Content-Digest") or response.headers["Docker-Content-Digest"] == digest, "registry_digest_mismatch")
            return {"digest": digest, "value": json.loads(raw)}
    except urllib.error.HTTPError as error:
        if missing and error.code == 404:
            return None
        raise RuntimeError("registry_http_" + str(error.code)) from None

def verify_private_repository(helper):
 windows=command(['wslpath','-w',str(helper)]).decode().strip();v=json.loads(command([PYTHON,'-I','-B',windows,'get'],input=b'https://index.docker.io/v1/\n'));need(v.get('Username')=='jtmb92','credential_account_changed')
 request=urllib.request.Request('https://hub.docker.com/v2/users/login/',data=json.dumps({'username':v['Username'],'password':v['Secret']}).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(request,timeout=30) as response:token=json.load(response)['token']
 request=urllib.request.Request('https://hub.docker.com/v2/repositories/'+REPOSITORY+'/',headers={'Authorization':'JWT '+token})
 with urllib.request.urlopen(request,timeout=30) as response:repo=json.load(response)
 need(repo.get('is_private') is True,'private_repository_required')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--publish',action='store_true');a=ap.parse_args()
 need(os.geteuid()==0 and ROOT.is_dir() and ROOT.resolve()==ROOT and ROOT.stat().st_uid==0 and ROOT.stat().st_mode&0o077==0,'private_owned_review_root')
 review=json.loads((ROOT/'review.json').read_text());binding=json.loads((EVIDENCE/'BORTUS-qualified-OCI-binding-20261114.json').read_text());prep=json.loads((EVIDENCE/'BORTUS-private-registry-preparation-20261114.json').read_text())
 need(prep['private'] is True and prep['repository']=='docker.io/'+REPOSITORY,'private_destination_required')
 need(review['state']=='ready' and review['source']==SOURCE and review['image_id']==MANIFEST and binding['selected_manifest_digest']==MANIFEST,'qualified_review_identity')
 image=json.loads(command(['docker','image','inspect',MANIFEST]))[0]
 need(image['Id']==MANIFEST and image['Config']['Labels']==binding['labels'] and image['RootFS']['Layers']==binding['ordered_diff_ids'],'unchanged_qualified_image_required')
 need(command(['docker','info','--format','{{.DockerRootDir}}']).decode().strip()==str(ROOT.parent/'docker'),'existing_H_docker_required')
 helper=Path(__file__).resolve().with_name('windows-docker-credential-bortus.py');hs=hashlib.sha256(helper.read_bytes()).hexdigest()
 lock=os.open(ROOT/'publisher.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 tag='release-'+SOURCE;target='docker.io/'+REPOSITORY+':'+tag;client=ROOT/'publication-client'
 receipt=ROOT/('publication.json' if a.publish else 'publication-probe.json');need(not receipt.exists(),'existing_publication_record_requires_reconciliation')
 rec={'state':'checking','source':SOURCE,'manifest':MANIFEST,'repository':'docker.io/'+REPOSITORY,'tag':target,'production_changed':False,'credentials_saved':False,'image_rebuilt':False,'private_at_preparation':True,'actual_reader_acceptance':False,'scope':'Private artifact transport only; not production/adoption/reader qualification','startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  verify_private_repository(helper);rec['private_readback_at_execution']=True
  token=registry_token(helper);remote=document(token,tag,missing=True)
  if remote:need(remote['digest']==MANIFEST,'existing_tag_differs_no_overwrite')
  if not a.publish:rec.update(state='probe-passed',immutable_tag_exists=remote is not None)
  elif remote:rec.update(state='existing-exact-private-artifact',digest=MANIFEST)
  else:
   need(not client.exists(),'existing_client_scratch_requires_reconciliation');(client/'bin').mkdir(parents=True,mode=0o700);(client/'config').mkdir(mode=0o700)
   windows=command(['wslpath','-w',str(helper)]).decode().strip();launcher=client/'bin/docker-credential-bortus-windows'
   launcher.write_text('#!/usr/bin/python3\nimport subprocess,sys\np=subprocess.run('+repr([PYTHON,'-I','-B',windows])+'+sys.argv[1:],input=sys.stdin.buffer.read(4097),stdout=sys.stdout.buffer,stderr=subprocess.DEVNULL)\nraise SystemExit(p.returncode)\n');launcher.chmod(0o700)
   write(client/'config/config.json',{'credsStore':'bortus-windows'});env={**os.environ,'DOCKER_CONFIG':str(client/'config'),'PATH':str(client/'bin')+':/usr/local/bin:/usr/bin:/bin','TMPDIR':str(ROOT/'tmp')}
   command(['docker','tag',MANIFEST,target],env=env)
   with (ROOT/'private-push.log').open('xb') as log:result=subprocess.run(['docker','push',target],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
   need(result.returncode==0,'private_push_failed');token=registry_token(helper);remote=document(token,tag)
   need(remote['digest']==MANIFEST,'published_digest_differs');descriptor=remote['value'];need(descriptor['config']['digest']==binding['config_image_id'] and [v['digest'] for v in descriptor['layers']]==binding['layer_blob_digests'],'published_graph_differs')
   cfg=document(token,descriptor['config']['digest'],kind='blobs');need(cfg['digest']==binding['config_image_id'] and cfg['value']['config']['Labels']==binding['labels'],'published_config_differs')
   rec.update(state='published-private-immutable-artifact',digest=MANIFEST,reference='docker.io/'+REPOSITORY+'@'+MANIFEST,remote_config_verified=True,remote_layer_digests_verified=True)
  return 0
 except Exception as e:
  rec.update(state='failed-no-production-change',errorCode=str(e) if isinstance(e,RuntimeError) else type(e).__name__);return 1
 finally:
  if client.exists():
   need(client.resolve().parent==ROOT and not client.is_symlink(),'client_cleanup_containment');shutil.rmtree(client)
  need(hashlib.sha256(helper.read_bytes()).hexdigest()==hs,'helper_changed');rec['finishedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(receipt,rec);os.close(lock);print(json.dumps(rec))
if __name__=='__main__':raise SystemExit(main())
