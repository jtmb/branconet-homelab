#!/usr/bin/env python3
"""xTeVe local-state/identity/HTTP proof. No scaling, login or provider streams.

Controller modes: baseline, cold, after, restart. A persistent 64-hex HMAC key
arrives on stdin. Tar plaintext is streamed through RAM, never extracted.
"""
import argparse
import base64
import copy
import datetime
import gzip
import hashlib
import hmac
import importlib.util
import io
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import shlex
import socket
import stat
import subprocess
import sys
import tarfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

OLD = 'alturismo/xteve:latest@sha256:7885f2759c0da3c5f2c72b2e45ba4b602bdd7d6f04cc6abba201091f11c93a95'
NEW = 'docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'
DEP = '52adec00-5c42-4cd2-8fb0-9428828ca368'
HR = 'ace99a34-343b-40cd-b1b3-6ef2f324a8b0'
NODE = 'eda66e65-f388-4b97-b64f-a709cda81894'
SERVICE = 'e87b3fdb-c58e-4c84-86f1-2e8f7184999a'
SECRET = '176c57f7-b8bf-4149-87b1-95b747020c78'
CLAIMS = {
    'xteve-data-0': ('d40f1490-7254-4599-be82-2fad35abb88b', '0ab90957-d5ce-496d-9ddc-658299729a15', 'pvc-d40f1490-7254-4599-be82-2fad35abb88b', 'driver.longhorn.io'),
    'xteve-data-1': ('b7207fe9-3768-4ad5-9ca0-ee4429137b33', '8be538e5-bcca-490e-b075-7556d1c0aa31', 'pvc-b7207fe9-3768-4ad5-9ca0-ee4429137b33', 'driver.longhorn.io'),
    'xteve-data-3': ('93527524-e3c1-4e2e-a9c4-1a844743d8b1', '548595f5-a4ea-4b8d-a225-1f15d7b3c09e', 'plex-xteve-data-3', 'smb.csi.k8s.io'),
}
MOUNTS = [{'name': 'data-0', 'mountPath': '/root/.xteve'}, {'name': 'data-1', 'mountPath': '/config'},
          {'name': 'data-2', 'mountPath': '/tmp/xteve'}, {'name': 'data-3', 'mountPath': '/iptv'}]
VOLUMES = [{'name': 'data-' + str(n), 'persistentVolumeClaim': {'claimName': 'xteve-data-' + str(n)}}
           if n != 2 else {'name': 'data-2', 'emptyDir': {'medium': 'Memory'}} for n in range(4)]
SOURCE_COMMIT = '0e999b85b9c77c3fdcfcfaf5e96150523fd4481b'
# Baseline01 predates quiescence. Its exact revision remains supported: added
# derivation proofs retain the original path/content HMAC and comparison domains.
BASELINE_OBSERVER_SHA256 = '32f6530f0a2f84d18d849dbc9eda257101ab962c85512c60cb8c3f107a701308'
MAX_DATA = 4 * 1024**3
MAX_PARSE = 32 * 1024**2
PARSED = {'settings.json', 'xepg.json', 'urls.json', 'pms.json', 'data/xteve.xml', 'data/xteve.xml.gz', 'data/xteve.m3u'}
DERIVED = {'data/xteve.xml', 'data/xteve.xml.gz', 'data/xteve.m3u', 'urls.json'}
BACKUP_PATTERN = re.compile(r'backup/xteve_auto_backup_(\d{8}_\d{4})\.zip')
SYSTEM_FILES = {'authentication.json', 'pms.json', 'settings.json', 'xepg.json', 'urls.json'}
PROVIDER_OBSERVATIONS = {'last.update', 'counter.download', 'counter.error', 'provider.availability'}
RUNTIME_SOURCE_PINS = {
    'src/backup.go': 'a59629f10349918359c946b35fc06b8c7eef928ac3f7dbfd9dd8f605f76f204e',
    'src/provider.go': '6ac294eece3d6d6c6ecad2765fe5689c8aeabf7c6a75e66619d084aac20e5a82',
    'src/xepg.go': '48484378d4ccd7f0f281d9d50f9cd6f900666e22431d708fcd6ceac7318c2ecb',
    'src/compression.go': '71c6761671d7533d9aebcb15523e9b3c7cbe6403517c305cc7a0e41b8bd3f25b',
}


class Refusal(ValueError):
    """Only finite source-written stage labels may leave the observer."""


def need(ok, stage='guard'):
    if not ok: raise Refusal(stage)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def mac(key, domain, value):
    return hmac.new(key, canonical(['xteve-state-v1', domain, value]), hashlib.sha256).hexdigest()


