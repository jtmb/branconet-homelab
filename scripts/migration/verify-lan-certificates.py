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
import socket
import ssl
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


def verify_bortus_https(root_pem, leaves):
    """Read-only transport acceptance independent of held Helm reconciliation."""
    host = 'bortus.branconet.lan'
    ingress = get('ingress', 'bortus-lan-tls', 'bortus')
    meta = ingress['metadata']
    assert meta['labels']['kustomize.toolkit.fluxcd.io/name'] == 'migration-releases'
    assert meta['labels']['kustomize.toolkit.fluxcd.io/namespace'] == 'flux-system'
    assert 'meta.helm.sh/release-name' not in meta.get('annotations', {})
    annotations = meta['annotations']
    assert annotations['traefik.ingress.kubernetes.io/router.entrypoints'] == 'websecure'
    assert annotations['traefik.ingress.kubernetes.io/router.tls'] == 'true'
    assert annotations['traefik.ingress.kubernetes.io/router.priority'] == '1000'
    assert ingress['spec'] == {
        'ingressClassName': 'traefik',
        'tls': [{'hosts': [host], 'secretName': 'branconet-local-ingress-tls'}],
        'rules': [{'host': host, 'http': {'paths': [{
            'path': '/', 'pathType': 'Prefix',
            'backend': {'service': {'name': 'bortus', 'port': {'number': 4000}}}}]}}]}
    assert get('helmrelease', 'bortus', 'flux-system')['spec']['suspend'] is True
    leaf = [row for row in leaves if row['namespace'] == 'bortus'
            and row['name'] == 'branconet-local-ingress-tls']
    assert len(leaf) == 1 and leaf[0]['hosts'] == [host]
    context = ssl.create_default_context(cadata=root_pem.decode('ascii'))
    results = []
    for address in ('192.168.0.4', '192.168.0.5', '192.168.0.6'):
        with socket.create_connection((address, 443), timeout=15) as raw:
            with context.wrap_socket(raw, server_hostname=host) as connection:
                digest = hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest()
                assert digest == leaf[0]['DERFingerprintSHA256']
                connection.sendall(('GET / HTTP/1.1\r\nHost: ' + host +
                                    '\r\nConnection: close\r\n\r\n').encode('ascii'))
                status = b''
                while b'\r\n' not in status and len(status) < 1024:
                    chunk = connection.recv(1)
                    assert chunk, 'No HTTP status line'
                    status += chunk
                protocol, code, _ = status.decode('ascii').strip().split(' ', 2)
                assert protocol == 'HTTP/1.1' and int(code) in (200, 301, 302, 303, 307, 308)
                results.append({'address': address, 'host': host, 'status': int(code),
                                'leafSHA256': digest, 'tlsVerified': True})
    return {'ingressUID': meta['uid'], 'releaseSuspended': True, 'nodes': results}


