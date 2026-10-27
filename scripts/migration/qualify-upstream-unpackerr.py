#!/usr/bin/env python3
"""Bounded read-only Unpackerr config/identity/integration preservation check.

Run in WSL with --mode baseline|after|restart and --output-dir under the existing
native task root. Secret/configuration values are HMACed in process memory; raw
logs and configuration are never written. Does not scale, download or delete.
Use --profile official-1.0 for the pinned 0.16.1 to 1.0.0 transition and its
empty listen-address override; the default preserves the earlier 0.16 profile.
"""
import argparse
import datetime
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OLD = 'docker.io/library/unpackerr-security-20261023@sha256:6342be9c7797b126633a56948b4dab131fde45fde3b8b173a3c84a8f4efc6213'
NEW = 'ghcr.io/unpackerr/unpackerr:0.16.1@sha256:406586865431b40b29353d899fb75a788f5384743f7f381444db5fe55d206914'
RUNTIME = 'sha256:7000ff3072154ea8f82d7905c6214571b8bbfb68c937ed989dab3cac39f6017f'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519',
       '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, limit=4 * 1024**2):
    p = subprocess.run(SSH + [shlex.join(args)], capture_output=True, timeout=90)
    need(p.returncode == 0 and len(p.stdout) <= limit, 'bounded_cluster_read')
    return p.stdout


