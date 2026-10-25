#!/usr/bin/env python3
"""Operator-only before/after qBittorrent observer; execute ON masternode.

No application writes except one authentication session per invocation. No restart,
recheck, resume, logout, config write, SQLite conversion or credential reset.
Credentials, cookies, API records and launcher values remain in cluster-node RAM.
Only HMAC fingerprints, counts and booleans enter the private receipt.

Copy this script to masternode using existing strict SSH. Supply the SAME existing
32-byte hex HMAC key on stdin for both invocations, never as an argument:
  python3 qualify-qbittorrent.py baseline --expected-image IMAGE@sha256:DIGEST \
    --expected-runtime sha256:DIGEST --receipt /PRIVATE/before.json
  python3 qualify-qbittorrent.py after --expected-image IMAGE@sha256:DIGEST \
    --expected-runtime sha256:DIGEST --baseline /PRIVATE/before.json \
    --receipt /PRIVATE/after.json

Baseline requires exactly 231 torrents. After defaults to identical inventory.
An optional private --approved-inventory file must describe EXACT added/removed
HMAC IDs, each with a nonempty operator reason: {"added": {"HMAC": "reason"},
"removed": {"HMAC": "reason"}}. No arbitrary count tolerance or field exceptions.
Reasons are not echoed. Approvals authorize comparison exceptions, not API actions.
Failed comparisons still write a protected receipt for review; exit status is 1.
All original preference keys must match except listen_port, which must match the
current VPN forwarded-port file at each capture. New preference keys are retained
as fingerprints but do not substitute for missing original keys. Queue-priority,
path or other durable-field drift requires review, even when plausibly natural.
The capture must settle within 300 seconds; at most 1000 torrents and 100000 files.
No authentication retry is attempted. The process disables core dumps.

API contract: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0)
Legacy source default: release-5.1.4/src/base/bittorrent/sessionimpl.cpp.
This observer is not cold-copy, media-content, tracker-connectivity or restore proof.
"""

import argparse
import base64
import datetime
import hashlib
import hmac
import http.cookiejar
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request

NS = 'plex'
DEP_UID = '404fad04-5e8b-460b-aa29-dbc7450e4a54'
MONITOR_UID = '8ea48d58-186d-4c3d-a90a-d6bda3414246'
CLAIMS = {
    'qbittorrent-data-0-retry1': '999128b4-0ae2-4396-a8e4-eebace5d26f0',
    'qbittorrent-data-1': '33bd6c4e-0568-4d2c-8c32-9cd3cce2e778',
    'gluetun-data-0': 'b94e164d-1209-4929-b755-bd8925bd9153',
    'gluetun-data-1-retry1': 'cdfd60f4-e76a-4037-827b-02459d1ac3ff',
    'qbit-monitor-state': '29f9332d-c2a6-4f24-a83f-210620046cd2',
}
SECRETS = {
    'qbittorrent-runtime': '04148ff6-969b-4294-9679-179caa56612e',
    'qbittorrent-launch': '09495fd4-276a-4a34-8600-6a2edfeed5a4',
    'gluetun-runtime': '309fe107-1c10-4e88-a81c-c5553f52118b',
    'gluetun-launch': 'c71b0f55-3fa0-425a-92f9-2a23b070b18e',
}
MAX_REPLY = 16 * 1024**2
MAX_TOTAL = 128 * 1024**2
MAX_TORRENTS = 1000
MAX_FILES = 100000
MAX_SECONDS = 300
DURABLE = ('hash', 'infohash_v1', 'infohash_v2', 'name', 'save_path', 'download_path',
           'content_path', 'category', 'tags', 'priority', 'auto_tmm', 'force_start',
           'seq_dl', 'f_l_piece_prio', 'super_seeding', 'dl_limit', 'up_limit',
           'ratio_limit', 'seeding_time_limit', 'inactive_seeding_time_limit',
           'share_limit_action', 'share_limits_mode', 'max_ratio', 'max_seeding_time',
           'max_inactive_seeding_time', 'total_size', 'size', 'added_on', 'comment', 'private')
REQUIRED = ('hash', 'name', 'save_path', 'category', 'tags', 'priority', 'auto_tmm',
            'force_start', 'dl_limit', 'up_limit', 'ratio_limit', 'seeding_time_limit')
