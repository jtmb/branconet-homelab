#!/usr/bin/env python3
"""Read-only compiled-overlay-v1 export/preload compatibility contracts.

This module has no Docker, SSH, sudo, import, publication or deployment entry
point. Export records and node envelopes describe packaging identities only.
The original stage-bortus-release-image.py and node protocol remain separate.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import stat
import tarfile

FORMAT = 'bortus-compiled-overlay-staging/v1'
RECIPE = 'compiled-overlay-v1'
HOSTS = ('192.168.0.4', '192.168.0.5', '192.168.0.6')
INDEX = 'application/vnd.oci.image.index.v1+json'
MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
CONFIG = 'application/vnd.oci.image.config.v1+json'
LAYER_MEDIA = {'application/vnd.oci.image.layer.v1.tar',
               'application/vnd.oci.image.layer.v1.tar+gzip'}
AUTHORITIES = {'raw_git_context', 'raw_git_manifest', 'current_source_333',
               'compiled_dependency_41723', 'assembly_authority', 'assembly_result',
               'payload_inventory', 'saved_image_result'}
MAX_METADATA = 8 * 1024 ** 2


def require(ok, code):
    if not ok:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hexid(value, length=64):
    return type(value) is str and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def sha(value):
    return type(value) is str and value.startswith('sha256:') and hexid(value[7:])


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_key')
        result[key] = value
    return result


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_METADATA, 'metadata_bound')
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'nonfinite_json'))


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def validate_contract(value):
    fields = {'format', 'recipe', 'source_commit', 'application_tree', 'build_id',
              'image_tag', 'canonical_alias', 'local_image_id', 'manifest_digest',
              'manifest_bytes', 'raw_config_digest', 'raw_config_bytes',
              'archive_sha256', 'archive_bytes', 'runtime_base_id', 'labels',
              'layers', 'ordered_diff_ids', 'authority_sha256', 'runtime_qualified', 'deployed'}
    require(type(value) is dict and set(value) == fields, 'contract_fields')
    require(value['format'] == FORMAT and value['recipe'] == RECIPE, 'contract_recipe')
    require(hexid(value['source_commit'], 40) and hexid(value['application_tree'], 40) and
            type(value['build_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', value['build_id']), 'contract_source')
    tag = 'bortus:compiled-overlay-' + value['source_commit']
    require(value['image_tag'] == tag and value['canonical_alias'] == 'docker.io/library/' + tag, 'contract_tag')
    require(all(sha(value[k]) for k in ('local_image_id', 'manifest_digest', 'raw_config_digest', 'runtime_base_id')) and
            value['local_image_id'] == value['manifest_digest'] and
            value['manifest_digest'] != value['raw_config_digest'], 'contract_identities')
    require(all(type(value[k]) is int and 0 < value[k] <= MAX_METADATA for k in ('manifest_bytes', 'raw_config_bytes')) and
            type(value['archive_bytes']) is int and 0 < value['archive_bytes'] <= 4 * 1024 ** 3 and
            hexid(value['archive_sha256']), 'contract_sizes')
    authorities = value['authority_sha256']
    require(type(authorities) is dict and set(authorities) == AUTHORITIES and
            all(hexid(h) for h in authorities.values()), 'contract_authorities')
    expected_labels = {
        'org.opencontainers.image.revision': value['source_commit'],
        'io.branconet.bortus.source-tree': value['application_tree'],
        'io.branconet.bortus.context-sha256': authorities['raw_git_context'],
        'io.branconet.bortus.manifest-sha256': authorities['raw_git_manifest'],
        'io.branconet.bortus.recipe': RECIPE,
        'io.branconet.bortus.build-id': value['build_id']}
    labels = value['labels']
    require(type(labels) is dict and set(labels) == set(expected_labels) | {
            'io.branconet.bortus.build-owner', 'org.opencontainers.image.base.name'} and
            all(labels[k] == v for k, v in expected_labels.items()) and
            type(labels['io.branconet.bortus.build-owner']) is str and
            re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', labels['io.branconet.bortus.build-owner']) and
            type(labels['org.opencontainers.image.base.name']) is str and
            re.fullmatch('[a-z0-9][a-z0-9._/:@-]{0,252}', labels['org.opencontainers.image.base.name']), 'contract_labels')
    layers = value['layers']
    require(type(layers) is list and len(layers) == 20 and all(
        type(d) is dict and set(d) == {'digest', 'size', 'mediaType'} and sha(d['digest']) and
        type(d['size']) is int and 0 <= d['size'] <= 4 * 1024 ** 3 and d['mediaType'] in LAYER_MEDIA
        for d in layers), 'contract_layers')
    require(type(value['ordered_diff_ids']) is list and len(value['ordered_diff_ids']) == 20 and
            all(sha(h) for h in value['ordered_diff_ids']) and
            layers[-1]['mediaType'] == 'application/vnd.oci.image.layer.v1.tar' and
            layers[-1]['digest'] == value['ordered_diff_ids'][-1], 'contract_diff_ids')
    require(value['runtime_qualified'] is False and value['deployed'] is False, 'contract_scope')
    return copy.deepcopy(value)


def load_contract(raw, expected_sha256):
    """The reviewed caller supplies the independent exact contract-file pin."""
    require(hexid(expected_sha256) and type(raw) is bytes and digest(raw) == expected_sha256, 'contract_hash')
    return validate_contract(decode(raw))


def verify_authorities(contract, streams):
    """Hash authority files, without expanding the compiled graph or running tools."""
    contract = validate_contract(contract)
    require(type(streams) is dict and set(streams) == AUTHORITIES, 'authority_set')
    for key, source in streams.items():
        hashed = hashlib.sha256()
        count = 0
        for chunk in iter(lambda: source.read(65536), b''):
            count += len(chunk)
            require(count <= (4 * 1024 ** 3 if key == 'raw_git_context' else 32 * 1024 ** 2), 'authority_bound')
            hashed.update(chunk)
        require(hashed.hexdigest() == contract['authority_sha256'][key], 'authority_identity')
    return True


def manifest_value(contract):
    return {'schemaVersion': 2, 'mediaType': MANIFEST,
            'config': {'mediaType': CONFIG, 'digest': contract['raw_config_digest'], 'size': contract['raw_config_bytes']},
            'layers': contract['layers']}


def verify_config(raw, contract):
    require(len(raw) == contract['raw_config_bytes'] and 'sha256:' + digest(raw) == contract['raw_config_digest'], 'config_identity')
    config = decode(raw)
    require(type(config) is dict and config.get('os') == 'linux' and config.get('architecture') == 'amd64' and
            type(config.get('config')) is dict and config['config'].get('Labels') == contract['labels'] and
            config.get('rootfs') == {'type': 'layers', 'diff_ids': contract['ordered_diff_ids']}, 'config_content')
    # Do not return config.Env or any other unselected config data.


def archive_module():
    # Import exposes the existing bounded archive primitives; its guarded main
    # is never called. No legacy receipt or transport is adopted by this format.
    spec = importlib.util.spec_from_file_location('overlay_archive_primitives',
                                                 pathlib.Path(__file__).with_name('stage-bortus-release-image.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_archive(stream, contract):
    contract = validate_contract(contract)
    def identity():
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), 'archive_regular')
        return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
    original = identity()
    s = archive_module()
    verified = s.archive_identity(stream, contract['image_tag'], contract['raw_config_digest'],
                                  contract['labels'], allow_repeated_layers=True)
    require(verified['archive_sha256'] == contract['archive_sha256'] and
            verified['archive_bytes'] == contract['archive_bytes'] and
            verified['layer_blob_digests'] == [d['digest'] for d in contract['layers']] and
            verified['ordered_diff_ids'] == contract['ordered_diff_ids'], 'archive_identity')
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode='r:') as archive:
        members = {m.name: m for m in archive}
        required = {'index.json', 'manifest.json', 'oci-layout',
                    'blobs/sha256/' + contract['manifest_digest'][7:],
                    'blobs/sha256/' + contract['raw_config_digest'][7:]} | {
                        'blobs/sha256/' + d['digest'][7:] for d in contract['layers']}
        require({m.name for m in members.values() if m.isfile()} == required, 'archive_inventory')
        require(all(m.isfile() or m.name.rstrip('/') in {'blobs', 'blobs/sha256'}
                    for m in members.values()), 'archive_directories')
        def metadata(name):
            require(members[name].isfile() and members[name].size <= MAX_METADATA, 'archive_metadata')
            return archive.extractfile(members[name]).read()
        require(decode(metadata('oci-layout')) == {'imageLayoutVersion': '1.0.0'}, 'archive_layout')
        top = decode(metadata('index.json'))
        expected = {'schemaVersion': 2, 'mediaType': INDEX, 'manifests': [{
            'mediaType': MANIFEST, 'digest': contract['manifest_digest'], 'size': contract['manifest_bytes'],
            'annotations': {'io.containerd.image.name': contract['canonical_alias'],
                            'org.opencontainers.image.ref.name': contract['image_tag'].split(':', 1)[1]}}]}
        require(top == expected, 'archive_index')
        raw = metadata('blobs/sha256/' + contract['manifest_digest'][7:])
        require(len(raw) == contract['manifest_bytes'] and 'sha256:' + digest(raw) == contract['manifest_digest'] and
                decode(raw) == manifest_value(contract), 'archive_manifest')
        verify_config(metadata('blobs/sha256/' + contract['raw_config_digest'][7:]), contract)
        for layer in contract['layers']:
            member = members['blobs/sha256/' + layer['digest'][7:]]
            require(member.size == layer['size'], 'archive_layer_size')
            prefix = archive.extractfile(member).read(2)
            require((prefix == b'\x1f\x8b') == layer['mediaType'].endswith('+gzip'), 'archive_layer_media')
    require(identity() == original, 'archive_changed')
    return expected_export_record(contract)


def expected_export_record(contract):
    """Expected packaging record shape; constructing it is not export evidence."""
    return {'format': FORMAT, 'purpose': 'export-contract', 'contract': validate_contract(contract),
            'runtime_qualified': False, 'deployed': False}


def verify_export_record(raw, expected_sha256, contract):
    require(hexid(expected_sha256) and digest(raw) == expected_sha256, 'export_record_hash')
    require(encoded(decode(raw)) == encoded(expected_export_record(contract)), 'export_record_identity')
    return expected_sha256


def preload_envelopes(contract, export_raw, export_sha256):
    """Plan three sequential node identities; contains no credentials or dispatch."""
    contract = validate_contract(contract)
    verify_export_record(export_raw, export_sha256, contract)
    return [{'format': FORMAT, 'purpose': 'preload-contract', 'host': host, 'ordinal': i,
             'export_record_sha256': export_sha256, 'contract': copy.deepcopy(contract),
             'runtime_qualified': False, 'deployed': False} for i, host in enumerate(HOSTS, 1)]


def verify_node_observation(envelope, contract, export_sha256, inventory, manifest_raw, config_raw):
    """Check supplied content bytes, never query a node or import an image."""
    contract = validate_contract(contract)
    require(hexid(export_sha256), 'export_record_hash')
    candidates = [{'format': FORMAT, 'purpose': 'preload-contract', 'host': host, 'ordinal': i,
                   'export_record_sha256': export_sha256, 'contract': contract,
                   'runtime_qualified': False, 'deployed': False} for i, host in enumerate(HOSTS, 1)]
    require(type(envelope) is dict and any(type(envelope.get('ordinal')) is int and
            encoded(envelope) == encoded(c) for c in candidates), 'node_envelope')
    require(type(inventory) is bytes and len(inventory) <= 1024 ** 2, 'inventory_bound')
    lines = inventory.decode('utf-8').splitlines()
    require(lines and lines[0].split()[:3] == ['REF', 'TYPE', 'DIGEST'] and len(lines) <= 16385, 'inventory_header')
    rows = [line.split() for line in lines[1:] if line.split()]
    require(all(len(row) >= 3 and sha(row[2]) for row in rows), 'inventory_rows')
    matching = [r for r in rows if r[0] in (contract['image_tag'], contract['canonical_alias'])]
    require(len(matching) == 1 and matching[0][2] == contract['manifest_digest'], 'node_tag_identity')
    require(type(manifest_raw) is bytes and len(manifest_raw) == contract['manifest_bytes'] and
            'sha256:' + digest(manifest_raw) == contract['manifest_digest'] and
            decode(manifest_raw) == manifest_value(contract), 'node_manifest_identity')
    verify_config(config_raw, contract)
    return {'format': FORMAT, 'host': envelope['host'], 'ordinal': envelope['ordinal'],
            'manifest_digest': contract['manifest_digest'], 'raw_config_digest': contract['raw_config_digest'],
            'packaging_content_matches': True, 'runtime_qualified': False, 'deployed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--contract-sha256', required=True)
    args = parser.parse_args()
    try:
        with open(args.contract, 'rb') as source:
            value = load_contract(source.read(MAX_METADATA + 1), args.contract_sha256)
        print(json.dumps({'format': FORMAT, 'recipe': value['recipe'],
                          'contract_valid': True, 'runtime_qualified': False, 'deployed': False}))
        return 0
    except Exception:
        print('Compiled-overlay contract refused.', file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
