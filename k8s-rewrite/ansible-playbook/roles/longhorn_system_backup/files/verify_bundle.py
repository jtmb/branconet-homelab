"""Validate a native SystemBackup ZIP in memory; never restore cluster objects."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

import yaml


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--plan', type=Path, required=True)
    a = parser.parse_args()
    root = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    need(root.is_mount() and a.plan.resolve() in [root / 'platform-upstream-review-20261027' / name / 'plan.json'
         for name in ('longhorn-system-backup', 'longhorn-system-backup-20261028')],
         'owned_original_plan')
    plan = json.loads(a.plan.read_text())
    need(plan['manifest']['metadata']['name'] == a.name, 'same_backup_identity')
    data = sys.stdin.buffer.read(16 * 1024**2 + 1)
    need(len(data) <= 16 * 1024**2, 'bounded_native_zip')
    docs = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        need(len(archive.infolist()) <= 256 and archive.testzip() is None, 'zip_member_bound_and_crc')
        seen = set()
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            need(member.filename not in seen and not name.is_absolute() and '..' not in name.parts
                 and name.parts[0] == a.name and not stat.S_ISLNK(member.external_attr >> 16), 'safe_unique_member')
            seen.add(member.filename)
            if member.is_dir():
                continue
            total += member.file_size
            need(member.file_size <= 4 * 1024**2 and total <= 16 * 1024**2 and name.suffix == '.yaml', 'bounded_yaml_member')
            docs[str(name.relative_to(a.name))] = yaml.safe_load(archive.read(member))
    need(docs['metadata.yaml']['longhornversion'] == 'v1.12.1', 'original_longhorn_version')
    counts = {}
    for name, doc in docs.items():
        if name == 'metadata.yaml':
            continue
        need(isinstance(doc, dict) and isinstance(doc.get('items'), list), 'resource_list_shape')
        need(doc.get('kind') not in ['Secret', 'SecretList'], 'native_bundle_must_not_contain_secret_values')
        counts[name] = len(doc['items'])
    volumes = docs['yamls/longhorn/volumes.yaml']['items']
    need({v['metadata']['name']: v['metadata']['uid'] for v in volumes}
         == {name: row['uid'] for name, row in plan['observed']['volumes'].items()}, 'all_prepared_volume_uids')
    pv = docs['yamls/kubernetes/persistentvolumes.yaml']['items']
    pvc = docs['yamls/kubernetes/persistentvolumeclaims.yaml']['items']
    need(len(pv) == len(pvc) == len(volumes), 'complete_longhorn_bindings')
    claims = {(c['metadata']['namespace'], c['metadata']['name']): c for c in pvc}
    need(len(claims) == len(pvc), 'unique_claims')
    handles = set()
    for volume in pv:
        spec = volume['spec']
        need(spec['csi']['driver'] == 'driver.longhorn.io', 'longhorn_pv_driver')
        handle = spec['csi']['volumeHandle']
        need(handle in plan['observed']['volumes'] and handle not in handles, 'unique_existing_volume_handle')
        handles.add(handle)
        ref = spec['claimRef']
        claim = claims[(ref['namespace'], ref['name'])]
        need(ref['uid'] == claim['metadata']['uid'] and claim['spec']['volumeName'] == volume['metadata']['name'],
             'exact_claim_pv_volume_binding')
    need(handles == set(plan['observed']['volumes']), 'every_volume_bound_in_bundle')
    print(json.dumps({'zipSHA256': hashlib.sha256(data).hexdigest(), 'allYAMLDocumentsParsed': len(docs),
                      'allPreparedVolumeUIDsIncluded': len(volumes), 'completeBindingChains': len(pv),
                      'resourceListCounts': counts, 'secretObjectsIncluded': False, 'systemRestoreExecuted': False}))


if __name__ == '__main__':
    main()