def verify_bortus_http_redirect():
    """Public non-following HTTP probes; path/query and foundation ownership are exact."""
    host = 'bortus.branconet.lan'
    path = '/auth/login?probe=lan-tls'
    expected_location = 'https://' + host + path
    ingress = get('ingress', 'bortus-lan-http-redirect', 'bortus')
    meta = ingress['metadata']
    assert ingress['kind'] == 'Ingress' and meta['name'] == 'bortus-lan-http-redirect' and meta['namespace'] == 'bortus' and meta['uid']
    assert not meta.get('deletionTimestamp')
    assert meta['labels']['kustomize.toolkit.fluxcd.io/name'] == 'migration-releases'
    assert meta['labels']['kustomize.toolkit.fluxcd.io/namespace'] == 'flux-system'
    assert 'meta.helm.sh/release-name' not in meta.get('annotations', {})
    public = call(['kubectl', '-n', 'traefik', 'get', 'secret', 'traefik-dashboard-config', '-o',
                   'go-template={{.metadata.uid}}|{{index .data "bortus-https-redirect.yaml"}}'])
    secret_uid, encoded = public.split(b'|', 1)
    expected_content = 'http:\n  middlewares:\n    bortus-lan-https-redirect:\n      redirectScheme:\n        scheme: https\n        permanent: true\n'.encode('ascii')
    assert secret_uid and base64.b64decode(encoded, validate=True) == expected_content
    expected_annotations = {
        'traefik.ingress.kubernetes.io/router.entrypoints': 'web',
        'traefik.ingress.kubernetes.io/router.priority': '1000',
        'traefik.ingress.kubernetes.io/router.middlewares': 'bortus-lan-https-redirect@file'}
    assert {k: v for k, v in ingress['metadata']['annotations'].items()
            if k.startswith('traefik.ingress.kubernetes.io/')} == expected_annotations
    assert ingress['spec'] == {
        'ingressClassName': 'traefik',
        'rules': [{'host': host, 'http': {'paths': [{
            'path': '/', 'pathType': 'Prefix',
            'backend': {'service': {'name': 'bortus', 'port': {'number': 4000}}}}]}}]}
    release = get('helmrelease', 'bortus', 'flux-system')
    assert release['spec']['suspend'] is True
    results = []
    for address in ('192.168.0.4', '192.168.0.5', '192.168.0.6'):
        deadline = time.monotonic() + 15
        with socket.create_connection((address, 80), timeout=15) as connection:
            connection.sendall(('GET ' + path + ' HTTP/1.1\r\nHost: ' + host +
                                '\r\nConnection: close\r\n\r\n').encode('ascii'))
            data = b''
            while b'\r\n\r\n' not in data:
                remaining = deadline - time.monotonic()
                assert remaining > 0 and len(data) < 16384, 'Bounded redirect headers unavailable'
                connection.settimeout(remaining)
                block = connection.recv(min(4096, 16384-len(data)))
                assert block, 'HTTP redirect headers incomplete'
                data += block
            header = data.split(b'\r\n\r\n', 1)[0].decode('iso-8859-1').split('\r\n')
            status = header[0].split(' ', 2)
            assert len(status) == 3 and status[0] in ('HTTP/1.0', 'HTTP/1.1') and status[1] in ('301', '308')
            locations = []
            for line in header[1:]:
                assert ':' in line and not line.startswith((' ', '\t')), 'Malformed redirect header'
                key, value = line.split(':', 1)
                if key.lower() == 'location': locations.append(value.strip())
            assert locations == [expected_location], 'Redirect must preserve exact public path and query'
            results.append({'address': address, 'port': 80, 'host': host, 'requestPath': path,
                            'status': int(status[1]), 'location': locations[0], 'redirectFollowed': False})
    assert get('helmrelease', 'bortus', 'flux-system')['spec']['suspend'] is True
    return {'ingressUID': ingress['metadata']['uid'], 'fileProviderSecretUID': secret_uid.decode('ascii'),
            'publicKey': 'bortus-https-redirect.yaml', 'publicContentSHA256': hashlib.sha256(expected_content).hexdigest(),
            'helmReleaseUID': release['metadata']['uid'], 'releaseSuspended': True,
            'credentialsSent': False, 'redirectFollowed': False, 'nodes': results}


