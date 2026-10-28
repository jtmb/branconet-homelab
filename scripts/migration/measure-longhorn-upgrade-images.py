"""Measure pinned public OCI layers in RAM; never pull, unpack or prune on nodes."""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
B = O / 'longhorn-capacity-budget'
FLOOR = 15 * 1024**3
CHUNK = 1024**2
START = time.monotonic()
MAX_COMPRESSED = 2 * 1024**3
MAX_UNCOMPRESSED = 8 * 1024**3


def need(value, reason):
    if not value:
        raise ValueError(reason)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(name, value):
    with (B / name).open('x') as out:
        json.dump(value, out, indent=2)
        out.flush()
        os.fsync(out.fileno())


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        need(urllib.parse.urlsplit(url).scheme == 'https', 'https_redirect_only')
        redirected = super().redirect_request(request, fp, code, msg, headers, url)
        if urllib.parse.urlsplit(request.full_url).netloc != urllib.parse.urlsplit(url).netloc:
            redirected.remove_header('Authorization')
        return redirected


OPENER = urllib.request.build_opener(Redirect())


def request(url, headers=None):
    need(time.monotonic() - START < 1100, 'bounded_measurement_deadline')
    need(urllib.parse.urlsplit(url).scheme == 'https', 'https_source_only')
    return OPENER.open(urllib.request.Request(url, headers=headers or {}), timeout=45)


def small(url, expected=None, headers=None):
    with request(url, headers) as response:
        raw = response.read(4 * CHUNK + 1)
    need(len(raw) <= 4 * CHUNK and (expected is None or digest(raw) == expected), 'bounded_authenticated_metadata')
    return json.loads(raw)


class Reader:
    def __init__(self, source, maximum):
        self.source, self.maximum = source, maximum
        self.bytes, self.hash = 0, hashlib.sha256()

    def read(self, count=-1):
        # Gzip and TAR stream readers only require bounded forward reads.
        need(0 <= count <= CHUNK, 'bounded_forward_read')
        data = self.source.read(count)
        self.bytes += len(data)
        need(self.bytes <= self.maximum and time.monotonic() - START < 1100, 'layer_stream_bound_or_deadline')
        self.hash.update(data)
        return data


