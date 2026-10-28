#!/usr/bin/env python3
"""Fetch a fresh pinned public database generation; preserve every old generation."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request

BASE = Path('/home/brajam/.local/share/branconet-migration')
GIB = 1024 ** 3
PINS = {
    'db': {'repository': 'aquasec/trivy-db', 'schema': 2, 'database': 'trivy.db',
           'manifest': '452d17eef654f98231ca8a6d2878566f2c9baf27f65cd981066d605f4d106da7',
           'blob': '5ca9e0f4a3c4348fcabecb2444da33564a613cf5ffcb8f794160f82f5f4dca17', 'blob_bytes': 135962259,
           'media': 'application/vnd.aquasec.trivy.db.layer.v1.tar+gzip'},
    'java-db': {'repository': 'aquasec/trivy-java-db', 'schema': 1, 'database': 'trivy-java.db',
           'manifest': '9dc2c050bad276d40ab60712b47c9aefeb049786be538a116011ae6fbe9710ec',
           'blob': '477155def438f883e43c0b4256ac30b005690774fbbcd5d756b381aa4c6f2acf', 'blob_bytes': 988455878,
           'media': 'application/vnd.aquasec.trivy.javadb.layer.v1.tar+gzip'},
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 ** 2), b''):
            h.update(block)
    return h.hexdigest()


class TLSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        need(url.scheme == 'https' and url.hostname in ['mirror.gcr.io', 'storage.googleapis.com'] and
             url.port in [None, 443] and url.username is None and url.password is None, 'public_blob_redirect_scope')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--run-id', required=True)
    a = parser.parse_args()
    need(a.apply and os.getuid() == 1000 and re.fullmatch('[0-9a-f]{32}', a.run_id), 'explicit_local_operator')
    os.umask(0o077)
    unit = 'branconet-trivy-db-refresh-' + a.run_id + '.service'
    cgroup = Path('/proc/self/cgroup').read_text().strip()
    need(cgroup.startswith('0::/user.slice/user-1000.slice/') and cgroup.endswith('/' + unit), 'actual_owned_unit')
    cg = Path('/sys/fs/cgroup') / cgroup.split('::', 1)[1].lstrip('/')
    actual = {n: (cg / n).read_text().strip() for n in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    quota, period = actual['cpu.max'].split()
    need(actual['memory.max'] == str(GIB) and actual['memory.swap.max'] == '0' and
         quota != 'max' and int(quota) <= 2 * int(period) and actual['pids.max'] == '128' and
         os.getpriority(os.PRIO_PROCESS, 0) == 10, 'actual_resource_limits')
    need(BASE.resolve() == BASE and stat.S_IMODE(BASE.stat().st_mode) & 0o002 == 0, 'operator_base')
    root = BASE / ('trivy-db-generation-20261024-' + a.run_id)
    root.mkdir(mode=0o700)
    for name in ['raw', 'cache', 'cache/db', 'cache/java-db']:
        (root / name).mkdir(mode=0o700)
    started = time.monotonic(); capacity_samples = []
    receipt = {'schemaVersion': 1, 'sourceKind': 'public-oci-databases', 'runID': a.run_id,
               'state': 'downloading', 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'unit': unit, 'actualCgroup': cgroup, 'resourceLimits': actual,
               'helperSHA256': digest(Path(__file__).resolve()), 'pins': PINS,
               'oldGenerationsChanged': False, 'productionClusterChanged': False, 'files': {}}
    def save():
        path = root / 'receipt.json'; temporary = root / 'receipt.partial.json'
        with temporary.open('w') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
        temporary.chmod(0o600); temporary.replace(path)
    def capacity(initial=False):
        v = os.statvfs(root); w = os.statvfs('/mnt/c')
        required = (10 if initial else 2) * GIB
        need(v.f_bavail * v.f_frsize >= required and w.f_bavail * w.f_frsize >= required and
             v.f_favail >= v.f_files // 10 and time.monotonic() - started < 1150, 'physical_logical_capacity_or_deadline')
        allocated = 0
        for folder, dirs, files in os.walk(root):
            for name in files:
                info = (Path(folder) / name).lstat()
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'owned_output_special_file')
                allocated += info.st_blocks * 512
        need(allocated <= 8 * GIB, 'fresh_generation_allocation_bound')
        sample = {'elapsedSeconds': round(time.monotonic() - started, 3), 'nativeAvailableBytes': v.f_bavail * v.f_frsize,
                  'physicalCAvailableBytes': w.f_bavail * w.f_frsize, 'allocatedBytes': allocated}
        need(len(capacity_samples) < 2000, 'capacity_observation_bound'); capacity_samples.append(sample)
    save()
    try:
        mounts = json.loads(subprocess.run(['findmnt', '--json', '--target', '/mnt/c', '--output', 'SOURCE,FSTYPE,TARGET'],
                            capture_output=True, text=True, check=True, timeout=15).stdout)['filesystems']
        need(mounts == [{'source': 'C:\\', 'fstype': '9p', 'target': '/mnt/c'}], 'physical_C_mount_binding')
        native = json.loads(subprocess.run(['findmnt', '--json', '--target', '/', '--output', 'UUID,FSTYPE'],
                            capture_output=True, text=True, check=True, timeout=15).stdout)['filesystems']
        need(native == [{'uuid': 'de6eee3d-80cf-41dc-bf4c-91ee606d02da', 'fstype': 'ext4'}], 'native_root_binding')
        capacity(True)
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}), TLSOnly())
        for name, pin in PINS.items():
            prefix = 'https://mirror.gcr.io/v2/' + pin['repository']
            url = prefix + '/manifests/sha256:' + pin['manifest']
            with client.open(urllib.request.Request(url, headers={'Accept': 'application/vnd.oci.image.manifest.v1+json'}), timeout=30) as response:
                data = response.read(2 * 1024 ** 2 + 1)
                need(response.status == 200 and response.url == url and len(data) <= 2 * 1024 ** 2 and
                     hashlib.sha256(data).hexdigest() == pin['manifest'] and
                     response.headers.get('Docker-Content-Digest') == 'sha256:' + pin['manifest'], 'immutable_manifest')
            manifest = json.loads(data)
            layers = manifest['layers']
            need(manifest.get('schemaVersion') == 2 and len(layers) == 1 and
                 layers[0]['digest'] == 'sha256:' + pin['blob'] and layers[0]['size'] == pin['blob_bytes'] and
                 layers[0]['mediaType'] == pin['media'] and manifest['config'] == {
                    'mediaType': 'application/vnd.oci.empty.v1+json', 'digest': 'sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a',
                    'size': 2, 'data': 'e30='}, 'database_OCI_binding')
            (root / 'raw' / (name + '-manifest.json')).write_bytes(data)
            blob = root / 'raw' / (name + '.tar.gz')
            h = hashlib.sha256(); count = 0; last = time.monotonic()
            with client.open(prefix + '/blobs/sha256:' + pin['blob'], timeout=30) as response, blob.open('xb') as out:
                need(response.status == 200 and int(response.headers['Content-Length']) == pin['blob_bytes'], 'blob_status_size')
                for block in iter(lambda: response.read(1024 ** 2), b''):
                    count += len(block); need(count <= pin['blob_bytes'], 'blob_stream_bound')
                    out.write(block); h.update(block)
                    if time.monotonic() - last > 2:
                        capacity(); last = time.monotonic()
                out.flush(); os.fsync(out.fileno())
            need(count == pin['blob_bytes'] and h.hexdigest() == pin['blob'] and digest(blob) == pin['blob'], 'complete_blob_SHA256')
            expected = {pin['database'], 'metadata.json'}; seen = set(); expanded = 0
            with gzip.open(blob, 'rb') as uncompressed:
                with tarfile.open(fileobj=uncompressed, mode='r|') as archive:
                    for member in archive:
                        filename = member.name.removeprefix('./')
                        need(filename in expected and filename not in seen and member.isfile() and
                             not member.issym() and not member.islnk() and 0 < member.size <= (65536 if filename == 'metadata.json' else 4 * GIB), 'exact_database_tar_member')
                        seen.add(filename); expanded += member.size; need(expanded <= 4 * GIB, 'expanded_database_bound')
                        target = root / 'cache' / name / filename; stream = archive.extractfile(member)
                        with target.open('xb') as out:
                            copied = 0
                            for block in iter(lambda: stream.read(1024 ** 2), b''):
                                copied += len(block); need(copied <= member.size, 'expanded_stream_bound'); out.write(block)
                                if time.monotonic() - last > 2:
                                    capacity(); last = time.monotonic()
                            out.flush(); os.fsync(out.fileno())
                        need(copied == member.size, 'expanded_size')
                        receipt['files'][name + '/' + filename] = {'bytes': member.size, 'sha256': digest(target)}
                padding = 0
                for block in iter(lambda: uncompressed.read(1024 ** 2), b''):
                    padding += len(block); need(padding <= 1024 ** 2 and not any(block), 'gzip_footer_or_trailing_payload')
            need(seen == expected, 'complete_database_archive')
            metadata = json.loads((root / 'cache' / name / 'metadata.json').read_bytes())
            need(metadata.get('Version') == pin['schema'], 'database_schema')
            updated = re.sub(r'(\.\d{6})\d+(?=[+-]|$)', r'\1', metadata['UpdatedAt'].replace('Z', '+00:00'))
            age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(updated)).total_seconds() / 3600
            need(0 <= age <= (24 if name == 'db' else 168), 'fresh_database_age')
            receipt[name + 'Metadata'] = metadata; receipt[name + 'AgeHours'] = age
            capacity(); save()
        need(digest(Path(__file__).resolve()) == receipt['helperSHA256'], 'helper_changed')
        receipt.update(state='verified-new-generation-not-staged-not-scanned', completedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), capacitySamples=capacity_samples)
        save()
        for path in root.rglob('*'):
            if path.is_file():
                path.chmod(0o400)
        print(json.dumps({'state': receipt['state'], 'root': str(root), 'receiptSHA256': digest(root / 'receipt.json'), 'files': receipt['files'], 'databaseMetadata': receipt['dbMetadata']}))
    except Exception as error:
        receipt.update(state='failed-originals-and-partial-generation-retained', errorCategory=str(error) if type(error) is ValueError else type(error).__name__, completedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), capacitySamples=capacity_samples)
        save()
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Fresh database generation refused; raw URLs and diagnostics withheld (' + type(error).__name__ + ')')
