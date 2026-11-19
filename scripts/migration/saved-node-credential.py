"""Read the existing Ansible credential without logging or persisting its value."""
import argparse
import base64
import json
from pathlib import Path
import subprocess

RUNTIME = Path('/home/brajam/.local/share/branconet-migration')
NATIVE_NODES = ('192.168.0.4', '192.168.0.5', '192.168.0.6')


def native_value(name, key):
    result = subprocess.run([str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'),
        '--request-timeout=20s', 'get', 'secret', name, '-n', 'bortus-secrets', '-o', 'json'],
        capture_output=True, timeout=25)
    if result.returncode or len(result.stdout) > 65536:
        raise RuntimeError('saved_native_credential_unavailable')
    obj = json.loads(result.stdout)
    if obj['metadata']['name'] != name or obj['metadata']['namespace'] != 'bortus-secrets':
        raise RuntimeError('saved_native_credential_identity_changed')
    return base64.b64decode(obj['data'][key], validate=True).decode()


def existing_password():
    # Original vaulted administrator fields, already migrated into native Secrets.
    username = native_value('vault-admin-user-4a647de7', 'admin_usr')
    if username != 'james':
        raise RuntimeError('saved_node_credential_account_mismatch')
    password = native_value('vault-admin-pass-fc618395', 'admin_pwd')
    if not password or len(password.encode()) > 4096 or any(c in password for c in '\0\r\n'):
        raise RuntimeError('credential_lookup_value_invalid')
    return password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-sudo', action='store_true', required=True)
    parser.parse_args()
    password = existing_password()
    try:
        verified = []
        for host in NATIVE_NODES:
            result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002',
                'james@' + host, "sudo -S -k -p '' true"],
                input=(password + '\n').encode(), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=25)
            if result.returncode:
                raise RuntimeError('existing_node_credential_authentication_failed')
            verified.append(host)
        print(json.dumps({'existing_source': 'native vaulted admin_usr/admin_pwd',
                          'sudo_verified_nodes': verified, 'credential_persisted': False}))
    finally:
        password = None


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(json.dumps({'credential_source_check': str(error)}))
        raise SystemExit(1)
