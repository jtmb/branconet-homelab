#!/usr/bin/env python3
"""Enable kube-apiserver audit logging, one control-plane node per run.

Phases, in order:
  node02, node03, node01  one API server each through
                          playbooks/apiserver-audit-logging.yml. node01 holds
                          the API VIP (highest keepalived priority, preempting),
                          so it goes last: the VIP fails over to an already
                          verified standby and returns when node01 is ready.
                          Each phase refuses until every earlier node already
                          runs the audit flags.
  kubeadm-config          persist the same flags and mounts in
                          kube-system/kubeadm-config so `kubeadm upgrade` keeps
                          them; refused until all three API servers run them.
  status                  read-only report of all of the above.
  preview                 read-only: read each live manifest (sudo) and run the
                          transform in memory, reporting exactly what would change.

The saved node credential is read in memory and passed only through the
ansible-playbook process environment. Receipts (no credential, no event
bodies) go to --work-dir. Runbook: docs/API-AUDIT-LOGGING.md.
"""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ANSIBLE = REPO / 'k8s-rewrite/ansible-playbook'
PLAYBOOK = ANSIBLE / 'playbooks/apiserver-audit-logging.yml'
POLICY = ANSIBLE / 'playbooks/files/kube-apiserver-audit-policy.yaml'
RUNTIME = pathlib.Path('/home/brajam/.local/share/branconet-migration')
KUBECTL = [str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'), '--request-timeout=30s']
ORDER = ('node02', 'node03', 'node01')
HOSTS = {'node01': 'masternode', 'node02': 'workernode1', 'node03': 'workernode2'}


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, REPO / 'scripts/migration' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load('apiserver_audit', 'apiserver_audit.py')


def kubectl(*args, data=None):
    return subprocess.run([*KUBECTL, *args], input=data, capture_output=True, check=True, timeout=40).stdout


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def node_state(node):
    pod = json.loads(kubectl('-n', 'kube-system', 'get', 'pod', 'kube-apiserver-' + node, '-o', 'json'))
    command = pod['spec']['containers'][0]['command']
    flags = AUDIT._audit_flags(command[1:])
    if not flags:
        state = 'absent'
    elif flags == dict(AUDIT.FLAGS):
        state = 'enabled'
    else:
        state = 'differs'
    ready = any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod['status'].get('conditions', []))
    restarts = sum(s.get('restartCount', 0) for s in pod['status'].get('containerStatuses', []))
    return {'audit': state, 'ready': ready, 'restarts': restarts,
            'config_hash': pod['metadata']['annotations'].get('kubernetes.io/config.hash')}


def kubeadm_state():
    cm = json.loads(kubectl('-n', 'kube-system', 'get', 'cm', 'kubeadm-config', '-o', 'json'))
    try:
        return AUDIT.cluster_configuration_state(yaml.safe_load(cm['data']['ClusterConfiguration'])), cm
    except AUDIT.AuditConfigError as error:
        return 'refused:' + str(error), cm


def status():
    report = {node: node_state(node) for node in ORDER}
    report['kubeadm-config'] = kubeadm_state()[0]
    return report


