#!/usr/bin/env python3
"""Enable kube-apiserver audit logging in kubeadm-owned configuration.

Pure transforms shared by playbooks/apiserver-audit-logging.yml (static Pod
manifest, one node at a time) and run-apiserver-audit-logging.py
(kube-system/kubeadm-config, so a later `kubeadm upgrade` keeps the setting).

Neither document is edited by text substitution. Each is parsed, the audit
flags, mounts and volumes are appended, and the result is re-parsed and
compared with the expected object. Anything partial or different from these
exact settings is refused rather than merged.

CLI (used by the play, manifest on stdin):
    apiserver_audit.py manifest  -> JSON {state, changed, manifest, sha256_before, sha256_after}
"""
import copy
import hashlib
import json
import sys

import yaml

POLICY_PATH = '/etc/kubernetes/audit-policy.yaml'
LOG_DIR = '/var/log/kubernetes/audit'
LOG_PATH = LOG_DIR + '/audit.log'

# Rotation: 100 MB files, 30 gzip-compressed backups, 30 days. Sizing and the
# measured retention window are in docs/API-AUDIT-LOGGING.md.
FLAGS = (
    ('audit-policy-file', POLICY_PATH),
    ('audit-log-path', LOG_PATH),
    ('audit-log-maxage', '30'),
    ('audit-log-maxbackup', '30'),
    ('audit-log-maxsize', '100'),
    ('audit-log-compress', 'true'),
)
MOUNTS = (
    {'name': 'audit-policy', 'mountPath': POLICY_PATH, 'readOnly': True},
    {'name': 'audit-log', 'mountPath': LOG_DIR},
)
VOLUMES = (
    {'name': 'audit-policy', 'hostPath': {'path': POLICY_PATH, 'type': 'File'}},
    {'name': 'audit-log', 'hostPath': {'path': LOG_DIR, 'type': 'DirectoryOrCreate'}},
)
KUBEADM_VOLUMES = (
    {'name': 'audit-policy', 'hostPath': POLICY_PATH, 'mountPath': POLICY_PATH,
     'readOnly': True, 'pathType': 'File'},
    {'name': 'audit-log', 'hostPath': LOG_DIR, 'mountPath': LOG_DIR,
     'pathType': 'DirectoryOrCreate'},
)
AUDIT_NAMES = frozenset(item['name'] for item in MOUNTS)
AUDIT_PATHS = frozenset((POLICY_PATH, LOG_DIR))


class AuditConfigError(ValueError):
    """The document is not the expected one, or already differs from these settings."""


def _mount(item):
    return dict(item, readOnly=bool(item.get('readOnly', False)))


def _container(pod):
    if not isinstance(pod, dict) or pod.get('apiVersion') != 'v1' or pod.get('kind') != 'Pod':
        raise AuditConfigError('not_a_pod')
    metadata = pod.get('metadata') or {}
    if metadata.get('name') != 'kube-apiserver' or metadata.get('namespace') != 'kube-system':
        raise AuditConfigError('not_kube_apiserver')
    containers = (pod.get('spec') or {}).get('containers') or []
    if len(containers) != 1 or containers[0].get('name') != 'kube-apiserver':
        raise AuditConfigError('unexpected_containers')
    command = containers[0].get('command')
    if not isinstance(command, list) or not command or command[0] != 'kube-apiserver':
        raise AuditConfigError('unexpected_command')
    if any(not isinstance(arg, str) for arg in command):
        raise AuditConfigError('unexpected_command')
    return containers[0]


def _audit_flags(arguments):
    flags = {}
    for argument in arguments:
        if not argument.startswith('--audit-'):
            continue
        name, separator, value = argument[2:].partition('=')
        if name in flags:
            raise AuditConfigError('duplicate_audit_flag')
        flags[name] = value if separator else None
    return flags


def manifest_state(pod):
    """Return 'absent' or 'enabled'. Partial or different settings raise."""
    container = _container(pod)
    flags = _audit_flags(container['command'][1:])
    mounts = container.get('volumeMounts') or []
    volumes = pod['spec'].get('volumes') or []
    named_mounts = {item.get('name'): item for item in mounts if item.get('name') in AUDIT_NAMES}
    named_volumes = {item.get('name'): item for item in volumes if item.get('name') in AUDIT_NAMES}
    if not flags and not named_mounts and not named_volumes:
        if any(item.get('mountPath') in AUDIT_PATHS for item in mounts):
            raise AuditConfigError('audit_path_already_mounted')
        return 'absent'
    if (flags == dict(FLAGS)
            and len(named_mounts) == len(MOUNTS) and len(named_volumes) == len(VOLUMES)
            and all(_mount(named_mounts[item['name']]) == _mount(item) for item in MOUNTS)
            and all(named_volumes[item['name']] == item for item in VOLUMES)
            and sum(item.get('name') in AUDIT_NAMES for item in mounts) == len(MOUNTS)
            and sum(item.get('name') in AUDIT_NAMES for item in volumes) == len(VOLUMES)):
        return 'enabled'
    raise AuditConfigError('audit_settings_differ')


