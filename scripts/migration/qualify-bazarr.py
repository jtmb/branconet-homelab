#!/usr/bin/env python3
"""GET-only Bazarr update observation. Operator runs on master; never run in CI."""
import argparse
import datetime
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

NS = 'plex'
DEP_UID = '2bfbbb63-e949-4a5d-afd3-a923e2d02472'
PVC_UID = '5bddaab4-1974-4211-bcae-8392d1006804'
OLD = 'ghcr.io/hotio/bazarr:latest@sha256:004b1072983d1af766fc11d048121ded9d296fdd64ea304762afa9dfcaf51edb'
NEW = 'ghcr.io/hotio/bazarr:latest@sha256:c63aa057947400abded2583f7027d6ac1f8d70a8130401c36d5a244ef5999466'
NEW_RUNTIME = 'sha256:df6257b02f48a5470692f066d83dfaa1844e43bc5ebb691d529bf0d44ad1801d'
SECURITY_BASELINE_RUNTIME = NEW_RUNTIME
HOST = 'bazarr.branconet.lan'
MAX_REPLY = 64 * 1024 ** 2
MAX_TOTAL = 64 * 1024 ** 2
MAX_RECORDS = 50000
NORMALIZATION_PROOF_SHA256 = '51819b03f0cd14ddebfc4d186d5cbe186ab90181671980a3f434b87534f4b22a'
SECURITY_PATCH = False
# Exact old Validator defaults, AST-read from pinned v1.5.6 app/config.py.
# These numbers are legacy config defaults, not v1.6.2's effective score weights.
OLD_SCORE_DEFAULTS = {
    'movie_scores': {'audio_codec': 3, 'edition': 1, 'hash': 119, 'hearing_impaired': 1,
                     'release_group': 13, 'resolution': 2, 'source': 7, 'streaming_service': 1,
                     'title': 60, 'video_codec': 2, 'year': 30},
    'series_scores': {'audio_codec': 3, 'episode': 30, 'hash': 359, 'hearing_impaired': 1,
                      'release_group': 14, 'resolution': 2, 'season': 30, 'series': 180,
                      'source': 7, 'streaming_service': 1, 'video_codec': 2, 'year': 90},
}


class Refused(Exception):
    pass


def need(value, reason):
    if not value:
        raise Refused(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def command(argv, limit=MAX_REPLY):
    # Communicate through memory only; never include raw errors in a receipt.
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL)
    try:
        # Only fixed narrow resource GETs and a head-bounded config read run here.
        # The subprocess deadline also covers an exec stream that never closes.
        data, _ = child.communicate(timeout=30)
        need(len(data) <= limit, 'command_response_limit')
        need(child.returncode == 0, 'kubectl_failed')
        return data
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def kube(*argv, limit=MAX_REPLY):
    return command(['kubectl', '--request-timeout=20s', '-n', NS, *argv], limit)


def obj(*argv):
    return json.loads(kube(*argv, '-o', 'json'))