def preview():
    """Read each live manifest (sudo, read-only) and run the transform in memory."""
    credential = _load('saved_node_credential', 'saved-node-credential.py')
    env = dict(os.environ, ANSIBLE_CONFIG=str(ANSIBLE / 'ansible.cfg'), ANSIBLE_NOCOLOR='1',
               BRANCONET_MIGRATION_SUDO_PASSWORD=credential.existing_password())
    try:
        result = subprocess.run(
            [str(RUNTIME / 'venv/bin/ansible'), 'k8s_nodes', '--one-line', '-m', 'ansible.builtin.slurp',
             '-a', 'src=/etc/kubernetes/manifests/kube-apiserver.yaml', '--become',
             '-e', "ansible_become_password={{ lookup('ansible.builtin.env', 'BRANCONET_MIGRATION_SUDO_PASSWORD') }}"],
            cwd=ANSIBLE, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    finally:
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    hosts = {}
    for line in result.stdout.splitlines():
        alias, separator, payload = line.partition(' => ')
        if separator and alias.split(' | ')[0] in HOSTS.values():
            hosts[alias.split(' | ')[0]] = json.loads(payload)
    if set(hosts) != set(HOSTS.values()):
        raise SystemExit(f'preview read {sorted(hosts)}; ansible rc={result.returncode}')
    names = {alias: node for node, alias in HOSTS.items()}
    report = {}
    for alias, outcome in sorted(hosts.items()):
        if outcome.get('failed') or 'content' not in outcome:
            report[names[alias]] = {'error': outcome.get('msg', 'read_failed')}
            continue
        text = base64.b64decode(outcome['content']).decode()
        try:
            transformed = AUDIT.manifest_transform(text)
        except AUDIT.AuditConfigError as error:
            report[names[alias]] = {'error': str(error)}
            continue
        before, after = yaml.safe_load(text), yaml.safe_load(transformed['manifest'])
        old, new = before['spec']['containers'][0], after['spec']['containers'][0]
        report[names[alias]] = {
            'state': transformed['state'], 'changed': transformed['changed'],
            'image_unchanged': old['image'] == new['image'], 'image': new['image'],
            'added_flags': new['command'][len(old['command']):],
            'existing_flags_unchanged': new['command'][:len(old['command'])] == old['command'],
            'added_mounts': [m['name'] for m in new['volumeMounts'][len(old.get('volumeMounts', [])):]],
            'added_volumes': [v['name'] for v in after['spec']['volumes'][len(before['spec'].get('volumes', [])):]],
            'sha256_before': transformed['sha256_before']}
    return report


def persist_kubeadm_config():
    states = {node: node_state(node) for node in ORDER}
    if any(s['audit'] != 'enabled' or not s['ready'] for s in states.values()):
        raise SystemExit('kubeadm-config is persisted only after all three API servers run audit logging: '
                         + json.dumps(states))
    state, cm = kubeadm_state()
    if state == 'enabled':
        return {'kubeadm-config': 'already-set'}
    if state != 'absent':
        raise SystemExit('kubeadm-config audit settings need manual review: ' + state)
    text, changed = AUDIT.enable_cluster_configuration(cm['data']['ClusterConfiguration'])
    assert changed
    cm['data']['ClusterConfiguration'] = text
    # The object carries metadata.resourceVersion, so a concurrent change fails
    # with a conflict instead of being overwritten.
    kubectl('replace', '-f', '-', data=json.dumps(cm).encode())
    after, _ = kubeadm_state()
    if after != 'enabled':
        raise SystemExit('kubeadm-config did not verify after replace: ' + after)
    return {'kubeadm-config': 'updated', 'resourceVersion_before': cm['metadata']['resourceVersion']}


def run_node(node, work_dir, syntax_check):
    attempt = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    extra = {'audit_logging_apply': True, 'audit_target_host': HOSTS[node],
             'audit_target_node': node, 'audit_attempt': attempt}
    env = dict(os.environ, ANSIBLE_CONFIG=str(ANSIBLE / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    command = [str(RUNTIME / 'venv/bin/ansible-playbook'), str(PLAYBOOK.relative_to(ANSIBLE)),
               '--limit', HOSTS[node], '--extra-vars', json.dumps(extra)]
    if syntax_check:
        return subprocess.run(command + ['--syntax-check'], cwd=ANSIBLE, env=env).returncode
    earlier = ORDER[:ORDER.index(node)]
    before = {n: node_state(n) for n in ORDER}
    pending = [n for n in earlier if before[n]['audit'] != 'enabled']
    if pending:
        raise SystemExit(f'{node} waits for {pending}; order is {list(ORDER)}')
    work_dir.mkdir(parents=True, exist_ok=True)
    receipt = work_dir / f'apiserver-audit-{node}-{attempt}.json'
    log = work_dir / f'apiserver-audit-{node}-{attempt}.log'
    record = {'node': node, 'attempt': attempt, 'started': attempt, 'before': before,
              'playbook_sha256': sha256(PLAYBOOK), 'policy_sha256': sha256(POLICY),
              'transform_sha256': sha256(REPO / 'scripts/migration/apiserver_audit.py'),
              'log_check_sha256': sha256(REPO / 'scripts/migration/apiserver_audit_log_check.py'),
              'backup_path': f'/etc/kubernetes/kube-apiserver.yaml.pre-audit-log.{attempt}',
              'credential_persisted': False}
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    credential = _load('saved_node_credential', 'saved-node-credential.py')
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = credential.existing_password()
    try:
        with log.open('w') as output:
            process = subprocess.Popen(command, cwd=ANSIBLE, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                sys.stdout.write(line)
                output.write(line)
            returncode = process.wait()
    finally:
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    record.update(returncode=returncode,
                  finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                  after={n: node_state(n) for n in ORDER})
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'receipt': str(receipt), 'returncode': returncode, 'after': record['after'][node]}))
    return returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('phase', choices=[*ORDER, 'kubeadm-config', 'status', 'preview'])
    parser.add_argument('--work-dir', type=pathlib.Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    if args.phase == 'status':
        print(json.dumps(status(), indent=2))
        return 0
    if args.phase == 'preview':
        print(json.dumps(preview(), indent=2))
        return 0
    if args.phase == 'kubeadm-config':
        print(json.dumps(persist_kubeadm_config()))
        return 0
    if not args.syntax_check and args.work_dir is None:
        parser.error('--work-dir is required for a node phase')
    return run_node(args.phase, args.work_dir, args.syntax_check)


if __name__ == '__main__':
    raise SystemExit(main())
