#!/usr/bin/env python3
"""Read-only Plex account/library/native identity and NAS-access comparison."""
import argparse
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import shlex
import subprocess
import uuid
import xml.etree.ElementTree as ET

BASE = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'lscr.io/linuxserver/plex@sha256:a3a3a850a64fb747c59f85dbc19b157781c3b9c921a83799127894b0ebdf3a68'
CONFIG = '/config/Library/Application Support/Plex Media Server'
TABLES = ['accounts', 'library_section_permissions', 'library_sections', 'section_locations',
          'metadata_items', 'media_items', 'media_parts', 'media_streams', 'metadata_item_settings',
          'metadata_item_views', 'metadata_item_accounts', 'metadata_item_setting_markers',
          'media_item_settings', 'media_part_settings', 'media_stream_settings', 'view_settings',
          'tags', 'taggings', 'directories', 'preferences', 'schema_migrations']


def need(ok, reason):
    if not ok: raise ValueError(reason)


def call(args, timeout=45):
    p = subprocess.run(SSH + [shlex.join(args)], capture_output=True, timeout=timeout)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'bounded_cluster_operation')
    return p.stdout


def get(kind, name, ns='plex'):
    return json.loads(call(['kubectl', '-n', ns, 'get', kind, name, '-o', 'json']))


