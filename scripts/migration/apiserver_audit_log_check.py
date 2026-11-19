#!/usr/bin/env python3
"""Read-only check of a kube-apiserver audit log on a control-plane host.

Run by playbooks/apiserver-audit-logging.yml (as root, standard library only)
after a node's API server restarts with audit logging:

    apiserver_audit_log_check.py <audit.log> <probe-configmap-name>

Reports, without printing any event body:
- how many events the current file holds, by audit level,
- how many credential-bearing events (Secrets, ConfigMaps, token requests,
  token reviews) it holds and how many of those carry a request/response body
  (must be zero: the policy keeps them at Metadata),
- how many RBAC changes carry their request body (the one body-level rule),
- the completed event for the probe read of a nonexistent ConfigMap.
"""
import json
import sys

CREDENTIAL_RESOURCES = frozenset(('secrets', 'configmaps', 'tokenreviews'))
RBAC_GROUP = 'rbac.authorization.k8s.io'


def is_credential_event(event):
    reference = event.get('objectRef') or {}
    resource = reference.get('resource')
    return resource in CREDENTIAL_RESOURCES or (
        resource == 'serviceaccounts' and reference.get('subresource') == 'token')


def summarize(lines, probe):
    summary = {'events': 0, 'unparsed_lines': 0, 'levels': {}, 'credential_events': 0,
               'credential_bodies': 0, 'rbac_changes_with_body': 0, 'probe': None}
    for raw in lines:
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except ValueError:
            summary['unparsed_lines'] += 1
            continue
        if not isinstance(event, dict) or event.get('kind') != 'Event':
            summary['unparsed_lines'] += 1
            continue
        summary['events'] += 1
        level = str(event.get('level'))
        summary['levels'][level] = summary['levels'].get(level, 0) + 1
        if is_credential_event(event):
            summary['credential_events'] += 1
            if 'requestObject' in event or 'responseObject' in event:
                summary['credential_bodies'] += 1
        reference = event.get('objectRef') or {}
        if reference.get('apiGroup') == RBAC_GROUP and 'requestObject' in event:
            summary['rbac_changes_with_body'] += 1
        if (reference.get('resource') == 'configmaps' and reference.get('name') == probe
                and event.get('stage') == 'ResponseComplete'):
            summary['probe'] = {
                'level': event.get('level'),
                'verb': event.get('verb'),
                'code': (event.get('responseStatus') or {}).get('code'),
                'has_body': 'requestObject' in event or 'responseObject' in event,
            }
    return summary


def main(argv):
    if len(argv) != 2:
        print(json.dumps({'error': 'usage: apiserver_audit_log_check.py <audit.log> <probe-name>'}))
        return 2
    path, probe = argv
    try:
        with open(path, 'rb') as handle:
            summary = summarize(handle, probe)
    except FileNotFoundError:
        print(json.dumps({'error': 'audit_log_missing'}))
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
