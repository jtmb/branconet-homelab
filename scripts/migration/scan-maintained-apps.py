#!/usr/bin/env python3
"""Finite maintained vendor app scans with pinned public inputs and no suppression."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
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
    need(len(sys.argv) == 2 and sys.argv[1] in ['homepage-jackett', 'homepage-current-r3', 'jackett-current-r3', 'mealie-current-r3', 'tautulli-current-r3', 'tautulli-linuxserver-current-r3', 'vaultwarden-current-r3', 'pihole-current-r3', 'qbittorrent-current-r3', 'threadfin-current-r3', 'ruckusdb-current-r3', 'wordpress-current-r3', 'coredns-current-r3', 'plex-current-r3', 'owned-qbit-current-r3', 'owned-jtmb-current-r3', 'fleet-current-r5', 'vendor-candidates-r5'], 'finite_scan_generation')
    generation = sys.argv[1]
    vendor = generation == 'vendor-candidates-r5'
    fleet = generation in ['fleet-current-r5', 'vendor-candidates-r5']
    runtime = OUT / 'fleet-r5-runtime' if fleet else OUT
    revalidated = generation != 'homepage-jackett'
    cg = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    need(cg.endswith('/branconet-apps-review-' + generation + '-20261026.service'), 'owned_user_unit')
    group = Path('/sys/fs/cgroup') / cg.lstrip('/')
    need((group / 'memory.max').read_text().strip() == str(1024**3) and (group / 'memory.swap.max').read_text().strip() == '0'
         and (group / 'pids.max').read_text().strip() == '128' and os.getpriority(os.PRIO_PROCESS, 0) == 10, 'resource_bounds')
    need(not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK), 'credentials_hidden')
    proof = json.loads((OUT / ('public-inputs-r5-receipt.json' if fleet else 'public-inputs-r3-receipt.json' if revalidated else 'public-inputs-receipt.json')).read_bytes())
    need(proof['complete'] and sha(TOOL) == TOOL_SHA, 'trusted_tool_and_inputs')
    pins = {TOOL: identity(TOOL)}
    hashes = {TOOL: TOOL_SHA}
    for row in proof['files'].values():
        p = Path(row['path'])
        need(p.resolve() == p and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'complete_fresh_database_digest')
        need(not revalidated or row.get('readBackSHA256') == [row['sha256']] * 2, 'verified_download_readback')
        pins[p] = identity(p)
        hashes[p] = row['sha256']
    java = json.loads((OUT / ('java-inputs-r3-receipt.json' if fleet else 'java-inputs-r2-receipt.json')).read_bytes())
    need(java['complete'], 'explicit_java_identity_index')
    if fleet:
        need(datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(java['javaIdentificationDB']['NextUpdate'].replace('Z', '+00:00')), 'current_java_index')
    for row in java['files'].values():
        p = Path(row['path'])
        need(p.resolve() == p and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'complete_java_identity_index_digest')
        pins[p] = identity(p)
        hashes[p] = row['sha256']
    updated = datetime.datetime.fromisoformat(proof['vulnerabilityDB']['UpdatedAt'].replace('Z', '+00:00'))
    need(0 <= (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() <= 86400, 'fresh_database')
    kev_path = OUT / ('cisa-kev-r5.json' if fleet else 'cisa-kev-r3.json' if revalidated else 'cisa-kev.json')
    if fleet:
        need(sha(kev_path) == proof['cisa']['sha256'], 'pinned_cisa_catalog')
        pins[kev_path] = identity(kev_path)
        hashes[kev_path] = proof['cisa']['sha256']
    kev = {r['cveID'] for r in json.loads(kev_path.read_bytes())['vulnerabilities']}
    if fleet:
        candidate_path = OUT / ('vendor-r5-scan-candidates.json' if vendor else 'fleet-r5-candidates.json')
        candidate_hash = '813b6922b762af1adaebccf282ed083cd91828ad7c8ce6d2740ded8c8ff7e460' if vendor else '8ffa19129baa4edeb7ad8978b101f571d78409e56fc19e1d477e6563fadd6db9'
        need(sha(candidate_path) == candidate_hash, 'finite_current_owner_digest_inventory')
        inventory = json.loads(candidate_path.read_bytes())
        need(not inventory['unresolved'] and len(inventory['images']) == (2 if vendor else 66), 'complete_runtime_image_bindings')
        grouped = {}
        for row in inventory['images']:
            if row.get('scanKind') == 'existing-readonly-layout':
                continue  # BORTUS remains exclusively on its verified local closure.
            repository, digest = row['reference'].split('@sha256:')
            repository = repository.rsplit(':', 1)[0] if ':' in repository.rsplit('/', 1)[-1] else repository
            reference = repository + '@sha256:' + digest
            need(len(digest) == 64 and set(digest) <= set('0123456789abcdef'), 'exact_runtime_digest')
            grouped.setdefault(reference, {'reference': reference, 'owners': []})['owners'].extend(row['owners'])
        candidates = list(grouped.values())
        need(len(candidates) == (2 if vendor else 64), 'finite_remote_runtime_targets')
        pins[candidate_path] = identity(candidate_path)
        hashes[candidate_path] = sha(candidate_path)
    elif generation == 'owned-jtmb-current-r3':
        candidates = json.loads((OUT / 'owned-jtmb-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/jtmb92/jtmb-dev:git-5989a1491415532244ef9c67635e7c72437387ab@sha256:ac5cdc8d7e1bb7d6a5bcea08d4e379ea63f2ec1e7ae93a267258a9c97593d830'], 'finite_owned_source_site_target')
    elif generation == 'owned-qbit-current-r3':
        candidates = json.loads((OUT / 'owned-qbit-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/jtmb92/qbit-monitor:git-f365b49bad13eab9d5e7083ecebeb4db2cc9fa69@sha256:397c69f6b04bd0ae328c48c3f492795d73fbbc2e19da10b5ae3a08619914b1fe'], 'finite_owned_source_monitor_target')
    elif generation == 'plex-current-r3':
        candidates = json.loads((OUT / 'plex-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/linuxserver/plex:1.43.5.11079-b3b13e506-ls330@sha256:01a53d9c7adcbb3701fbb0a4230c0a37c85453759b6b05a67356c3c7a09de08d'], 'finite_current_plex_target')
    elif generation == 'coredns-current-r3':
        candidates = json.loads((OUT / 'coredns-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/coredns/coredns:1.15.0@sha256:0a9d8c8ddf34347eb59aad9a8784f0710de88d6d112726d11d271f9bc6daca26'], 'finite_current_coredns_target')
    elif generation == 'wordpress-current-r3':
        candidates = json.loads((OUT / 'wordpress-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/library/wordpress:7.1.3-php8.3-apache@sha256:e5a724ec7ad9055f48b2941ac1b674b08e77ed60edb8937a6254fb89ec45ddf7'], 'finite_current_wordpress_target')
    elif generation == 'ruckusdb-current-r3':
        candidates = json.loads((OUT / 'ruckusdb-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/library/mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69'], 'finite_current_ruckusdb_target')
    elif generation == 'threadfin-current-r3':
        candidates = json.loads((OUT / 'threadfin-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['ghcr.io/volschin/threadfin:v3.4.0@sha256:79ba430d81feccaa36865cc9ecc905e5cb5d16f593965e30cb2feda128b43216'], 'finite_current_threadfin_target')
    elif generation == 'qbittorrent-current-r3':
        candidates = json.loads((OUT / 'qbittorrent-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['ghcr.io/linuxserver/qbittorrent:5.3.0_v2.1.2-ls485@sha256:75ecbb1c89ab7b0a21c4bde40b4820e4f1649d2d56d83b91913422155e8d2a5f'], 'finite_current_qbittorrent_target')
    elif generation == 'pihole-current-r3':
        candidates = json.loads((OUT / 'pihole-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/pihole/pihole:2026.10.0@sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113'], 'finite_current_pihole_target')
    elif generation == 'vaultwarden-current-r3':
        candidates = json.loads((OUT / 'vaultwarden-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/vaultwarden/server:1.37.4@sha256:efb3cde962015fcc036b2ea625242248611943b27212ebf4392841fb30fad055', 'docker.io/vaultwarden/server:1.37.4-alpine@sha256:19ea2b669945d842dadc3d500f2d6a795866a003330f59a47b9634658bae98bb'], 'finite_current_vaultwarden_variants')
    elif generation == 'tautulli-linuxserver-current-r3':
        candidates = json.loads((OUT / 'tautulli-linuxserver-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['ghcr.io/linuxserver/tautulli:v2.18.2-ls249@sha256:c6a48416d16b26f254b000133d2d844c1905ee58ed0f44aad9bda66598d39988'], 'finite_current_linuxserver_tautulli_target')
    elif generation == 'tautulli-current-r3':
        candidates = json.loads((OUT / 'tautulli-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['ghcr.io/tautulli/tautulli:v2.18.2@sha256:1b5875fe3193d450a62e7b438eb6701195c841f14f3dcb962e545eda42d3696f'], 'finite_current_tautulli_target')
    elif generation == 'mealie-current-r3':
        candidates = json.loads((OUT / 'mealie-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['ghcr.io/mealie-recipes/mealie:v3.29.0@sha256:78eb28b8776d0bad40c5e605c72b3f4f5976793e491558c7dcbdfc04c835d4bc'], 'finite_current_mealie_target')
    elif generation == 'jackett-current-r3':
        candidates = json.loads((OUT / 'jackett-current-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['docker.io/linuxserver/jackett:0.24.2910@sha256:19d90927b95397f2d1364e4999e11456abdbbb382b54cd765fc3b3da24d7088b'], 'finite_current_jackett_target')
    else:
        candidates = json.loads((OUT / 'homepage-jackett-candidates.json').read_bytes())['images']
        need([r['reference'] for r in candidates] == ['ghcr.io/gethomepage/homepage:v2.7.0@sha256:19c5c09184458a41b7b5915e71463a39f36cd33540f41bdbed008791b8182d5f', 'ghcr.io/gethomepage/homepage:v1.13.2@sha256:a0b71c8e757298d02560186bab9fbe3fc2d375c523a62cc1019177b37e48aa28', 'docker.io/linuxserver/jackett:0.24.2900@sha256:d1b82a9c5bbaea44284a550af739bd838749b72f15b10ef61b6c9d9d1b2f1ed7'], 'finite_vendor_targets')
        if revalidated:
            candidates = candidates[:1]
    receipts = []
    whole_started = time.monotonic()
    for n, image in enumerate(candidates):
        if fleet and time.monotonic() - whole_started > 3500:
            break
        path = OUT / ('apps-' + generation + '-' + str(n))
        need(not path.exists(), 'immutable_scan_attempt')
        path.mkdir(mode=0o700)
        receipt = path / 'receipt.json'
        r = {'image': image['reference'], 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'scanComplete': False, 'securityAcceptance': False, 'sourceSHA256': sha(Path(__file__)),
             'toolSHA256': TOOL_SHA, 'databaseUpdatedAt': proof['vulnerabilityDB']['UpdatedAt'],
             'databaseManifestDigest': proof['databaseManifestDigest'], 'suppressionUsed': False, 'containerCreated': False}
        r['javaIdentificationIndex'] = {'manifestDigest': java['databaseManifestDigest'], 'metadata': java['javaIdentificationDB']}
        if fleet:
            r['runtimeOwners'] = image['owners']
            r['inventoryUTC'] = inventory['inventoryUTC']
        child = None
        try:
            fs = os.statvfs(OUT)
            need(fs.f_bavail * fs.f_frsize >= 17 * 1024**3, 'native_capacity_floor')
            output = path / 'results.json'
            cmd = [str(TOOL), 'image', '--image-src', 'remote', '--platform', 'linux/amd64',
                   '--config', str(OUT / 'empty-config.yaml'), '--cache-dir', str(runtime / 'cache'), '--scanners', 'vuln',
                   '--offline-scan', '--skip-db-update', '--skip-java-db-update', '--ignorefile', str(OUT / 'no-ignore'),
                   '--timeout', '7m', '--parallel', '2', '--quiet', '--no-progress', '--list-all-pkgs',
                   '--format', 'template', '--template', '@' + str(OUT / 'results.tpl'), '--output', str(output), image['reference']]
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(runtime / 'home'), 'DOCKER_CONFIG': str(OUT / 'docker-config'),
                   'TMPDIR': str(runtime / 'tmp'), 'TMP': str(runtime / 'tmp'), 'TEMP': str(runtime / 'tmp'), 'GOMAXPROCS': '2',
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
                    if fleet:
                        allocated = 0
                        for scratch in [runtime / 'tmp', runtime / 'home', runtime / 'cache/fanal']:
                            for current, directories, files in os.walk(scratch, followlinks=False):
                                for name in [*directories, *files]:
                                    p = Path(current) / name
                                    try:
                                        s = p.lstat()
                                    except FileNotFoundError:
                                        continue
                                    need(not stat.S_ISLNK(s.st_mode) and s.st_uid == 1000, 'owned_analysis_member')
                                    allocated += s.st_blocks * 512
                        need(allocated <= 2 * 1024**3, 'bounded_fresh_analysis')
                    time.sleep(2)
            need(child.returncode == 0 and 0 < output.stat().st_size <= 64 * 1024**2, 'complete_successful_scan')
            results = json.loads(output.read_bytes())
            need(isinstance(results, list) and results and all(isinstance(x, dict) for x in results), 'results_only_shape')
            need(all(identity(p) == ident for p, ident in pins.items()), 'immutable_scanner_inputs')
            need(all(sha(p) == digest for p, digest in hashes.items()), 'complete_input_hashes_after_scan')
            rows = [v for x in results for v in x.get('Vulnerabilities') or []]
            r.update(scanComplete=True, state='completed', scannerExitCode=child.returncode, resultsSHA256=sha(output),
                     inputHashesReverifiedAfterScan=True,
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
        if not r['scanComplete'] and not fleet:
            return 1
    complete = len(receipts) == len(candidates) and all(json.loads(Path(p).read_bytes())['scanComplete'] for p in receipts)
    save(OUT / ('apps-scan-summary-' + generation + '.json'), {'receipts': receipts, 'allComplete': complete,
         'targetCount': len(candidates), 'attempted': len(receipts), 'pending': candidates[len(receipts):], 'productionChanged': False})
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
