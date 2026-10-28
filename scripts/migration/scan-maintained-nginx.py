#!/usr/bin/env python3
"""Exact official Nginx variant scans, fresh public inputs, no suppression."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'security-review-20261026'
TOOL = ROOT / 'local-oci-scan/bin/trivy'
TOOL_SHA = 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        offset = 0
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
            offset += len(b)
            if offset % (16 * 1024**2) == 0:
                os.posix_fadvise(f.fileno(), offset - 16 * 1024**2, 16 * 1024**2, os.POSIX_FADV_DONTNEED)
        os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return h.hexdigest()


def identity(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid)


def save(path, value):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def main():
    os.umask(0o077)
    need(len(sys.argv) == 2 and sys.argv[1] == 'r2', 'finite_scan_generation')
    generation = sys.argv[1]
    cg = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    need(cg.endswith('/branconet-nginx-review-' + generation + '-20261026.service'), 'owned_user_unit')
    group = Path('/sys/fs/cgroup') / cg.lstrip('/')
    need((group / 'memory.max').read_text().strip() == str(1024**3) and (group / 'memory.swap.max').read_text().strip() == '0'
         and (group / 'pids.max').read_text().strip() == '128' and os.getpriority(os.PRIO_PROCESS, 0) == 10, 'resource_bounds')
    need(not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK), 'credentials_hidden')
    proof = json.loads((OUT / 'public-inputs-receipt.json').read_bytes())
    need(proof['complete'] and sha(TOOL) == TOOL_SHA, 'trusted_tool_and_inputs')
    pins = {TOOL: identity(TOOL)}
    for row in proof['files'].values():
        p = Path(row['path'])
        need(p.resolve() == p and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'complete_fresh_database_digest')
        pins[p] = identity(p)
    java = json.loads((OUT / 'java-inputs-r2-receipt.json').read_bytes())
    need(java['complete'], 'explicit_java_identity_index')
    for row in java['files'].values():
        p = Path(row['path'])
        need(p.resolve() == p and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'complete_java_identity_index_digest')
        pins[p] = identity(p)
    updated = datetime.datetime.fromisoformat(proof['vulnerabilityDB']['UpdatedAt'].replace('Z', '+00:00'))
    need(0 <= (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() <= 86400, 'fresh_database')
    kev = {r['cveID'] for r in json.loads((OUT / 'cisa-kev.json').read_bytes())['vulnerabilities']}
    candidates = json.loads((OUT / 'nginx-candidates.json').read_bytes())['images']
    need(len(candidates) == 3 and all(r['reference'].startswith('docker.io/library/nginx:1.30.6') for r in candidates), 'finite_vendor_targets')
    receipts = []
    for n, image in enumerate(candidates):
        path = OUT / ('nginx-' + generation + '-' + str(n))
        need(not path.exists(), 'immutable_scan_attempt')
        path.mkdir(mode=0o700)
        receipt = path / 'receipt.json'
        r = {'image': image['reference'], 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'scanComplete': False, 'securityAcceptance': False, 'sourceSHA256': sha(Path(__file__)),
             'toolSHA256': TOOL_SHA, 'databaseUpdatedAt': proof['vulnerabilityDB']['UpdatedAt'],
             'databaseManifestDigest': proof['databaseManifestDigest'], 'suppressionUsed': False, 'containerCreated': False}
        r['javaIdentificationIndex'] = {'manifestDigest': java['databaseManifestDigest'], 'metadata': java['javaIdentificationDB']}
        child = None
        try:
            fs = os.statvfs(OUT)
            need(fs.f_bavail * fs.f_frsize >= 17 * 1024**3, 'native_capacity_floor')
            output = path / 'results.json'
            cmd = [str(TOOL), 'image', '--image-src', 'remote', '--platform', 'linux/amd64',
                   '--config', str(OUT / 'empty-config.yaml'), '--cache-dir', str(OUT / 'cache'), '--scanners', 'vuln',
                   '--offline-scan', '--skip-db-update', '--skip-java-db-update', '--ignorefile', str(OUT / 'no-ignore'),
                   '--timeout', '7m', '--parallel', '2', '--quiet', '--no-progress', '--list-all-pkgs',
                   '--format', 'template', '--template', '@' + str(OUT / 'results.tpl'), '--output', str(output), image['reference']]
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(OUT / 'home'), 'DOCKER_CONFIG': str(OUT / 'docker-config'),
                   'TMPDIR': str(OUT / 'tmp'), 'TMP': str(OUT / 'tmp'), 'TEMP': str(OUT / 'tmp'), 'GOMAXPROCS': '2',
                   'GOMEMLIMIT': '512MiB', 'TRIVY_SKIP_VERSION_CHECK': 'true', 'LANG': 'C', 'LC_ALL': 'C'}
            r.update(state='scanning', command=cmd)
            save(receipt, r)
            with (path / 'scanner.stderr').open('xb') as errors:
                child = subprocess.Popen(cmd, env=env, cwd=OUT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
                start = time.monotonic()
                while child.poll() is None:
                    need(time.monotonic() - start < 480, 'observation_deadline')
                    fs = os.statvfs(OUT)
                    need(fs.f_bavail * fs.f_frsize >= 15 * 1024**3, 'native_retained_floor')
                    need(not output.exists() or output.stat().st_size <= 64 * 1024**2, 'bounded_results')
                    need((path / 'scanner.stderr').stat().st_size <= 16 * 1024**2, 'bounded_diagnostics')
                    time.sleep(2)
            need(child.returncode == 0 and 0 < output.stat().st_size <= 64 * 1024**2, 'complete_successful_scan')
            results = json.loads(output.read_bytes())
            need(isinstance(results, list) and results and all(isinstance(x, dict) for x in results), 'results_only_shape')
            need(all(identity(p) == ident for p, ident in pins.items()), 'immutable_scanner_inputs')
            rows = [v for x in results for v in x.get('Vulnerabilities') or []]
            r.update(scanComplete=True, state='completed', scannerExitCode=child.returncode, resultsSHA256=sha(output),
                     severityCounts=dict(collections.Counter(v['Severity'] for v in rows)),
                     fixableCriticalHigh=sum(v['Severity'] in ['CRITICAL', 'HIGH'] and bool(v.get('FixedVersion')) for v in rows),
                     knownExploitedCVEs=sorted({v['VulnerabilityID'] for v in rows} & kev),
                     detectedTargets=[{'target': x.get('Target'), 'type': x.get('Type'), 'packages': len(x.get('Packages') or [])} for x in results])
        except Exception as error:
            r.update(state='failed_not_clean', errorCategory=str(error) if type(error) is ValueError else type(error).__name__)
        finally:
            if child is not None and child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=10)
            r['finishedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save(receipt, r)
            receipts.append(str(receipt))
            print(json.dumps({k: v for k, v in r.items() if k != 'command'}), flush=True)
        if not r['scanComplete']:
            return 1
    save(OUT / ('nginx-scan-summary-' + generation + '.json'), {'receipts': receipts, 'allComplete': True, 'productionChanged': False})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