def identity(mode):
    expected = OLD if mode == 'baseline' else NEW
    dep = obj('get', 'deployment', 'bazarr')
    md, ds, state = dep['metadata'], dep['spec'], dep.get('status', {})
    need(md['uid'] == DEP_UID and not md.get('deletionTimestamp'), 'deployment_identity')
    need(ds.get('replicas', 1) == 1 and state.get('observedGeneration', 0) >= md['generation'], 'deployment_generation')
    need(all(state.get(k, 0) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']), 'deployment_not_ready')
    containers = ds['template']['spec']['containers']
    need(len(containers) == 1 and containers[0]['name'] == 'bazarr' and containers[0]['image'] == expected, 'deployment_image')
    mounts = containers[0]['volumeMounts']
    need(any(m['name'] == 'data-0' and m['mountPath'] == '/config' and not m.get('subPath') and not m.get('readOnly', False) for m in mounts), 'config_mount')
    claims = {}
    for name in ['bazarr-data-0', 'bazarr-data-1', 'bazarr-data-2']:
        pvc = obj('get', 'pvc', name)
        need(pvc['status']['phase'] == 'Bound' and not pvc['metadata'].get('deletionTimestamp'), 'claim_not_bound')
        claims[name] = {'uid': pvc['metadata']['uid'], 'volume': pvc['spec']['volumeName'],
                        'storage_class': pvc['spec'].get('storageClassName', '')}
    need(claims['bazarr-data-0'] == {'uid': PVC_UID, 'volume': 'pvc-' + PVC_UID, 'storage_class': 'longhorn'}, 'config_claim_identity')
    actual_claims = {v.get('persistentVolumeClaim', {}).get('claimName') for v in ds['template']['spec'].get('volumes', [])}
    need(set(claims) <= actual_claims, 'deployment_claims')
    rss = obj('get', 'replicasets', '-l', 'app=bazarr')['items']
    owners = {r['metadata']['uid'] for r in rss if any(o.get('uid') == DEP_UID and o.get('controller') for o in r['metadata'].get('ownerReferences', []))}
    pods = [p for p in obj('get', 'pods', '-l', 'app=bazarr')['items'] if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase') not in ['Succeeded', 'Failed']]
    need(len(pods) == 1, 'pod_count')
    pod = pods[0]
    need(any(o.get('uid') in owners and o.get('controller') for o in pod['metadata'].get('ownerReferences', [])), 'pod_owner')
    need(pod['status'].get('phase') == 'Running' and any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod['status'].get('conditions', [])), 'pod_not_ready')
    statuses = pod['status'].get('containerStatuses', [])
    need(len(statuses) == 1 and statuses[0]['name'] == 'bazarr' and statuses[0].get('ready') is True, 'container_not_ready')
    runtime = statuses[0].get('imageID', '').rsplit('@', 1)[-1]
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', runtime), 'runtime_digest_missing')
    if mode != 'baseline':
        need(runtime in [NEW_RUNTIME, NEW.rsplit('@', 1)[1]], 'runtime_digest')
    elif SECURITY_PATCH:
        need(runtime in [SECURITY_BASELINE_RUNTIME, OLD.rsplit('@', 1)[1]], 'security_baseline_runtime_digest')
    service = obj('get', 'service', 'bazarr')
    need(service['spec'].get('selector', {}).get('app') == 'bazarr', 'service_selector')
    ip = ipaddress.ip_address(service['spec']['clusterIP'])
    need(ip.is_private and not ip.is_loopback and not ip.is_link_local, 'service_address')
    need(any(p['port'] == 6767 and p.get('targetPort') in [6767, 'p6767-tcp'] for p in service['spec']['ports']), 'service_port')
    slices = obj('get', 'endpointslices', '-l', 'kubernetes.io/service-name=bazarr')['items']
    endpoints = [e for s in slices for e in s.get('endpoints', []) if e.get('conditions', {}).get('ready') is True]
    need(len(endpoints) == 1 and endpoints[0].get('targetRef', {}).get('uid') == pod['metadata']['uid'] and pod['status']['podIP'] in endpoints[0]['addresses'], 'service_endpoint_identity')
    return {'deployment_uid': DEP_UID, 'deployment_generation': md['generation'], 'claims': claims,
            'pod_uid': pod['metadata']['uid'], 'pod_name': pod['metadata']['name'],
            'restart_count': statuses[0].get('restartCount', 0), 'image': expected,
            'runtime_digest': runtime, 'service_uid': service['metadata']['uid'],
            'cluster_ip': str(ip)}


def observe_pod(state, mode, raw_key):
    reader = Path(__file__).with_name('bazarr-sqlite-observer.py')
    source = reader.read_bytes()
    need(len(source) <= 65536, 'observer_source_limit')
    digest = hashlib.sha256(source).hexdigest()
    child = subprocess.run(['kubectl', '--request-timeout=150s', '-n', NS, 'exec', '-i',
                            state['pod_name'], '-c', 'bazarr', '--', '/usr/bin/python3', '-B', '-c',
                            source.decode(), mode, state['cluster_ip']] + (['security-patch'] if SECURITY_PATCH else []),
                           input=raw_key, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=150)
    need(len(child.stdout) <= MAX_REPLY, 'observer_response_limit')
    if child.returncode:
        try:
            refused = json.loads(child.stdout)
            reason = refused.get('reason', '')
        except Exception:
            reason = ''
        need(False, 'observer_refused_' + reason if re.fullmatch(r'[a-z0-9_]{1,96}', reason) else 'observer_failed_raw_details_suppressed')
    result = json.loads(child.stdout)
    need(result.get('schema_version') == 1 and result.get('mode') == mode and result.get('quick_check_passed') is True, 'observer_result_shape')
    need(hashlib.sha256(reader.read_bytes()).hexdigest() == digest, 'observer_source_changed')
    result['observer_sha256'] = digest
    return result


def vendor_normalization(before, after, key, baseline_sha, proof_path):
    proof = protected_file(proof_path)
    need(hashlib.sha256(proof_path.read_bytes()).hexdigest() == NORMALIZATION_PROOF_SHA256, 'normalization_proof_sha256')
    need(proof.get('state') == 'read-only-diagnosis' and proof.get('baseline_sha256') == baseline_sha, 'normalization_baseline_binding')
    for flag in ['cold_archive_authenticated', 'cold_config_matches_original_baseline',
                 'live_config_matches_diagnostic', 'all_removed_notifiers_disabled_empty']:
        need(proof.get(flag) is True, 'normalization_evidence_incomplete')
    defaults = proof['public_default_equivalence']
    need(defaults.get('score_field_count') == 23 and defaults.get('customized_score_count') == 0, 'customized_scores_not_normalizable')
    for flag in ['all_auth_leaves_preserved', 'all_removed_scores_equal_old_public_defaults',
                 'podnapisi_disabled_old_and_new', 'podnapisi_ssl_equal_old_default',
                 'gemini_old_key_empty', 'gemini_new_keys_empty_list']:
        need(defaults.get(flag) is True, 'normalization_default_evidence')

    def mac(value):
        return hmac.new(key, canonical(value), hashlib.sha256).hexdigest()

    def value_mac(value):
        return mac({'type': type(value).__name__, 'value': value})

    old_config = before['application']['config_leaf_fingerprints']
    new_config = after['application']['config_leaf_fingerprints']
    paths = {(section, field): value for section, fields in OLD_SCORE_DEFAULTS.items()
             for field, value in fields.items()}
    paths[('podnapisi', 'verify_ssl')] = True
    paths[('translator', 'gemini_key')] = ''
    need(len(paths) == 25 and proof.get('changed_count') == 25, 'normalization_config_count')
    changes = proof['changed_config_leaves']
    need(len(changes) == 25 and {row.get('path') for row in changes} == {'/'.join(p) for p in paths}, 'normalization_exact_field_paths')
    need(all(row.get('new_missing') is True for row in changes), 'normalization_requires_vendor_removal')
    allowed_config = set()
    for route, expected in paths.items():
        fingerprint = mac({'path': list(route)})
        need(old_config.get(fingerprint) == value_mac(expected), 'nondefault_old_config_cannot_be_removed')
        need(fingerprint not in new_config, 'removed_default_unexpected_new_value')
        allowed_config.add(fingerprint)
    gemini_keys = mac({'path': ['translator', 'gemini_keys']})
    need(new_config.get(gemini_keys) == value_mac([]), 'new_gemini_key_list_not_empty')
    providers = mac({'path': ['general', 'enabled_providers']})
    need(providers in old_config and new_config.get(providers) == old_config[providers], 'enabled_providers_changed')

    removed = proof['removed_notifiers']
    need(proof.get('removed_count') == 2 and len(removed) == 2, 'normalization_notifier_count')
    allowed_notifiers = set()
    old_rows = before['fingerprints']['table_settings_notifier']
    new_rows = after['fingerprints']['table_settings_notifier']
    for row in removed:
        rid = row.get('row_fingerprint')
        need(isinstance(rid, str) and bool(re.fullmatch(r'[0-9a-f]{64}', rid)), 'normalization_notifier_identity')
        need(row.get('disabled') is True and row.get('url_empty') is True and row.get('standard_identifier') is True, 'active_notifier_cannot_be_removed')
        need(rid in old_rows and rid not in new_rows and set(old_rows[rid]) == {'name', 'enabled', 'url'}, 'normalization_exact_missing_notifier')
        need(old_rows[rid]['enabled'] == value_mac(0) and old_rows[rid]['url'] in [value_mac(None), value_mac('')], 'nonempty_notifier_cannot_be_removed')
        allowed_notifiers.add(rid)
    need(len(allowed_notifiers) == 2, 'normalization_duplicate_notifier')
    metadata = {'proof_sha256': NORMALIZATION_PROOF_SHA256,
                'baseline_sha256': baseline_sha, 'cold_archive_sha256': proof['cold_archive_sha256'],
                'diagnostic_sha256': proof['diagnostic_sha256'],
                'removed_old_default_score_leaves': 23, 'removed_disabled_provider_tls_default': 1,
                'empty_legacy_gemini_key_to_empty_list': True, 'removed_disabled_empty_notifier_rows': 2,
                'upstream_scoring_behavior_changed': True, 'equivalent_effective_weights_claimed': False,
                'old_config_source_sha256': 'ef9bc6edf6c1759a6183265a84a420747b19016fee3690fda9be5f6d4bc49c79',
                'new_config_source_sha256': 'acfd53a791cf3d749fd8493a33375e06f005b7e8c7e5f9cfea431b59acd7c8d2',
                'config_source_url': 'https://github.com/morpheus65535/bazarr/blob/v1.6.2/bazarr/app/config.py',
                'notifier_source_url': 'https://github.com/morpheus65535/bazarr/blob/v1.6.2/bazarr/app/notifier.py'}
    return allowed_config, allowed_notifiers, metadata


def compare(before, after, allowed_config=frozenset(), allowed_notifiers=frozenset()):
    need(before['key_binding'] == after['key_binding'], 'hmac_key_changed')
    failures = {}
    for table, rows in before['fingerprints'].items():
        current = after['fingerprints'].get(table, {})
        failures[table] = sum(rid not in current or any(current[rid].get(field) != value for field, value in fields.items())
                              for rid, fields in rows.items()
                              if not (table == 'table_settings_notifier' and rid in allowed_notifiers and rid not in current))
    old_subs, new_subs = before['subtitle_fingerprints'], after['subtitle_fingerprints']
    failures['semantic_subtitles'] = sum(new_subs.get(value, 0) < count for value, count in old_subs.items())
    old_config = before['application']['config_leaf_fingerprints']
    new_config = after['application']['config_leaf_fingerprints']
    failures['config_leaves'] = sum(new_config.get(key) != value for key, value in old_config.items()
                                   if not (key in allowed_config and key not in new_config))
    old_foreign, new_foreign = before['foreign_key_violations'], after['foreign_key_violations']
    failures['new_foreign_key_violations'] = sum(count > old_foreign.get(value, 0) for value, count in new_foreign.items())
    need(not any(failures.values()), 'preexisting_semantic_data_or_config_changed')
    return failures


def protected_file(path):
    need(path.is_absolute() and path.resolve() == path, 'protected_path_required')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077 and info.st_size <= MAX_TOTAL, 'protected_file_permissions')
    return json.loads(path.read_text())


def write_new(path, value):
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'receipt_path')
    need(not any((parent / '.git').exists() for parent in path.parents), 'receipt_inside_git')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077, 'receipt_parent_permissions')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    global OLD, NEW, NEW_RUNTIME, SECURITY_PATCH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['baseline', 'after', 'restart'])
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--prior-receipt', type=Path)
    parser.add_argument('--vendor-normalization-proof', type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--security-patch', action='store_true', help='Same1.6.2 app; exact reviewed local dependency/OS overlay, no vendor normalization')
    args = parser.parse_args()
    SECURITY_PATCH = args.security_patch
    if args.security_patch:
        OLD = NEW
        NEW = 'docker.io/library/bazarr-security-20261023@sha256:bcf9a782f3381b4182bed0985e0d38df79da0218ead2ca47c577595e9dafe21b'
        NEW_RUNTIME = NEW.rsplit('@', 1)[1]
    os.umask(0o077)
    # Exactly one existing operator HMAC key; never create or persist key material here.
    raw = sys.stdin.buffer.read(66)
    need(re.fullmatch(b'[0-9a-f]{64}\n?', raw) is not None, 'stdin_requires_32_byte_hex_key')
    key = bytes.fromhex(raw.decode().strip())
    need((args.mode == 'baseline') == (args.baseline is None), 'baseline_argument')
    need((args.mode == 'restart') == (args.prior_receipt is not None), 'restart_argument')
    need(args.vendor_normalization_proof is None if args.security_patch else (args.mode == 'baseline') == (args.vendor_normalization_proof is None), 'normalization_proof_argument')
    start = identity(args.mode)
    observation = observe_pod(start, args.mode, raw)
    finish = identity(args.mode)
    need(start == finish, 'runtime_changed_during_observation')
    checks = None
    baseline_sha = None
    normalization = None
    if args.baseline:
        prior = protected_file(args.baseline)
        need(prior.get('mode') == 'baseline' and prior.get('schema_version') == 1, 'baseline_shape')
        need(prior['identity']['claims'] == start['claims'] and prior['identity']['service_uid'] == start['service_uid'], 'original_claim_or_service_changed')
        baseline_sha = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        need(prior.get('security_patch', False) == args.security_patch, 'same_qualification_scope')
        if args.security_patch:
            need(prior['identity']['image'] == OLD and prior['identity']['runtime_digest'] in [SECURITY_BASELINE_RUNTIME, OLD.rsplit('@', 1)[1]], 'security_baseline_image')
            need(prior['observation']['application']['version'] == '1.6.2', 'security_baseline_version')
        config_exceptions, notifier_exceptions = set(), set()
        if not args.security_patch:
            config_exceptions, notifier_exceptions, normalization = vendor_normalization(
                prior['observation'], observation, key, baseline_sha, args.vendor_normalization_proof)
        checks = compare(prior['observation'], observation, config_exceptions, notifier_exceptions)
    if args.prior_receipt:
        prior = protected_file(args.prior_receipt)
        need(prior.get('mode') == 'after' and prior.get('schema_version') == 1 and prior.get('baseline_sha256') == baseline_sha, 'prior_receipt_shape')
        need(prior.get('security_patch', False) == args.security_patch, 'same_restart_scope')
        if not args.security_patch:
            need(prior.get('vendor_normalization', {}).get('proof_sha256') == NORMALIZATION_PROOF_SHA256, 'prior_normalization_proof_binding')
        need(prior['identity']['claims'] == start['claims'] and prior['identity']['image'] == start['image'], 'restart_identity')
        need(prior['identity']['pod_uid'] != start['pod_uid'] or prior['identity']['restart_count'] < start['restart_count'], 'restart_not_observed')
        compare(prior['observation'], observation)
    # Private runtime names/IPs are used in memory but omitted from durable receipts.
    safe_identity = {k: v for k, v in start.items() if k not in ['pod_name', 'cluster_ip']}
    receipt = {'schema_version': 1, 'mode': args.mode, 'security_patch': args.security_patch, 'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'identity': safe_identity, 'observation': observation, 'comparison_mismatches': checks,
               'baseline_sha256': baseline_sha, 'vendor_normalization': normalization,
               'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'get_only': True, 'data_preservation_passed': args.mode != 'baseline',
               'sql_quick_check_verified': True, 'auth_config_preservation_passed': args.mode != 'baseline', 'user_password_table_verified': False,
               'integration_connection_tests_run': False, 'external_routes_verified': False,
               'full_acceptance_complete': False}
    write_new(args.receipt, receipt)
    print(json.dumps({'status': 'observed', 'mode': args.mode, 'version': observation['application']['version'],
                      'counts': observation['counts'], 'subtitle_count': observation['subtitle_count'], 'data_preservation_passed': args.mode != 'baseline',
                      'full_acceptance_complete': False}))


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'status': 'refused', 'reason': 'unexpected_operation_failed_raw_details_suppressed'}))
        raise SystemExit(1)