def layer(repository, descriptor, diff_id, headers):
    need(descriptor['mediaType'] in ('application/vnd.oci.image.layer.v1.tar+gzip',
                                   'application/vnd.docker.image.rootfs.diff.tar.gzip'), 'gzip_layer_only')
    need(0 < descriptor['size'] <= MAX_COMPRESSED and re.fullmatch(r'sha256:[0-9a-f]{64}', descriptor['digest']), 'bounded_layer_descriptor')
    url = 'https://registry-1.docker.io/v2/' + repository + '/blobs/' + descriptor['digest']
    counts = {'file': 0, 'directory': 0, 'symlink': 0, 'hardlink': 0, 'special': 0}
    apparent, projected, entries = 0, 0, 0
    with request(url, headers) as response:
        compressed = Reader(response, descriptor['size'])
        with gzip.GzipFile(fileobj=compressed, mode='rb') as expanded:
            uncompressed = Reader(expanded, MAX_UNCOMPRESSED)
            with tarfile.open(fileobj=uncompressed, mode='r|', stream=True, encoding='utf8', errors='surrogateescape') as archive:
                for member in archive:
                    entries += 1
                    need(entries <= 200000 and len(member.name) <= 4096 and 0 <= member.size <= MAX_UNCOMPRESSED,
                         'bounded_tar_metadata')
                    kind = ('file' if member.isfile() else 'directory' if member.isdir() else
                            'symlink' if member.issym() else 'hardlink' if member.islnk() else 'special')
                    counts[kind] += 1
                    apparent += member.size
                    # Sum every layer's additions without credit for deletion,
                    # replacement, hardlink sharing or cached parent snapshots.
                    # Add two filesystem blocks per entry for inode/directory/
                    # attribute overhead. This is a conservative projection,
                    # not an observed containerd allocation.
                    projected += ((member.size + 4095) // 4096) * 4096 + 8192
                    need(apparent <= MAX_UNCOMPRESSED, 'tar_apparent_byte_bound')
            while uncompressed.read(CHUNK):
                pass
        while compressed.read(CHUNK):
            pass
    need(compressed.bytes == descriptor['size'] and 'sha256:' + compressed.hash.hexdigest() == descriptor['digest'],
         'complete_compressed_layer_hash')
    need('sha256:' + uncompressed.hash.hexdigest() == diff_id, 'complete_uncompressed_diff_id')
    return {'digest': descriptor['digest'], 'diffID': diff_id, 'compressedBytes': compressed.bytes,
            'uncompressedTarBytes': uncompressed.bytes, 'apparentMemberBytes': apparent,
            'tarEntries': entries, 'memberCounts': counts, 'projectedFilesystemBytes': projected,
            'compressedHashVerified': True, 'uncompressedHashVerified': True, 'payloadSavedToDisk': False}


def main():
    need(sys.version_info >= (3, 13), 'streaming_tar_metadata_runtime')
    need(B.is_dir() and B.resolve() == B and os.geteuid() == 1000, 'existing_owned_measurement_root')
    filesystem = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(B), '-o', 'UUID,FSTYPE'], timeout=15))['filesystems'][0]
    need(filesystem['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b'
         and filesystem['fstype'] == 'ext4', 'original_physical_output_filesystem')
    need(os.environ.get('TMPDIR') == str(B / 'tmp') and (B / 'tmp').is_dir(), 'owned_temporary_path')
    # Windows is hidden by the isolated job; its actual free space is recorded
    # immediately before launch. Here check the real bound ext4 destination.
    space = os.statvfs(B)
    need(space.f_bavail * space.f_frsize >= FLOOR + 8 * CHUNK, 'fifteen_GiB_after_metadata_stage')
    group = Path('/proc/self/cgroup').read_text().strip()
    need(group.startswith('0::/system.slice/branconet-longhorn-capacity-'), 'owned_measured_job')
    cg = Path('/sys/fs/cgroup') / group.split('::', 1)[1].lstrip('/')
    limits = {key: (cg / key).read_text().strip() for key in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    quota, period = limits['cpu.max'].split()
    need(limits['memory.max'] == '536870912' and limits['memory.swap.max'] == '0'
         and limits['pids.max'] == '64' and quota != 'max' and int(quota) <= int(period), 'actual_resource_limits')
    need(not os.access('/home/brajam/.ssh', os.R_OK | os.X_OK)
         and not os.access('/mnt/c/Users', os.R_OK | os.X_OK), 'credentials_and_windows_hidden')
    save('execution-context.json', {'cgroup': group, 'limits': limits, 'filesystem': filesystem,
                                   'availableBeforeBytes': space.f_bavail * space.f_frsize,
                                   'credentialsHidden': True, 'payloadWrittenToDisk': False,
                                   'pythonVersion': sys.version})
    candidates_raw = (O / 'longhorn-1.13.0-candidates.json').read_bytes()
    candidates = json.loads(candidates_raw)
    need(len(candidates['images']) == 14 and sum(row['compressedLayerBytes'] for row in candidates['images']) <= MAX_COMPRESSED
         and candidates['officialManifestSHA256'] ==
         'd0f99488e7b2789312d45b0127ce7388df71a971e6fca2085e88635303cc0a1f', 'reviewed_candidate_set')
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {'schema': 1, 'status': 'started', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': source_hash, 'candidateMetadataSHA256': hashlib.sha256(candidates_raw).hexdigest(),
              'images': [], 'clusterMutated': False, 'imagePayloadSavedToDisk': False,
              'projectionIsNativeUnpackMeasurement': False}
    measured = {}
    try:
        for row in candidates['images']:
            match = re.fullmatch(r'docker.io/(longhornio/([a-z0-9-]+)):[^@]+@(sha256:[0-9a-f]{64})', row['reference'])
            need(match, 'reviewed_public_longhorn_repository')
            repository, component, index_digest = match.groups()
            token = small('https://auth.docker.io/token?' + urllib.parse.urlencode(
                {'service': 'registry.docker.io', 'scope': 'repository:' + repository + ':pull'}))['token']
            headers = {'Authorization': 'Bearer ' + token,
                       'Accept': 'application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json'}
            base = 'https://registry-1.docker.io/v2/' + repository
            index = small(base + '/manifests/' + index_digest, index_digest, headers)
            matches = [x for x in index.get('manifests', []) if x.get('platform', {}).get('os') == 'linux'
                       and x.get('platform', {}).get('architecture') == 'amd64']
            need(len(matches) == 1 and matches[0]['digest'] == row['amd64ManifestDigest'], 'pinned_index_to_amd64')
            manifest = small(base + '/manifests/' + row['amd64ManifestDigest'], row['amd64ManifestDigest'], headers)
            need(sum(x['size'] for x in manifest['layers']) == row['compressedLayerBytes'], 'reviewed_total_transfer_bound')
            need(manifest['config']['digest'] == row['configurationDigest'], 'pinned_configuration')
            configuration = small(base + '/blobs/' + row['configurationDigest'], row['configurationDigest'], headers)
            need(configuration['architecture'] == 'amd64' and configuration['os'] == 'linux'
                 and len(configuration['rootfs']['diff_ids']) == len(manifest['layers']), 'platform_and_layer_chain')
            retained_raw = (O / (component + '-metadata.json')).read_bytes()
            retained = json.loads(retained_raw)
            need(retained['manifest'] == manifest and retained['configuration'] == configuration
                 and retained['rootDigest'] == index_digest, 'retained_reviewed_image_unchanged')
            rows = []
            for descriptor, diff_id in zip(manifest['layers'], configuration['rootfs']['diff_ids']):
                key = descriptor['digest']
                if key not in measured:
                    value = layer(repository, descriptor, diff_id, headers)
                    save('layer-' + key[7:] + '.json', value)
                    measured[key] = value
                need(measured[key]['diffID'] == diff_id, 'shared_layer_identity')
                rows.append(measured[key])
            image = {'reference': row['reference'], 'metadataSHA256': hashlib.sha256(retained_raw).hexdigest(),
                     'amd64ManifestDigest': row['amd64ManifestDigest'], 'configurationDigest': row['configurationDigest'],
                     'layers': rows, 'compressedBytes': sum(x['compressedBytes'] for x in rows),
                     'projectedFilesystemBytes': sum(x['projectedFilesystemBytes'] for x in rows)}
            result['images'].append(image)
            save('image-' + component + '.json', image)
            print(json.dumps({'event': 'image_measured', 'component': component,
                              'compressedBytes': image['compressedBytes'],
                              'projectedFilesystemBytes': image['projectedFilesystemBytes']}), flush=True)
        need(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == source_hash, 'executed_source_unchanged')
        result.update(status='completed', uniqueLayers=len(measured),
                      uniqueCompressedBytes=sum(x['compressedBytes'] for x in measured.values()),
                      uniqueProjectedFilesystemBytes=sum(x['projectedFilesystemBytes'] for x in measured.values()),
                      allLayersFullyAuthenticated=True)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        save('measurement-result.json', result)


if __name__ == '__main__':
    main()