START = time.monotonic()


class Refused(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Refused(code)


def bounded():
    need(time.monotonic() - START < MAX_SECONDS, 'observation_deadline')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def command(argv, data=None, limit=MAX_REPLY):
    bounded()
    # Child stdout is a private pipe in cluster-node RAM, never terminal output.
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        out, _ = proc.communicate(data, timeout=min(25, max(1, MAX_SECONDS - (time.monotonic() - START))))
        need(proc.returncode == 0 and len(out) <= limit, 'bounded_command_failed')
        return out
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def kube(*args, data=None, limit=MAX_REPLY):
    return command(['kubectl', '--request-timeout=20s', '-n', NS, *args], data, limit)


def obj(kind, name):
    return json.loads(kube('get', kind, name, '-o', 'json'))


def refs(spec):
    result = set()
    for c in spec.get('containers', []) + spec.get('initContainers', []):
        for env in c.get('env', []):
            ref = env.get('valueFrom', {}).get('secretKeyRef', {})
            if ref:
                result.add(ref['name'])
        for env in c.get('envFrom', []):
            if 'secretRef' in env:
                result.add(env['secretRef']['name'])
    for volume in spec.get('volumes', []):
        if 'secret' in volume:
            result.add(volume['secret']['secretName'])
    return result


def ready_deployment(name, uid):
    dep = obj('deployment', name)
    need(dep['metadata']['uid'] == uid and not dep['metadata'].get('deletionTimestamp'), 'deployment_identity')
    need(dep['spec'].get('replicas') == 1, 'replica_count')
    state = dep.get('status', {})
    need(state.get('observedGeneration', 0) >= dep['metadata']['generation'] and
         all(state.get(k) == 1 for k in ('replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas')), 'deployment_not_ready')
    selector = ','.join(k + '=' + v for k, v in dep['spec']['selector']['matchLabels'].items())
    rss = json.loads(kube('get', 'replicasets', '-l', selector, '-o', 'json'))['items']
    owners = {r['metadata']['uid'] for r in rss if any(o.get('uid') == uid and o.get('controller') for o in r['metadata'].get('ownerReferences', []))}
    pods = json.loads(kube('get', 'pods', '-l', selector, '-o', 'json'))['items']
    pods = [p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase') not in ('Succeeded', 'Failed')]
    need(len(pods) == 1, 'pod_count')
    pod = pods[0]
    need(any(o.get('controller') and o.get('uid') in owners for o in pod['metadata'].get('ownerReferences', [])), 'pod_owner')
    need(pod['status'].get('phase') == 'Running' and any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in pod['status'].get('conditions', [])), 'pod_not_ready')
    need(all(s.get('ready') for s in pod['status'].get('containerStatuses', [])), 'container_not_ready')
    return dep, pod


def identity(args, mac):
    dep, pod = ready_deployment('qbittorrent', DEP_UID)
    monitor, mpod = ready_deployment('qbit-monitor', MONITOR_UID)
    need(pod['spec'].get('nodeName') == 'masternode', 'application_moved_off_masternode')
    spec = dep['spec']['template']['spec']
    cs = spec['containers']
    need(len(cs) == 1 and cs[0]['name'] == 'qbittorrent' and cs[0]['image'] == args.expected_image, 'expected_image')
    need(cs[0].get('command') == ['$(MIGRATION_COMMAND_0)'], 'native_launch_reference')
    need(any(e.get('name') == 'MIGRATION_COMMAND_0' and e.get('valueFrom', {}).get('secretKeyRef') == {'name': 'qbittorrent-launch', 'key': 'command-0'} for e in cs[0].get('env', [])), 'native_launch_key')
    statuses = {s['name']: s for s in pod['status']['containerStatuses']}
    runtime = statuses['qbittorrent']['imageID'].rsplit('@', 1)[-1]
    need(runtime == args.expected_runtime, 'runtime_digest')
    need(pod['spec']['containers'][0]['image'] == args.expected_image, 'pod_image')
    gs = [c for c in spec.get('initContainers', []) if c['name'] == 'gluetun']
    need(len(gs) == 1 and gs[0].get('restartPolicy') == 'Always' and
         'NET_ADMIN' in gs[0].get('securityContext', {}).get('capabilities', {}).get('add', []) and gs[0].get('startupProbe'), 'vpn_wiring')
    gstatus = [s for s in pod['status'].get('initContainerStatuses', []) if s['name'] == 'gluetun']
    need(len(gstatus) == 1 and gstatus[0].get('ready') and gstatus[0].get('started'), 'vpn_not_ready')
    need(not spec.get('hostNetwork', False) and spec.get('dnsPolicy') == 'None' and spec.get('dnsConfig', {}).get('nameservers') == ['127.0.0.1'], 'vpn_dns')
    mspec = monitor['spec']['template']['spec']
    need({'qbittorrent-runtime', 'qbittorrent-launch', 'gluetun-runtime', 'gluetun-launch'} <= refs(spec), 'original_secret_refs')
    need('qbittorrent-runtime' in refs(mspec), 'monitor_credentials_reference')
    actual_claims = {v['persistentVolumeClaim']['claimName'] for s in (spec, mspec) for v in s.get('volumes', []) if 'persistentVolumeClaim' in v}
    need(set(CLAIMS) <= actual_claims, 'original_claim_refs')
    claim_state = {}
    for name, uid in CLAIMS.items():
        pvc = obj('pvc', name)
        need(pvc['metadata']['uid'] == uid and not pvc['metadata'].get('deletionTimestamp') and pvc['status'].get('phase') == 'Bound', 'original_claim_identity')
        claim_state[name] = {'uid': uid, 'spec_hmac': mac(pvc['spec'])}
    secret_state = {}
    for name in sorted(refs(spec) | refs(mspec)):
        md = json.loads(kube('get', 'secret', name, '-o', 'jsonpath={.metadata}'))
        need(not md.get('deletionTimestamp') and (name not in SECRETS or md['uid'] == SECRETS[name]), 'original_secret_identity')
        secret_state[name] = {'uid': md['uid'], 'resource_version': md['resourceVersion']}
    normalized = json.loads(json.dumps(dep['spec']))
    normalized['template']['spec']['containers'][0]['image'] = '<qualification-image>'
    # Images alone may change; credentials, launch, resources, mounts, VPN and monitor stay exact.
    service = obj('service', 'qbittorrent')
    ip = ipaddress.ip_address(service['spec']['clusterIP'])
    need(ip.is_private and not ip.is_loopback and not ip.is_link_local, 'service_address')
    ports = [p for p in service['spec']['ports'] if p['port'] == 8112 and p.get('protocol', 'TCP') == 'TCP']
    need(len(ports) == 1, 'service_api_port')
    slices = json.loads(kube('get', 'endpointslices', '-l', 'kubernetes.io/service-name=qbittorrent', '-o', 'json'))['items']
    endpoints = [e for s in slices for e in s.get('endpoints', []) if e.get('conditions', {}).get('ready')]
    need(endpoints and all(e.get('targetRef', {}).get('uid') == pod['metadata']['uid'] for e in endpoints), 'service_target')
    stable = {'deployment_uid': DEP_UID, 'deployment_spec_hmac': mac(normalized),
              'claims': claim_state, 'secrets': secret_state, 'monitor_uid': MONITOR_UID,
              'monitor_spec_hmac': mac(monitor['spec']), 'service_uid': service['metadata']['uid'],
              'service_spec_hmac': mac(service['spec'])}
    observed = {'pod_uid': pod['metadata']['uid'], 'restart_count': statuses['qbittorrent']['restartCount'],
                'vpn_restart_count': gstatus[0]['restartCount'], 'monitor_pod_uid': mpod['metadata']['uid'],
                'monitor_restarts': [s['restartCount'] for s in mpod['status']['containerStatuses']],
                'image': args.expected_image, 'runtime_digest': runtime}
    address = '[' + str(ip) + ']' if ip.version == 6 else str(ip)
    return stable, observed, pod['metadata']['name'], 'http://' + address + ':8112'


PROFILE_CODE = r'''
import configparser,hashlib,hmac,json,os,pathlib,stat,sys
try:
 key=bytes.fromhex(sys.stdin.read(65).strip())
 def mac(v):return hmac.new(key,json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(),hashlib.sha256).hexdigest()
 p=pathlib.Path('/config/qBittorrent'); conf=p/'qBittorrent.conf'
 assert conf.stat().st_size < 1048576 and not conf.is_symlink()
 cp=configparser.ConfigParser(interpolation=None,strict=True);cp.optionxform=str;cp.read(conf)
 mode=cp.get('BitTorrent','Session\\ResumeDataStorageType',fallback='Legacy')
 assert mode == 'Legacy'
 auth={k:v for section in cp.sections() for k,v in cp[section].items() if k.startswith('WebUI\\') and any(s in k.lower() for s in ['password','username','auth','whitelist','hostheader','csrf','address','port','https','ssl'])}
 assert any('Username' in k for k in auth) and any('Password_PBKDF2' in k for k in auth)
 folder=p/'BT_backup'; entries=list(folder.iterdir());assert len(entries)<=10000
 resumes={f.stem:f for f in entries if f.suffix=='.fastresume'};torrents={f.stem:f for f in entries if f.suffix=='.torrent'}
 assert resumes and set(resumes)==set(torrents)
 assert not any(f.suffix in ('.db','.sqlite','.sqlite3') for f in entries)
 modes=set()
 for f in list(resumes.values())+list(torrents.values()):
  assert not f.is_symlink() and f.is_file()
  s=f.stat();modes.add((s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)))
  if f.suffix=='.fastresume':
   with f.open('rb') as stream:assert stream.read(1)==b'd'
 metadata=[]
 for f in [pathlib.Path('/config'),p,folder,conf,pathlib.Path('/downloads')]:
  s=f.stat();metadata.append([s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)])
 legacy=pathlib.Path('/usr/bin/qbittorrent-nox'); vendor=pathlib.Path('/app/qbittorrent-nox')
 print(json.dumps({'legacy':True,'paired_count':len(resumes),'pair_ids':sorted(mac(k.lower()) for k in resumes),'auth_hmac':mac(auth),'metadata':metadata,'file_modes':sorted(modes),'legacy_path_executable':legacy.is_file() and os.access(legacy,os.X_OK),'legacy_resolves_to_vendor':legacy.exists() and vendor.exists() and legacy.samefile(vendor)}))
except Exception:
 sys.exit(1)
'''


def profile(pod, key):
    return json.loads(kube('exec', '-i', pod, '-c', 'qbittorrent', '--', 'python3', '-c', PROFILE_CODE,
                           data=key.hex().encode(), limit=1024 * 1024))


def forwarded_port(pod):
    # Gluetun is a Go image; do not assume it contains Python.
    raw = kube('exec', pod, '-c', 'gluetun', '--', 'head', '-c', '64', '/tmp/gluetun/forwarded_port', limit=64)
    need(len(raw) < 64 and re.fullmatch(rb'[0-9]{1,5}\s*', raw), 'forwarded_port_format')
    port = int(raw.strip())
    need(1 <= port <= 65535, 'forwarded_port_range')
    return port


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refused('api_redirect_refused')


class API:
    def __init__(self, base, user, password):
        self.base, self.bytes, self.calls = base, 0, 0
        self.cookies = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                                  urllib.request.HTTPCookieProcessor(self.cookies))
        payload = urllib.parse.urlencode({'username': user, 'password': password}).encode()
        need(self.request('auth/login', payload) == b'Ok.' and any(c.name == 'SID' and c.value for c in self.cookies), 'native_credentials_not_authenticated')

    def request(self, path, data=None):
        bounded()
        need((data is not None and path == 'auth/login') or (data is None and
             (path in ('app/version', 'app/buildInfo', 'app/preferences', 'torrents/info', 'torrents/categories', 'torrents/tags') or
              re.fullmatch(r'torrents/files\?hash=[0-9a-fA-F]{40,64}', path))), 'api_endpoint_not_allowed')
        self.calls += 1
        need(self.calls <= MAX_TORRENTS + 20, 'api_call_bound')
        req = urllib.request.Request(self.base + '/api/v2/' + path, data=data,
                                     headers={'Referer': self.base, 'Accept': 'application/json'},
                                     method='POST' if data is not None else 'GET')
        with self.client.open(req, timeout=10) as response:
            raw = response.read(MAX_REPLY + 1)
            self.bytes += len(raw)
            need(response.status == 200 and len(raw) <= MAX_REPLY and self.bytes <= MAX_TOTAL, 'api_response_bound')
            return raw

    def get(self, path):
        return json.loads(self.request(path))


