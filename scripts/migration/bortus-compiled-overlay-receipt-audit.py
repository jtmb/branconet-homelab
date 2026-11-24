#!/usr/bin/env python3
"""Read-only content audit of separately pinned overlay staging receipts.

Pins establish byte identity, not provenance. Even completed records cannot
establish actual transport, current node state, runtime or delivery acceptance.
There is no execution, archive access, repair, adoption or receipt writer here.
"""
import argparse
import importlib.util
import os
import pathlib
import stat
import sys
import uuid

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location('overlay_audit_contract',
    pathlib.Path(__file__).with_name('bortus-compiled-overlay-contract.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

FORMAT = 'bortus-compiled-overlay-receipt-audit/v1'
REQUEST = 'bortus-compiled-overlay-receipt-selection/v1'
ADAPTER = 'bortus-compiled-overlay-adapter/v1'
CONTRACT_PIN = 'a47ea88d868bc99e0007ca78af7f393a616db4cbbfd03fd59f62c69c4c397ca1'
SOURCE_PINS = {
    'io': '2bb52cbd84ce93aa946eab25c68992e9ded90927a3097d7d245b66baf2e95493',
    'contract': '234a58a1f6ecdbf53ffeca1812881b1107bcd4d47ca38b02350cd35638209f45',
    'node': '26766ee11768fd48ea6a5ade1f92d12f5fc5cb3fabbbcf11948591553dcefd2d'}
CLASSES = ('public-synthetic', 'externally-observed')
PHASES = ('validating', 'pending', 'refused', 'uncertain', 'completed')
BASE = {'format', 'purpose', 'phase', 'owner', 'source_commit', 'runtime_qualified', 'deployed'}
NODE_ID = {'host', 'ordinal', 'contract_sha256', 'export_execution_sha256'}
NODE_RESULT = {'archive_sha256', 'archive_bytes', 'manifest_digest', 'raw_config_digest',
               'import_exit_code', 'packaging_content_matches'}
NODE_EXITS = {s + '_exit_code' for s in
              ('images-before', 'images-preimport', 'import', 'images-after', 'manifest', 'config')}
GATES = ('security', 'performance', 'actual_assistive_technology', 'true_zoom',
         'full_browser_acceptance', 'native_values', 'native_history', 'native_CAS',
         'native_rotation', 'retention', 'compatible_independent_recovery',
         'compatible_rollback', 'fresh_consistent_encrypted_backup', 'quiescence',
         'populated_schema_preservation', 'effective_RBAC', 'effective_admission',
         'preserved_data', 'validated_single_publisher', 'final_PRD_deployment',
         'final_PRD_actual_verification')


def require(ok, code):
    if not ok:
        raise ValueError(code)


def same(actual, expected):
    # Canonical JSON retains bool/int/float distinctions, unlike Python ==.
    return C.encoded(actual) == C.encoded(expected)


def pinned(raw, pin):
    require(C.hexid(pin) and type(raw) is bytes and C.digest(raw) == pin, 'receipt_pin')
    return C.decode(raw)


def owner(value):
    require(type(value) is str and str(uuid.UUID(value)) == value, 'owner')


def exit_codes(value, keys, completed):
    for key in keys & set(value):
        require(type(value[key]) is int and -255 <= value[key] <= 255, 'exit_type')
        if completed:
            require(value[key] == 0, 'exit_failure')


def base(value, purpose, contract):
    require(type(value) is dict and BASE <= set(value), 'receipt_fields')
    expected_purpose = 'node-preload' if purpose == 'node' and value['phase'] in ('completed', 'uncertain') else purpose
    require(value['format'] == ADAPTER and value['purpose'] in (purpose, expected_purpose)
            and value['phase'] in PHASES and value['source_commit'] == contract['source_commit']
            and value['runtime_qualified'] is False and value['deployed'] is False, 'receipt_scope')
    owner(value['owner'])
    if 'contract_sha256' in value:
        require(value['contract_sha256'] == CONTRACT_PIN, 'receipt_contract')
    if 'failure' in value:
        require(value['phase'] in ('refused', 'uncertain') and value['failure'] == {
            'export': 'export_failed', 'preload': 'preload_failed', 'node': 'node_staging_failed'}[purpose],
            'failure_code')


def node_reply(contract, host, ordinal, export_pin):
    return {'format': ADAPTER, 'purpose': 'node-preload', 'phase': 'completed',
            'host': host, 'ordinal': ordinal, 'contract_sha256': CONTRACT_PIN,
            'export_execution_sha256': export_pin, 'source_commit': contract['source_commit'],
            'archive_sha256': contract['archive_sha256'], 'archive_bytes': contract['archive_bytes'],
            'manifest_digest': contract['manifest_digest'], 'raw_config_digest': contract['raw_config_digest'],
            'import_exit_code': 0, 'packaging_content_matches': True,
            'runtime_qualified': False, 'deployed': False}


def export_record(value, contract):
    base(value, 'export', contract)
    complete = value['phase'] == 'completed'
    fields = BASE | {'contract_sha256', 'save_exit_code', 'packaging_record', 'archive_path'}
    final_payload = complete or 'packaging_record' in value
    if final_payload:
        require(set(value) == (fields if complete else fields | {'failure'})
                and (complete or value['phase'] == 'uncertain') and type(value['save_exit_code']) is int
                and value['save_exit_code'] == 0, 'export_completed_fields')
        require(same(value['packaging_record'], C.expected_export_record(contract)), 'packaging_identity')
        # Validate as POSIX data only. Never follow an archive path from a receipt.
        path = value['archive_path']
        require(type(path) is str and 0 < len(path) <= 4096 and '\0' not in path
                and path.startswith('/') and '..' not in pathlib.PurePosixPath(path).parts,
                'archive_path')
    else:
        allowed = BASE | {'nodes', 'contract_sha256', 'source-before_exit_code',
                          'save_exit_code', 'source-after_exit_code', 'failure'}
        require(BASE | {'nodes'} <= set(value) <= allowed and value['nodes'] == [], 'export_partial_fields')
        exit_codes(value, {'source-before_exit_code', 'save_exit_code', 'source-after_exit_code'}, False)
    return value['phase']


def node_record(value, contract, host, ordinal, export_pin):
    base(value, 'node', contract)
    complete = value['phase'] == 'completed'
    expected = node_reply(contract, host, ordinal, export_pin)
    for key in NODE_ID & set(value):
        require(same(value[key], expected[key]), 'node_identity')
    final_payload = complete or bool((NODE_RESULT - NODE_EXITS) & set(value))
    if final_payload:
        fields = BASE | NODE_ID | NODE_RESULT | NODE_EXITS | {'nodes'}
        require(set(value) == (fields if complete else fields | {'failure'})
                and (complete or value['phase'] == 'uncertain'), 'node_completed_fields')
        expected['phase'] = value['phase']
        require(all(same(value[k], v) for k, v in expected.items()), 'node_observation')
    else:
        require(BASE | {'nodes'} <= set(value) <= BASE | NODE_ID | NODE_EXITS | {'nodes', 'failure'},
                'node_partial_fields')
    require(value['nodes'] == [], 'node_children')
    exit_codes(value, NODE_EXITS, final_payload)
    return value['phase']


def controller_record(value, contract, export_pin):
    base(value, 'preload', contract)
    complete = value['phase'] == 'completed'
    fields = BASE | {'nodes', 'contract_sha256', 'export_execution_sha256', 'source_sha256'}
    exits = {h + '_exit_code' for h in C.HOSTS}
    if complete:
        require(set(value) == fields | exits, 'preload_completed_fields')
    else:
        require(BASE | {'nodes'} <= set(value) <= fields | exits | {'failure'}, 'preload_partial_fields')
    if 'export_execution_sha256' in value:
        require(value['export_execution_sha256'] == export_pin and C.hexid(export_pin), 'preload_export_pin')
    if 'source_sha256' in value:
        require(same(value['source_sha256'], SOURCE_PINS), 'tooling_pins')
    rows = value['nodes']
    require(type(rows) is list and len(rows) <= 3 and (not complete or len(rows) == 3), 'preload_nodes')
    phases = []
    for i, row in enumerate(rows, 1):
        require(type(row) is dict and type(row.get('ordinal')) is int
                and row['ordinal'] == i and row.get('host') == C.HOSTS[i - 1], 'preload_order')
        if row.get('phase') == 'completed':
            require(all(p == 'completed' for p in phases)
                    and same(row, node_reply(contract, C.HOSTS[i - 1], i, export_pin)), 'preload_reply')
        else:
            require(not complete and i == len(rows) and set(row) == {'host', 'ordinal', 'phase'}
                    and row['phase'] in ('pending', 'refused', 'uncertain'), 'preload_partial_node')
        phases.append(row['phase'])
    exit_codes(value, exits, complete)
    return value['phase'], phases


def audit(contract_raw, contract_pin, selection_raw, selection_pin, receipts, evidence_class):
    require(contract_pin == CONTRACT_PIN, 'exact_contract_pin')
    contract = C.load_contract(contract_raw, contract_pin)
    require(evidence_class in CLASSES, 'evidence_class')
    selection = pinned(selection_raw, selection_pin)
    fields = {'format', 'evidence_class', 'contract_sha256', 'export_sha256', 'preload_sha256',
              'nodes', 'runtime_qualified', 'deployed'}
    require(type(selection) is dict and set(selection) == fields and selection['format'] == REQUEST
            and selection['evidence_class'] == evidence_class and selection['contract_sha256'] == contract_pin
            and selection['runtime_qualified'] is False and selection['deployed'] is False, 'selection_fields')
    require(type(selection['nodes']) is list and len(selection['nodes']) == 3, 'selection_nodes')
    pins = {'export': selection['export_sha256'], 'preload': selection['preload_sha256']}
    for i, row in enumerate(selection['nodes'], 1):
        require(type(row) is dict and set(row) == {'host', 'ordinal', 'sha256'}
                and type(row['ordinal']) is int and row['ordinal'] == i
                and row['host'] == C.HOSTS[i - 1], 'selection_order')
        pins['node-' + str(i)] = row['sha256']
    require(all(p is None or C.hexid(p) for p in pins.values()), 'selection_pins')
    require(type(receipts) is dict and set(receipts) == set(pins), 'receipt_set')
    values, status = {}, {}
    for key, pin in pins.items():
        if pin is None:
            require(receipts[key] is None, 'unselected_receipt')
            status[key] = 'missing'
        else:
            require(receipts[key] is not None, 'selected_receipt_missing')
            values[key] = pinned(receipts[key], pin)
    export_pin = selection['export_sha256']
    if 'export' in values:
        status['export'] = export_record(values['export'], contract)
    controller_phases = []
    if 'preload' in values:
        status['preload'], controller_phases = controller_record(values['preload'], contract, export_pin)
    for i, host in enumerate(C.HOSTS, 1):
        key = 'node-' + str(i)
        if key in values:
            require(C.hexid(export_pin), 'node_export_pin_missing')
            status[key] = node_record(values[key], contract, host, i, export_pin)
    owners = [v['owner'] for v in values.values()]
    require(len(owners) == len(set(owners)), 'reused_owner')
    if any(status[k] == 'completed' for k in ('preload', 'node-1', 'node-2', 'node-3')):
        require(status['export'] == 'completed', 'completed_without_export')
    # A complete node receipt with a lost controller reply is possible. Report
    # this disagreement; never upgrade the controller's pending/uncertain phase.
    mismatches = [i for i in range(1, 4)
                  if (controller_phases[i - 1] if i <= len(controller_phases) else 'missing')
                  != status['node-' + str(i)]]
    complete = all(v == 'completed' for v in status.values()) and not mismatches
    return {'format': FORMAT, 'evidence_class': evidence_class,
            'evidence_class_is_caller_claim': True,
            'content_status': 'completed-content-consistent' if complete else 'incomplete',
            'synthetic_source_only': evidence_class == 'public-synthetic',
            'receipt_phases': status, 'controller_node_phase_disagreements': mismatches,
            'selection_sha256': selection_pin, 'contract_sha256': contract_pin,
            'receipt_sha256': pins, 'source_commit': contract['source_commit'],
            'archive_sha256': contract['archive_sha256'], 'archive_bytes': contract['archive_bytes'],
            'manifest_digest': contract['manifest_digest'], 'raw_config_digest': contract['raw_config_digest'],
            'actual_transport_proven': False, 'current_node_state_proven': False,
            'archive_bytes_reverified': False, 'provenance_authenticated': False,
            'execution_authorized': False, 'runtime_qualified': False, 'deployed': False,
            'overall_CI_qualified': False, 'four_findings_unresolved': True,
            'prior_32_and_earlier_one_unresolved': True, 'all_44_original_clauses_preserved': True,
            'original_A01_A22_acceptance': {f'A{i:02}': 'unchanged-see-original-plan' for i in range(1, 23)},
            'unresolved_delivery_gates': list(GATES), 'full_goal_active': True}


def stable(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_file(path):
    """Bounded regular/single-link POSIX read, no symlink traversal or writes."""
    path = pathlib.Path(path)
    require(os.name == 'posix' and path.is_absolute() and '..' not in path.parts
            and len(path.parts) <= 32, 'input_path')
    descriptors, anchors = [], []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        descriptors.append(fd)
        current = pathlib.Path('/')
        for part in path.parts[1:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            descriptors.append(fd)
            current /= part
            info = os.fstat(fd)
            require(info.st_uid in (0, os.getuid()) and info.st_mode & 0o022 == 0, 'input_ancestor')
            anchors.append((current, fd, stable(info)[:4]))
        filefd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
        descriptors.append(filefd)
        before = os.fstat(filefd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid()
                and before.st_mode & 0o022 == 0 and 0 < before.st_size <= C.MAX_METADATA, 'input_file')
        with os.fdopen(filefd, 'rb', closefd=False) as stream:
            raw = stream.read(C.MAX_METADATA + 1)
        require(len(raw) == before.st_size and stable(before) == stable(os.fstat(filefd))
                == stable(path.lstat()), 'input_changed')
        require(all(stable(p.lstat())[:4] == old == stable(os.fstat(d))[:4]
                    for p, d, old in anchors), 'ancestor_changed')
        return raw
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--selection', required=True)
    parser.add_argument('--selection-sha256', required=True)
    parser.add_argument('--evidence-class', choices=CLASSES, required=True)
    for name in ('export', 'preload', 'node-1', 'node-2', 'node-3'):
        parser.add_argument('--' + name)
    args = parser.parse_args(argv)
    try:
        receipts = {k: read_file(getattr(args, k.replace('-', '_')))
                    if getattr(args, k.replace('-', '_')) is not None else None
                    for k in ('export', 'preload', 'node-1', 'node-2', 'node-3')}
        result = audit(read_file(args.contract), args.contract_sha256,
                       read_file(args.selection), args.selection_sha256, receipts, args.evidence_class)
        print(C.encoded(result).decode())
        return 0 if result['content_status'] == 'completed-content-consistent' else 2
    except Exception:
        print('Overlay receipt content audit refused; no authority granted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
