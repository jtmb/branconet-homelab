#!/usr/bin/env python3
"""Run one phase of the kubelet serving-certificate trust rollout.

Phases (run in order): kubelet, apiserver, kubeadm-config.
- kubelet / apiserver: the serial Ansible play in playbooks/kubelet-serving-tls.yml,
  with the saved node credential supplied in memory (never logged).
- kubeadm-config: persist both settings in kube-system/kubelet-config and
  kube-system/kubeadm-config so a later `kubeadm upgrade` keeps them. Uses a
  resourceVersion-guarded replace and changes nothing else in either document.
"""
import argparse
import base64
import importlib.util
import json
import os
import pathlib
import subprocess
import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ANSIBLE = REPO / 'k8s-rewrite/ansible-playbook'
RUNTIME = pathlib.Path('/home/brajam/.local/share/branconet-migration')
KUBECTL = [str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'), '--request-timeout=30s']
FLAG = {'name': 'kubelet-certificate-authority', 'value': '/etc/kubernetes/pki/ca.crt'}


def kubectl(*args, data=None):
    return subprocess.run([*KUBECTL, *args], input=data, capture_output=True, check=True, timeout=40).stdout


def persist_kubeadm_config():
    results = {}
    cm = json.loads(kubectl('-n', 'kube-system', 'get', 'cm', 'kubelet-config', '-o', 'json'))
    kubelet = yaml.safe_load(cm['data']['kubelet'])
    if kubelet.get('serverTLSBootstrap') is not True:
        lines = cm['data']['kubelet'].splitlines(keepends=True)
        index = next(i for i, l in enumerate(lines) if l.startswith('rotateCertificates:'))
        lines.insert(index + 1, 'serverTLSBootstrap: true\n')
        cm['data']['kubelet'] = ''.join(lines)
        assert yaml.safe_load(cm['data']['kubelet']) == dict(kubelet, serverTLSBootstrap=True)
        kubectl('replace', '-f', '-', data=json.dumps(cm).encode())
        results['kubelet-config'] = 'updated'
    else:
        results['kubelet-config'] = 'already-set'
    cm = json.loads(kubectl('-n', 'kube-system', 'get', 'cm', 'kubeadm-config', '-o', 'json'))
    cluster = yaml.safe_load(cm['data']['ClusterConfiguration'])
    extra = cluster['apiServer'].setdefault('extraArgs', [])
    if FLAG not in extra:
        if any(a['name'] == FLAG['name'] for a in extra):
            raise SystemExit('kubeadm-config already has a different kubelet CA flag; review manually')
        original = cm['data']['ClusterConfiguration']
        lines = original.splitlines(keepends=True)
        start = lines.index('apiServer:\n')
        end = next((i for i in range(start + 1, len(lines)) if lines[i][:1] not in (' ', '\n')), len(lines))
        index = next(i for i in range(start + 1, end) if lines[i] == '  extraArgs:\n')
        lines[index + 1:index + 1] = [f"  - name: {FLAG['name']}\n", f"    value: {FLAG['value']}\n"]
        cm['data']['ClusterConfiguration'] = ''.join(lines)
        expected = yaml.safe_load(original)
        expected['apiServer']['extraArgs'] = [FLAG] + expected['apiServer']['extraArgs']
        assert yaml.safe_load(cm['data']['ClusterConfiguration']) == expected
        kubectl('replace', '-f', '-', data=json.dumps(cm).encode())
        results['kubeadm-config'] = 'updated'
    else:
        results['kubeadm-config'] = 'already-set'
    print(json.dumps(results))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['kubelet', 'apiserver', 'kubeadm-config'])
    parser.add_argument('--work-dir', type=pathlib.Path, required=True)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    if args.phase == 'kubeadm-config':
        return persist_kubeadm_config()
    config = yaml.safe_load((RUNTIME / 'admin.conf').read_text())
    ca = args.work_dir / 'cluster-ca.crt'
    ca.write_bytes(base64.b64decode(config['clusters'][0]['cluster']['certificate-authority-data']))
    env = dict(os.environ, ANSIBLE_CONFIG=str(ANSIBLE / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    command = [str(RUNTIME / 'venv/bin/ansible-playbook'), 'playbooks/kubelet-serving-tls.yml', '--extra-vars',
               json.dumps({'kubelet_serving_phase': args.phase, 'cluster_ca_file': str(ca)})]
    if args.syntax_check:
        return subprocess.run(command + ['--syntax-check'], cwd=ANSIBLE, env=env).returncode
    spec = importlib.util.spec_from_file_location('saved_node_credential', REPO / 'scripts/migration/saved-node-credential.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = module.existing_password()
    try:
        return subprocess.run(command, cwd=ANSIBLE, env=env, stdin=subprocess.DEVNULL).returncode
    finally:
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)


if __name__ == '__main__':
    raise SystemExit(main())