def progress(value):
    need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1, 'progress_shape')
    return value


def torrent_rows(rows, mac):
    need(isinstance(rows, list) and len(rows) <= MAX_TORRENTS, 'torrent_bound')
    out, raw_ids = {}, {}
    for row in rows:
        need(isinstance(row, dict) and all(f in row for f in REQUIRED), 'torrent_required_fields')
        tid = row['hash']
        need(isinstance(tid, str) and re.fullmatch(r'[0-9a-fA-F]{40,64}', tid), 'torrent_identity_shape')
        ident = mac(tid.lower())
        need(ident not in out, 'duplicate_torrent_identity')
        fields = {k: row[k] for k in DURABLE if k in row}
        fields['tags'] = sorted(t.strip() for t in row['tags'].split(',') if t.strip())
        need(isinstance(row.get('state'), str), 'torrent_state_shape')
        need(row['state'] not in ('checkingUP', 'checkingDL', 'checkingResumeData', 'moving', 'unknown'), 'torrent_not_settled')
        fields['stopped_intent'] = row['state'].startswith('stopped')
        # Transient throughput/state changes are allowed, but newly broken torrents are not.
        fields['error_or_missing_files'] = row['state'] in ('error', 'missingFiles')
        out[ident] = {'fields': {k: mac(v) for k, v in fields.items()}, 'progress': progress(row['progress'])}
        raw_ids[ident] = tid
    return out, raw_ids


