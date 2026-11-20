#!/usr/bin/env python3
"""Explicit operator-only YTPTube bootstrap/download/restart checks; never run by CI."""
import argparse
import base64
import datetime
import hashlib
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request

NAMESPACE = 'plex'
SECRET = 'ytdl-ytptube-auth'
VIDEO = 'YE7VzlLtp-4'
SOURCE_COMMIT = 'c8a42e08ded27280573d7ebe6312dd109b2bb161'
PREFIX = '.branconet-acceptance/ytptube-20261023-'
LIMIT = 20 * 1024 ** 2
CLI = ('--no-playlist --download-sections "*0-5" --force-keyframes-at-cuts '
       '--format "worstvideo[height<=240]+worstaudio/worst[height<=240][vcodec!=none][acodec!=none]" '
       '--max-filesize 20M --limit-rate 1M --concurrent-fragments 1 '
       '--retries 0 --fragment-retries 0 --extractor-retries 0 --socket-timeout 15 '
       '--no-download-archive --no-exec --no-cookies --no-write-info-json '
       '--no-write-thumbnail --no-write-subs --no-write-auto-subs')


class Refused(Exception):
    pass


def kubectl(*args, body=None, timeout=30):
    # Never echo stderr: API/server errors can contain request material.
    result = subprocess.run(['kubectl', '-n', NAMESPACE, *args],
                            input=body, capture_output=True, timeout=timeout)
    if result.returncode:
        raise Refused('kubectl_operation_failed')
    return result.stdout


def obj(*args):
    return json.loads(kubectl(*args, '-o', 'json'))


def prepare_receipt(path):
    if not path.is_absolute() or path.resolve() != path or path.parent.is_symlink():
        raise Refused('receipt_requires_absolute_non_symlink_path')
    # An operator may stage this one public script outside its source checkout.
    # A fixed parents[2] would then mistake the protected runtime directory for Git.
    if any((parent / '.git').exists() for parent in path.parents):
        raise Refused('receipts_must_remain_outside_git')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_uid != os.getuid() or path.parent.stat().st_mode & 0o077:
        raise Refused('receipt_directory_must_be_owner_only')


def save_new(path, value):
    prepare_receipt(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def bootstrap():
    uid = kubectl('get', 'secret', SECRET, '--ignore-not-found', '-o', 'jsonpath={.metadata.uid}').decode()
    if uid:
        return {'state': 'existing-native-secret-preserved', 'secret_uid': uid}
    payload = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
               'metadata': {'name': SECRET, 'namespace': NAMESPACE},
               'stringData': {'username': 'operator-' + secrets.token_hex(4), 'password': secrets.token_urlsafe(36)}}
    # The only plaintext credential transfer is an in-memory JSON stdin pipe.
    try:
        uid = kubectl('create', '-f', '-', '-o', 'jsonpath={.metadata.uid}', body=json.dumps(payload).encode()).decode()
    except Refused:
        uid = kubectl('get', 'secret', SECRET, '--ignore-not-found', '-o', 'jsonpath={.metadata.uid}').decode()
        if not uid:
            raise
        return {'state': 'concurrently-created-native-secret-preserved', 'secret_uid': uid}
    finally:
        payload.clear()
    return {'state': 'native-secret-created-no-values-disclosed', 'secret_uid': uid}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refused('unexpected_http_redirect')


class Session:
    def __init__(self):
        service = obj('get', 'service', 'ytdl')
        address = ipaddress.ip_address(service['spec']['clusterIP'])
        if not address.is_private or not any(p['port'] == 8081 for p in service['spec']['ports']):
            raise Refused('unexpected_ytdl_service')
        host = f'[{address}]' if address.version == 6 else str(address)
        self.base = f'http://{host}:8081'
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                                urllib.request.HTTPCookieProcessor(self.jar))
        self.logged_in = False

    def request(self, path, payload=None, timeout=20):
        if not path.startswith('/api/'):
            raise Refused('unexpected_api_path')
        request = urllib.request.Request(self.base + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'Origin': self.base})
        try:
            with self.http.open(request, timeout=timeout) as response:
                raw = response.read(8 * 1024 ** 2 + 1)
                if len(raw) > 8 * 1024 ** 2:
                    raise Refused('api_response_too_large')
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raise Refused('application_http_' + str(error.code)) from None
        except (urllib.error.URLError, TimeoutError):
            raise Refused('application_connection_or_timeout') from None

    def login(self):
        status = self.request('/api/auth/status')
        if status.get('disabled') is not False or status.get('setup_required') is not False:
            raise Refused('authentication_disabled_or_unbootstrapped')
        secret = obj('get', 'secret', SECRET)
        credentials = {key: base64.b64decode(secret['data'][key], validate=True).decode() for key in ('username', 'password')}
        try:
            self.request('/api/auth/login', credentials)
            self.logged_in = True
            status = self.request('/api/auth/status')
            if status.get('authenticated') is not True or status.get('user', {}).get('username') != credentials['username']:
                raise Refused('protected_cookie_login_failed')
        finally:
            secret.clear()
            credentials.clear()

    def close(self):
        try:
            if self.logged_in:
                self.request('/api/auth/logout', {})
        finally:
            self.jar.clear()


