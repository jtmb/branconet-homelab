#!/usr/bin/env python3
"""Restore only source-proven5.1 defaults after the exact5.3 image update.

Run on masternode. Supply the existing observer HMAC key on stdin. No credential,
cookie or settings values are printed. Refuse custom or concurrently changed
values. The original baseline must prove every restored historical value.
Native Secrets, torrent data, alerts and authentication settings are untouched.
"""
import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import resource
import socket
import sys
import urllib.parse
import urllib.request

spec = importlib.util.spec_from_file_location('observer', Path(__file__).with_name('qualify-qbittorrent.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
IMAGE = 'docker.io/library/qbittorrent-current-security-20261023@sha256:9e546e0ac277ef9b241cb383bfa9157e47df3269e62481348a63f4d19b87adf8'
HISTORICAL = {
    'mail_notification_sender': 'qBittorrent_notification@example.com',
    'mail_notification_smtp': 'smtp.changeme.com',
    'dht_bootstrap_nodes': 'dht.libtorrent.org:25401, dht.transmissionbt.com:6881, router.bittorrent.com:6881',
    'peer_tos': 4,
}
NEW_DEFAULTS = {
    'mail_notification_sender': '', 'mail_notification_smtp': '',
    'dht_bootstrap_nodes': 'dht.libtorrent.org:25401, dht.transmissionbt.com:6881, router.bt.ouinet.work:6881',
    'peer_tos': 1, 'mail_notification_encryption_type': 'SMTPS',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    a = parser.parse_args()
    q.need(a.apply and socket.gethostname().split('.')[0].lower() == 'masternode', 'explicit_masternode_scope')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    q.output_path(a.receipt)
    key = bytes.fromhex(sys.stdin.read(66).strip())
    q.need(len(key) == 32, 'existing_hmac_key_required')
    mac = lambda v: hmac.new(key, q.canonical(v), hashlib.sha256).hexdigest()
    baseline = q.protected_read(a.baseline)
    q.need(baseline['passed'] and baseline['mode'] == 'baseline' and
           baseline['key_binding'] == mac('qbittorrent-observer-v1'), 'original_baseline_identity')
    old = baseline['observation']['preferences']
    q.need(all(old[k] == mac(v) for k, v in HISTORICAL.items()) and
           old['mail_notification_ssl_enabled'] == mac(False), 'custom_historical_settings_refused')
    args = argparse.Namespace(expected_image=IMAGE, expected_runtime=IMAGE.rsplit('@', 1)[1])
    identity, runtime, pod, base = q.identity(args, mac)
    secret = q.obj('secret', 'qbittorrent-runtime')
    user = base64.b64decode(secret['data']['QBITTORRENT_USERNAME'], validate=True).decode()
    password = base64.b64decode(secret['data']['QBITTORRENT_PASSWORD'], validate=True).decode()
    api = q.API(base, user, password)
    del user, password, secret
    q.need(api.request('app/version').decode().strip() == 'v5.3.0', 'exact_application_version')
    current = api.get('app/preferences')
    target = dict(HISTORICAL, mail_notification_encryption_type='None')
    q.need(current.get('mail_notification_enabled') is False, 'notification_configuration_changed')
    q.need(all(current.get(k) in (NEW_DEFAULTS[k], v) for k, v in target.items()), 'concurrent_or_custom_settings_refused')
    port = q.forwarded_port(pod)
    target['listen_port'] = port
    changes = {k: v for k, v in target.items() if current.get(k) != v}
    q.need(api.get('app/preferences') == current and q.forwarded_port(pod) == port, 'concurrent_settings_or_forwarded_port_change')
    if changes:
        body = urllib.parse.urlencode({'json': json.dumps(changes, separators=(',', ':'))}).encode()
        request = urllib.request.Request(base + '/api/v2/app/setPreferences', data=body,
            headers={'Referer': base, 'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        with api.client.open(request, timeout=10) as response:
            result = response.read(1025)
            q.need(response.status in (200, 204) and len(result) <= 1024, 'settings_update_refused')
    after = api.get('app/preferences')
    q.need(all(after.get(k) == v for k, v in target.items()), 'settings_readback_mismatch')
    q.need({k: v for k, v in current.items() if k not in target} ==
           {k: v for k, v in after.items() if k not in target}, 'unrelated_preference_changed')
    final_identity, final_runtime, _, _ = q.identity(args, mac)
    q.need(final_identity == identity and final_runtime == runtime and q.forwarded_port(pod) == port,
           'identity_or_forwarded_port_changed')
    receipt = {'schema': 1, 'passed': True, 'changed_names': sorted(changes),
               'before_hmac': mac(current), 'after_hmac': mac(after),
               'original_baseline_sha256': hashlib.sha256(a.baseline.read_bytes()).hexdigest(),
               'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'native_secrets_unchanged': True, 'forwarded_port_matches': True,
               'no_torrent_mutation': True, 'full_acceptance_complete': False}
    with os.fdopen(os.open(a.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(receipt, f, sort_keys=True, indent=2)
        f.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'passed': False, 'raw_details_suppressed': True}))
        raise SystemExit(1)