def capture(api, mac, expected_version):
    version = api.request('app/version').decode().strip().removeprefix('v')
    need(version == expected_version, 'application_version')
    build = api.get('app/buildInfo')
    expected_lt = '2.0.11' if expected_version == '5.1.4' else '2.0.15'
    # Upstream lt::version() includes a fourth release-tag component, normally .0.
    need(build.get('libtorrent') in (expected_lt, expected_lt + '.0'), 'libtorrent_version')
    prefs = api.get('app/preferences')
    need(isinstance(prefs, dict) and type(prefs.get('listen_port')) is int, 'preferences_shape')
    categories = api.get('torrents/categories')
    tags = api.get('torrents/tags')
    need(isinstance(categories, dict) and isinstance(tags, list) and all(isinstance(t, str) for t in tags), 'category_tag_shape')
    rows, ids = torrent_rows(api.get('torrents/info'), mac)
    total_files = 0
    for ident, tid in ids.items():
        files = api.get('torrents/files?hash=' + tid)
        need(isinstance(files, list), 'file_list_shape')
        total_files += len(files)
        need(total_files <= MAX_FILES, 'file_count_bound')
        projected = {}
        for f in files:
            need(isinstance(f, dict) and all(k in f for k in ('index', 'name', 'size', 'priority', 'progress')), 'file_fields')
            need(type(f['index']) is int and f['index'] >= 0 and str(f['index']) not in projected, 'file_identity')
            projected[str(f['index'])] = {'durable': mac({k: f[k] for k in ('index', 'name', 'size', 'priority')}), 'progress': progress(f['progress'])}
        rows[ident]['files'] = projected
    end, _ = torrent_rows(api.get('torrents/info'), mac)
    need(set(end) == set(rows) and all(end[k]['fields'] == rows[k]['fields'] and end[k]['progress'] + 1e-9 >= rows[k]['progress'] for k in rows), 'torrents_changed_during_observation')
    for ident in rows:
        rows[ident]['progress'] = end[ident]['progress']
    need(api.get('app/preferences') == prefs and api.get('torrents/categories') == categories and sorted(api.get('torrents/tags')) == sorted(tags), 'settings_changed_during_observation')
    return {'version': version, 'libtorrent': build['libtorrent'], 'native_credentials_authenticated': True,
            'preferences': {k: mac(v) for k, v in prefs.items() if k != 'listen_port'},
            'listen_port': prefs['listen_port'], 'categories_hmac': mac(categories), 'tags_hmac': mac(sorted(tags)),
            'torrents': rows, 'torrent_count': len(rows), 'file_count': total_files,
            'api_calls': api.calls, 'api_bytes': api.bytes}


