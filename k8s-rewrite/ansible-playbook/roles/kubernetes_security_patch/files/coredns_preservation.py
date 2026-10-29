"""Preserve independently managed CoreDNS while kubeadm's addon phase is skipped."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

BASE = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/autonomous-hardening-20261028')
RECEIPT = BASE / 'kubernetes1372-coredns-preflight-preservation.json'
SHA = '76ff2b1444af600c5f49b34f8c6a80b51e3c840d14661fd9811c03bc3daa0a74'
IMAGE = 'docker.io/coredns/coredns:1.15.0@sha256:0a9d8c8ddf34347eb59aad9a8784f0710de88d6d112726d11d271f9bc6daca26'


def project(obj):
    # Preserve every declarative field, including admission defaults and metadata
    # labels/annotations. Only API bookkeeping and observed status may vary.
    value = {k: v for k, v in obj.items() if k not in ('metadata', 'status')}
    value['metadata'] = {k: v for k, v in obj['metadata'].items()
                         if k not in ('resourceVersion', 'generation', 'managedFields', 'creationTimestamp')}
    return value


def main():
    assert RECEIPT.resolve() == RECEIPT and RECEIPT.is_file()
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest() == SHA
    baseline = json.loads(RECEIPT.read_text())
    assert baseline['failedRunID'] == 'b6816a54662f4fc2839969b1eeb4e787'
    assert baseline['hostAndStaticBytesExactlyPreserved'] is True
    original = baseline['coredns']
    assert {c['image'] for c in original['deployment']['spec']['template']['spec']['containers']} == {IMAGE}
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
    checked = []
    for kind in ('deployment', 'configmap', 'service', 'serviceaccount', 'poddisruptionbudget'):
        result = subprocess.run(ssh + [shlex.join(['kubectl', '-n', 'kube-system', 'get', kind,
                                 'coredns', '--ignore-not-found', '-o', 'json'])],
                                capture_output=True, timeout=45)
        assert result.returncode == 0 and len(result.stdout) < 1024**2
        current = json.loads(result.stdout) if result.stdout.strip() else None
        if kind not in original:
            assert current is None, 'Previously absent DNS resource appeared'
            continue
        assert current is not None and project(current) == project(original[kind]), 'CoreDNS declaration changed'
        if kind == 'deployment':
            assert current['status'].get('readyReplicas', 0) == current['spec'].get('replicas', 1)
        checked.append(kind)
    service_receipt = BASE / 'kubernetes1372-dns-service-preservation.json'
    assert service_receipt.resolve() == service_receipt
    assert hashlib.sha256(service_receipt.read_bytes()).hexdigest() == '57a93668055d15c2bc5f0c2eebba5d195916b7803deb9aade13442eaec33c159'
    result = subprocess.run(ssh + ['kubectl -n kube-system get service kube-dns -o json'],
                            capture_output=True, timeout=45)
    assert result.returncode == 0 and len(result.stdout) < 1024**2
    assert project(json.loads(result.stdout)) == project(json.loads(service_receipt.read_text()))
    checked.append('service/kube-dns')
    print(json.dumps({'passed': True, 'baselineSHA256': SHA, 'originalDNSDeclarationsPreserved': checked,
                      'addonPhaseSkipped': True, 'dnsMigrationPerformed': False}))


if __name__ == '__main__':
    main()
