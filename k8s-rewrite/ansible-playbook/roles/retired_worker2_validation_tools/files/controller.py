"""Use existing TTY-only privilege input; retain only small audit receipts."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'platform-upstream-review-20261027/longhorn-application-batch-20261028/worker2-validation-tools'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remove-empty-directory', action='store_true')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('privilege', here.parent.parent / 'legacy_plex_preservation/files/controller.py')
    privilege = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(privilege)
    spec = importlib.util.spec_from_file_location('retire', here / 'retire.py')
    retire = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retire)
    fs = json.loads(subprocess.check_output(['findmnt', '--json', '--target', str(ROOT), '--output', 'UUID'], text=True))['filesystems'][0]
    privilege.need(fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b', 'existing_F_backed_root')
    original = Path('/mnt/c/Users/james/.codex/local-ci/branconet-charts-local-ci/.tools')
    originals = {}
    for name, expected in retire.HASHES.items():
        p = original / name
        privilege.need(p.is_file() and retire.sha(p) == expected, 'protected_original_hash:' + name)
        originals[str(p)] = expected
    reference = ROOT / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
    raw = reference.read_bytes()
    privilege.need(hashlib.sha256(raw).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'guard_reference_hash')
    os.umask(0o077)
    OUT.mkdir(exist_ok=True)
    ownership = OUT / 'ownership.json'
    if not ownership.exists():
        ownership.write_text(json.dumps({'owner': 'retired_worker2_validation_tools', 'root': str(OUT), 'physicalFilesystemUUID': fs['uuid'], 'generatedPaths': ['ownership.json', 'inventory.json', 'apply.json'], 'regeneration': 'Copy only the three individually hash-verified protected original binaries if validation is needed again; no build or download required.', 'protectedOriginals': originals, 'protected': 'All siblings, source, locks, validation receipts, vendor files, runtime commands and reference guard; no tree removal.'}, indent=2) + '\n')
    privilege.need(not (args.apply and args.remove_empty_directory), 'exclusive_mode')
    target = OUT / ('empty-directory.json' if args.remove_empty_directory else 'apply.json' if args.apply else 'inventory.json')
    privilege.need(not target.exists(), 'never_overwrite_evidence')
    if args.apply:
        inventory = json.loads((OUT / 'inventory.json').read_text())
        privilege.need(not inventory['retained'] and len(inventory['qualified']) == 3, 'all_targets_previously_qualified_no_refusal_retry')
    if args.remove_empty_directory:
        previous = json.loads((OUT / 'apply.json').read_text())
        privilege.need(not previous['retained'] and len(previous['removed']) == 3, 'successful_prior_binary_retirement')
        invocation = 'remove_empty(' + repr(raw.decode()) + ')'
    else:
        invocation = 'run(' + repr(raw.decode()) + ', apply=' + repr(args.apply) + ')'
    source = (here / 'retire.py').read_text() + '\nprint(json.dumps(' + invocation + '))\n'
    encoded = base64.b64encode(source.encode()).decode()
    remote = 'import base64;exec(compile(base64.b64decode(' + repr(encoded) + '),"<worker2-retirement>","exec"))'
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.5', shlex.join(['sudo', '-S', '-p', '', '--', '/usr/bin/python3', '-B', '-c', remote])]
    password = privilege.privilege_input()
    try:
        child = subprocess.run(cmd, input=password + b'\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    finally:
        password = None
    privilege.need(child.returncode == 0, 'remote_failed:' + child.stderr.decode())
    result = json.loads(child.stdout)
    result['protectedOriginals'] = originals
    for name, expected in retire.HASHES.items():
        privilege.need(retire.sha(original / name) == expected, 'original_changed')
    with target.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