def enable_manifest(pod):
    """Return (pod, changed). Only appends; never edits or reorders existing fields."""
    if manifest_state(pod) == 'enabled':
        return pod, False
    result = copy.deepcopy(pod)
    container = _container(result)
    container['command'] = container['command'] + ['--%s=%s' % item for item in FLAGS]
    container['volumeMounts'] = list(container.get('volumeMounts') or []) + [dict(item) for item in MOUNTS]
    result['spec']['volumes'] = list(result['spec'].get('volumes') or []) + copy.deepcopy(list(VOLUMES))
    if manifest_state(result) != 'enabled':
        raise AuditConfigError('transform_incomplete')
    return result, True


def _render(document):
    text = yaml.safe_dump(document, sort_keys=False, default_flow_style=False)
    if yaml.safe_load(text) != document:
        raise AuditConfigError('render_mismatch')
    return text


def manifest_transform(text):
    pod = yaml.safe_load(text)
    state = manifest_state(pod)
    result, changed = enable_manifest(pod)
    rendered = _render(result) if changed else text
    return {
        'state': state,
        'changed': changed,
        'manifest': rendered,
        'sha256_before': hashlib.sha256(text.encode()).hexdigest(),
        'sha256_after': hashlib.sha256(rendered.encode()).hexdigest(),
    }


def cluster_configuration_state(config):
    if (not isinstance(config, dict) or config.get('kind') != 'ClusterConfiguration'
            or config.get('apiVersion') != 'kubeadm.k8s.io/v1beta4'):
        raise AuditConfigError('not_v1beta4_cluster_configuration')
    api = config.get('apiServer') or {}
    arguments = api.get('extraArgs') or []
    volumes = api.get('extraVolumes') or []
    if not isinstance(arguments, list) or not isinstance(volumes, list):
        raise AuditConfigError('unexpected_api_server_shape')
    flags = {}
    for item in arguments:
        name = item.get('name', '')
        if name.startswith('audit-'):
            if name in flags:
                raise AuditConfigError('duplicate_audit_flag')
            flags[name] = item.get('value')
    named = [item for item in volumes if item.get('name') in AUDIT_NAMES]
    if not flags and not named:
        if any(item.get('mountPath') in AUDIT_PATHS or item.get('hostPath') in AUDIT_PATHS
               for item in volumes):
            raise AuditConfigError('audit_path_already_mounted')
        return 'absent'
    by_name = {item['name']: item for item in named}
    if (flags == dict(FLAGS) and len(named) == len(KUBEADM_VOLUMES) and len(by_name) == len(named)
            and all(_mount(by_name[item['name']]) == _mount(item) for item in KUBEADM_VOLUMES)):
        return 'enabled'
    raise AuditConfigError('audit_settings_differ')


def enable_cluster_configuration(text):
    """Return (text, changed) for kubeadm-config's ClusterConfiguration value."""
    config = yaml.safe_load(text)
    if cluster_configuration_state(config) == 'enabled':
        return text, False
    result = copy.deepcopy(config)
    api = result.setdefault('apiServer', {})
    api['extraArgs'] = list(api.get('extraArgs') or []) + [{'name': n, 'value': v} for n, v in FLAGS]
    api['extraVolumes'] = list(api.get('extraVolumes') or []) + [dict(item) for item in KUBEADM_VOLUMES]
    if cluster_configuration_state(result) != 'enabled':
        raise AuditConfigError('transform_incomplete')
    return _render(result), True


def main(argv):
    if argv != ['manifest']:
        print(json.dumps({'error': 'usage: apiserver_audit.py manifest < kube-apiserver.yaml'}))
        return 2
    try:
        result = manifest_transform(sys.stdin.read())
    except (AuditConfigError, yaml.YAMLError) as error:
        print(json.dumps({'error': str(error) if isinstance(error, AuditConfigError) else 'yaml_error'}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
