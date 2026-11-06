"""Controller-only hash-bound native image/binary scan and staging authority."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import re
import urllib.request

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
NODES = {'masternode', 'workernode1', 'workernode2'}
IMAGES = {'kube-apiserver', 'kube-controller-manager', 'kube-scheduler', 'kube-proxy'}


def need(test, message):
    if not test:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def bound_path(ref):
    p = Path(ref['path'])
    need(p.is_absolute() and p.resolve() == p and ROOT in p.parents and p.is_file(), 'Evidence outside existing root')
    need(file_sha(p) == ref['sha256'], 'Evidence SHA256 mismatch')
    return p


def load_bound(ref):
    return json.loads(bound_path(ref).read_text())


def fresh(value):
    age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(dt.timedelta(0) <= age <= dt.timedelta(hours=6), 'Evidence exceeds six-hour freshness bound')


def scan(ref, subject, allowed):
    evidence = load_bound(ref)
    need(evidence['scanner'] == 'trivy' and evidence['subjectSHA256'] == subject
         and evidence['exitCode'] == 0, 'Native scan failed or subject mismatch')
    fresh(evidence['completedAt'])
    report = load_bound(evidence['report'])
    results = report if isinstance(report, list) else report.get('Results')
    need(isinstance(results, list) and results, 'Native Trivy JSON results missing')
    need(evidence['scanComplete'] is True and evidence['suppressionUsed'] is False
         and evidence['inputHashesReverifiedAfterScan'] is True and evidence['knownExploitedCVEs'] == [], 'Incomplete or suppressed native scan')
    versions = [p['Version'] for r in results for p in r.get('Packages', []) if p.get('Name') == 'stdlib']
    need(versions and set(versions) == {'v1.26.10'}, 'Actual native Go1.26.10 package evidence missing')
    need(not any(v['VulnerabilityID'] == 'CVE-2026-111943' for r in results for v in r.get('Vulnerabilities', [])), 'Target certificate vulnerability remains')
    actual = {v['VulnerabilityID'] for r in results for v in r.get('Vulnerabilities', [])
              if v.get('Severity') in ['HIGH', 'CRITICAL']}
    need(actual <= set(allowed), 'Unreviewed HIGH/CRITICAL findings remain')
    # Exception IDs are explicit reviewed manifest authority, not an assertion
    # that the image or package is vulnerability-free.


def qualify(ref):
    d = load_bound(ref)
    need(d['schema'] == 'kubernetes1372-native-authority-v1', 'Wrong authority schema')
    fresh(d['capturedAt'])
    need(set(d['nodeUIDs']) == NODES and set(d['images']) == IMAGES, 'Incomplete original-node/image set')
    need(set(d['binaries']) == {'kubeadm', 'kubelet', 'kubectl'}, 'Unreviewed native binary set')
    verifier = d['signatureTool']
    tool = Path(verifier['path'])
    need(tool.is_absolute() and tool.resolve() == tool and file_sha(tool) == verifier['sha256'], 'Signature verifier binary changed')
    cache = Path(verifier['cacheDirectory'])
    need(cache.is_absolute() and cache.resolve() == cache and ROOT in cache.parents and cache.is_dir(), 'Signature cache must exist inside task root')
    need(cache.stat().st_uid == os.geteuid() and not cache.stat().st_mode & 0o077, 'Signature cache must be task-private')
    env = dict(os.environ, HOME=str(cache), XDG_CACHE_HOME=str(cache), TUF_ROOT=str(cache), TMPDIR=str(cache), TMP=str(cache), TEMP=str(cache))
    for key in list(env):
        if key.startswith(('COSIGN_', 'SIGSTORE_')):
            env.pop(key)
    for n, binary in d['binaries'].items():
        need(binary['url'] == 'https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/' + n
             and re.fullmatch('[a-f0-9]{64}', binary['sha256']) and binary['bytes'] > 0, 'Wrong upstream native artifact')
        blob = bound_path(binary['blob'])
        need(binary['blob']['sha256'] == binary['sha256'] and blob.stat().st_size == binary['bytes'], 'Native blob binding mismatch')
        checksum = bound_path(binary['checksum'])
        need(checksum.read_text().strip().split()[0] == binary['sha256'], 'Official checksum differs')
        with urllib.request.urlopen(binary['url'] + '.sha256', timeout=30) as response:
            published = response.read(1025)
        need(len(published) <= 1024 and published.decode().strip().split()[0] == binary['sha256'], 'Live official release checksum differs')
        with blob.open('rb') as f:
            elf = f.read(20)
        need(elf[:6] == b'\x7fELF\x02\x01' and int.from_bytes(elf[18:20], 'little') == 62, 'Require native linux/amd64 ELF')
        signature = bound_path(binary['signature']); certificate = bound_path(binary['certificate'])
        verification = load_bound(binary['signatureVerification'])
        need(verification['subjectSHA256'] == binary['sha256'] and verification['exitCode'] == 0
             and verification['certificateIdentity'] == 'krel-staging@k8s-releng-prod.iam.gserviceaccount.com'
             and verification['certificateIssuer'] == 'https://accounts.google.com'
             and verification['bypassFlagsUsed'] is False, 'Publisher signature receipt mismatch')
        fresh(verification['completedAt'])
        checked = subprocess.run([str(tool), 'verify-blob', str(blob), '--signature', str(signature),
                    '--certificate', str(certificate), '--certificate-identity', 'krel-staging@k8s-releng-prod.iam.gserviceaccount.com',
                    '--certificate-oidc-issuer', 'https://accounts.google.com'],
                    capture_output=True, text=True, env=env, timeout=120)
        need(checked.returncode == 0, 'Independent publisher signature/certificate verification failed')
        scan(binary['scan'], binary['sha256'], binary.get('reviewedVulnerabilityIDs', []))
        need(set(binary['prestage']) == NODES and set(binary['originalByNode']) == NODES
             and set(binary['originalBackups']) == NODES, 'Require original bytes and native staging on every node')
        binary['verifiedStaging'] = {}
        for host in NODES:
            original = binary['originalByNode'][host]
            need(original['path'] == '/usr/local/bin/' + n and original['uid'] == 0 and original['gid'] == 0
                 and original['mode'] == 0o755 and original['bytes'] > 0, 'Unexpected original installation metadata')
            backup = bound_path(binary['originalBackups'][host])
            need(binary['originalBackups'][host]['sha256'] == original['sha256']
                 and backup.stat().st_size == original['bytes'], 'Original raw installed binary backup unavailable')
            stage = load_bound(binary['prestage'][host]); fresh(stage['capturedAt'])
            need(stage['node'] == host and stage['nodeUID'] == d['nodeUIDs'][host]
                 and stage['path'] == '/usr/local/bin/.kubernetes1372-' + n + '-' + binary['sha256'] + '.new'
                 and stage['sha256'] == binary['sha256'] and stage['bytes'] == binary['bytes']
                 and stage['ownerTask'] == 'kubernetes1372-security-patch' and stage['newlyCreated'] is True,
                 'Native staging ownership or identity mismatch')
            binary['verifiedStaging'][host] = {k: stage[k] for k in ['path', 'sha256', 'bytes', 'newlyCreated']}
    # Reuse the already qualified native four-image scanner and its exact
    # unsuppressed results/budget bindings; do not invent a clean scan wrapper.
    source = Path(__file__).resolve().parents[2] / 'kubernetes1372_vendor_preload/files/controller.py'
    need(sha(source.read_bytes()) == d['vendorScan']['controllerSHA256'], 'Vendor qualifier source changed')
    spec = importlib.util.spec_from_file_location('official1372', source)
    vendor = importlib.util.module_from_spec(spec); spec.loader.exec_module(vendor)
    summary = load_bound(d['vendorScan']['summary'])
    need(d['vendorScan']['summary']['sha256'] == vendor.FILES['qualification-summary.json'], 'Native summary authority mismatch')
    fresh(summary['timestampUTC'])
    for n, image in d['images'].items():
        need(image['reference'] == 'registry.k8s.io/' + n + ':v1.37.2@' + image['amd64Digest'], 'Nonofficial image reference')
        for key in ['rootDigest', 'amd64Digest', 'configDigest']:
            need(re.fullmatch('sha256:[a-f0-9]{64}', image[key]), 'Invalid immutable digest')
        measured = vendor.measurement(n, live_registry=True)
        need(measured['root'] == image['rootDigest'] and measured['manifest'] == image['amd64Digest']
             and measured['config'] == image['configDigest'] and measured['registryMetadataVerified'] is True,
             'Actual native scan/registry/budget authority differs')
        need(set(image['prestage']) == NODES, 'Require all-node native image prestaging')
        for host, stage_ref in image['prestage'].items():
            stage = load_bound(stage_ref)
            fresh(stage['capturedAt'])
            need(stage['node'] == host and stage['nodeUID'] == d['nodeUIDs'][host]
                 and stage['runtimeEndpoint'] == 'unix:///run/containerd-k8s/containerd.sock'
                 and stage['amd64Digest'] == image['amd64Digest'] and stage['configDigest'] == image['configDigest']
                 and stage['tag'] == 'registry.k8s.io/' + n + ':v1.37.2' and stage['present'] is True,
                 'Native runtime prestaging receipt mismatch')
    checkpoint = load_bound(d['checkpoint'])
    need(checkpoint['schema'] == 'kernel202-current58-v1' and checkpoint['clusterNodes'] == d['nodeUIDs'], 'Original checkpoint/node binding mismatch')
    need(re.fullmatch(r'registry\.k8s\.io/kube-proxy:v1\.37\.1(?:@sha256:[a-f0-9]{64})?', d['proxyBeforeImage']), 'Unexpected proxy baseline')
    return d


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    print(json.dumps(qualify({'path': a.manifest, 'sha256': a.sha256})))
