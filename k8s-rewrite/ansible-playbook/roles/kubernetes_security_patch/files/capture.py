"""Assemble/validate operator authority from existing evidence; stdout only."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patch_authority', HERE / 'authority.py')
authority = importlib.util.module_from_spec(spec); spec.loader.exec_module(authority)


def ref(path):
    p = Path(path)
    authority.need(p.resolve() == p and authority.ROOT in p.parents and p.is_file(), 'Existing evidence must be inside task root')
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--checkpoint-sha256', required=True)
    p.add_argument('--binary-evidence', required=True, help='Existing object with binaries map matching documented schema')
    p.add_argument('--binary-evidence-sha256', required=True)
    p.add_argument('--image-staging', required=True, help='Existing object images:{component:{node:{path,sha256}}}')
    p.add_argument('--image-staging-sha256', required=True)
    a = p.parse_args()
    checkpoint_ref = {'path': a.checkpoint, 'sha256': a.checkpoint_sha256}
    checkpoint = authority.load_bound(checkpoint_ref)
    binaries = authority.load_bound({'path': a.binary_evidence, 'sha256': a.binary_evidence_sha256})
    stages = authority.load_bound({'path': a.image_staging, 'sha256': a.image_staging_sha256})
    h = authority.ROOT / 'platform-upstream-review-20261027/autonomous-hardening-20261028'
    summary_ref = ref(h / 'kubernetes1372-full-scan/qualification-summary.json')
    summary = authority.load_bound(summary_ref)
    source = HERE.parents[1] / 'kubernetes1372_vendor_preload/files/controller.py'
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i',
                        '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4',
                        'kubectl -n kube-system get daemonset kube-proxy -o json'],
                       capture_output=True, text=True, timeout=60)
    authority.need(r.returncode == 0, 'Read-only original proxy capture failed')
    proxy = json.loads(r.stdout)
    image = next(c['image'] for c in proxy['spec']['template']['spec']['containers'] if c['name'] == 'kube-proxy')
    result = {'schema': 'kubernetes1372-native-authority-v1', 'capturedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
              'nodeUIDs': checkpoint['clusterNodes'], 'checkpoint': checkpoint_ref, 'proxyBeforeImage': image,
              'binaries': binaries['binaries'], 'signatureTool': binaries['signatureTool'], 'vendorScan': {'summary': summary_ref, 'controllerSHA256': hashlib.sha256(source.read_bytes()).hexdigest()},
              'images': {}}
    for entry in summary['images']:
        name = entry['name']
        result['images'][name] = {k: entry[k] for k in ['rootDigest', 'amd64Digest', 'configDigest']}
        result['images'][name].update(reference='registry.k8s.io/' + name + ':v1.37.2@' + entry['amd64Digest'], prestage=stages['images'][name])
    # This is a concrete draft, not qualification. Run authority.py and the full
    # read-only Ansible preflight against its exact saved bytes before apply.
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