def json_object(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate-json-key'); result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'nonfinite-json'))


def xml_semantics(raw):
    need(len(raw) <= MAX_PARSE and b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'xml-bound')
    root = ET.fromstring(raw)
    def node(element):
        children = list(element)
        return [element.tag, sorted(element.attrib.items()), element.text or '' if not children else (element.text or '').strip(),
                [node(c) for c in children]]
    value = node(root)
    # xepg.go ranges a Go map: only top-level channel/program order is unstable.
    if root.tag == 'tv': value[3] = sorted(value[3], key=canonical)
    return value


def m3u_semantics(raw):
    text = raw.decode('utf-8'); lines = text.splitlines()
    need(lines and lines[0].startswith('#EXTM3U '), 'generated-playlist-header')
    origins = set()
    def origin(match):
        uri = urllib.parse.urlsplit(match.group(0)); need(uri.scheme in ['http', 'https'] and not uri.username and not uri.password, 'generated-playlist-origin')
        origins.add((uri.scheme, uri.netloc)); return '<generated-origin>' + uri.path
    lines[0] = re.sub(r'https?://[^"\s]+/xmltv/xteve\.xml', origin, lines[0])
    for i in range(1, len(lines)):
        if not lines[i] or lines[i].startswith('#'): continue
        uri = urllib.parse.urlsplit(lines[i])
        need(uri.scheme in ['http', 'https'] and not uri.username and not uri.password and not uri.query and not uri.fragment, 'generated-playlist-url')
        need(re.fullmatch('/stream/[0-9a-f]{32}', uri.path) is not None, 'generated-stream-id')
        origins.add((uri.scheme, uri.netloc)); lines[i] = '<generated-origin>' + uri.path
    need(len(origins) == 1, 'generated-playlist-single-origin')
    return lines


def settings_runtime_contract(value, key):
    """Keep all user configuration; separately prove exact provider observations."""
    stable = copy.deepcopy(value); stable['xteveAutoUpdate'] = '<reviewed-maintenance-boolean>'
    providers = {}
    for kind, rows in value.get('files', {}).items():
        need(kind in ['m3u', 'xmltv', 'hdhr'] and isinstance(rows, dict), 'provider-schema')
        for provider_id, row in rows.items():
            need(isinstance(row, dict), 'provider-object')
            identity = copy.deepcopy(row)
            for field in PROVIDER_OBSERVATIONS: identity.pop(field, None)
            compatibility = identity.get('compatibility', {})
            need(isinstance(compatibility, dict), 'provider-compatibility')
            if kind == 'xmltv':
                compatibility.pop('xmltv.channels', None); compatibility.pop('xmltv.programs', None)
            stable['files'][kind][provider_id] = identity
            filename = row.get('file.xteve')
            need(isinstance(filename, str) and filename and PurePosixPath(filename).name == filename and filename not in ['.', '..'], 'provider-cache-name')
            observations = {k: row.get(k) for k in PROVIDER_OBSERVATIONS}
            for field in ['counter.download', 'counter.error', 'provider.availability']:
                v = observations[field]; need(type(v) in [int, float] and int(v) == v and 0 <= v <= 10**9, 'provider-counter')
                observations[field] = int(v)
            timestamp = observations.pop('last.update')
            need(isinstance(timestamp, str), 'provider-date')
            # A naive ordinal preserves local-clock ordering without assuming TZ.
            date = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') if timestamp else None
            observations['last_update_ordinal'] = date.toordinal() * 86400 + date.hour * 3600 + date.minute * 60 + date.second if date else None
            providers[mac(key, 'provider-id', [kind, provider_id])] = {
                'kind': kind, 'identity_hmac': mac(key, 'provider-identity', identity),
                'cache_path_hmac': mac(key, 'path', ['state', 'data/' + filename]),
                'observations': observations,
                'xml_channels': row.get('compatibility', {}).get('xmltv.channels') if kind == 'xmltv' else None,
                'xml_programmes': row.get('compatibility', {}).get('xmltv.programs') if kind == 'xmltv' else None,
            }
    return {'configuration_hmac': mac(key, 'all-user-configuration', stable), 'providers': providers,
            'backup_keep': value.get('backup.keep'), 'standard_backup_path': value.get('backup.path') == '/root/.xteve/backup/'}


def provider_xml_proof(raw, key):
    value = xml_semantics(raw); need(value[0] == 'tv', 'provider-XMLTV-root')
    programs = [x for x in value[3] if x[0] == 'programme']
    other = [x for x in value[3] if x[0] != 'programme']
    return {'channels': sum(x[0] == 'channel' for x in other), 'programmes': len(programs),
            'non_programme_hmac': mac(key, 'provider-XMLTV-identity', [value[0], [p for p in value[1] if p[0] != 'date'], value[2], other]),
            'programme_hmac': mac(key, 'provider-XMLTV-programmes', programs)}


def backup_zip_proof(raw, key):
    members = {}; settings = None; total = 0; seen = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        for info in bundle.infolist():
            name = info.filename.rstrip('/')
            need(name not in seen and not name.startswith('/') and '..' not in PurePosixPath(name).parts, 'backup-member-path')
            seen.add(name); need(len(seen) <= 4096 and not info.flag_bits & 1, 'backup-member-bound')
            need(name in SYSTEM_FILES or name == 'data/images' or name.startswith('data/images/'), 'backup-source-scope')
            mode = info.external_attr >> 16
            need(not stat.S_ISLNK(mode), 'backup-symlink')
            if info.is_dir(): continue
            total += info.file_size; need(total <= MAX_PARSE, 'backup-plaintext-bound')
            body = bundle.read(info); need(len(body) == info.file_size, 'backup-member-length')
            token = mac(key, 'path', ['state', name])
            members[token] = mac(key, ['file-bytes', 'state', name], hashlib.sha256(body).hexdigest())
            if name == 'settings.json':
                value = json_object(body); settings = settings_runtime_contract(value, key)
                settings['auto_update'] = value.get('xteveAutoUpdate')
    need(SYSTEM_FILES <= seen and settings is not None, 'backup-system-files')
    return {'members': members, 'settings': settings}


def entry_record(scope, name, metadata, digest, raw, key):
    token = mac(key, 'path', [scope, name]); record = dict(metadata)
    record['raw_hmac'] = mac(key, ['file-bytes', scope, name], digest)
    record['comparison'] = record['raw_hmac']; record['rule'] = 'exact-bytes'
    detail = {}
    if scope == 'state' and name in PARSED and raw is not None:
        if name.endswith('.json'):
            value = json_object(raw); need(isinstance(value, dict), 'system-json-object')
            if name == 'settings.json':
                need(isinstance(value.get('xteveAutoUpdate'), bool), 'updater-boolean')
                detail = {'auto_update': value['xteveAutoUpdate'], 'api': value.get('api', False),
                          'authentication_api': value.get('authentication.api', False),
                          'authentication_pms': value.get('authentication.pms', False),
                          'authentication_m3u': value.get('authentication.m3u', False),
                          'authentication_xml': value.get('authentication.xml', False),
                          'files_update': value.get('files.update'), 'uuid_hmac': mac(key, 'uuid', value.get('uuid')),
                          'configuration_hmac': mac(key, 'original-settings', value)}
                detail['runtime_contract'] = settings_runtime_contract(value, key)
                value['xteveAutoUpdate'] = '<reviewed-maintenance-boolean>'
            elif name == 'xepg.json':
                detail = {'mapping_count': len(value), 'active_mapping_count': sum(v.get('x-active', False) is True for v in value.values() if isinstance(v, dict))}
            record['comparison'] = mac(key, ['json', name], value); record['rule'] = 'complete-json'
        elif name.endswith('.xml') or name.endswith('.xml.gz'):
            if name.endswith('.gz'):
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz: raw = gz.read(MAX_PARSE + 1)
                need(len(raw) <= MAX_PARSE, 'xml-gzip-bound')
            record['comparison'] = mac(key, ['xml', 'data/xteve.xml'], xml_semantics(raw)); record['rule'] = 'complete-xml-unordered-root'
        else:
            record['comparison'] = mac(key, 'generated-playlist', m3u_semantics(raw)); record['rule'] = 'complete-playlist-request-origin'
    return token, record, detail


def read_tar(stream, scope, key, archive_manifest=None):
    entries = {}; details = {}; total = 0; seen = set(); provider_xml = {}; backups = {}
    with tarfile.open(fileobj=stream, mode='r|') as bundle:
        for member in bundle:
            original = member.name.rstrip('/')
            if archive_manifest is not None and original == 'manifest.json':
                need(not seen and member.isfile() and member.size <= 8 * 1024**2, 'manifest-member')
                raw = bundle.extractfile(member).read(); need(json.loads(raw) == archive_manifest, 'manifest-second-pass'); continue
            if archive_manifest is not None:
                need(original == 'data-0' or original.startswith('data-0/'), 'archive-root')
                name = original[7:] if original.startswith('data-0/') else ''
            else:
                need(original == '.' or original.startswith('./'), 'tar-root'); name = original[2:] if original.startswith('./') else ''
            need(not name.startswith('/') and '..' not in PurePosixPath(name).parts and name not in seen, 'tar-path')
            seen.add(name); need(len(seen) <= 4096, 'entry-bound')
            metadata = {'uid': member.uid, 'gid': member.gid, 'mode': member.mode}
            raw = None; detail = {}
            if member.isdir(): metadata['kind'] = 'directory'; digest = None
            elif member.issym(): metadata['kind'] = 'symlink'; digest = ['symlink', member.linkname]
            else:
                need(member.isfile() and not member.islnk(), 'regular-file')
                metadata.update(kind='file', bytes=member.size); total += member.size
                need(total <= MAX_DATA and member.size >= 0, 'data-bound')
                is_provider_xml = scope == 'state' and len(PurePosixPath(name).parts) == 2 and name.startswith('data/') and name.endswith('.xml') and name != 'data/xteve.xml'
                backup_match = BACKUP_PATTERN.fullmatch(name) if scope == 'state' else None
                collect = scope == 'state' and (name in PARSED or backup_match or is_provider_xml and member.size <= MAX_PARSE)
                if collect: need(member.size <= MAX_PARSE, 'parse-bound')
                body = bundle.extractfile(member); digestor = hashlib.sha256(); chunks = []; count = 0
                for block in iter(lambda: body.read(1024**2), b''):
                    count += len(block); digestor.update(block)
                    if collect: chunks.append(block)
                need(count == member.size, 'file-length'); digest = digestor.hexdigest()
                if collect: raw = b''.join(chunks)
            if archive_manifest is not None:
                row = archive_manifest['entries'][original]
                need(all(metadata[k] == row[k] for k in ['kind', 'uid', 'gid', 'mode']), 'archive-metadata')
                if member.isfile(): need(member.size == row['bytes'] and digest == row['sha256'], 'archive-content')
                if member.issym(): need(member.linkname == row['link'], 'archive-link')
            token, record, detail = entry_record(scope, name, metadata, digest, raw, key)
            entries[token] = record
            if detail: details[name] = detail
            if member.isfile() and raw is not None:
                if is_provider_xml:
                    try: provider_xml[token] = {'valid': True, **provider_xml_proof(raw, key)}
                    except Exception: provider_xml[token] = {'valid': False}
                if backup_match:
                    stamp = datetime.datetime.strptime(backup_match.group(1), '%Y%m%d_%H%M')
                    try: proof = {'valid': True, **backup_zip_proof(raw, key)}
                    except Exception: proof = {'valid': False}
                    backups[token] = {'order': int(stamp.strftime('%Y%m%d%H%M')), 'proof': proof}
    need('' in seen, 'root-missing')
    if archive_manifest is not None: need(len(seen) == len(archive_manifest['entries']) and total == archive_manifest['total_file_bytes'], 'archive-complete')
    return {'entries': entries, 'details': details, 'total_bytes': total, 'entry_count': len(entries),
            'provider_xml': provider_xml, 'generated_backups': backups}


def compare_tree(old, new):
    if set(old['entries']) != set(new['entries']): return False
    for name, left in old['entries'].items():
        right = new['entries'][name]
        # Full values remain compared after the source-proven serialization rule.
        fields = ['kind', 'uid', 'gid', 'mode', 'comparison', 'rule']
        if left['rule'] == 'exact-bytes': fields.append('bytes')
        if any(left.get(k) != right.get(k) for k in fields): return False
    return True


def compare_runtime_state(old, new, key, startup_cycles, original_cold_archive=True):
    """Explain exact startup observations; never claim changed caches byte-equal.

    Caller must authenticate the complete original cold archives separately.
    Every original non-derived file, configuration field and mapping stays strict.
    """
    report = {'passed': False, 'source_commit': SOURCE_COMMIT, 'source_file_sha256': RUNTIME_SOURCE_PINS,
              'startup_cycles': startup_cycles, 'rotated_generated_backups': 0, 'new_generated_backups': 0,
              'provider_XML_refreshes': [], 'provider_observation_changes': 0,
              'comparison_anchor_is_authenticated_cold_archive': original_cold_archive,
              'all_live_bytes_unchanged': False, 'failures': []}
    try:
        need(startup_cycles in [1, 2], 'finite-startup-count')
        a = old['details']['settings.json']['runtime_contract']; b = new['details']['settings.json']['runtime_contract']
        need(a['configuration_hmac'] == b['configuration_hmac'], 'all-user-configuration')
        need(set(a['providers']) == set(b['providers']), 'provider-identities')
        refreshable = {}
        for pid, prior in a['providers'].items():
            now = b['providers'][pid]
            need(all(prior[k] == now[k] for k in ['kind', 'identity_hmac', 'cache_path_hmac']), 'provider-path-URL-credentials')
            x, y = prior['observations'], now['observations']
            downloads = y['counter.download'] - x['counter.download']; errors = y['counter.error'] - x['counter.error']
            need(downloads == startup_cycles and 0 <= errors <= downloads, 'provider-attempt-count')
            expected = 100 if y['counter.error'] == 0 else int(y['counter.error'] * 100 / y['counter.download'] * -1 + 100)
            need(y['provider.availability'] == expected, 'provider-availability-formula')
            if errors == downloads: need(y['last_update_ordinal'] == x['last_update_ordinal'], 'failed-provider-date')
            else:
                need(y['last_update_ordinal'] is not None and (x['last_update_ordinal'] is None or y['last_update_ordinal'] >= x['last_update_ordinal']), 'successful-provider-date')
                utc = datetime.datetime.now(datetime.timezone.utc)
                need(y['last_update_ordinal'] <= utc.toordinal() * 86400 + utc.hour * 3600 + utc.minute * 60 + utc.second + 15 * 3600, 'provider-date-not-future')
            report['provider_observation_changes'] += 1
            token = prior['cache_path_hmac']
            if old['entries'].get(token, {}).get('raw_hmac') != new['entries'].get(token, {}).get('raw_hmac'):
                need(prior['kind'] == 'xmltv' and errors < downloads and token in old['entries'] and token in new['entries'], 'only-existing-refreshed-XMLTV')
                ox = old.get('provider_xml', {}).get(token, {}); nx = new.get('provider_xml', {}).get(token, {})
                need(ox.get('valid') is True and nx.get('valid') is True, 'bounded-XMLTV-content-proof')
                need(ox['non_programme_hmac'] == nx['non_programme_hmac'], 'provider-XMLTV-channel-identities')
                need((prior['xml_channels'], prior['xml_programmes']) == (ox['channels'], ox['programmes']), 'old-provider-compatibility-counts')
                need((now['xml_channels'], now['xml_programmes']) == (nx['channels'], nx['programmes']), 'new-provider-compatibility-counts')
                refreshable[token] = True
                report['provider_XML_refreshes'].append({'path_hmac': token, 'old_channels': ox['channels'], 'new_channels': nx['channels'],
                    'old_programmes': ox['programmes'], 'new_programmes': nx['programmes'],
                    'programme_content_changed': ox['programme_hmac'] != nx['programme_hmac'],
                    'old_content_hmac': old['entries'][token]['raw_hmac'], 'new_content_hmac': new['entries'][token]['raw_hmac'],
                    'old_content_retained_in_authenticated_cold_archive': original_cold_archive, 'live_bytes_equal': False})
            else:
                need((prior['xml_channels'], prior['xml_programmes']) == (now['xml_channels'], now['xml_programmes']), 'unchanged-cache-compatibility')
        old_backups = old.get('generated_backups', {}); new_backups = new.get('generated_backups', {})
        need(a['standard_backup_path'] and b['standard_backup_path'] and a['backup_keep'] == b['backup_keep'], 'backup-path-policy')
        keep = a['backup_keep']; need(type(keep) is int and 1 <= keep <= 100, 'bounded-backup-retention')
        removed = set(old_backups) - set(new_backups); added = set(new_backups) - set(old_backups)
        need(1 <= len(added) <= startup_cycles, 'new-backup-count')
        ordered = sorted(old_backups, key=lambda token: old_backups[token]['order'])
        remove_count = max(0, len(old_backups) + len(added) - keep)
        need(removed == set(ordered[:remove_count]) and len(new_backups) == min(keep, len(old_backups) + len(added)), 'oldest-first-backup-retention')
        if ordered: need(all(new_backups[token]['order'] > old_backups[ordered[-1]]['order'] for token in added), 'new-backup-date-order')
        settings_token = mac(key, 'path', ['state', 'settings.json'])
        for token in added:
            row = new['entries'][token]; need((row['kind'], row['uid'], row['gid'], row['mode']) == ('file', 0, 0, 0o644), 'new-backup-metadata')
            proof = new_backups[token]['proof']; need(proof.get('valid') is True, 'new-backup-CRC-source-scope')
            snap = proof['settings']; need(snap['auto_update'] is False and snap['configuration_hmac'] == a['configuration_hmac'], 'backup-original-user-configuration')
            need(set(snap['providers']) == set(a['providers']), 'backup-provider-identities')
            for pid, prior in a['providers'].items():
                v = snap['providers'][pid]; y = b['providers'][pid]
                need(v['identity_hmac'] == prior['identity_hmac'] and v['cache_path_hmac'] == prior['cache_path_hmac'], 'backup-provider-credentials')
                delta = v['observations']['counter.download'] - prior['observations']['counter.download']
                need(0 <= delta < startup_cycles and prior['observations']['counter.error'] <= v['observations']['counter.error'] <= y['observations']['counter.error'], 'backup-pre-refresh-counters')
            for member, content in proof['members'].items():
                if member == settings_token: continue
                need(member in new['entries'] and new['entries'][member]['kind'] == 'file' and new['entries'][member]['raw_hmac'] == content, 'backup-member-user-data')
        need(set(old['entries']) - set(new['entries']) == removed, 'no-other-removed-files')
        need(set(new['entries']) - set(old['entries']) == added, 'no-other-added-files')
        for token in set(old['entries']) & set(new['entries']):
            left, right = old['entries'][token], new['entries'][token]
            need(all(left[k] == right[k] for k in ['kind', 'uid', 'gid', 'mode']), 'original-file-metadata')
            if token == settings_token or token in refreshable: continue
            need(compare_tree({'entries': {token: left}}, {'entries': {token: right}}), 'all-other-original-file-content')
        report.update(passed=True, rotated_generated_backups=len(removed), new_generated_backups=len(added),
                      rotated_backup_path_hmacs=sorted(removed),
                      rotated_backup_content_hmacs=[old['entries'][token]['raw_hmac'] for token in sorted(removed)],
                      rotated_originals_retained_in_authenticated_cold_archive=original_cold_archive,
                      original_accounts_credentials_UUID_providers_mappings_preserved=True)
    except Exception as error:
        report['failures'].append(str(error) if isinstance(error, Refusal) else type(error).__name__)
    return report


def projection(pod, deployment):
    base = deployment['spec']['template']['spec']; live = pod['spec']; c = live['containers'][0]
    need(len(live['containers']) == 1 and not live.get('initContainers') and not live.get('ephemeralContainers'), 'pod-containers')
    extra = [v for v in live['volumes'] if v['name'] not in {x['name'] for x in base['volumes']}]
    need(len(extra) == 1 and re.fullmatch(r'kube-api-access-[a-z0-9]{5}', extra[0]['name']), 'admission-volume')
    expected = {'defaultMode': 420, 'sources': [
        {'serviceAccountToken': {'expirationSeconds': 3607, 'path': 'token'}},
        {'configMap': {'items': [{'key': 'ca.crt', 'path': 'ca.crt'}], 'name': 'kube-root-ca.crt'}},
        {'downwardAPI': {'items': [{'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'metadata.namespace'}, 'path': 'namespace'}]}},
    ]}
    need(set(extra[0]) == {'name', 'projected'} and extra[0]['projected'] == expected, 'admission-projection')
    need([v for v in live['volumes'] if v not in extra] == base['volumes'], 'pod-original-volumes')
    mount = {'name': extra[0]['name'], 'mountPath': '/var/run/secrets/kubernetes.io/serviceaccount', 'readOnly': True}
    need(c['volumeMounts'] == base['containers'][0]['volumeMounts'] + [mount], 'pod-original-mounts')


def observe_node(request):
    need(socket.gethostname().split('.')[0].lower() == 'masternode', 'master-only')
    key = bytes.fromhex(request['key']); need(len(key) == 32, 'key')
    image = OLD if request['mode'] == 'baseline' else NEW
    def kube(*args, namespace='plex'):
        result = subprocess.run(['kubectl', '--request-timeout=25s', '-n', namespace, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
        need(result.returncode == 0 and len(result.stdout) <= 8 * 1024**2, 'kube-read')
        return json.loads(result.stdout)
    def obj(kind, name, namespace='plex'): return kube('get', kind, name, '-o', 'json', namespace=namespace)
    def ident(value, uid): need(value['metadata']['uid'] == uid and not value['metadata'].get('deletionTimestamp'), 'resource-identity')
    def fence():
        dep = obj('deployment', 'xteve'); ident(dep, DEP)
        need(dep['spec'].get('replicas') == 1 and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'], 'deployment-generation')
        need(all(dep['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']), 'deployment-ready')
        hr = obj('helmrelease', 'xteve', 'flux-system'); ident(hr, HR)
        need(hr['spec'].get('releaseName') == 'xteve' and hr['spec'].get('targetNamespace') == 'plex' and hr['spec'].get('values', {}).get('replicaCount') == 1 and not hr['spec'].get('suspend', False), 'release-spec')
        need(hr['status'].get('observedGeneration', 0) >= hr['metadata']['generation'] and any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])), 'release-ready')
        cspec = dep['spec']['template']['spec']; need(len(cspec['containers']) == 1, 'deployment-container')
        c = cspec['containers'][0]; need(c['name'] == 'xteve' and c['image'] == image, 'image')
        need(c.get('envFrom') == [{'secretRef': {'name': 'xteve-runtime'}}] and not c.get('env'), 'native-secret-reference')
        need(c['volumeMounts'] == MOUNTS and cspec['volumes'] == VOLUMES, 'original-storage-layout')
        storage = {}
        for name, (uid, puid, volume, driver) in CLAIMS.items():
            pvc = obj('pvc', name); pv = obj('pv', volume); ident(pvc, uid); ident(pv, puid)
            need(pvc['status']['phase'] == 'Bound' and pvc['spec']['volumeName'] == volume and pv['spec']['claimRef']['uid'] == uid and pv['spec']['csi']['driver'] == driver, 'storage-binding')
            if driver == 'driver.longhorn.io': need(pvc['spec']['storageClassName'] == 'longhorn' and pv['spec']['csi']['volumeHandle'] == volume, 'longhorn-binding')
            storage[name] = {'pvc': uid, 'pv': puid, 'pvc_spec': mac(key, ['pvc', name], pvc['spec']), 'pv_spec': mac(key, ['pv', name], pv['spec'])}
        active = []
        for p in kube('get', 'pods', '-o', 'json')['items']:
            if not any(v.get('persistentVolumeClaim', {}).get('claimName') in ['xteve-data-0', 'xteve-data-1'] for v in p['spec'].get('volumes', [])): continue
            running = any('running' in x.get('state', {}) for k in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for x in p['status'].get(k, []))
            if p['status'].get('phase') not in ['Succeeded', 'Failed'] or running: active.append(p)
        need(len(active) == 1, 'sole-writer'); pod = active[0]
        need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running' and pod['spec']['nodeName'] == 'workernode2', 'pod-ready')
        statuses = pod['status'].get('containerStatuses', []); need(len(statuses) == 1 and statuses[0]['ready'] and statuses[0]['name'] == 'xteve', 'container-ready')
        need(pod['spec']['containers'][0]['image'] == image and statuses[0]['imageID'].rsplit('@', 1)[-1] == image.rsplit('@', 1)[-1], 'runtime-image')
        projection(pod, dep)
        need(pod['spec']['containers'][0].get('envFrom') == c.get('envFrom') and not pod['spec']['containers'][0].get('env'), 'pod-environment')
        owners = [o for o in pod['metadata'].get('ownerReferences', []) if o.get('controller')]; need(len(owners) == 1 and owners[0]['kind'] == 'ReplicaSet', 'replicaset-owner')
        rs = obj('replicaset', owners[0]['name']); ident(rs, owners[0]['uid'])
        need(any(o.get('controller') and o['kind'] == 'Deployment' and o['uid'] == DEP for o in rs['metadata'].get('ownerReferences', [])), 'deployment-owner')
        node = obj('node', 'workernode2'); ident(node, NODE)
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']), 'node-ready')
        need(not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in node['status']['conditions']), 'node-pressure')
        sec = obj('secret', 'xteve-runtime'); ident(sec, SECRET)
        svc = obj('service', 'xteve'); ident(svc, SERVICE)
        need(svc['spec']['selector'] == {'app': 'xteve'} and any(p['port'] == p['targetPort'] == 34400 and p['protocol'] == 'TCP' for p in svc['spec']['ports']), 'service-routing')
        ipaddress.ip_address(svc['spec']['clusterIP'])
        normalized = copy.deepcopy(dep['spec']); normalized['template']['spec']['containers'][0]['image'] = '<maintenance-image>'
        ann = normalized['template'].get('metadata', {}).get('annotations', {}); ann.pop('kubectl.kubernetes.io/restartedAt', None)
        if not ann: normalized['template'].get('metadata', {}).pop('annotations', None)
        stable = {'deployment_uid': DEP, 'release_uid': HR, 'node_uid': NODE, 'service_uid': SERVICE, 'secret_uid': SECRET,
                  'deployment_spec': mac(key, 'deployment', normalized), 'release_spec': mac(key, 'release', hr['spec']),
                  'storage': storage, 'service_spec': mac(key, 'service', svc['spec']),
                  'native_secret': mac(key, 'native-secret', {k: sec.get(k) for k in ['type', 'immutable', 'data']})}
        writer = {'pod_uid': pod['metadata']['uid'], 'restart_count': statuses[0].get('restartCount', 0), 'image': image, 'runtime': statuses[0]['imageID'].rsplit('@', 1)[-1]}
        return stable, writer, pod['metadata']['name'], svc['spec']['clusterIP']
    stable, writer, pod, address = fence()
    def capture():
        result = {}
        for scope, root in [('state', '/root/.xteve'), ('config', '/config')]:
            child = subprocess.Popen(['kubectl', '--request-timeout=25s', '-n', 'plex', 'exec', pod, '-c', 'xteve', '--', 'tar', '-cf', '-', '-C', root, '.'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            timer = threading.Timer(120, child.kill); timer.start()
            try:
                result[scope] = read_tar(child.stdout, scope, key)
                # Consume any tar padding; errors and stderr never escape.
                trailing = child.stdout.read(1024**2 + 1); need(len(trailing) <= 1024**2 and not any(trailing), 'tar-trailer')
                need(child.wait(timeout=10) == 0, 'tar-exit')
            finally:
                timer.cancel()
                if child.poll() is None: child.kill(); child.wait()
        need('settings.json' in result['state']['details'], 'settings-present')
        return result
    before = capture(); settings = before['state']['details']['settings.json']
    need(settings['auto_update'] is (request['mode'] == 'baseline'), 'updater-contract')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()); http = {}
    routes = ['/discover.json', '/device.xml', '/lineup_status.json', '/lineup.json', '/xmltv/xteve.xml', '/m3u/xteve.m3u', '/api/']
    for route in routes:
        payload = canonical({'cmd': 'status'}) if route == '/api/' and settings['api'] and not settings['authentication_api'] else None
        req = urllib.request.Request('http://' + address + ':34400' + route, data=payload,
                                     headers={'Content-Type': 'application/json'} if payload else {})
        try: response = client.open(req, timeout=20)
        except urllib.error.HTTPError as error: response = error
        with response:
            raw = response.read(MAX_PARSE + 1); need(len(raw) <= MAX_PARSE, 'http-bound'); status = response.code
        expected = 423 if route == '/api/' and not settings['api'] else 404 if route == '/api/' and payload is None else 403 if (
            route == '/lineup.json' and settings['authentication_pms'] or route == '/xmltv/xteve.xml' and settings['authentication_xml'] or route == '/m3u/xteve.m3u' and settings['authentication_m3u']) else 200
        need(status == expected, 'HTTP-' + route)
        value = None
        if status == 200:
            if route in ['/discover.json', '/lineup_status.json', '/lineup.json', '/api/']:
                value = json_object(raw)
                if route == '/lineup.json': need(isinstance(value, list), 'lineup-array'); value = sorted(value, key=canonical)
                if route == '/lineup_status.json': need(value.get('ScanInProgress') == 0, 'scan-in-progress')
                if route == '/api/': need(value.get('status') is True and 'token' not in value, 'unauthenticated-status-only')
            elif route == '/m3u/xteve.m3u': value = m3u_semantics(raw)
            else: value = xml_semantics(raw)
        http[route] = {'status': status, 'bytes': len(raw), 'raw_hmac': mac(key, ['http-body', route], hashlib.sha256(raw).hexdigest()),
                       'semantic_hmac': mac(key, ['http-semantic', route], value), 'successful_content_read': status == 200}
    after = capture(); failures = []
    for scope in ['state', 'config']:
        if not compare_tree(before[scope], after[scope]): failures.append('HTTP-local-state-change-' + scope)
    stable_after, writer_after, pod_after, address_after = fence()
    need((stable, writer, pod, address) == (stable_after, writer_after, pod_after, address_after), 'observation-fence')
    changed = [token for scope in ['state', 'config'] for token, row in before[scope]['entries'].items()
               if after[scope]['entries'].get(token, {}).get('raw_hmac') != row['raw_hmac']]
    return {'stable': stable, 'writer': writer, 'before_http': before, 'trees': after, 'http': http,
            'read_GET_cache_rewrite_count': len(changed), 'read_GET_changed_path_hmacs': changed, 'failures': failures,
            'provider_stream_opened': False, 'login_or_update_requested': False, 'smb_walked': False}


def private(path, exists=True):
    need(path.is_absolute() and path.resolve() == path, 'private-path')
    need(not any((p / '.git').exists() for p in [path.parent, *path.parent.parents]), 'outside-git')
    parent = path.parent.stat(); need(parent.st_uid == os.getuid() and not parent.st_mode & 0o077, 'private-parent')
    if exists:
        info = path.lstat(); need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and not info.st_mode & 0o077, 'private-file')
    else: need(not path.exists() and not path.is_symlink(), 'new-receipt')


def shared_module():
    p = Path(__file__).resolve().parents[2] / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py'
    spec = importlib.util.spec_from_file_location('xteve_archive_shared', p); shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
    return shared, p


def cold_tree(path, expected_sha, scope, key, shared):
    private(path); need(path.stat().st_size <= 65536 and shared.file_hash(path) == expected_sha, 'cold-receipt-pin')
    r = json.loads(path.read_bytes()); app = 'xteve' if scope == 'state' else 'xteve-config'; claim = 'xteve-data-' + ('0' if scope == 'state' else '1')
    need(r['application'] == app and r['status'] == 'completed' and r['cold_archive_verified'] is True, 'cold-complete')
    need(r['deployment_uid'] == DEP and r['helmrelease_uid'] == HR and r['namespace'] == 'plex' and r['original_image'] == OLD, 'cold-writer')
    need(r['claim'] == claim and r['claim_uid'] == CLAIMS[claim][0] and r['volume'] == CLAIMS[claim][2], 'cold-claim')
    archive = Path(r['archive_path']); private(archive)
    need(archive.stat().st_size == r['archive_bytes'] and shared.file_hash(archive) == r['archive_sha256'], 'archive-pin')
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in [shared.AGE, shared.IDENTITY]]
    need(shared.file_hash(shared.AGE) == shared.AGE_SHA256, 'age-pin')
    def decrypt(fn):
        child = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        timer = threading.Timer(180, child.kill); timer.start()
        try:
            value = fn(child.stdout); trailing = child.stdout.read(1024**2 + 1)
            need(len(trailing) <= 1024**2 and not any(trailing) and child.wait(timeout=15) == 0, 'age-authentication')
            return value
        finally:
            timer.cancel()
            if child.poll() is None: child.kill(); child.wait()
    manifest = decrypt(shared.verify_archive)
    need(hashlib.sha256(shared.canonical(manifest)).hexdigest() == r['manifest_sha256'], 'manifest-pin')
    tree = decrypt(lambda stream: read_tar(stream, scope, key, manifest))
    need(shared.file_hash(archive) == r['archive_sha256'] and shared.file_hash(path) == expected_sha, 'cold-unchanged')
    for p, identity in pins: need(shared.protected(p, p == shared.IDENTITY) == identity, 'decrypt-input-unchanged')
    return tree, {'receipt_sha256': expected_sha, 'archive_sha256': r['archive_sha256'],
                  'archive_path': str(archive), 'archive_bytes': r['archive_bytes']}


def read_receipt(path, mode, key, sources):
    private(path); need(path.stat().st_size <= 8 * 1024**2, 'receipt-size')
    r = json.loads(path.read_bytes()); signature = r.pop('receipt_hmac')
    need(hmac.compare_digest(signature, mac(key, 'receipt', r)), 'receipt-authentication')
    expected_sources = dict(sources)
    if mode == 'baseline' and r['sources'].get('observer') == BASELINE_OBSERVER_SHA256:
        expected_sources['observer'] = BASELINE_OBSERVER_SHA256
    need(r['mode'] == mode and r['passed'] and r['sources'] == expected_sources, 'receipt-contract')
    return r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['baseline', 'cold', 'after', 'restart'])
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--baseline', type=Path); parser.add_argument('--cold', type=Path); parser.add_argument('--previous-after', type=Path)
    for scope in ['state', 'config']:
        parser.add_argument('--cold-' + scope + '-receipt', type=Path); parser.add_argument('--cold-' + scope + '-sha256')
    args = parser.parse_args(); need(os.name == 'posix', 'WSL-only')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077)
    key_text = sys.stdin.buffer.read(67).strip(); need(re.fullmatch(b'[0-9a-fA-F]{64}', key_text), 'key-format'); key = bytes.fromhex(key_text.decode())
    private(args.receipt, False); shared, shared_path = shared_module()
    source = Path(__file__).read_text(encoding='utf-8')
    sources = {'observer': hashlib.sha256(source.encode()).hexdigest(), 'archive_primitives': shared.file_hash(shared_path), 'upstream_commit': SOURCE_COMMIT}
    receipt = {'schema_version': 1, 'mode': args.mode, 'passed': False, 'sources': sources, 'failures': [],
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'login_verified': False,
               'stream_verified': False, 'restore_executed': False, 'restart_executed': False, 'smb_walked': False}
    try:
        if args.mode == 'cold':
            need(args.baseline is not None, 'original-baseline-required')
            baseline = read_receipt(args.baseline, 'baseline', key, sources)
            receipt['trees'] = {}; receipt['cold_archives'] = {}
            for scope in ['state', 'config']:
                path = getattr(args, 'cold_' + scope + '_receipt'); pin = getattr(args, 'cold_' + scope + '_sha256')
                need(path is not None and re.fullmatch('[0-9a-f]{64}', pin or ''), 'cold-inputs')
                receipt['trees'][scope], receipt['cold_archives'][scope] = cold_tree(path, pin, scope, key, shared)
                if not compare_tree(baseline['observation']['trees'][scope], receipt['trees'][scope]): receipt['failures'].append('baseline-to-cold-files-' + scope)
            need(receipt['trees']['state']['details']['settings.json']['auto_update'] is True, 'cold-before-updater-change')
            receipt['anchors'] = {'baseline': shared.file_hash(args.baseline)}
        else:
            payload = canonical({'key': key.hex(), 'mode': args.mode})
            program = source.rsplit("if __name__ == '__main__':", 1)[0] + "\nresource.setrlimit(resource.RLIMIT_CORE,(0,0))\ntry:\n request=json.loads(sys.stdin.buffer.read(1024))\n result=observe_node(request)\n print(json.dumps(result,sort_keys=True))\nexcept Exception as e:\n print(json.dumps({'observer_refused':True,'stage':str(e) if isinstance(e,Refusal) else type(e).__name__}))\n raise SystemExit(1)\n"
            child = subprocess.run(shared.SSH + [shlex.join(['python3', '-B', '-c', program])], input=payload, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=420)
            need(len(child.stdout) <= 8 * 1024**2, 'observation-bound')
            result = json.loads(child.stdout) if child.stdout else {}
            if child.returncode != 0:
                receipt['refusal_stage'] = result.get('stage', 'remote-observer'); need(False, 'remote-refused')
            receipt['observation'] = result; receipt['failures'] += result['failures']
            if args.mode in ['after', 'restart']:
                need(args.baseline is not None and args.cold is not None, 'anchors-required')
                baseline = read_receipt(args.baseline, 'baseline', key, sources); cold = read_receipt(args.cold, 'cold', key, sources)
                need(cold['anchors']['baseline'] == shared.file_hash(args.baseline), 'cold-same-baseline')
                for preserved in cold['cold_archives'].values():
                    archive = Path(preserved['archive_path']); private(archive)
                    need(archive.stat().st_size == preserved['archive_bytes'] and shared.file_hash(archive) == preserved['archive_sha256'], 'original-archive-still-present')
                receipt['authenticated_original_archives_still_present'] = True
                old = baseline['observation']
                for label, a, b in [('native-identities-specs', old['stable'], result['stable']), ('public-HTTP-semantics',
                    {k:(v['status'],v['semantic_hmac']) for k,v in old['http'].items()}, {k:(v['status'],v['semantic_hmac']) for k,v in result['http'].items()})]:
                    if a != b: receipt['failures'].append(label)
                for scope in ['state', 'config']:
                    if scope == 'state':
                        proof = compare_runtime_state(cold['trees'][scope], result['trees'][scope], key, 2 if args.mode == 'restart' else 1)
                        receipt['runtime_preservation'] = proof
                        if not proof['passed']: receipt['failures'].append('cold-files-state')
                    elif not compare_tree(cold['trees'][scope], result['trees'][scope]): receipt['failures'].append('cold-files-' + scope)
                receipt['anchors'] = {'baseline': shared.file_hash(args.baseline), 'cold': shared.file_hash(args.cold)}
                if args.mode == 'restart':
                    need(args.previous_after is not None, 'previous-after-required'); previous = read_receipt(args.previous_after, 'after', key, sources)
                    need(previous['anchors'] == receipt['anchors'], 'restart-same-anchors')
                    a, b = previous['observation']['writer'], result['writer']
                    if a['pod_uid'] == b['pod_uid'] and b['restart_count'] <= a['restart_count']: receipt['failures'].append('restart-not-observed')
                    need(a['image'] == b['image'] and a['runtime'] == b['runtime'], 'restart-image')
                    for scope in ['state', 'config']:
                        if scope == 'state':
                            proof = compare_runtime_state(previous['observation']['trees'][scope], result['trees'][scope], key, 1, original_cold_archive=False)
                            receipt['restart_runtime_preservation'] = proof
                            if not proof['passed']: receipt['failures'].append('restart-files-state')
                        elif not compare_tree(previous['observation']['trees'][scope], result['trees'][scope]): receipt['failures'].append('restart-files-' + scope)
                    receipt['anchors']['previous_after'] = shared.file_hash(args.previous_after)
        need(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == sources['observer'] and shared.file_hash(shared_path) == sources['archive_primitives'], 'source-unchanged')
        receipt['passed'] = not receipt['failures']
    except Exception as error:
        receipt['failures'].append('observation-refused'); receipt['error_type'] = type(error).__name__
        # Only our finite stage labels are emitted; arbitrary parser errors are not.
    receipt['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); receipt['receipt_hmac'] = mac(key, 'receipt', receipt)
    with os.fdopen(os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'passed': receipt['passed'], 'mode': args.mode, 'failures': receipt['failures'], 'refusal_stage': receipt.get('refusal_stage')}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception: raise SystemExit('xTeVe observation refused; raw diagnostics suppressed')
