#!/usr/bin/env python3
"""Verify native LAN certificates; optionally request normal renewal/client trust."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i',
       '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
DOMAINS = {'branconet.lan', 'branconet.local'}


def call(args, body=None):
    p = subprocess.run(SSH + [shlex.join(args)], input=body, capture_output=True, timeout=45)
    if p.returncode or len(p.stdout) > 1024**2:
        raise ValueError('Public certificate operation refused')
    return p.stdout


def get(kind, name=None, ns='cert-manager'):
    return json.loads(call(['kubectl', '-n', ns, 'get', kind, *([name] if name else []), '-o', 'json']))


def public_secret(ns, name):
    raw = call(['kubectl', '-n', ns, 'get', 'secret', name, '-o',
                'go-template={{.metadata.uid}}|{{.metadata.resourceVersion}}|{{index .data "tls.crt"}}'])
    uid, rv, encoded = raw.split(b'|', 2)
    pem = base64.b64decode(encoded, validate=True)
    assert len(pem) <= 32768
    return x509.load_pem_x509_certificate(pem), pem, {'namespace': ns, 'name': name,
            'uid': uid.decode(), 'resourceVersion': rv.decode(),
            'publicPEMSHA256': hashlib.sha256(pem).hexdigest(), 'privateKeyRead': False}


def constrained(cert):
    try:
        extension = cert.extensions.get_extension_for_class(x509.NameConstraints)
    except x509.ExtensionNotFound:
        return False
    value = extension.value
    return (extension.critical and
            {v.value for v in value.permitted_subtrees if isinstance(v, x509.DNSName)} == DOMAINS and
            {str(v.value) for v in value.excluded_subtrees if isinstance(v, x509.IPAddress)} == {'0.0.0.0/0', '::/0'})


def windows_path(path):
    return r'\\wsl.localhost\Ubuntu' + str(path).replace('/', '\\')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--apply-root-renewal', action='store_true')
    p.add_argument('--install-windows-trust', action='store_true')
    p.add_argument('--expected-root-sha256')
    a = p.parse_args()
    os.umask(0o077)
    assert ROOT.is_mount() and a.output_dir.resolve() == a.output_dir and ROOT in a.output_dir.parents
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert not a.output_dir.stat().st_mode & 0o077
    node = get('node', 'masternode')
    assert node['metadata']['uid'] == 'f2df6169-4592-4544-b62c-74d89f598648'
    changed = False
    initial_key = None
    start = time.monotonic()
    while True:
        assert time.monotonic() - start < 240
        owner = get('certificate', 'branconet-local-root')
        assert (owner['spec']['isCA'] and owner['spec']['secretName'] == 'branconet-local-root-ca'
                and owner['spec']['privateKey']['rotationPolicy'] == 'Never'
                and owner['spec']['nameConstraints']['critical']
                and set(owner['spec']['nameConstraints']['permitted']['dnsDomains']) == DOMAINS)
        root, pem, root_meta = public_secret('cert-manager', 'branconet-local-root-ca')
        key = root.public_key()
        assert isinstance(key, rsa.RSAPublicKey) and key.key_size == 4096
        if initial_key is None:
            initial_key = key.public_numbers()
        assert key.public_numbers() == initial_key
        issuing = any(c['type'] == 'Issuing' and c['status'] == 'True' for c in owner['status']['conditions'])
        if constrained(root) and not issuing:
            break
        if not issuing:
            assert a.apply_root_renewal and not changed
            # The same status operation as cmctl renew, preserving spec and key.
            condition = {'type': 'Issuing', 'status': 'True', 'observedGeneration': owner['metadata']['generation'],
                         'lastTransitionTime': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         'reason': 'ManuallyTriggered', 'message': 'Certificate re-issuance manually triggered'}
            patch = [{'op': 'test', 'path': '/metadata/uid', 'value': owner['metadata']['uid']},
                     {'op': 'test', 'path': '/metadata/resourceVersion', 'value': owner['metadata']['resourceVersion']},
                     {'op': 'add', 'path': '/status/conditions/-', 'value': condition}]
            result = json.loads(call(['kubectl', '-n', 'cert-manager', 'patch', 'certificate', 'branconet-local-root',
                                    '--subresource=status', '--type=json', '--patch-file=/dev/stdin', '-o', 'json'],
                                   json.dumps(patch).encode()))
            assert result['spec'] == owner['spec']
            changed = True
        time.sleep(5)
    assert root.subject == root.issuer and root.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    key.verify(root.signature, root.tbs_certificate_bytes, padding.PKCS1v15(), root.signature_hash_algorithm)
    now = datetime.datetime.now(datetime.timezone.utc)
    assert root.not_valid_before_utc <= now < root.not_valid_after_utc
    fingerprint = root.fingerprint(hashes.SHA256()).hex()
    if a.expected_root_sha256:
        assert fingerprint == a.expected_root_sha256.lower()
    root_file = a.output_dir / 'branconet-local-root.crt'
    root_file.write_bytes(pem)
    items = json.loads(call(['kubectl', 'get', 'certificates', '-A', '-o', 'json']))['items']
    leaves = [d for d in items if d['spec']['issuerRef'].get('kind') == 'ClusterIssuer'
              and d['spec']['issuerRef']['name'] == 'branconet-local-ca']
    assert 0 < len(leaves) <= 100
    rows = []
    for d in leaves:
        assert any(c['type'] == 'Ready' and c['status'] == 'True' and
                   c.get('observedGeneration') == d['metadata']['generation'] for c in d['status']['conditions'])
        cert, _, metadata = public_secret(d['metadata']['namespace'], d['spec']['secretName'])
        assert cert.issuer == root.subject
        key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
        assert set(names) == set(d['spec']['dnsNames']) and all(n.endswith(('.branconet.lan', '.branconet.local')) for n in names)
        assert not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        assert ExtendedKeyUsageOID.SERVER_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        assert cert.not_valid_before_utc <= now < cert.not_valid_after_utc <= root.not_valid_after_utc
        rows.append({**metadata, 'hosts': names, 'DERFingerprintSHA256': cert.fingerprint(hashes.SHA256()).hex()})
    trust = None
    if a.install_windows_trust:
        assert a.expected_root_sha256
        script = Path(__file__).resolve().parents[2] / 'k8s-rewrite/ansible-playbook/roles/lan_tls/files/install_windows_root.py'
        receipt = a.output_dir / ('windows-root-trust-' + uuid.uuid4().hex + '.json')
        result = subprocess.run(['/mnt/c/Users/james/AppData/Local/Programs/Python/Python312/python.exe',
                                 '-I', '-B', windows_path(script), '--certificate', windows_path(root_file),
                                 '--expected-sha256', fingerprint, '--receipt', windows_path(receipt),
                                 '--apply'], capture_output=True, timeout=60)
        assert result.returncode == 0 and receipt.is_file()
        trust = json.loads(receipt.read_text(encoding='utf-8-sig'))
        assert trust['passed'] and trust['trusted'] and trust['rootSHA256'].lower() == fingerprint
        changed |= trust['changed']
    report = {'passed': True, 'changed': changed, 'UTC': now.isoformat(), 'root': root_meta,
              'rootDERFingerprintSHA256': fingerprint, 'leaves': rows, 'privateKeyRead': False,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'windowsTrust': trust}
    receipt = a.output_dir / ('certificate-verification-' + uuid.uuid4().hex + '.json')
    receipt.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'changed': changed, 'receipt': str(receipt)}))


if __name__ == '__main__':
    main()