def writer(expected_image):
    deployment = obj('get', 'deployment', 'ytdl')
    active = [p for p in obj('get', 'pods', '-l', 'app=ytdl')['items']
              if p.get('status', {}).get('phase') not in ('Succeeded', 'Failed')]
    ready = [p for p in active
             if not p['metadata'].get('deletionTimestamp') and p.get('status', {}).get('phase') == 'Running'
             and any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in p['status'].get('conditions', []))]
    if len(active) != 1 or len(ready) != 1 or deployment['spec'].get('replicas') != 1:
        raise Refused('require_exactly_one_ready_ytdl_writer')
    pod = ready[0]
    owners = [o for o in pod['metadata'].get('ownerReferences', []) if o.get('controller') and o['kind'] == 'ReplicaSet']
    if len(owners) != 1:
        raise Refused('unexpected_pod_owner')
    rs = obj('get', 'replicaset', owners[0]['name'])
    if not any(o.get('controller') and o['kind'] == 'Deployment' and o['uid'] == deployment['metadata']['uid']
               for o in rs['metadata'].get('ownerReferences', [])):
        raise Refused('pod_not_owned_by_existing_deployment')
    container = next(c for c in pod['spec']['containers'] if c['name'] == 'ytdl')
    status = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'ytdl')
    if container['image'] != expected_image or not status['imageID'].endswith(expected_image.split('@', 1)[1]):
        raise Refused('writer_immutable_image_mismatch')
    volumes = {v['name']: v.get('persistentVolumeClaim', {}).get('claimName') for v in pod['spec']['volumes']}
    claims = {}
    for mount in container['volumeMounts']:
        if mount['mountPath'] not in ('/config', '/downloads', '/tmp_dir'):
            continue
        name = volumes[mount['name']]
        if mount['mountPath'] == '/downloads' and name != 'ytdl-data-2':
            raise Refused('original_nas_download_claim_required')
        if mount['mountPath'] == '/config' and (name != 'ytdl-data-0' or mount.get('subPath') != 'ytptube-config'):
            raise Refused('original_metube_state_requires_separate_ytptube_subdirectory')
        if mount['mountPath'] == '/tmp_dir' and name != 'ytdl-data-1':
            raise Refused('original_temporary_claim_required')
        claim = obj('get', 'pvc', name)
        if claim['status'].get('phase') != 'Bound':
            raise Refused('original_claim_not_bound')
        claims[mount['mountPath']] = {'name': name, 'uid': claim['metadata']['uid'], 'subPath': mount.get('subPath', '')}
    if set(claims) != {'/config', '/downloads', '/tmp_dir'}:
        raise Refused('required_storage_mounts_missing')
    return {'pod': pod['metadata']['name'], 'pod_uid': pod['metadata']['uid'],
            'deployment_uid': deployment['metadata']['uid'], 'image': expected_image,
            'image_id': status['imageID'], 'restart_count': status['restartCount'], 'claims': claims}


