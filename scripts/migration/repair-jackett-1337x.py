#!/usr/bin/env python3
"""One dated, quiescent 1337x preference migration; preserve failed state first."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import uuid

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
BASE = ROOT.parent
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
IMAGE = 'docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'
APP = 'docker.io/linuxserver/jackett:0.24.2910@sha256:19d90927b95397f2d1364e4999e11456abdbbb382b54cd765fc3b3da24d7088b'
CLAIM_UID = '7d4e8aea-5715-4ee3-8e56-352b7b1e99f0'
EDITOR = r'''
import pathlib,os,sys,json,hashlib,tempfile,stat
p=pathlib.Path('/state/1337x.json');raw=p.read_bytes();assert len(raw)<=65536
if sys.argv[1]=='read':sys.stdout.buffer.write(raw);raise SystemExit()
request=json.loads(sys.stdin.buffer.read(65536));assert hashlib.sha256(raw).hexdigest()==request['beforeSHA256']
s=p.stat();assert s.st_uid==1000 and s.st_gid==1000 and p.resolve()==p
before=json.loads(raw);after=json.loads(raw);assert isinstance(before,list)and len({x['id']for x in before})==len(before)
desired=request['desired'];assert set(desired)=={'primarydownloadlink','fallbackdownloadlink'}and set(desired.values())<={'//itorrents.','magnet:'}
for name,value in desired.items():
 rows=[x for x in after if x['id']==name];assert len(rows)==1;rows[0]['value']=value
def others(rows):return[{k:v for k,v in r.items()if not(k=='value'and r['id']in desired)}for r in rows]
assert others(before)==others(after)
encoded=(json.dumps(after,indent=2,ensure_ascii=False)+'\n').encode();assert len(encoded)<=65536
fd,name=tempfile.mkstemp(prefix='.branconet-1337x-',dir=str(p.parent))
with os.fdopen(fd,'wb')as stream:
 os.fchmod(stream.fileno(),stat.S_IMODE(s.st_mode));stream.write(encoded);stream.flush();os.fsync(stream.fileno())
os.replace(name,p);d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(d)
finally:os.close(d)
assert json.loads(p.read_bytes())==after and p.stat().st_uid==s.st_uid and p.stat().st_gid==s.st_gid and stat.S_IMODE(p.stat().st_mode)==stat.S_IMODE(s.st_mode)
print(json.dumps({'beforeSHA256':hashlib.sha256(raw).hexdigest(),'afterSHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'allOtherFieldsUnchanged':True,'changedSettingIDs':sorted(desired),'publicChoices':desired}))
'''


def need(ok, why):
    if not ok:
        raise ValueError(why)


def call(args, data=None, timeout=90):
    p = subprocess.run(SSH + [shlex.join(args)], input=data, capture_output=True, timeout=timeout)
    need(p.returncode == 0 and len(p.stdout) <= 8 * 1024**2, 'bounded_cluster_operation')
    return p.stdout


def kube(*args, data=None, timeout=90):
    return call(['kubectl', '-n', 'plex', *args], data, timeout)


def get(kind, name, ns='plex'):
    return json.loads(call(['kubectl', '-n', ns, 'get', kind, name, '-o', 'json']))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['capture', 'apply'], required=True)
    p.add_argument('--expected-revision', required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    need(a.apply and os.name == 'posix' and len(a.expected_revision) == 40, 'explicit_dated_execution')
    os.umask(0o077)
    temporary = ROOT / 'operator-control/tmp'
    need(temporary.is_dir() and temporary.resolve() == temporary and not temporary.stat().st_mode & 0o077, 'existing_private_temporary_root')
    os.environ.update(TMPDIR=str(temporary), TEMP=str(temporary), TMP=str(temporary), GOMAXPROCS='1', GOMEMLIMIT='64MiB')
    scope = ROOT / 'upstream-jackett-20261026'
    out = scope / 'choice-repair'
    out.mkdir(mode=0o700, exist_ok=True)
    target = out / (a.phase + '.json')
    need(not target.exists() and out.resolve() == out and not out.stat().st_mode & 0o077, 'immutable_private_phase')
    result = {'phase': a.phase, 'passed': False, 'sourceSHA256': digest(Path(__file__)),
              'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sourceDataModified': False}
    actor = None

    def guard():
        d = get('deployment', 'jackett')
        h = get('helmrelease', 'jackett', 'flux-system')
        claim = get('pvc', 'jackett-data-0')
        node = get('node', 'workernode2')
        source = get('gitrepository', 'branconet-charts', 'flux-system')
        need(d['metadata']['uid'] == '8ff38b3e-d114-4a03-adfd-2078d359530c'
             and h['metadata']['uid'] == 'cc166e8b-d45a-4e77-bdfe-e874240cfb4d'
             and claim['metadata']['uid'] == CLAIM_UID and claim['status']['phase'] == 'Bound'
             and claim['spec']['storageClassName'] == 'longhorn'
             and node['metadata']['uid'] == 'eda66e65-f388-4b97-b64f-a709cda81894'
             and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']), 'original_native_identities')
        need(source['status']['artifact']['revision'] == 'validated@sha1:' + a.expected_revision
             and h['status']['lastAttemptedRevision'].endswith(a.expected_revision[:12])
             and h['spec']['values']['replicaCount'] == 0 and not h['spec'].get('suspend', False)
             and h['status'].get('observedGeneration') == h['metadata']['generation']
             and any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status']['conditions'])
             and d['spec']['replicas'] == 0 and d['status'].get('observedGeneration') == d['metadata']['generation']
             and all(d['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas'])
             and d['spec']['template']['spec']['containers'][0]['image'] == APP, 'quiescent_exact_flux_writer')
        for pod in json.loads(kube('get', 'pods', '-o', 'json'))['items']:
            consumes = any(v.get('persistentVolumeClaim', {}).get('claimName') == 'jackett-data-0' for v in pod['spec'].get('volumes', []))
            need(not consumes or (actor and pod['metadata']['uid'] == actor['uid']), 'no_other_claim_consumer')

    def check_actor():
        pod = get('pod', actor['name'])
        need(pod['metadata']['uid'] == actor['uid'] and pod['status']['phase'] == 'Running'
             and pod['status']['containerStatuses'][0]['ready']
             and pod['spec']['containers'][0]['image'] == IMAGE
             and pod['spec'].get('automountServiceAccountToken') is False
             and pod['spec']['nodeName'] == 'workernode2', 'exact_scoped_editor')
        spec = pod['spec']
        container = spec['containers'][0]
        need(len(spec['containers']) == 1 and not spec.get('initContainers') and not spec.get('ephemeralContainers')
             and not container.get('env') and not container.get('envFrom')
             and container['securityContext'] == {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}
             and container['volumeMounts'] == [{'name': 'state', 'mountPath': '/state', 'subPath': 'Jackett/Indexers'}]
             and len(spec['volumes']) == 1 and spec['volumes'][0].get('persistentVolumeClaim', {}).get('claimName') == 'jackett-data-0', 'admitted_scope_and_privileges')

    def execute(mode, payload=None):
        guard()
        check_actor()
        return kube('exec', '-i', actor['name'], '--', 'python3', '-I', '-B', '-c', EDITOR, mode, data=payload)

    try:
        if a.phase == 'capture':
            guard()
            name = 'jackett-choice-' + uuid.uuid4().hex[:12]
            pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'plex', 'labels': {'migration-task': 'jackett-choice-repair'}},
                   'spec': {'nodeName': 'workernode2', 'restartPolicy': 'Never', 'activeDeadlineSeconds': 600, 'automountServiceAccountToken': False,
                   'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'runAsNonRoot': True, 'seccompProfile': {'type': 'RuntimeDefault'}},
                   'containers': [{'name': 'editor', 'image': IMAGE, 'imagePullPolicy': 'IfNotPresent', 'command': ['python3', '-I', '-B', '-c', 'import time;time.sleep(600)'],
                   'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '128Mi'}},
                   'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                   'volumeMounts': [{'name': 'state', 'mountPath': '/state', 'subPath': 'Jackett/Indexers'}]}],
                   'volumes': [{'name': 'state', 'persistentVolumeClaim': {'claimName': 'jackett-data-0'}}]}}
            created = json.loads(kube('create', '-f', '-', '-o', 'json', data=json.dumps(pod).encode()))
            actor = {'name': name, 'uid': created['metadata']['uid']}
            kube('wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s', timeout=200)
            raw = execute('read')
            need(len(raw) <= 65536 and isinstance(json.loads(raw), list), 'one_bounded_config_file')
            age = BASE / 'bin/age'
            need(digest(age) == 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c', 'trusted_encryptor')
            cipher = out / '1337x-before-repair.json.age'
            with cipher.open('xb') as f:
                encrypted = subprocess.run([str(age), '-R', '/home/brajam/.ssh/id_ed25519.pub'], input=raw, stdout=f, stderr=subprocess.DEVNULL, timeout=30)
            recovered = subprocess.run([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(cipher)], capture_output=True, timeout=30)
            need(encrypted.returncode == 0 and recovered.returncode == 0 and recovered.stdout == raw, 'complete_failed_state_authentication')
            result.update(passed=True, actor=actor, archive=str(cipher), archiveSHA256=digest(cipher), archiveBytes=cipher.stat().st_size,
                          plaintextSHA256=hashlib.sha256(raw).hexdigest(), failedStatePreserved=True)
        else:
            capture = json.loads((out / 'capture.json').read_text())
            need(capture['passed'] and capture['failedStatePreserved'], 'original_captured_failure')
            actor = capture['actor']
            copies = json.loads((ROOT / 'operator-control/smb-jackett-config-repair-copy-status.json').read_text())['files']
            need(len(copies) == 1 and copies[0]['source'] == capture['archive'] and copies[0]['completeAgeAuthentication']
                 and copies[0]['destinationSHA256'] == capture['archiveSHA256'], 'verified_off_node_failed_state')
            # The original, fully authenticated complete claim is the preference authority.
            cold_paths = list((scope / 'cold').glob('*/receipt.json'))
            need(len(cold_paths) == 1, 'single_original_cold_snapshot')
            cold = json.loads(cold_paths[0].read_text())
            need(cold['cold_archive_verified'] and cold['temporary_pod_deleted'] and cold['claim_uid'] == CLAIM_UID
                 and digest(Path(cold['archive_path'])) == cold['archive_sha256'], 'authenticated_original_choice_source')
            child = subprocess.Popen([str(BASE / 'bin/age'), '-d', '-i', '/home/brajam/.ssh/id_ed25519', cold['archive_path']], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            original = None
            with tarfile.open(fileobj=child.stdout, mode='r|') as tar:
                for member in tar:
                    if member.name == 'data-0/Jackett/Indexers/1337x.json':
                        need(member.isfile() and member.size <= 65536, 'original_indexer_file')
                        original = json.load(tar.extractfile(member))
            while child.stdout.read(65536):
                pass
            need(child.wait(timeout=30) == 0 and isinstance(original, list), 'full_original_cipher_authentication')
            settings = {x['id']: x['value'] for x in original}
            mapping = {'http://itorrents.org/': '//itorrents.', 'magnet:': 'magnet:'}
            desired = {'primarydownloadlink': mapping[settings['downloadlink']], 'fallbackdownloadlink': mapping[settings['downloadlink(fallback)']]}
            payload = {'beforeSHA256': capture['plaintextSHA256'], 'desired': desired}
            result['edit'] = json.loads(execute('write', json.dumps(payload).encode()))
            need(result['edit']['allOtherFieldsUnchanged'], 'only_two_choice_values_changed')
            need(hashlib.sha256(execute('read')).hexdigest() == result['edit']['afterSHA256'], 'stored_result_readback')
            result.update(passed=True, sourceDataModified=True, originalColdReceiptSHA256=digest(cold_paths[0]))
    except Exception as error:
        result['errorCategory'] = str(error) if type(error) is ValueError else type(error).__name__
    finally:
        if actor and (a.phase == 'apply' or not result['passed']):
            try:
                options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': actor['uid']}, 'propagationPolicy': 'Foreground'}
                kube('delete', '--raw', '/api/v1/namespaces/plex/pods/' + actor['name'], '-f', '-', data=json.dumps(options).encode())
                kube('wait', 'pod/' + actor['name'], '--for=delete', '--timeout=120s', timeout=140)
                result['temporaryPodDeleted'] = True
            except Exception as error:
                result.update(passed=False, cleanupErrorType=type(error).__name__)
        with target.open('x') as f:
            json.dump(result, f, sort_keys=True, indent=2)
        print(json.dumps({k: v for k, v in result.items() if k != 'edit'}))
    return int(not result['passed'])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'errorType': type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