def ensure_explicit_leaf_usage(owner, requested):
    """Normal cert-manager renewal for the one reviewed, already-reconciled leaf."""
    ns, name = owner['metadata']['namespace'], owner['metadata']['name']
    cert, pem, meta = public_secret(ns, owner['spec']['secretName'])
    try:
        assert ExtendedKeyUsageOID.SERVER_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        return owner, cert, pem, meta, False
    except x509.ExtensionNotFound:
        assert requested and (ns, name) == ('ingenium', 'ingenium-tls')
        assert owner['spec']['issuerRef']['name'] == 'branconet-local-ca'
        assert owner['spec']['usages'] == ['digital signature', 'key encipherment', 'server auth']
        assert owner['spec']['secretName'] == 'ingenium-tls'
        assert owner['spec']['dnsNames'] == ['ingenium.branconet.lan']
    before_spec = owner['spec']
    if not any(c['type'] == 'Issuing' and c['status'] == 'True' for c in owner['status']['conditions']):
        condition = {'type': 'Issuing', 'status': 'True', 'observedGeneration': owner['metadata']['generation'],
                     'lastTransitionTime': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                     'reason': 'ManuallyTriggered', 'message': 'Certificate re-issuance manually triggered'}
        patch = [{'op': 'test', 'path': '/metadata/uid', 'value': owner['metadata']['uid']},
                 {'op': 'test', 'path': '/metadata/resourceVersion', 'value': owner['metadata']['resourceVersion']},
                 {'op': 'add', 'path': '/status/conditions/-', 'value': condition}]
        result = json.loads(call(['kubectl', '-n', ns, 'patch', 'certificate', name,
                                 '--subresource=status', '--type=json', '--patch-file=/dev/stdin', '-o', 'json'],
                                json.dumps(patch).encode()))
        assert result['spec'] == before_spec
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        current = get('certificate', name, ns)
        assert current['metadata']['uid'] == owner['metadata']['uid'] and current['spec'] == before_spec
        leaf, leaf_pem, leaf_meta = public_secret(ns, current['spec']['secretName'])
        try:
            ready = ExtendedKeyUsageOID.SERVER_AUTH in leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        except x509.ExtensionNotFound:
            ready = False
        if ready and not any(c['type'] == 'Issuing' and c['status'] == 'True' for c in current['status']['conditions']):
            assert leaf_meta['uid'] == meta['uid']
            return current, leaf, leaf_pem, leaf_meta, True
        time.sleep(3)
    raise ValueError('Normal leaf renewal still pending; do not change trust or repeat mutation')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--apply-root-renewal', action='store_true')
    p.add_argument('--install-windows-trust', action='store_true')
    p.add_argument('--expected-root-sha256')
    p.add_argument('--verify-bortus-https', action='store_true')
    p.add_argument('--verify-bortus-http-redirect', action='store_true')
    p.add_argument('--renew-missing-leaf-usage', action='store_true')
    a = p.parse_args()
    if a.verify_bortus_http_redirect and not a.verify_bortus_https:
        p.error('--verify-bortus-http-redirect requires --verify-bortus-https')
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
    renewed = []
    for d in leaves:
        assert any(c['type'] == 'Ready' and c['status'] == 'True' and
                   c.get('observedGeneration') == d['metadata']['generation'] for c in d['status']['conditions'])
        d, cert, _, metadata, did_renew = ensure_explicit_leaf_usage(d, a.renew_missing_leaf_usage)
        # Renewal can issue after this invocation's initial timestamp.
        # Compare certificate validity with the actual observation time.
        now = datetime.datetime.now(datetime.timezone.utc)
        if did_renew:
            renewed.append({'namespace': d['metadata']['namespace'], 'name': d['metadata']['name']})
            changed = True
        assert cert.issuer == root.subject
        key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
        assert set(names) == set(d['spec']['dnsNames']) and all(n.endswith(('.branconet.lan', '.branconet.local')) for n in names)
        assert not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        assert ExtendedKeyUsageOID.SERVER_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        assert cert.not_valid_before_utc <= now < cert.not_valid_after_utc <= root.not_valid_after_utc
        rows.append({**metadata, 'hosts': names, 'DERFingerprintSHA256': cert.fingerprint(hashes.SHA256()).hex()})
    bortus = verify_bortus_https(pem, rows) if a.verify_bortus_https else None
    redirect = verify_bortus_http_redirect() if a.verify_bortus_http_redirect else None
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
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'windowsTrust': trust,
              'bortusHTTPS': bortus, 'bortusHTTPRedirect': redirect, 'renewedLeaves': renewed}
    receipt = a.output_dir / ('certificate-verification-' + uuid.uuid4().hex + '.json')
    receipt.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'changed': changed, 'receipt': str(receipt)}))


if __name__ == '__main__':
    main()