def fence(image):
    d, h = get('deployment', 'plex'), get('helmrelease', 'plex', 'flux-system')
    need(d['metadata']['uid'] == '62dbb208-e8a8-487c-8264-788cd90e3f9d'
         and h['metadata']['uid'] == '66bf6326-157d-4875-b4c5-1a4d03636f5e', 'original_owner')
    need(d['spec']['replicas'] == 1 and d['status'].get('observedGeneration') == d['metadata']['generation']
         and all(d['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas'])
         and h['status'].get('observedGeneration') == h['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status'].get('conditions', [])), 'ready_flux_writer')
    pods = json.loads(call(['kubectl', '-n', 'plex', 'get', 'pods', '-l', 'app=plex', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_owned_server'); pod = pods[0]; c = pod['spec']['containers'][0]; cs = pod['status']['containerStatuses'][0]
    need(not pod['metadata'].get('deletionTimestamp') and cs['ready'] and c['name'] == 'plex' and c['image'] == image
         and c['envFrom'] == [{'secretRef': {'name': 'plex-runtime'}}], 'original_server_launch')
    if image != OLD:
        need(image in ['docker.io/library/plex-security-20261023@sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397', 'docker.io/linuxserver/plex:1.43.5.11079-b3b13e506-ls330@sha256:01a53d9c7adcbb3701fbb0a4230c0a37c85453759b6b05a67356c3c7a09de08d'] and cs['imageID'].endswith('@' + image.rsplit('@', 1)[1])
             and {'name': 'VERSION', 'value': 'docker'} in c.get('env', []), 'exact_baked_server_no_bootstrap_update')
    claims = {}
    for index, path in enumerate(['/config', '/movies', '/pvr', '/tv']):
        alias = 'data-' + str(index); name = 'plex-' + alias; claim = get('pvc', name); pv = get('pv', claim['spec']['volumeName'])
        need(claim['status']['phase'] == 'Bound' and pv['spec']['claimRef']['uid'] == claim['metadata']['uid']
             and any(m['name'] == alias and m['mountPath'] == path and not m.get('subPath') for m in c['volumeMounts'])
             and any(v['name'] == alias and v.get('persistentVolumeClaim', {}).get('claimName') == name for v in pod['spec']['volumes']), 'existing_config_and_nas_bindings')
        need(pv['spec']['csi']['driver'] == ('driver.longhorn.io' if index == 0 else 'smb.csi.k8s.io'), 'existing_storage_drivers')
        claims[name] = {'uid': claim['metadata']['uid'], 'pvUID': pv['metadata']['uid'], 'driver': pv['spec']['csi']['driver']}
    need(claims['plex-data-0']['uid'] == 'f1f3f7d0-4706-43ff-871d-e7b6f7bfe7f2', 'original_config_claim')
    secrets = {}
    for name in ['plex-runtime', 'plex-launch']:
        values = call(['kubectl', '-n', 'plex', 'get', 'secret', name, '-o', 'jsonpath={.metadata.uid}{" "}{.metadata.resourceVersion}']).decode().split()
        need(len(values) == 2, 'native_secret_metadata_only'); secrets[name] = values
    return {'deploymentUID': d['metadata']['uid'], 'releaseUID': h['metadata']['uid'], 'claims': claims, 'secrets': secrets,
            'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'], 'image': image, 'imageID': cs['imageID']}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--baseline', type=Path); p.add_argument('--image', default=OLD)
    p.add_argument('--cold-library-proof', type=Path); p.add_argument('--cold-library-proof-sha256')
    a = p.parse_args(); os.umask(0o077)
    need(a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    report = {'passed': False, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'libraryOrMediaModified': False}
    try:
        keyfile = a.output_dir / 'observation.key'
        if not keyfile.exists():
            with keyfile.open('xb') as f: f.write(os.urandom(32))
        key = keyfile.read_bytes(); need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
        def digest(raw): return hmac.new(key, raw, hashlib.sha256).hexdigest()
        writer = fence(a.image); prefix = ['kubectl', '-n', 'plex', 'exec', writer['pod'], '--']
        identity = ET.fromstring(call(prefix + ['curl', '-fsS', '--max-time', '20', 'http://127.0.0.1:32400/identity']))
        need(identity.attrib['version'] == '1.43.5.11079-b3b13e506' and identity.attrib.get('claimed') == '1', 'same_claimed_production_beta')
        prefs = ET.fromstring(call(prefix + ['cat', CONFIG + '/Preferences.xml']))
        fields = {k: prefs.attrib.get(k) for k in ['MachineIdentifier', 'ProcessedMachineIdentifier', 'AnonymousMachineIdentifier',
                  'PlexOnlineToken', 'PlexOnlineUsername', 'PlexOnlineMail', 'FriendlyName']}
        need(fields['MachineIdentifier'] and fields['PlexOnlineToken'], 'existing_server_and_account_identity')
        # Native token stays inside the Pod's pipe and curl stdin; never argv/file.
        shell = r'''set -eu
sed -n 's/.* PlexOnlineToken="\([^"]*\)".*/\1/p' '/config/Library/Application Support/Plex Media Server/Preferences.xml' | jq -Rer 'select(length > 0) | "url = " + ("http://127.0.0.1:32400/library/sections" | tojson) + "\nheader = " + (("X-Plex-Token: " + .) | tojson)' | curl --silent --show-error --fail --max-time 30 --config -
'''
        sections = ET.fromstring(call(prefix + ['sh', '-c', shell])); need(sections.tag == 'MediaContainer', 'native_authenticated_library_api')
        section_identity = [{'key': s.attrib.get('key'), 'uuid': s.attrib.get('uuid'), 'type': s.attrib.get('type'),
                             'locations': [x.attrib.get('path') for x in s.findall('Location')]} for s in sections.findall('Directory')]
        pieces = ["SELECT '" + n + "' AS table_name, (SELECT count(*) FROM \"" + n + "\") AS rows, hex(sha3_query('SELECT * FROM \"" + n + "\" ORDER BY rowid',256)) AS digest" for n in TABLES]
        sql = 'BEGIN; ' + ' UNION ALL '.join(pieces) + '; COMMIT;'
        rows = json.loads(call(prefix + ['/usr/lib/plexmediaserver/Plex SQLite', '-readonly', '-json', '-cmd', '.timeout 5000',
                                        CONFIG + '/Plug-in Support/Databases/com.plexapp.plugins.library.db', sql], timeout=120))
        need([x['table_name'] for x in rows] == TABLES and all(len(x['digest']) == 64 for x in rows), 'complete_core_library_and_account_tables')
        tables = {x['table_name']: {'rows': x['rows'], 'hmac': digest(x['digest'].encode())} for x in rows}
        # One existing media prefix only. No recursive NAS inventory or media copy.
        access = call(prefix + ['s6-setuidgid', 'abc', 'sh', '-c', r'''set -eu; test "$(id -u)" = 1000
for d in /movies /pvr /tv; do test -r "$d" && test -x "$d"; done
f=$(timeout 20 find /movies -maxdepth 3 -type f \( -name '*.mkv' -o -name '*.mp4' -o -name '*.avi' \) -print -quit); test -n "$f"; head -c 65536 "$f" | sha256sum
''']).decode().split()[0]
        need(len(access) == 64 and fence(a.image) == writer, 'native_uid_media_read_and_stable_writer')
        report.update(writer=writer, appVersion=identity.attrib['version'], claimed=True, identityHMAC=digest(json.dumps(fields, sort_keys=True).encode()),
                      librarySections=len(section_identity), librarySectionHMAC=digest(json.dumps(section_identity, sort_keys=True).encode()),
                      nativeLibraryAPI=True, tables=tables, originalMediaPrefixReadSHA256=access, mediaReaderUID=1000)
        if a.baseline:
            need(a.baseline.parent == a.output_dir, 'same_baseline_scope'); old = json.loads(a.baseline.read_bytes())
            need(old['passed'] and all(old[k] == report[k] for k in ['identityHMAC', 'librarySections', 'librarySectionHMAC', 'originalMediaPrefixReadSHA256']), 'original_accounts_library_and_identity')
            compared = dict(tables); original = dict(old['tables'])
            if a.cold_library_proof:
                # The hot baseline predates shutdown. Compare every section row
                # and column against the complete authenticated cold archive,
                # rather than excluding mutable fields or accepting drift.
                proof_path = a.cold_library_proof
                need(proof_path.parent == a.output_dir and proof_path.resolve() == proof_path
                     and not proof_path.stat().st_mode & 0o077
                     and hashlib.sha256(proof_path.read_bytes()).hexdigest() == a.cold_library_proof_sha256,
                     'exact_private_cold_library_proof')
                proof = json.loads(proof_path.read_bytes())
                need(proof['sourceSHA256'] == '981d8a4c83019a7d1ccd5e14a4ca996c193c92958c91e1558ca899b78407d953'
                     and proof['originalColdReceiptSHA256'] == '81f22d8e3a683f1ec43eb8360d92d805ea3ad19473c5ea1fac265108625c397b'
                     and proof['wholeColdArchiveAuthenticated'] and proof['changedColumnsByRow'] == {}
                     and proof['coldColumnsHMAC'] == proof['liveColumnsHMAC'], 'complete_cold_section_equality')
                live = json.loads(call(prefix + ['/usr/lib/plexmediaserver/Plex SQLite', '-readonly', '-json',
                              CONFIG + '/Plug-in Support/Databases/com.plexapp.plugins.library.db',
                              'SELECT * FROM library_sections ORDER BY id;']))
                need(len(live) == proof['rows'] == original['library_sections']['rows']
                     and len(proof['columns']) == 23 and all(set(x) == set(proof['columns']) for x in live),
                     'all_original_section_columns_and_rows')
                actual = {k: digest(json.dumps([x[k] for x in live],sort_keys=True,separators=(',',':')).encode())
                          for k in proof['columns']}
                need(actual == proof['coldColumnsHMAC'], 'current_all_column_cold_equality')
                compared.pop('library_sections'); original.pop('library_sections')
                report['coldLibrarySectionProofSHA256'] = a.cold_library_proof_sha256
                report['sectionColumnsComparedAgainstFullColdArchive'] = proof['columns']
                report['sectionFieldsExcludedFromEquality'] = []
            need(compared == original, 'original_accounts_media_and_watch_state_tables')
            need(all(old['writer'][k] == writer[k] for k in ['deploymentUID', 'releaseUID', 'claims', 'secrets'])
                 and old['writer']['podUID'] != writer['podUID'], 'same_native_data_and_identity_new_pod')
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    report['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = a.output_dir / ('plex-functional-' + uuid.uuid4().hex + '.json'); out.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