def protected_read(path):
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'private_input_path')
    s = path.stat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077 and s.st_size <= MAX_TOTAL, 'private_input_permissions')
    return json.loads(path.read_bytes())


def output_path(path):
    need(path.is_absolute() and path.resolve() == path and not path.exists() and not path.is_symlink(), 'new_private_receipt_required')
    need(not any((p / '.git').exists() for p in path.parents), 'receipt_inside_git')
    p = path.parent.stat()
    need(stat.S_ISDIR(p.st_mode) and p.st_uid == os.getuid() and not p.st_mode & 0o077, 'receipt_directory_permissions')


def compare(before, after, approved):
    need(before.get('schema') == 1 and before.get('mode') == 'baseline' and before.get('passed'), 'baseline_shape')
    need(before['key_binding'] == after['key_binding'], 'hmac_key_changed')
    fail = []
    for k in ('identity', 'credential_binding', 'launch', 'auth_hmac'):
        if before[k] != after[k]:
            fail.append(k + '_changed')
    b, a = before['observation'], after['observation']
    for k in ('categories_hmac', 'tags_hmac'):
        if b[k] != a[k]:
            fail.append(k + '_changed')
    changed_preferences = sorted(k for k, v in b['preferences'].items() if a['preferences'].get(k) != v)
    if changed_preferences:
        fail.append('original_preferences_changed')
    old, new = b['torrents'], a['torrents']
    missing, added = sorted(set(old) - set(new)), sorted(set(new) - set(old))
    need(isinstance(approved, dict) and set(approved) == {'added', 'removed'}, 'inventory_approval_shape')
    for k in ('added', 'removed'):
        need(isinstance(approved[k], dict) and all(re.fullmatch('[0-9a-f]{64}', t) and isinstance(r, str) and r.strip() for t, r in approved[k].items()), 'inventory_approval_entries')
    if set(missing) != set(approved['removed']) or set(added) != set(approved['added']):
        fail.append('unapproved_inventory_change')
    durable_changed, progress_regressed, files_changed = [], [], []
    for ident in sorted(set(old) & set(new)):
        x, y = old[ident], new[ident]
        if any(y['fields'].get(k) != v for k, v in x['fields'].items()):
            durable_changed.append(ident)
        if y['progress'] + 1e-9 < x['progress']:
            progress_regressed.append(ident)
        if set(x['files']) != set(y['files']) or any(y['files'].get(k, {}).get('durable') != v['durable'] for k, v in x['files'].items()):
            files_changed.append(ident)
        elif any(y['files'][k]['progress'] + 1e-9 < v['progress'] for k, v in x['files'].items()):
            if ident not in progress_regressed:
                progress_regressed.append(ident)
    if durable_changed: fail.append('durable_torrent_fields_changed')
    if progress_regressed: fail.append('progress_regressed')
    if files_changed: fail.append('file_identity_or_priority_changed')
    for k in ('metadata', 'file_modes'):
        if before['profile'][k] != after['profile'][k]: fail.append('profile_' + k + '_changed')
    return {'failures': fail, 'missing_ids': missing, 'added_ids': added,
            'durable_changed_ids': durable_changed, 'progress_regressed_ids': progress_regressed,
            'file_changed_ids': files_changed, 'changed_preference_names': changed_preferences,
            'inventory_approval_used': bool(approved['added'] or approved['removed'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('baseline', 'after'))
    parser.add_argument('--expected-image', required=True)
    parser.add_argument('--expected-runtime', required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--approved-inventory', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    need(os.name == 'posix' and socket.gethostname().split('.')[0].lower() == 'masternode', 'must_execute_on_cluster_masternode')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(Refused('observation_deadline')))
    signal.alarm(MAX_SECONDS)
    os.umask(0o077)
    output_path(args.receipt)
    need(re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', args.expected_image) and re.fullmatch(r'sha256:[0-9a-f]{64}', args.expected_runtime), 'immutable_images_required')
    need((args.mode == 'baseline') == (args.baseline is None) and (not args.approved_inventory or args.mode == 'after'), 'mode_arguments')
    raw = sys.stdin.buffer.read(66)
    need(re.fullmatch(b'[0-9a-f]{64}\n?', raw), 'stdin_hmac_key_required')
    key = bytes.fromhex(raw.decode().strip())
    mac = lambda value: hmac.new(key, canonical(value), hashlib.sha256).hexdigest()
    prior = protected_read(args.baseline) if args.baseline else None
    approved = protected_read(args.approved_inventory) if args.approved_inventory else {'added': {}, 'removed': {}}
    stable, runtime, pod, base = identity(args, mac)
    prof = profile(pod, key)
    native, launch = obj('secret', 'qbittorrent-runtime'), obj('secret', 'qbittorrent-launch')
    need(native['metadata']['uid'] == SECRETS['qbittorrent-runtime'] and launch['metadata']['uid'] == SECRETS['qbittorrent-launch'], 'credential_secret_identity')
    credential_binding = mac({'runtime': native['data'], 'launch': launch['data']})
    username = base64.b64decode(native['data']['QBITTORRENT_USERNAME'], validate=True).decode()
    password = base64.b64decode(native['data']['QBITTORRENT_PASSWORD'], validate=True).decode()
    launcher = base64.b64decode(launch['data']['command-0'], validate=True).decode()
    need(username and password and len(username) < 4096 and len(password) < 4096 and len(launcher) < 65536, 'credential_shape')
    launch_flags = {'references_legacy_usr_bin': '/usr/bin/qbittorrent-nox' in launcher,
                    'references_vendor_app': '/app/qbittorrent-nox' in launcher,
                    'references_binary_name': 'qbittorrent-nox' in launcher}
    need(not launch_flags['references_legacy_usr_bin'] or prof['legacy_path_executable'], 'native_launch_legacy_path_missing')
    del launcher, native, launch
    port = forwarded_port(pod)
    api = API(base, username, password)
    del username, password
    observation = capture(api, mac, '5.1.4' if args.mode == 'baseline' else '5.3.0')
    need(observation['listen_port'] == port == forwarded_port(pod), 'forwarded_listen_port_mismatch_or_changed')
    # Resume filenames are infohashes; this binds the disk inventory to authenticated API IDs.
    need(set(prof['pair_ids']) == set(observation['torrents']), 'resume_api_inventory_mismatch')
    if args.mode == 'baseline': need(observation['torrent_count'] == 231, 'expected_231_baseline_torrents')
    finish_stable, finish_runtime, _, _ = identity(args, mac)
    need(stable == finish_stable and runtime == finish_runtime, 'runtime_or_wiring_changed_during_capture')
    finish_profile = profile(pod, key)
    need(prof == finish_profile, 'profile_changed_during_capture')
    receipt = {'schema': 1, 'mode': args.mode, 'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'key_binding': mac('qbittorrent-observer-v1'), 'identity': stable, 'runtime': runtime,
               'credential_binding': credential_binding, 'launch': launch_flags, 'auth_hmac': prof['auth_hmac'],
               'profile': prof, 'observation': observation, 'forwarded_port_matches': True,
               'legacy_resume_retained': True, 'comparison': None, 'passed': True,
               'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None,
               'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'only_api_post': 'auth/login', 'cold_copy_verified': False, 'restore_verified': False,
               'tracker_connectivity_verified': False, 'full_acceptance_complete': False}
    if prior:
        receipt['comparison'] = compare(prior, receipt, approved)
        receipt['passed'] = not receipt['comparison']['failures']
    with os.fdopen(os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': 'passed' if receipt['passed'] else 'comparison_failed', 'mode': args.mode,
                      'torrent_count': observation['torrent_count'], 'file_count': observation['file_count'],
                      'native_credentials_authenticated': True, 'legacy_resume_retained': True,
                      'launch': launch_flags, 'forwarded_port_matches': True,
                      'failures': receipt['comparison']['failures'] if prior else [], 'full_acceptance_complete': False}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Refused as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'status': 'refused', 'reason': 'operation_failed_raw_details_suppressed'}))
        raise SystemExit(1)