# Supplied as public code in argv; only the owned folder/action arrives via stdin.
REMOTE = r'''
import hashlib,importlib.metadata as m,importlib.util as u,json,os,pathlib,re,subprocess,sys,urllib.request
data=json.load(sys.stdin)
if os.getuid()!=1000: raise RuntimeError('expected application UID1000')
if data['action']=='runtime':
    if os.environ.get('YTP_YTDLP_AUTO_UPDATE','').lower()!='false': raise RuntimeError('extractor must be immutable')
    if os.environ.get('YTP_PIP_PACKAGES','').strip(): raise RuntimeError('runtime package installation must be empty')
    pip_file=pathlib.Path('/config/pip.txt')
    if pip_file.exists() and (pip_file.is_symlink() or not pip_file.is_file() or pip_file.stat().st_size>65536): raise RuntimeError('unexpected runtime package request file')
    if pip_file.exists() and any(line.strip() and not line.lstrip().startswith('#') for line in pip_file.read_text().splitlines()): raise RuntimeError('runtime package installation unavailable')
    if any(u.find_spec(name) is not None for name in ('pip','setuptools','pkg_resources','_distutils_hack','ensurepip')): raise RuntimeError('install-only code remains importable')
    if pathlib.Path(os.environ.get('YTP_APPRISE_CONFIG','/config/apprise.yml')).exists(): raise RuntimeError('notification config present')
    versions={k:m.version(k) for k in ('yt-dlp','yt-dlp-ejs','certifi')}
    if versions['yt-dlp']!='2026.10.21' or versions['yt-dlp-ejs']!='0.8.0' or versions['certifi']!='2026.10.19': raise RuntimeError('unexpected extractor packages')
    versions['deno']=subprocess.check_output(['/usr/bin/deno','--version'],text=True).splitlines()[0]
    versions['ffmpeg']=subprocess.check_output(['/usr/bin/ffmpeg','-version'],text=True).splitlines()[0]
    versions['ffprobe']=subprocess.check_output(['/usr/bin/ffprobe','-version'],text=True).splitlines()[0]
    if tuple(map(int,versions['deno'].split()[1].split('.')[:2]))<(2,3): raise RuntimeError('unsupported Deno')
    if os.environ.get('YTP_TEMP_PATH')!='/downloads/.ytptube-temp': raise RuntimeError('expected isolated NAS download temp')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:4416/ping',timeout=10) as response: provider=json.load(response)
    if not provider.get('version') or provider.get('server_uptime',-1)<0: raise RuntimeError('provider heartbeat invalid')
    versions['provider']=str(provider['version'])
    print(json.dumps({'versions':versions,'provider_heartbeat':True,'runtime_installers_absent':True}))
else:
    folder=data['folder']
    if not re.fullmatch(r'[.]branconet-acceptance/ytptube-20261023-[0-9a-f]{12}',folder): raise RuntimeError('foreign test folder')
    base=pathlib.Path('/downloads'); target=base/folder
    if not target.resolve().is_relative_to(base.resolve()): raise RuntimeError('escaped download root')
    files=[]
    if target.exists():
        for p in target.rglob('*'):
            if p.is_symlink(): raise RuntimeError('symlink inside test folder')
            if p.is_file(): files.append(p)
    nonce=folder.rsplit('-',1)[1]
    temporary=pathlib.Path('/downloads/.ytptube-temp')
    temp_files=[]
    for p in temporary.glob('branconet-ytptube-'+nonce+'*'):
        if p.is_symlink(): raise RuntimeError('symlink inside test temporary files')
        if p.is_file(): temp_files.append(p)
    total=sum(p.stat().st_size for p in files+temp_files)
    result={'exists':target.exists(),'total_bytes':total}
    if total>20*1024**2: raise RuntimeError('test files exceed 20MiB')
    if data['action']=='media':
        media=[p for p in files if p.suffix.lower() in ('.mp4','.webm','.mkv')]
        if len(media)!=1: raise RuntimeError('expected exactly one media output')
        p=media[0]
        probe=json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_entries','format=duration:stream=codec_type,codec_name,width,height','-of','json',str(p)],timeout=20))
        duration=float(probe['format']['duration'])
        if not 1<=duration<=7 or {'video','audio'}-{s['codec_type'] for s in probe['streams']}: raise RuntimeError('invalid audio/video sample')
        if any(s.get('height',0)>240 for s in probe['streams']): raise RuntimeError('sample exceeds low format cap')
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024**2),b''):h.update(chunk)
        if p.stat().st_size<=0: raise RuntimeError('empty output')
        result.update(filename=p.name,bytes=p.stat().st_size,sha256=h.hexdigest(),duration=duration,streams=probe['streams'])
    print(json.dumps(result))
'''


def remote(state, action, folder=None, timeout=40):
    return json.loads(kubectl('exec', '-i', state['pod'], '-c', 'ytdl', '--', '/opt/python/bin/python', '-c', REMOTE,
                             body=json.dumps({'action': action, 'folder': folder}).encode(), timeout=timeout))


