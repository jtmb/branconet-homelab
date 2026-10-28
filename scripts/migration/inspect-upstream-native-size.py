"""Authenticate two approved public image streams without storing payloads.

Budget is conservative overlay layer additions, not observed native allocation.
No credit for overwrites/whiteouts/sharing; every hardlink is budgeted as a copy.
"""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import runpy
import subprocess
import sys
import tarfile
import urllib.parse

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
B = F / 'platform-upstream-review-20261027/upstream-native-size-20261028'
S = F / 'security-review-20261026'
CHUNK = 1024**2
CAP = 4 * 1024**3
PINS = {
    'mysql': ('docker.io/library/mysql', 'a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7'),
    'ytptube': ('ghcr.io/arabcoders/ytptube', 'a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86'),
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def save(name, value):
    with (B / name).open('x') as out:
        json.dump(value, out, indent=2)
        out.flush()
        os.fsync(out.fileno())


def space():
    values = {name: os.statvfs(path).f_bavail * os.statvfs(path).f_frsize
              for name, path in [('windowsC', '/mnt/c'), ('windowsF', '/mnt/f'), ('nativeF', B)]}
    need(all(x >= 15 * 1024**3 + 16 * CHUNK for x in values.values()), 'storage_floor')
    return values


def rounded(n):
    return ((n + 4095) // 4096) * 4096


def main():
    name = sys.argv[1]
    revision = sys.argv[2] if len(sys.argv) == 3 else 'r1'
    need(revision in ('r1', 'r2'), 'finite_accounting_revision')
    need(name in PINS and sys.version_info >= (3, 13), 'finite_scope_and_streaming_tar')
    need(B.resolve() == B and B.is_dir() and os.geteuid() == 1000, 'owned_root')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(B), '-o', 'UUID,FSTYPE']))['filesystems'][0]
    need(fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b' and fs['fstype'] == 'ext4', 'physical_volume')
    group = Path('/proc/self/cgroup').read_text().strip().split('::')[1]
    unit_suffix = '-r2' if revision == 'r2' else ''
    need('branconet-native-size-' + name + unit_suffix + '-20261028.service' in group, 'owned_unit')
    cg = Path('/sys/fs/cgroup') / group.lstrip('/')
    limits = {k: (cg / k).read_text().strip() for k in ['memory.max', 'memory.swap.max', 'pids.max']}
    need(limits == {'memory.max': '1073741824', 'memory.swap.max': '0', 'pids.max': '128'}, 'resource_limits')
    need(os.getpriority(os.PRIO_PROCESS, 0) >= 10 and os.environ['TMPDIR'] == str(B), 'nice_and_temp')
    need(not os.access('/home/brajam/.ssh', os.R_OK | os.X_OK) and not os.access('/mnt/c/Users', os.R_OK | os.X_OK), 'hidden_credentials')
    helper = runpy.run_path(str(B / 'stream-helper.py'))
    request, small, Reader = (helper[x] for x in ['request', 'small', 'Reader'])
    metadata = (S / 'vendor-r5-refresh-metadata.json').read_bytes()
    need(hashlib.sha256(metadata).hexdigest() == '068348639fed49cadb197b43be929e32e5c1213c8f40aebf4a57b67f03fc41a7', 'approved_metadata')
    repository, pin = PINS[name]
    row = next(r for r in json.loads(metadata)['images'] if r['repository'] == repository)
    approved = next(m for m in row['manifests'] if m['rootDigest'] == 'sha256:' + pin)
    host, repo = repository.split('/', 1)
    if host == 'docker.io':
        token_url = 'https://auth.docker.io/token?' + urllib.parse.urlencode({'service': 'registry.docker.io', 'scope': 'repository:' + repo + ':pull'})
        registry = 'registry-1.docker.io'
    else:
        registry = 'ghcr.io'
        token_url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io', 'scope': 'repository:' + repo + ':pull'})
    token = small(token_url)['token']
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json'}
    base = 'https://' + registry + '/v2/' + repo
    root = small(base + '/manifests/sha256:' + pin, 'sha256:' + pin, headers)
    manifest = small(base + '/manifests/' + approved['amd64ManifestDigest'], approved['amd64ManifestDigest'], headers)
    need(root == approved['rootManifest'] and manifest == approved['amd64Manifest'], 'pinned_manifests')
    config = small(base + '/blobs/' + approved['configurationDigest'], approved['configurationDigest'], headers)
    diffs = config['rootfs']['diff_ids']
    need(config['architecture'] == 'amd64' and config['os'] == 'linux' and len(diffs) == len(manifest['layers']) <= 64, 'platform_and_layer_count')
    result = {'image': repository + '@sha256:' + pin, 'amd64ManifestDigest': approved['amd64ManifestDigest'],
              'configurationDigest': approved['configurationDigest'], 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'limits': limits, 'layers': [],
              'payloadSavedBytes': 0, 'status': 'started', 'budgetIsObservedNativeAllocation': False,
              'accounting': 'Each layer: max(actual TAR bytes, 4KiB-rounded regular/sparse logical payload) plus hardlink target copies plus 8192 bytes per member and implicit parent occurrence. No deletion/sharing credit. Unknown hardlink target uses largest regular file in complete image. Add compressed content and 16MiB manifest/database allowance for full staging.'}
    result['accountingRevision'] = revision
    if revision == 'r2':
        result['revisedDirectoryAccounting'] = 'Replace only repeated ancestor occurrence allowance with 8192 bytes per unique normalized explicit or implicit directory WITHIN EACH LAYER. Keep 8192 bytes per member, TAR/rounded payload maximum and hardlink copies unchanged. No cross-layer directory deduplication.'
    known, total_entries, total_tar, max_file = {}, 0, 0, 0
    chain = None
    try:
        for index, (desc, diff) in enumerate(zip(manifest['layers'], diffs)):
            floors = space()
            need(desc['mediaType'] in ('application/vnd.oci.image.layer.v1.tar+gzip', 'application/vnd.docker.image.rootfs.diff.tar.gzip'), 'gzip_only')
            need(0 < desc['size'] <= 512 * CHUNK and re.fullmatch(r'sha256:[0-9a-f]{64}', diff), 'descriptor_bounds')
            counts = dict(file=0, directory=0, hardlink=0, symlink=0, special=0, sparse=0)
            entries = regular = links = unknown = parents = apparent = 0
            directories, directory_chars = set(), 0
            with request(base + '/blobs/' + desc['digest'], headers) as response:
                compressed = Reader(response, desc['size'])
                with gzip.GzipFile(fileobj=compressed) as gzip_stream:
                    expanded = Reader(gzip_stream, CAP)
                    with tarfile.open(fileobj=expanded, mode='r|', stream=True, encoding='utf8', errors='surrogateescape') as tar:
                        for member in tar:
                            entries += 1
                            need(entries <= 200000 and len(member.name) <= 4096 and len(member.linkname) <= 4096 and 0 <= member.size <= CAP, 'member_limits')
                            need(sum(len(k) + len(v) for k, v in member.pax_headers.items()) <= CHUNK, 'pax_limits')
                            path = posixpath.normpath(member.name).lstrip('/')
                            need('..' not in path.split('/'), 'bounded_member_path')
                            parents += path.count('/')
                            if revision == 'r2':
                                # Scope deliberately resets for every layer: overlay
                                # directory copy-ups cannot be deduplicated globally.
                                directory = path if member.isdir() else posixpath.dirname(path)
                                while directory not in ('', '.'):
                                    if directory not in directories:
                                        directories.add(directory)
                                        directory_chars += len(directory)
                                    need(len(directories) <= 400000 and directory_chars <= 32 * CHUNK, 'bounded_unique_directory_metadata')
                                    directory = posixpath.dirname(directory)
                            kind = 'file' if member.isfile() else 'directory' if member.isdir() else 'hardlink' if member.islnk() else 'symlink' if member.issym() else 'special'
                            counts[kind] += 1
                            apparent += member.size
                            need(apparent <= CAP, 'logical_layer_cap')
                            if member.isfile():
                                size = rounded(member.size)
                                regular += size
                                max_file = max(max_file, size)
                                known[path] = max(known.get(path, 0), size)
                                counts['sparse'] += bool(member.sparse)
                            elif member.islnk():
                                target = posixpath.normpath(member.linkname).lstrip('/')
                                if target in known:
                                    size = known[target]
                                    links += size
                                    known[path] = max(known.get(path, 0), size)
                                else:
                                    unknown += 1
                            need(len(known) <= 400000, 'bounded_path_map')
                    while expanded.read(CHUNK):
                        pass
                while compressed.read(CHUNK):
                    pass
            need(compressed.bytes == desc['size'] and 'sha256:' + compressed.hash.hexdigest() == desc['digest'], 'compressed_integrity')
            need('sha256:' + expanded.hash.hexdigest() == diff, 'diffID_integrity')
            total_entries += entries
            total_tar += expanded.bytes
            need(total_entries <= 400000 and total_tar <= 8 * 1024**3, 'image_limits')
            chain = diff if chain is None else 'sha256:' + hashlib.sha256((chain + ' ' + diff).encode()).hexdigest()
            result['layers'].append({'index': index, 'digest': desc['digest'], 'diffID': diff, 'chainID': chain,
                'compressedBytes': compressed.bytes, 'uncompressedTarBytes': expanded.bytes, 'regularBlockRoundedBytes': regular,
                'knownHardlinkCopyBytes': links, 'unknownHardlinks': unknown, 'memberCounts': counts, 'members': entries,
                'metadataAllowanceBytes': (entries + parents) * 8192, 'storageBefore': floors, 'hashesVerified': True})
            if revision == 'r2':
                result['layers'][-1].update(ancestorOccurrences=parents, uniqueLayerDirectories=len(directories),
                    originalDirectoryAllowanceBytes=parents * 8192, revisedDirectoryAllowanceBytes=len(directories) * 8192,
                    revisedMetadataAllowanceBytes=(entries + len(directories)) * 8192)
            print(json.dumps({'image': name, 'layer': index, 'compressedBytes': compressed.bytes, 'tarBytes': expanded.bytes}), flush=True)
        cumulative = 0
        for layer in result['layers']:
            layer['hardlinkCopyUpperBytes'] = layer['knownHardlinkCopyBytes'] + layer['unknownHardlinks'] * max_file
            layer['unpackedUpperBytes'] = max(layer['uncompressedTarBytes'], layer['regularBlockRoundedBytes']) + layer['hardlinkCopyUpperBytes'] + layer['metadataAllowanceBytes']
            cumulative += layer['unpackedUpperBytes']
            layer['cumulativeUnpackedUpperBytes'] = cumulative
        result.update(status='completed', compressedBytes=sum(x['compressedBytes'] for x in result['layers']),
                      uncompressedTarBytes=total_tar, unpackedUpperBytes=cumulative, largestRegularFileBytes=max_file)
        result['wholeImageStagingUpperBytes'] = result['compressedBytes'] + cumulative + 16 * CHUNK
        if revision == 'r2':
            original_raw = (B / (name + '-measurement.json')).read_bytes()
            original = json.loads(original_raw)
            need(original['status'] == 'completed' and len(original['layers']) == len(result['layers']), 'original_completed_layer_count')
            invariant_keys = ['index', 'digest', 'diffID', 'chainID', 'compressedBytes', 'uncompressedTarBytes',
                              'regularBlockRoundedBytes', 'knownHardlinkCopyBytes', 'unknownHardlinks', 'memberCounts',
                              'members', 'metadataAllowanceBytes', 'hardlinkCopyUpperBytes', 'unpackedUpperBytes',
                              'cumulativeUnpackedUpperBytes']
            revised_cumulative = 0
            for old, layer in zip(original['layers'], result['layers']):
                need(all(old[k] == layer[k] for k in invariant_keys), 'original_layer_measurement_reproduced')
                layer['revisedUnpackedUpperBytes'] = layer['unpackedUpperBytes'] - layer['metadataAllowanceBytes'] + layer['revisedMetadataAllowanceBytes']
                revised_cumulative += layer['revisedUnpackedUpperBytes']
                layer['revisedCumulativeUnpackedUpperBytes'] = revised_cumulative
            need(all(original[k] == result[k] for k in ['compressedBytes', 'uncompressedTarBytes', 'unpackedUpperBytes', 'wholeImageStagingUpperBytes']), 'original_aggregate_reproduced')
            result.update(originalMeasurementSHA256=hashlib.sha256(original_raw).hexdigest(), originalMeasurementsReproduced=True,
                          revisedUnpackedUpperBytes=revised_cumulative,
                          revisedWholeImageStagingUpperBytes=result['compressedBytes'] + revised_cumulative + 16 * CHUNK)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        save(name + ('-r2' if revision == 'r2' else '') + '-measurement.json', result)


if __name__ == '__main__':
    main()
