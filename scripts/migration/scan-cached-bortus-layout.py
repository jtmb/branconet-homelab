#!/usr/bin/env python3
"""One offline static scan of the exact existing cached BORTUS runtime image.

Uses OCI layout input directly: no registry access, archive extraction, image
execution or application change. Run only inside the declared isolated user unit.
"""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'security-review-20261026'
LAYOUT = ROOT / 'bortus-cached-runtime-audit-20261025/scan-attempts/bortus-cached-3da0b68becea/selected-oci'
DIGEST = 'sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879'
IMAGE = 'docker.io/library/bortus@' + DIGEST
TOOL = ROOT / 'local-oci-scan/bin/trivy'
TOOL_SHA = 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83'
UNIT = 'branconet-apps-review-bortus-layout-current-r4-20261027.service'

def need(ok, code):
    if not ok:
        raise ValueError(code)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        total = 0
        for data in iter(lambda: stream.read(1024**2), b''):
            h.update(data)
            total += len(data)
            if total % (16 * 1024**2) == 0:
                os.posix_fadvise(stream.fileno(), total - 16 * 1024**2, 16 * 1024**2, os.POSIX_FADV_DONTNEED)
        os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return h.hexdigest()

def identity(path):
    s = path.stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid]

def layout_snapshot():
    need(LAYOUT.resolve() == LAYOUT and not os.access(LAYOUT, os.W_OK), 'readonly_layout_mount')
    index = json.loads((LAYOUT / 'index.json').read_bytes())
    need(len(index['manifests']) == 1 and index['manifests'][0]['digest'] == DIGEST, 'exact_single_runtime_manifest')
    descriptor = index['manifests'][0]
    manifest_path = LAYOUT / 'blobs/sha256' / DIGEST.split(':')[1]
    need(manifest_path.stat().st_size == descriptor['size'] and sha(manifest_path) == DIGEST.split(':')[1], 'runtime_manifest_digest')
    manifest = json.loads(manifest_path.read_bytes())
    need(manifest['schemaVersion'] == 2 and len(manifest['layers']) <= 128 and 'manifests' not in manifest, 'single_image_manifest')
    paths = [LAYOUT / 'index.json', LAYOUT / 'oci-layout', manifest_path]
    need(json.loads((LAYOUT / 'oci-layout').read_bytes()) == {'imageLayoutVersion': '1.0.0'}, 'oci_layout_version')
    for item in [manifest['config'], *manifest['layers']]:
        algorithm, digest = item['digest'].split(':')
        need(algorithm == 'sha256' and len(digest) == 64 and set(digest) <= set('0123456789abcdef'), 'safe_blob_name')
        p = LAYOUT / 'blobs/sha256' / digest
        need(p.resolve() == p and not p.is_symlink() and stat.S_ISREG(p.stat().st_mode) and p.stat().st_uid == 1000, 'regular_owned_blob')
        need(p.stat().st_size == item['size'] and sha(p) == digest, 'complete_immutable_blob')
        paths.append(p)
    need(len(set(paths)) == len(paths) == 19, 'exact_seventeen_blob_closure')
    need({p for p in LAYOUT.rglob('*') if p.is_file()} == set(paths), 'unclassified_layout_member')
    config_path = LAYOUT / 'blobs/sha256' / manifest['config']['digest'].split(':')[1]
    config = json.loads(config_path.read_bytes())
    need(config['os'] == 'linux' and config['architecture'] == 'amd64', 'runtime_platform')
    return [{'path': str(p), 'SHA256': sha(p), 'identity': identity(p)} for p in sorted(paths)]

def allocated_analysis_bytes():
    total = 0
    count = 0
    for root in [OUT / 'tmp', OUT / 'home', OUT / 'cache-r4/fanal']:
        if not root.exists():
            continue
        for current, directories, files in os.walk(root, followlinks=False):
            for name in [*directories, *files]:
                p = Path(current) / name
                try:
                    s = p.lstat()
                except FileNotFoundError:
                    continue
                need(not stat.S_ISLNK(s.st_mode) and s.st_uid == 1000, 'owned_analysis_member')
                total += s.st_blocks * 512
                count += 1
                need(count <= 400000, 'analysis_inode_bound')
    return total