def preflight(session, state):
    config = session.request('/api/system/configuration')
    app = config['app']
    if config.get('paused') or app.get('download_path') != '/downloads' or app.get('console_enabled') or app.get('browser_control_enabled'):
        raise Refused('unexpected_configuration')
    notifications = session.request('/api/notifications/?per_page=1')
    if notifications.get('pagination', {}).get('total') != 0:
        raise Refused('notifications_must_be_absent_before_test')
    presets = [p for p in config['presets'] if p['name'] == 'default']
    if len(presets) != 1 or presets[0].get('cookies') or presets[0].get('cli', '').strip() != '--socket-timeout 30 --download-archive %(archive_file)s':
        raise Refused('default_preset_differs_from_reviewed_release')
    runtime = remote(state, 'runtime')
    runtime['app_version'] = app['app_version']
    return runtime


def find_owned(session, folder):
    matches = []
    for store in ('queue', 'done'):
        result = session.request('/api/history/?type=' + store + '&per_page=100&order=DESC')
        matches.extend(i for i in result['items'] if i.get('folder') == folder)
    if len(matches) > 1:
        raise Refused('multiple_items_in_owned_test_folder')
    return matches[0] if matches else None


def preservation(path, state):
    if not path or not path.is_absolute() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise Refused('protected_preservation_metadata_required')
    raw = path.read_bytes()
    metadata = json.loads(raw)
    claims = {c['name']: c['uid'] for c in metadata['claims'] if c['namespace'] == NAMESPACE}
    actual = {v['name']: v['uid'] for v in state['claims'].values()}
    if len(metadata['claims']) != 3 or claims != actual or set(claims) != {'ytdl-data-0', 'ytdl-data-1', 'ytdl-data-2'}:
        raise Refused('original_three_pvc_identities_differ')
    if metadata['algorithm'] not in ('sha256', 'hmac-sha256') or not metadata['legacy_state_files']:
        raise Refused('legacy_fingerprint_metadata_missing')
    for name, value in metadata['legacy_state_files'].items():
        if not name.startswith(('data-0/', 'data-1/')) or '..' in Path(name).parts or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise Refused('invalid_legacy_fingerprint_metadata')
    return {'baseline_sha256': hashlib.sha256(raw).hexdigest(),
            'fingerprints_sha256': hashlib.sha256(json.dumps(metadata['legacy_state_files'], sort_keys=True).encode()).hexdigest(),
            'algorithm': metadata['algorithm'], 'claims': claims, 'legacy_reobserved': False}


def qualify(session, state, runtime, folder, receipt):
    if remote(state, 'quota', folder)['exists']:
        raise Refused('test_folder_already_exists')
    if session.request('/api/history/?type=queue&per_page=1')['pagination']['total'] != 0:
        raise Refused('existing_queue_must_be_idle_and_empty')
    nonce = folder.rsplit('-', 1)[1]
    item_id = None
    completed = False
    try:
        response = session.request('/api/history/?sync=true', {
            'url': 'https://www.youtube.com/watch?v=' + VIDEO, 'preset': 'default',
            'folder': folder, 'template': 'branconet-ytptube-' + nonce + '.%(ext)s',
            'cli': CLI, 'auto_start': False, 'extras': {'ignore_conditions': ['*']}}, timeout=120)
        if not isinstance(response, list) or len(response) != 1 or response[0].get('status') is not True:
            message = response[0].get('msg', '') if isinstance(response, list) and response else ''
            raise Refused(download_error_category(message))
        item = find_owned(session, folder)
        if not item or item.get('id') != VIDEO or not re.fullmatch(r'[0-9a-f-]{36}', item.get('_id', '')):
            raise Refused('owned_test_item_not_resolved')
        item_id = item['_id']
        save_new(receipt.with_name(receipt.name + '.queued.json'), {'history_id': item_id, 'folder': folder,
                 'state': 'owned-test-queued-not-accepted', 'video_id': VIDEO})
        session.request('/api/history/start', {'ids': [item_id]})
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            remote(state, 'quota', folder, timeout=max(1, min(40, deadline - time.monotonic())))
            if time.monotonic() >= deadline:
                break
            item = session.request('/api/history/' + item_id, timeout=max(1, min(20, deadline - time.monotonic())))
            if item.get('status') == 'finished':
                media = remote(state, 'media', folder, timeout=max(1, min(40, deadline - time.monotonic())))
                if item.get('filename') != media['filename']:
                    raise Refused('history_filename_mismatch')
                completed = True
                return {'state': 'sample-download-verified-restart-pending', 'history_id': item_id,
                        'folder': folder, 'video_id': VIDEO, 'media': media, 'runtime': runtime, 'writer': state}
            if item.get('status') in ('error', 'cancelled', 'canceled', 'skip', 'not_live'):
                raise Refused(download_error_category(str(item.get('error') or item.get('msg') or '')))
            time.sleep(max(0, min(2, deadline - time.monotonic())))
        raise Refused('test_download_deadline_exceeded')
    finally:
        if item_id and not completed:
            try:
                session.request('/api/history/cancel', {'ids': [item_id]})
            except Exception:
                pass  # Retain owned ID receipt; never broaden cancellation or delete files.


