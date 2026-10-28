#!/usr/bin/env python3
"""Verify the exact monitor repair against the original qBit and cold state.

Master-node only. stdin JSON carries the existing observer key plus authenticated
cold file metadata. No raw credentials, notification IDs, messages or API values
are printed. One authentication POST; no production writes or test notifications.
"""
import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import socket
import sys

sp = importlib.util.spec_from_file_location('q', Path(__file__).with_name('qualify-qbittorrent.py'))
q = importlib.util.module_from_spec(sp)
sp.loader.exec_module(q)
OLD = 'jtmb92/qbit-monitor@sha256:b1ba462564843f9f328b287a34e8a7dc4cd1f218e085862a77f42aaa1703ffec'
NEW = 'docker.io/library/qbit-monitor-security-20261023@sha256:ff2141541ec06f04df3acd145a8a94c33f6bb9e327615ff314994efeb199c4fe'
QBIT = 'docker.io/library/qbittorrent-current-security-20261023@sha256:9e546e0ac277ef9b241cb383bfa9157e47df3269e62481348a63f4d19b87adf8'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    q.need(socket.gethostname().split('.')[0].lower() == 'masternode', 'master_only')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    q.output_path(a.receipt)
    request = json.loads(sys.stdin.buffer.read(8193))
    key = bytes.fromhex(request.pop('key'))
    q.need(len(key) == 32 and set(request) == {'cold_state'}, 'existing_key_and_cold_binding')
    cold = request['cold_state']
    q.need(0 < cold['bytes'] <= 1024**2 and re.fullmatch('[a-f0-9]{64}', cold['sha256']), 'cold_state_shape')
    mac = lambda v: hmac.new(key, q.canonical(v), hashlib.sha256).hexdigest()
    before = q.protected_read(a.baseline)
    q.need(before['passed'] and before['key_binding'] == mac('qbittorrent-observer-v1'), 'original_baseline')
    args = argparse.Namespace(expected_image=QBIT, expected_runtime=QBIT.rsplit('@', 1)[1])
    stable, runtime, pod, base = q.identity(args, mac)
    monitor, mpod = q.ready_deployment('qbit-monitor', q.MONITOR_UID)
    q.need(len(monitor['spec']['template']['spec']['containers']) == 1 and
           monitor['spec']['template']['spec']['containers'][0]['image'] == NEW and
           mpod['status']['containerStatuses'][0]['imageID'].endswith(NEW.rsplit('@', 1)[1]), 'exact_monitor_image')
    # One reviewed additional image delta; every other original monitor field,
    # including alert configuration, mounts, resources and state claim, is exact.
    spec = json.loads(json.dumps(monitor['spec']))
    spec['template']['spec']['containers'][0]['image'] = OLD
    stable['monitor_spec_hmac'] = mac(spec)
    q.need(stable == before['identity'], 'original_wiring_or_native_secret_changed')
    name = mpod['metadata']['name']
    raw = q.kube('exec', name, '--', 'stat', '-c', '%u:%g:%a:%s', '/app/state/notified_torrents.txt', limit=256)
    uid, gid, mode, size = raw.decode().strip().split(':')
    q.need((int(uid), int(gid), int(mode, 8)) == (cold['uid'], cold['gid'], cold['mode']) and
           cold['bytes'] <= int(size) <= 1024**2, 'notification_state_metadata_or_truncation')
    # Detection modules append notification records. Every original byte must
    # remain; a valid newly notified torrent can add records after this prefix.
    prefix = q.kube('exec', name, '--', 'sh', '-c',
        'head -c ' + str(cold['bytes']) + ' /app/state/notified_torrents.txt | sha256sum', limit=256)
    q.need(prefix.decode().split()[0] == cold['sha256'], 'original_notification_state_changed')
    logs = q.kube('logs', name, '--tail=1000', limit=2 * 1024**2).decode(errors='replace')
    queue_cycles = logs.count('Torrents Validated.')
    q.need(queue_cycles >= 2 and 'Login successful' in logs and
           ('listen_port updated' in logs or 'Port is unchanged. No update needed.' in logs) and
           'Login failed' not in logs and 'Unable to retrieve torrent state' not in logs,
           'real_monitor_queue_or_forwarding_not_proven')
    prof = q.profile(pod, key)
    native, launch = q.obj('secret', 'qbittorrent-runtime'), q.obj('secret', 'qbittorrent-launch')
    binding = mac({'runtime': native['data'], 'launch': launch['data']})
    user = base64.b64decode(native['data']['QBITTORRENT_USERNAME']).decode()
    password = base64.b64decode(native['data']['QBITTORRENT_PASSWORD']).decode()
    launcher = base64.b64decode(launch['data']['command-0']).decode()
    launch_flags = {'references_legacy_usr_bin': '/usr/bin/qbittorrent-nox' in launcher,
                    'references_vendor_app': '/app/qbittorrent-nox' in launcher,
                    'references_binary_name': 'qbittorrent-nox' in launcher}
    api = q.API(base, user, password)
    del native, launch, user, password, launcher
    port = q.forwarded_port(pod)
    observation = q.capture(api, mac, '5.3.0')
    q.need(set(prof['pair_ids']) == set(observation['torrents']), 'resume_inventory')
    report = {'schema': 1, 'mode': 'after', 'key_binding': before['key_binding'],
        'identity': stable, 'credential_binding': binding, 'launch': launch_flags,
        'auth_hmac': prof['auth_hmac'], 'profile': prof, 'observation': observation,
        'forwarded_port_matches': observation['listen_port'] == port == q.forwarded_port(pod),
        'runtime': runtime, 'monitor_image': NEW, 'monitor_pod_uid': mpod['metadata']['uid'],
        'monitor_restart_count': mpod['status']['containerStatuses'][0]['restartCount'],
        'original_notification_bytes_preserved': cold['bytes'], 'current_notification_bytes': int(size),
        'actual_queue_cycles': queue_cycles, 'original_alert_configuration_unchanged': True,
        'test_notification_sent': False, 'browser_complete': False}
    report['comparison'] = q.compare(before, report, {'added': {}, 'removed': {}})
    report['passed'] = not report['comparison']['failures']
    report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with os.fdopen(os.open(a.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(report, f, sort_keys=True, indent=2)
    print(json.dumps({'passed': report['passed'], 'failures': report['comparison']['failures'],
        'original_notification_bytes_preserved': cold['bytes'], 'actual_queue_cycles': queue_cycles,
        'torrents': observation['torrent_count'], 'files': observation['file_count'],
        'forwarded_port_matches': report['forwarded_port_matches'], 'test_notification_sent': False}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'passed': False, 'raw_details_suppressed': True}))
        raise SystemExit(1)
