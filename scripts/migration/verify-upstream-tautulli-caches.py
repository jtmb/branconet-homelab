#!/usr/bin/env python3
"""Verify only the two source-owned GitHub caches; no cache or app writes."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-tautulli-20261026'
PROGRAM = r'''
import sys,os,json,hashlib,hmac,urllib.request,urllib.parse,time
from pathlib import Path
if os.geteuid()==0:os.setgroups([]);os.setgid(1000);os.setuid(1000)
request=json.loads(sys.stdin.read(16384));key=bytes.fromhex(request['key']);files={}
def mac(v):return hmac.new(key,json.dumps(['tautulli-upstream-v1',v],sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
for name in ['cache/github_version.json','cache/github_commits.json']:
 p=Path('/config')/name;before=p.stat();raw=p.read_bytes();assert len(raw)<=4*1024**2 and before.st_mtime_ns==p.stat().st_mtime_ns
 cached=json.loads(raw);assert set(cached)=={'github_data','_cache_time','_release_version'} and cached['_release_version']=='v2.18.2'
 assert type(cached['_cache_time'])is int and request['oldTimes'][name]<=cached['_cache_time']<=time.time()+5
 data=cached['github_data']
 if name.endswith('github_version.json'):assert mac(['github-cache-data',data])==request['oldVersionDataHMAC']
 else:
  url=data['url'];parsed=urllib.parse.urlparse(url)
  assert parsed.scheme=='https' and parsed.netloc=='api.github.com' and not parsed.query and not parsed.fragment
  assert parsed.path.startswith('/repos/Tautulli/Tautulli/compare/v2.18.2...')
  assert data['base_commit']['sha']=='9484667bc1f2d159368a999320b8f495bbfbd00a'
  with opener.open(urllib.request.Request(url,headers={'User-Agent':'Branconet-Tautulli-readonly-audit'}),timeout=30)as response:
   remote=response.read(4*1024**2+1);assert response.status==200 and len(remote)<=4*1024**2
  assert json.loads(remote)==data,'complete-pinned-github-comparison-data'
 files[name]={'hmac':mac(['file',name,hashlib.sha256(raw).hexdigest()]),'cacheTime':cached['_cache_time'],'releaseVersion':'v2.18.2','completeDataVerified':True,'productionModified':False}
print(json.dumps({'passed':True,'files':files,'primaryGithubHTTPSVerified':True}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['after', 'restart'], required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args();scope = runpy.run_path(str(Path(__file__).with_name('qualify-upstream-tautulli.py')))
    key = (OUT / 'observation.key').read_bytes();before = scope['fence'](scope['NEW'], args.revision, key)
    sql_scope = {};exec(scope['SQL'], sql_scope)
    old = {name:json.loads((OUT / 'cold-runtime' / name).read_text()) for name in ['cache/github_version.json', 'cache/github_commits.json']}
    payload = {'key':key.hex(), 'oldTimes':{name:row['_cache_time'] for name,row in old.items()},
               'oldVersionDataHMAC':sql_scope['mac'](key, ['github-cache-data', old['cache/github_version.json']['github_data']])}
    result = subprocess.run(scope['SSH'] + [shlex.join(['kubectl', '-n', 'plex', 'exec', '-i', before['pod'], '-c', 'tautulli', '--', 'python3', '-B', '-c', PROGRAM])], input=json.dumps(payload).encode(), capture_output=True, timeout=90)
    if result.returncode != 0:
        (OUT / (args.phase + '-cache-verification.stderr')).write_bytes(result.stderr)
        raise ValueError('private-cache-verification-diagnostic-saved')
    proof = json.loads(result.stdout);assert proof['passed'] and scope['fence'](scope['NEW'], args.revision, key) == before
    proof.update(writer=before, revision=args.revision, sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target = OUT / (args.phase + '-cache-proof.json');assert not target.exists()
    with target.open('x') as stream:json.dump(proof, stream, indent=2);stream.write('\n')
    print(json.dumps({'passed':True, 'phase':args.phase, 'sourceOwnedCaches':len(proof['files']), 'primaryGithubHTTPSVerified':True}))


if __name__ == '__main__':main()