def get(kind, name, ns='plex'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', ns, 'get', kind, name, '-o', 'json']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['baseline', 'after', 'restart'], required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--profile', choices=['official-0.16', 'official-1.0'], default='official-0.16')
    a = p.parse_args()
    old_image, new_image, child_digest = OLD, NEW, RUNTIME
    if a.profile == 'official-1.0':
        old_image = NEW
        new_image = 'ghcr.io/unpackerr/unpackerr:1.0.0@sha256:21c6bfa4f4c86ab2dd0232da0dfb3ed4c5d929e42e09894e7b4d2154d0c144f6'
        child_digest = 'sha256:4a3bba3267fd83da7ff8871c73feddcc6ec00ee4de303043ed63c2d38f8b0a4c'
    os.umask(0o077)
    need(os.name == 'posix' and ROOT.is_mount() and ROOT in a.output_dir.parents
         and a.output_dir.resolve() == a.output_dir, 'canonical_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(a.output_dir.stat().st_uid == os.getuid() and not a.output_dir.stat().st_mode & 0o077, 'private_owner')
    target = a.output_dir / (a.mode + '.json')
    need(not target.exists(), 'immutable_observation')
    keyfile = a.output_dir / 'observation.key'
    if a.mode == 'baseline':
        if not keyfile.exists():
            with keyfile.open('xb') as f:
                f.write(os.urandom(32))
        else:
            need((a.output_dir / 'baseline-controller-output.jsonl').exists(), 'retained_incomplete_baseline')
    key = keyfile.read_bytes()
    need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_hmac_key')
    mac = lambda v: hmac.new(key, json.dumps(v, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    dep = get('deployment', 'unpackerr')
    hr = get('helmrelease', 'unpackerr', 'flux-system')
    need(dep['metadata']['uid'] == '176fa046-630c-41df-9a53-5c4f5f5d6024'
         and hr['metadata']['uid'] == 'c7af079e-7de5-4e8d-a4ca-1c7d763e023b', 'original_controller_identities')
    need(dep['spec']['replicas'] == 1 and dep['status'].get('observedGeneration') == dep['metadata']['generation']
         and all(dep['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas'])
         and hr['status'].get('observedGeneration') == hr['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])), 'ready_reconciled_writer')
    image = old_image if a.mode == 'baseline' else new_image
    pods = json.loads(call(['kubectl', '-n', 'plex', 'get', 'pods', '-l', 'app=unpackerr', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_owned_pod')
    pod = pods[0]
    containers = pod['spec']['containers']
    statuses = pod['status']['containerStatuses']
    # containerd may report the immutable index or its resolved platform child.
    # Both are pinned by the reviewed registry metadata; arbitrary digests fail.
    allowed_runtime = {old_image.rsplit('@', 1)[1]} if a.mode == 'baseline' else {new_image.rsplit('@', 1)[1], child_digest}
    need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running'
         and len(containers) == len(statuses) == 1 and statuses[0]['ready']
         and containers[0]['name'] == 'unpackerr' and containers[0]['image'] == image
         and statuses[0]['imageID'].rsplit('@', 1)[-1] in allowed_runtime, 'exact_ready_runtime')
    claims = {}
    for name, uid, driver in [
        ('unpackerr-data-0', 'fe693679-9877-49cd-b146-75c30ec18a89', 'smb.csi.k8s.io'),
        ('unpackerr-data-1', '4644e693-b613-465d-a7ff-a5a9d3e1ffc1', 'driver.longhorn.io')]:
        pvc = get('pvc', name)
        pv = get('pv', pvc['spec']['volumeName'])
        need(pvc['metadata']['uid'] == uid and pvc['status']['phase'] == 'Bound'
             and pv['spec']['claimRef']['uid'] == uid and pv['spec']['csi']['driver'] == driver, 'original_storage')
        claims[name] = {'uid': uid, 'pvUID': pv['metadata']['uid'], 'specHMAC': mac(pvc['spec']), 'pvSpecHMAC': mac(pv['spec'])}
    secret = get('secret', 'unpackerr-runtime')
    need(secret['metadata']['uid'] == 'e8f8757e-c122-4760-8782-0c8736e1b481', 'original_native_secret')
    secretproof = {'uid': secret['metadata']['uid'], 'rv': secret['metadata']['resourceVersion'],
                   'contentHMAC': mac(secret.get('data', {})), 'type': secret.get('type', 'Opaque')}
    secret = None
    podname = pod['metadata']['name']
    raw = call(['kubectl', '-n', 'plex', 'exec', podname, '--', 'tar', '-cf', '-', '-C', '/config', '.'])
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as bundle:
        members = bundle.getmembers()
        need(len(members) <= 128 and sum(m.size for m in members) <= 2 * 1024**2, 'bounded_complete_config')
        for m in members:
            name = m.name.removeprefix('./')
            need(not name.startswith('/') and '..' not in Path(name).parts and (m.isdir() or m.isfile()), 'regular_config_tree')
            if not m.isfile():
                continue
            body = bundle.extractfile(m).read()
            need(len(body) == m.size, 'complete_config_file')
            files[name] = {'hmac': hmac.new(key, body, hashlib.sha256).hexdigest(),
                           'bytes': m.size, 'uid': m.uid, 'gid': m.gid, 'mode': m.mode}
    raw = body = None
    need(0 < len(files) <= 32 and any(n.endswith('.conf') for n in files), 'original_configuration_present')
    version_text = call(['kubectl', '-n', 'plex', 'exec', podname, '--', '/unpackerr', '--version']).decode()
    expected_version = '1.0.0' if a.profile == 'official-1.0' and a.mode != 'baseline' else '0.16.1'
    version = re.search(r'unpackerr, version (' + re.escape(expected_version) + r')\s', version_text)
    go_version = re.search(r'go version:\s+go([0-9.]+)', version_text)
    logs = call(['kubectl', '-n', 'plex', 'logs', podname, '--since=3m', '--tail=1000'], limit=2 * 1024**2).decode()
    integration = {'radarrMention': bool(re.search('radarr', logs, re.I)),
                   'sonarrMention': bool(re.search('sonarr', logs, re.I)),
                   'queueRetrievalLines': len(re.findall('Retrieved', logs)),
                   'authenticationFailure': bool(re.search(r'unauthorized|invalid api key|HTTP[/ ]\S* 401|status(?: code)?:? 401', logs, re.I)),
                   'errorFatalLines': sum(bool(re.search(r'\[(?:ERROR|FATAL)\]', line)) for line in logs.splitlines())}
    need(version is not None and integration['radarrMention'] and integration['sonarrMention']
         and integration['queueRetrievalLines'] >= 2 and not integration['authenticationFailure']
         and integration['errorFatalLines'] == 0, 'version_and_arr_integration_logs')
    logs = None
    normalized = json.loads(json.dumps(dep['spec']))
    normalized['template']['spec']['containers'][0]['image'] = '<reviewed-image>'
    extra_files = {}
    if a.profile == 'official-1.0':
        env = normalized['template']['spec']['containers'][0].get('env', [])
        # Kubernetes omits an explicitly empty string from its JSON response.
        need(env == [] if a.mode == 'baseline' else len(env) == 1
             and set(env[0]) <= {'name', 'value'}
             and env[0].get('name') == 'UN_WEBSERVER_LISTEN_ADDR'
             and env[0].get('value', '') == '', 'only_reviewed_headless_override')
        normalized['template']['spec']['containers'][0]['env'] = []
        need(go_version is not None and go_version[1] == ('1.27.0' if a.mode == 'baseline' else '1.27.1'),
             'reviewed_vendor_toolchain')
        if a.mode != 'baseline':
            old_files = json.loads((a.output_dir / 'baseline.json').read_bytes())['stable']['files']
            extra_files = {k: v for k, v in files.items() if k not in old_files}
            need(set(extra_files) <= {'unpackerr.history.jsonl'}, 'unreviewed_new_config_file')
            files = {k: v for k, v in files.items() if k in old_files}
            listeners = call(['kubectl', '-n', 'plex', 'exec', podname, '--', 'cat', '/proc/net/tcp', '/proc/net/tcp6']).decode()
            need(not any(len(parts := line.split()) >= 4 and parts[3] == '0A'
                         and int(parts[1].rsplit(':', 1)[-1], 16) == 5656 for line in listeners.splitlines()),
                 'headless_http_listener_present')
    annotations = normalized['template']['metadata'].get('annotations', {})
    annotations.pop('branconet.lan/security-restart', None)
    if not annotations:
        normalized['template']['metadata'].pop('annotations', None)
    stable = {'deploymentUID': dep['metadata']['uid'], 'releaseUID': hr['metadata']['uid'],
              'specHMAC': mac(normalized), 'claims': claims, 'nativeSecret': secretproof, 'files': files}
    failures = []
    if a.mode != 'baseline':
        old = json.loads((a.output_dir / 'baseline.json').read_bytes())
        need(old['passed'] and old['mode'] == 'baseline' and old['keyBinding'] == mac('unpackerr-upstream-v1'), 'exact_baseline')
        failures = [k for k, v in old['stable'].items() if stable.get(k) != v]
        need(pod['metadata']['uid'] != old['podUID'], 'different_adoption_pod')
        if a.mode == 'restart':
            prior = json.loads((a.output_dir / 'after.json').read_bytes())
            need(prior['passed'] and pod['metadata']['uid'] != prior['podUID'], 'different_restart_pod')
    result = {'mode': a.mode, 'passed': not failures, 'mismatches': failures, 'stable': stable,
              'keyBinding': mac('unpackerr-upstream-v1'), 'image': image, 'imageID': statuses[0]['imageID'],
              'podUID': pod['metadata']['uid'], 'restarts': statuses[0]['restartCount'],
              'appVersion': version[1], 'goVersion': go_version[1] if go_version else None, 'integrationLogChecks': integration,
              'profile': a.profile, 'reviewedAdditionalFiles': extra_files,
              'observedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'limitations': ['Log integration checks do not prove a real Arr import or NAS archive extraction.'],
              'nasCorpusWalked': False, 'browserAccepted': False}
    with target.open('xb') as f:
        f.write((json.dumps(result, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({'mode': a.mode, 'passed': result['passed'], 'mismatches': failures,
                      'configFiles': len(files), 'integrationLogChecks': integration, 'podUID': result['podUID']}))
    return int(bool(failures))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'errorCategory': str(error) if isinstance(error, ValueError) else type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