def download_error_category(message):
    text = str(message).lower()
    for status in ('401', '403', '429'):
        if status in text:
            return 'youtube_http_' + status
    for fragment, category in (('sign in', 'youtube_account_challenge'), ('cookie', 'youtube_cookie_requirement'),
                               ('javascript', 'youtube_javascript_failure'), ('deno', 'youtube_javascript_failure'),
                               ('format', 'youtube_format_unavailable')):
        if fragment in text:
            return category
    return 'youtube_extraction_or_download_failed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('bootstrap-secret', 'download', 'check-after-restart'))
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--preservation-baseline', type=Path)
    parser.add_argument('--expected-image')
    args = parser.parse_args()
    if args.receipt.exists():
        raise Refused('receipt_already_exists_no_replay')
    prepare_receipt(args.receipt)
    if args.mode == 'bootstrap-secret':
        result = bootstrap()
    else:
        if not re.fullmatch(r'[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}', args.expected_image or ''):
            raise Refused('accepted_immutable_image_required')
        state = writer(args.expected_image)
        retained = preservation(args.preservation_baseline, state)
        session = Session()
        try:
            session.login()
            runtime = preflight(session, state)
            if args.mode == 'download':
                folder = PREFIX + secrets.token_hex(6)
                save_new(args.receipt.with_name(args.receipt.name + '.attempt.json'), {'folder': folder, 'video_id': VIDEO})
                result = qualify(session, state, runtime, folder, args.receipt)
            else:
                if not args.baseline:
                    raise Refused('protected_baseline_required')
                baseline = json.loads(args.baseline.read_text())
                if baseline['state'] != 'sample-download-verified-restart-pending':
                    raise Refused('successful_original_sample_receipt_required')
                if state['claims'] != baseline['writer']['claims'] or state['deployment_uid'] != baseline['writer']['deployment_uid']:
                    raise Refused('persistent_storage_or_release_identity_changed')
                if retained['claims'] != baseline['preservation']['claims'] or retained['fingerprints_sha256'] != baseline['preservation']['fingerprints_sha256']:
                    raise Refused('legacy_baseline_binding_changed')
                if state['pod_uid'] == baseline['writer']['pod_uid'] and state['restart_count'] <= baseline['writer']['restart_count']:
                    raise Refused('no_actual_restart_observed')
                item = session.request('/api/history/' + baseline['history_id'])
                media = remote(state, 'media', baseline['folder'])
                if item.get('status') != 'finished' or item.get('filename') != media['filename'] or media != baseline['media'] or runtime != baseline['runtime']:
                    raise Refused('history_media_or_runtime_did_not_persist')
                result = {'state': 'sample-and-restart-persistence-verified', 'history_id': baseline['history_id'],
                          'folder': baseline['folder'], 'media': media, 'runtime': runtime, 'writer': state,
                          'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest()}
            result['preservation'] = retained
        finally:
            try:
                session.close()
            except Exception:
                pass
    result.update(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  namespace=NAMESPACE, secret_name=SECRET, api_source_commit=SOURCE_COMMIT)
    save_new(args.receipt, result)
    print(json.dumps({'state': result['state'], 'receipt': str(args.receipt)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not stringify untrusted HTTP, kubectl, app, Secret or cookie material.
        print(json.dumps({'state': 'not-accepted', 'category': str(error) if isinstance(error, Refused) else type(error).__name__}))
        raise SystemExit(1)
