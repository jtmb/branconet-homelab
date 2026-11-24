#!/usr/bin/env python3
"""Run the read-only control-plane certificate expiry check with the saved node credential.

The become password is read in memory from the existing native Secret (see
saved-node-credential.py), passed only through the child environment and never
logged. The playbook changes nothing on the nodes.
"""
import argparse
import importlib.util
import os
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
ANSIBLE = REPO / 'k8s-rewrite/ansible-playbook'
RUNTIME = pathlib.Path('/home/brajam/.local/share/branconet-migration')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--syntax-check', action='store_true')
    parser.add_argument('--min-days', type=int, default=90)
    args = parser.parse_args()
    env = dict(os.environ, ANSIBLE_CONFIG=str(ANSIBLE / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    command = [str(RUNTIME / 'venv/bin/ansible-playbook'), 'playbooks/control-plane-cert-expiry.yml',
               '--extra-vars', f'{{"cert_expiry_min_days": {int(args.min_days)}}}']
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
