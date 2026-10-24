#!/usr/bin/env python3
"""Authenticate one reviewed private CI image ZIP and stream originals into WSL."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tarfile
import threading
import urllib.request
import zipfile

REPOSITORY = 'jtmb/branconet-charts'
WORKFLOW = '.github/workflows/build-security-images.yml'
LOCK_SHA = '9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811'
GIB = 1024 ** 3
SERVICES = ('seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden')
SELECTED_COMMON = {'result.json', 'preflight.json', 'builder-host-limits.json', 'builder-limits.json',
                   'runtime-inputs-sha256.json'}
CAPS_COMMON = {name: 4 * 1024 ** 2 for name in ['result.json', 'preflight.json', 'builder-host-limits.json',
        'builder-limits.json', 'runtime-inputs-sha256.json', 'recipe-sha256.json', 'runtime-metadata.json', 'runner-sdk-reclamation.json']}
CAPS_COMMON.update({'build.log': 64 * 1024 ** 2, 'recipe.tar': 32 * 1024 ** 2,
                    'build-security-image.py': 256 * 1024})
EXPECTED_LIMITS = {'Memory': 3 * GIB, 'MemorySwap': 3 * GIB, 'CpuPeriod': 100000,
                   'CpuQuota': 150000, 'CpusetCpus': '0-1', 'PidsLimit': 512}


def need(value):
    if not value:
        raise ValueError('CI artifact prerequisite refused')


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def service_files(service):
    need(service in SERVICES)
    archive = service + '.oci.tar'
    selected = SELECTED_COMMON | {archive}
    caps = dict(CAPS_COMMON)
    caps[archive] = 4 * GIB
    if service == 'seerr':
        selected.add('pnpm-lock.yaml')
        caps['pnpm-lock.yaml'] = 16 * 1024 ** 2
    return archive, selected, caps


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHub:
    def __init__(self):
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
        result = subprocess.run(['git', '-c', 'credential.interactive=false', 'credential', 'fill'],
                                input=b'protocol=https\nhost=github.com\n\n', capture_output=True,
                                timeout=30, env=env)
        need(result.returncode == 0 and len(result.stdout) <= 65536)
        fields = dict(line.split('=', 1) for line in result.stdout.decode().splitlines() if '=' in line)
        self.token = fields.get('password'); need(bool(self.token))
        fields = None; result = None
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def get(self, suffix):
        need(suffix.startswith('/repos/' + REPOSITORY) and '\n' not in suffix)
        url = 'https://api.github.com' + suffix
        request = urllib.request.Request(url, method='GET', headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'})
        with self.client.open(request, timeout=30) as response:
            need(response.status == 200 and response.url == url)
            payload = response.read(2 * 1024 ** 2 + 1)
            need(len(payload) <= 2 * 1024 ** 2)
            return json.loads(payload)


def github_proof(args, zip_bytes):
    client = GitHub()
    try:
        prefix = '/repos/' + REPOSITORY
        repository = client.get(prefix)
        workflow = client.get(prefix + '/actions/workflows/build-security-images.yml')
        run = client.get(prefix + '/actions/runs/' + str(args.run_id))
        need(repository.get('full_name') == REPOSITORY and repository.get('private') is True)
        need(workflow.get('path') == WORKFLOW and workflow.get('state') == 'active' and workflow.get('id') == run.get('workflow_id'))
        need(run.get('id') == args.run_id and run.get('head_sha') == args.head_sha and run.get('head_branch') == 'main')
        need(run.get('event') == 'workflow_dispatch' and run.get('status') == 'completed' and run.get('conclusion') == 'success')
        need(run.get('repository', {}).get('id') == repository['id'] and run['repository'].get('full_name') == REPOSITORY)
        need(run.get('head_repository', {}).get('id') == repository['id'])
        attempt = run.get('run_attempt'); need(type(attempt) is int and attempt > 0)
        jobs = client.get(prefix + '/actions/runs/' + str(args.run_id) + '/attempts/' + str(attempt) + '/jobs?per_page=100')
        need(jobs.get('total_count') == 1 and len(jobs.get('jobs', [])) == 1)
        job = jobs['jobs'][0]
        need(type(job.get('id')) is int and job['id'] > 0 and job.get('run_id') == args.run_id and job.get('head_sha') == args.head_sha)
        need(job.get('name') == 'build' and job.get('status') == 'completed' and job.get('conclusion') == 'success')
        artifact = client.get(prefix + '/actions/artifacts/' + str(args.artifact_id))
        need(artifact.get('id') == args.artifact_id and artifact.get('expired') is False)
        need(artifact.get('name') == 'security-' + args.service + '-' + args.head_sha + '-' + str(args.run_id) + '-' + str(attempt))
        need(artifact.get('size_in_bytes') == zip_bytes and artifact.get('digest') == 'sha256:' + args.zip_sha256)
        source = artifact.get('workflow_run', {})
        need(source.get('id') == args.run_id and source.get('head_sha') == args.head_sha and source.get('head_branch') == 'main')
        need(source.get('repository_id') == repository['id'] and source.get('head_repository_id') == repository['id'])
        return {'repository': repository, 'workflow': workflow, 'run': run, 'job': job, 'artifact': artifact}
    finally:
        client.token = None


class HashingReader:
    def __init__(self, source):
        self.source, self.digest, self.count = source, hashlib.sha256(), 0

    def read(self, count=-1):
        data = self.source.read(count)
        self.digest.update(data); self.count += len(data)
        need(self.count <= 4 * GIB)
        return data


def inspect_oci(source):
    reader = HashingReader(source); index = None; layout = None; seen = set(); descriptors = {}
    with tarfile.open(fileobj=reader, mode='r|') as bundle:
        for member in bundle:
            name = member.name.removeprefix('./').rstrip('/')
            need(name and name not in seen and not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name)
            seen.add(name); need(len(seen) <= 4096 and not member.issym() and not member.islnk())
            if member.isdir():
                need(name in ['blobs', 'blobs/sha256']); continue
            need(member.isfile() and 0 <= member.size <= 4 * GIB)
            if name == 'index.json':
                need(member.size <= 4 * 1024 ** 2); index = json.load(bundle.extractfile(member))
            elif name == 'oci-layout':
                need(member.size <= 4096); layout = json.load(bundle.extractfile(member))
            else:
                need(re.fullmatch(r'blobs/sha256/[0-9a-f]{64}', name)); descriptors[name] = member.size
    for block in iter(lambda: reader.read(1024 * 1024), b''): pass
    need(layout == {'imageLayoutVersion': '1.0.0'} and isinstance(index, dict) and index.get('schemaVersion') == 2)
    need(index.get('mediaType') == 'application/vnd.oci.image.index.v1+json')
    roots = index.get('manifests', []); need(len(roots) == 1)
    root = roots[0]; digest = root.get('digest', '')
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', digest) and root.get('platform') == {'architecture': 'amd64', 'os': 'linux'})
    need(root.get('mediaType') == 'application/vnd.oci.image.manifest.v1+json')
    need(descriptors.get('blobs/sha256/' + digest.split(':')[1]) == root.get('size'))
    return {'sha256': reader.digest.hexdigest(), 'bytes': reader.count}, index


def validate_originals(data, files, github, oci_index, args):
    run = github['run']; attempt = run['run_attempt']
    result = data['result.json']; preflight = data['preflight.json']; runtime = data['runtime-inputs-sha256.json']
    archive_name, _, _ = service_files(args.service)
    need(result.get('state') == 'artifact-built-not-qualified-not-deployed' and result.get('service') == args.service and result.get('source_commit') == args.head_sha)
    need(result.get('archive_sha256') == files[archive_name]['sha256'] and result.get('archive_bytes') == files[archive_name]['bytes'])
    need(result.get('oci_index') == oci_index)
    build_metadata = data['runtime-metadata.json']
    root = oci_index['manifests'][0]
    need(build_metadata.get('containerimage.digest') == root['digest'] and build_metadata.get('containerimage.descriptor') == root)
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', build_metadata.get('containerimage.config.digest', '')))
    need(isinstance(runtime, dict) and 0 < len(runtime) <= 256 and 'Dockerfile' in runtime)
    if args.service == 'seerr':
        need(result.get('frozen_lock_sha256') == LOCK_SHA and runtime.get('pnpm-lock.yaml') == LOCK_SHA)
        need(files['pnpm-lock.yaml']['sha256'] == LOCK_SHA and files['pnpm-lock.yaml']['bytes'] == 561754)
    else:
        need('frozen_lock_sha256' in result and result['frozen_lock_sha256'] is None)
        need('pnpm-lock.yaml' not in files and 'pnpm-lock.yaml' not in runtime)
    need(all(isinstance(n, str) and n and not n.startswith('/') and '..' not in Path(n).parts and '\\' not in n and '\x00' not in n and re.fullmatch('[0-9a-f]{64}', h) for n, h in runtime.items()))
    if 'recipe-sha256.json' in data: need(data['recipe-sha256.json'] == runtime)
    if 'build-security-image.py' in files: need(files['build-security-image.py']['sha256'] == preflight.get('helper_sha256'))
    container = 'buildx_buildkit_security-' + str(args.run_id) + '-' + str(attempt) + '0'
    host = data['builder-host-limits.json']; effective = data['builder-limits.json']
    need(host.get('container') == container and host.get('actual') == EXPECTED_LIMITS and host.get('expected') == EXPECTED_LIMITS)
    need(effective.get('container') == container and effective.get('host_config') == EXPECTED_LIMITS)
    need(effective.get('effective_cgroup_v2') == ['3221225472', '0', '150000 100000', '0-1', '512'])
    need(preflight.get('state') == 'source-sealed-not-built' and preflight.get('service') == args.service and preflight.get('source_commit') == args.head_sha)
    need(str(preflight.get('run_id')) == str(args.run_id) and str(preflight.get('run_attempt')) == str(attempt))
    need(preflight.get('reserve_bytes') == 2 * GIB and preflight.get('build_budget_bytes') == 12 * GIB and preflight.get('max_oci_bytes') == 4 * GIB)
    capacity = preflight.get('capacity', []); need(len(capacity) == 2)
    need(all(c.get('available_bytes', 0) >= 18 * GIB and c.get('free_inode_fraction', 0) >= .10 for c in capacity))
    docker = preflight.get('docker_storage', {}); need(docker.get('free', 0) >= 18 * GIB and docker.get('inodes', 0) >= .10)


WSL_RECEIVER = r'''
import hashlib,json,os,pathlib,stat,struct,sys
operation='protocol-header'
def need(value):
 if not value: raise ValueError('native-receive-refused')
def exact(count):
 data=bytearray()
 while len(data)<count:
  block=sys.stdin.buffer.read(min(count-len(data),1024*1024)); need(bool(block)); data.extend(block)
 return bytes(data)
os.umask(0o077)
run,artifact=sys.argv[1:]; need(run.isdecimal() and artifact.isdecimal() and int(run)>0 and int(artifact)>0)
size=struct.unpack('!Q',exact(8))[0]; need(0<size<=4*1024*1024)
header=json.loads(exact(size)); files=header['retainedFiles']; need(0<len(files)<=16)
operation='base-directory'
base=pathlib.Path('/home/brajam/.local/share/branconet-migration/ci-image-artifacts-20261024')
need(base.resolve()==base)
base.mkdir(mode=0o700,parents=True,exist_ok=True)
info=base.lstat(); need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700)
folder=base/(run+'-'+artifact); need(not folder.exists() and not folder.is_symlink())
operation='capacity'
total=sum(v['bytes'] for v in files.values()); need(0<total<=5*1024**3)
space=os.statvfs(base); need(space.f_bavail*space.f_frsize>=total+2*1024**3)
operation='create-run-directory'
folder.mkdir(mode=0o700)
for name,row in sorted(files.items()):
 operation='write-original'
 need(name and '/' not in name and '\\' not in name and ':' not in name and name not in ['.','..','provenance.json'])
 need(type(row['bytes']) is int and 0<row['bytes']<=4*1024**3)
 target=folder/name; digest=hashlib.sha256(); remaining=row['bytes']
 with target.open('xb') as out:
  while remaining:
   block=exact(min(1024*1024,remaining)); out.write(block); digest.update(block); remaining-=len(block)
  out.flush(); os.fsync(out.fileno())
 need(digest.hexdigest()==row['sha256']); target.chmod(0o400)
 operation='verify-original'
 need(target.stat().st_size==row['bytes'])
 written=hashlib.sha256()
 with target.open('rb') as check:
  for block in iter(lambda:check.read(1024*1024),b''):written.update(block)
 need(written.hexdigest()==row['sha256'])
operation='protocol-eof'
need(sys.stdin.buffer.read(1)==b'')
operation='write-provenance'
proof=header['provenance']; encoded=(json.dumps(proof,sort_keys=True,indent=2)+'\n').encode()
target=folder/'provenance.json'
with target.open('xb') as out: out.write(encoded); out.flush(); os.fsync(out.fileno())
target.chmod(0o400)
operation='complete'
print(json.dumps({'status':'received-not-scanned-not-deployed','root':str(folder),'provenance_sha256':hashlib.sha256(encoded).hexdigest(),'files':proof['files'],'root_descriptor':header['rootDescriptor']}))
'''


def native_bootstrap():
    # Windows -> wsl command transport can reinterpret backslashes in a -c
    # argument. Encode the trusted program bytes; never interpolate input data.
    encoded = base64.b64encode(WSL_RECEIVER.encode()).decode()
    return '''import base64,json,sys,traceback
operation='bootstrap'
try:
 exec(compile(base64.b64decode(''' + repr(encoded) + '''),'<ci-artifact-receiver>','exec'))
except Exception as error:
 frames=traceback.extract_tb(error.__traceback__)
 lines=[f.lineno for f in frames if f.filename=='<ci-artifact-receiver>']
 line=lines[0] if lines else getattr(error,'lineno',None)
 print(json.dumps({'status':'failed','operation':operation,'errorType':type(error).__name__,'line':line}),file=sys.stderr)
 raise SystemExit(1)
'''


def report_native_failure(raw, exit_code):
    safe = {'status': 'native-reception-failed', 'operation': 'bootstrap',
            'errorType': 'UnclassifiedChildExit', 'line': None, 'exitCode': exit_code}
    try:
        need(len(raw) <= 4096)
        value = json.loads(raw)
        operations = ['bootstrap', 'protocol-header', 'base-directory', 'capacity', 'create-run-directory',
                      'write-original', 'verify-original', 'protocol-eof', 'write-provenance', 'complete']
        need(value.get('status') == 'failed' and value.get('operation') in operations)
        need(re.fullmatch('[A-Za-z]{1,64}', value.get('errorType', '')))
        need(value.get('line') is None or type(value['line']) is int and 0 < value['line'] < 10000)
        safe.update({name: value[name] for name in ['operation', 'errorType', 'line']})
    except Exception:
        pass
    print(json.dumps(safe), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', choices=SERVICES, default='seerr')
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--zip-sha256', required=True)
    parser.add_argument('--zip-bytes', type=int, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--artifact-id', type=int, required=True)
    parser.add_argument('--head-sha', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    archive_name, selected_names, caps = service_files(args.service)
    need(args.apply and os.name == 'nt' and args.run_id > 0 and args.artifact_id > 0)
    need(re.fullmatch('[0-9a-f]{64}', args.zip_sha256) and re.fullmatch('[0-9a-f]{40}', args.head_sha))
    need(0 < args.zip_bytes <= 5 * GIB and args.zip.is_absolute() and not args.zip.is_symlink())
    with args.zip.open('rb') as original:
        identity = os.fstat(original.fileno()); need(stat.S_ISREG(identity.st_mode) and identity.st_size == args.zip_bytes)
        digest = hashlib.sha256()
        for block in iter(lambda: original.read(1024 * 1024), b''): digest.update(block)
        need(digest.hexdigest() == args.zip_sha256)
        original.seek(0)
        with zipfile.ZipFile(original) as bundle:
            infos = bundle.infolist(); names = [i.filename for i in infos]
            need(0 < len(infos) <= 16 and len(set(names)) == len(names) == len(set(n.casefold() for n in names)))
            need(selected_names | {'runtime-metadata.json'} <= set(names) <= set(caps) and sum(i.file_size for i in infos) <= 5 * GIB)
            for item in infos:
                need(not item.is_dir() and item.filename in caps and 0 < item.file_size <= caps[item.filename])
                need(not item.flag_bits & 1 and stat.S_IFMT(item.external_attr >> 16) in [0, stat.S_IFREG])
            files = {}; data = {}; index = None
            for name in names:
                with bundle.open(name) as source:
                    if name == archive_name:
                        files[name], index = inspect_oci(source)
                    else:
                        sha = hashlib.sha256(); size = 0; payload = bytearray()
                        for block in iter(lambda: source.read(1024 * 1024), b''):
                            sha.update(block); size += len(block)
                            if name.endswith('.json'): payload.extend(block)
                        files[name] = {'sha256': sha.hexdigest(), 'bytes': size}
                        if name.endswith('.json'): data[name] = json.loads(payload)
                need(files[name]['bytes'] == bundle.getinfo(name).file_size)
            github = github_proof(args, identity.st_size)
            validate_originals(data, files, github, index, args)
            selected = {name: files[name] for name in sorted(selected_names)}
            proof = {'schemaVersion': 1, 'sourceKind': 'github-actions', 'github': github,
                     'outerZip': {'sha256': args.zip_sha256, 'bytes': identity.st_size},
                     'files': selected, 'retainedFiles': files,
                     'verificationBoundary': 'Authenticated API metadata and original ZIP/files only; image scan, runtime and deployment remain unqualified.'}
            header = compact({'provenance': proof, 'retainedFiles': files, 'rootDescriptor': index['manifests'][0]['digest']})
            child = subprocess.Popen(['wsl', '-d', 'Ubuntu', '-u', 'brajam', '--exec', 'python3', '-c', native_bootstrap(),
                                      str(args.run_id), str(args.artifact_id)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            timer = threading.Timer(600, child.kill); timer.daemon = True; timer.start()
            native_reported = False
            try:
                child.stdin.write(struct.pack('!Q', len(header))); child.stdin.write(header)
                for name in sorted(files):
                    with bundle.open(name) as source:
                        for block in iter(lambda: source.read(1024 * 1024), b''): child.stdin.write(block)
                child.stdin.close(); child.stdin = None
                result, errors = child.communicate(timeout=120)
                if child.returncode:
                    report_native_failure(errors, child.returncode)
                    native_reported = True
                need(child.returncode == 0 and len(result) <= 4 * 1024 ** 2)
                need(file_identity(os.fstat(original.fileno())) == file_identity(identity))
                reply = json.loads(result); need(reply.get('status') == 'received-not-scanned-not-deployed')
                print(json.dumps(reply)); return 0
            except Exception:
                if child.stdin is not None:
                    try: child.stdin.close()
                    except (BrokenPipeError, OSError): pass
                    child.stdin = None
                if child.poll() is None: child.kill()
                if not native_reported:
                    try:
                        _, errors = child.communicate(timeout=10)
                        report_native_failure(errors, child.returncode)
                    except Exception:
                        report_native_failure(b'', child.returncode)
                raise
            finally:
                timer.cancel()
                if child.poll() is None:
                    child.kill(); child.wait(timeout=10)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception: raise SystemExit('CI artifact reception refused; credentials and raw API/file diagnostics are suppressed; existing ZIP and any partial native reception are retained.')