def main():
    os.umask(0o077)
    cg = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    need(cg.endswith('/' + UNIT), 'owned_unit')
    group = Path('/sys/fs/cgroup') / cg.lstrip('/')
    need((group / 'memory.max').read_text().strip() == str(1024**3) and (group / 'memory.swap.max').read_text().strip() == '0'
         and (group / 'pids.max').read_text().strip() == '128' and os.getpriority(os.PRIO_PROCESS, 0) == 10, 'resource_limits')
    need(not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK), 'credentials_hidden')
    target = OUT / 'apps-bortus-layout-current-r4-0'
    need(not target.exists(), 'single_use_report')
    target.mkdir(mode=0o700)
    receipt = target / 'receipt.json'
    r = {'image': IMAGE, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scanComplete': False,
         'sourceSHA256': sha(Path(__file__)), 'sourceKind': 'existing_readonly_exact_OCI_layout', 'registryAcquisitionAttempted': False,
         'containerCreated': False, 'applicationExecuted': False, 'sourceTreeOrNativeValuesExported': False,
         'securityAcceptance': False, 'suppressionUsed': False, 'freshAnalysisCapBytes': 2 * 1024**3}
    child = None
    def save():
        receipt.write_text(json.dumps(r, indent=2) + '\n')
    try:
        proof = json.loads((OUT / 'public-inputs-r4-receipt.json').read_bytes())
        java = json.loads((OUT / 'java-inputs-r2-receipt.json').read_bytes())
        need(proof['complete'] and java['complete'] and sha(TOOL) == TOOL_SHA, 'pinned_tool_and_inputs')
        updated = datetime.datetime.fromisoformat(proof['vulnerabilityDB']['UpdatedAt'].replace('Z', '+00:00'))
        need(0 <= (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() <= 86400, 'fresh_core_feed')
        java_next = datetime.datetime.fromisoformat(java['javaIdentificationDB']['NextUpdate'].replace('Z', '+00:00'))
        need(datetime.datetime.now(datetime.timezone.utc) < java_next, 'current_java_index')
        pins = {TOOL: TOOL_SHA}
        for bundle in [proof, java]:
            for row in bundle['files'].values():
                p = Path(row['path'])
                need(p.resolve() == p and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'complete_pinned_feed')
                pins[p] = row['sha256']
        need(sha(OUT / 'cisa-kev-r4.json') == proof['cisa']['sha256'], 'pinned_cisa_catalog')
        pins[OUT / 'cisa-kev-r4.json'] = proof['cisa']['sha256']
        need((OUT / 'empty-config.yaml').read_bytes() == b'{}\n' and (OUT / 'no-ignore').read_bytes() == b''
             and (OUT / 'results.tpl').read_bytes() == b'{{ toJson . }}\n', 'unchanged_empty_controls')
        identities = {p: identity(p) for p in pins}
        before = layout_snapshot()
        r.update(layoutInput=before, toolSHA256=TOOL_SHA, databaseManifestDigest=proof['databaseManifestDigest'],
                 databaseUpdatedAt=proof['vulnerabilityDB']['UpdatedAt'], javaIdentificationIndex={'manifestDigest': java['databaseManifestDigest'], 'metadata': java['javaIdentificationDB']})
        result = target / 'results.json'
        command = [str(TOOL), 'image', '--platform', 'linux/amd64', '--input', str(LAYOUT) + '@' + DIGEST,
                   '--config', str(OUT / 'empty-config.yaml'), '--cache-dir', str(OUT / 'cache-r4'), '--scanners', 'vuln',
                   '--offline-scan', '--skip-db-update', '--skip-java-db-update', '--ignorefile', str(OUT / 'no-ignore'),
                   '--timeout', '7m', '--parallel', '2', '--quiet', '--no-progress', '--list-all-pkgs', '--format', 'template',
                   '--template', '@' + str(OUT / 'results.tpl'), '--output', str(result)]
        r.update(command=command, state='scanning')
        save()
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': str(OUT / 'home'),
               'DOCKER_CONFIG': str(OUT / 'docker-config'), 'TMPDIR': str(OUT / 'tmp'), 'TMP': str(OUT / 'tmp'),
               'TEMP': str(OUT / 'tmp'), 'GOMAXPROCS': '2', 'GOMEMLIMIT': '512MiB', 'TRIVY_SKIP_VERSION_CHECK': 'true'}
        with (target / 'scanner.stderr').open('xb') as errors:
            child = subprocess.Popen(command, env=env, cwd=OUT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
            start = time.monotonic()
            while child.poll() is None:
                need(time.monotonic() - start < 480, 'observation_deadline')
                fs = os.statvfs(OUT)
                need(fs.f_bavail * fs.f_frsize >= 15 * 1024**3 and allocated_analysis_bytes() <= 2 * 1024**3, 'retained_space_and_analysis_cap')
                need(not result.exists() or result.stat().st_size <= 64 * 1024**2, 'result_bound')
                need((target / 'scanner.stderr').stat().st_size <= 16 * 1024**2, 'diagnostic_bound')
                time.sleep(2)
        need(child.returncode == 0 and 0 < result.stat().st_size <= 64 * 1024**2, 'complete_successful_scan')
        data = json.loads(result.read_bytes())
        need(isinstance(data, list) and data and all(isinstance(x, dict) for x in data), 'results_only_shape')
        need(layout_snapshot() == before and all(identity(p) == identities[p] and sha(p) == digest for p, digest in pins.items()), 'complete_immutable_inputs_after_scan')
        kev = {x['cveID'] for x in json.loads((OUT / 'cisa-kev-r4.json').read_bytes())['vulnerabilities']}
        rows = [v for x in data for v in x.get('Vulnerabilities') or []]
        r.update(scanComplete=True, state='completed', scannerExitCode=0, resultsSHA256=sha(result), inputHashesReverifiedAfterScan=True,
                 severityCounts=dict(collections.Counter(v['Severity'] for v in rows)), knownExploitedCVEs=sorted({v['VulnerabilityID'] for v in rows if v['VulnerabilityID'] in kev}),
                 fixableCriticalHigh=sum(v['Severity'] in ['CRITICAL', 'HIGH'] and bool(v.get('FixedVersion')) for v in rows),
                 detectedTargets=[{'target': x['Target'], 'type': x.get('Type'), 'packages': len(x.get('Packages') or [])} for x in data])
    except BaseException as e:
        r.update(state='failed', errorCategory=str(e) if isinstance(e, ValueError) else type(e).__name__)
        raise
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
        r['finishedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    print(json.dumps({k: r[k] for k in ['image', 'scanComplete', 'severityCounts', 'knownExploitedCVEs', 'registryAcquisitionAttempted']}))

if __name__ == '__main__':
    main()
