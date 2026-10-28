"""Authenticate the host-installed engine payload without saving image layers."""
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tarfile
import urllib.parse

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
B = F / 'platform-upstream-review-20261027/longhorn-capacity-budget'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    need(os.geteuid() == 1000 and F.is_mount(), 'original_owner_and_filesystem')
    cg = Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1].lstrip('/')
    need(cg.name == 'branconet-longhorn-host-payload-20261028.service', 'exact_bounded_worker')
    limits = {x: (cg / x).read_text().strip() for x in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    quota, period = limits['cpu.max'].split()
    need(limits['memory.max'] == '536870912' and limits['memory.swap.max'] == '0'
         and limits['pids.max'] == '64' and quota != 'max' and int(quota) <= int(period), 'actual_resource_limits')
    need(not os.access('/home/brajam/.ssh', os.R_OK) and not os.access('/mnt/c/Users', os.R_OK), 'credentials_and_windows_hidden')
    measured = json.loads((B / 'measurement-result.json').read_text())
    source = B / 'measure-images-frozen.py'
    need(sha(source) == measured['sourceSHA256'] and measured['allLayersFullyAuthenticated'], 'original_authenticated_reader_and_measurement')
    spec = importlib.util.spec_from_file_location('original_public_layer_reader', source)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    original = json.loads((B / 'image-longhorn-engine.json').read_text())
    metadata = B.parent / 'longhorn-engine-metadata.json'
    need(sha(metadata) == original['metadataSHA256'], 'exact_pinned_original_image')
    image = json.loads(metadata.read_text())
    layers = image['manifest']['layers']
    diffs = image['configuration']['rootfs']['diff_ids']
    need(layers[5]['digest'] == 'sha256:8af4fdabeeb48d827aa9a70fddae38d78b86dcfef5656c18787c01e8c89049b6', 'original_engine_binary_layer')
    url = 'https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.13.0/controller/engine_image_controller.go'
    with m.request(url) as response:
        manager_source = response.read(256 * 1024 + 1)
    need(len(manager_source) <= 256 * 1024 and b'cp -p /usr/local/bin/longhorn /data/' in manager_source,
         'official_host_install_command_copies_the_longhorn_binary')
    token = m.small('https://auth.docker.io/token?' + urllib.parse.urlencode(
        {'service': 'registry.docker.io', 'scope': 'repository:longhornio/longhorn-engine:pull'}))['token']
    headers = {'Authorization': 'Bearer ' + token}
    result = {'status': 'started', 'sourceSHA256': sha(Path(__file__)),
              'originalReaderSHA256': sha(source), 'metadataSHA256': sha(metadata),
              'officialInstallSource': url, 'officialInstallSourceSHA256': hashlib.sha256(manager_source).hexdigest(),
              'resourceLimits': limits, 'layers': [], 'payloadWrittenToDisk': False,
              'nodesChanged': False, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    host = None
    try:
        for index in range(5, len(layers)):
            descriptor = layers[index]
            entries = []
            with m.request('https://registry-1.docker.io/v2/longhornio/longhorn-engine/blobs/' + descriptor['digest'], headers) as response:
                compressed = m.Reader(response, descriptor['size'])
                with gzip.GzipFile(fileobj=compressed, mode='rb') as expanded:
                    raw = m.Reader(expanded, 256 * 1024**2)
                    with tarfile.open(fileobj=raw, mode='r|', stream=True) as archive:
                        for member in archive:
                            name = member.name.removeprefix('./').rstrip('/')
                            need(not name.startswith('/') and '..' not in Path(name).parts and len(entries) < 100, 'bounded_safe_public_member')
                            need(member.isfile() or member.isdir(), 'regular_payload_or_directory_only')
                            entries.append({'name': name, 'bytes': member.size, 'type': member.type.decode('ascii')})
                            if name == 'usr/local/bin/longhorn':
                                need(index == 5 and host is None and member.isfile() and 0 < member.size < 64 * 1024**2, 'single_regular_bounded_engine_binary')
                                h, count = hashlib.sha256(), 0
                                with archive.extractfile(member) as body:
                                    first = body.read(64)
                                    need(first[:4] == b'\x7fELF' and first[4:6] == bytes([2, 1]) and int.from_bytes(first[18:20], 'little') == 62, 'amd64_elf_payload')
                                    h.update(first)
                                    count += len(first)
                                    for data in iter(lambda: body.read(1024**2), b''):
                                        count += len(data)
                                        h.update(data)
                                need(count == member.size, 'complete_engine_binary_hash')
                                host = {'pathInImage': name, 'bytes': count, 'sha256': h.hexdigest(), 'mode': member.mode}
                            elif index > 5:
                                need(not name.startswith('usr/local/bin/.wh.') and name not in ('usr/.wh.local', 'usr/local/.wh.bin', 'usr/.wh..wh..opq', 'usr/local/.wh..wh..opq', '.wh.usr', '.wh..wh..opq')
                                     and not (name in ('usr', 'usr/local', 'usr/local/bin') and not member.isdir()), 'later_layers_preserve_the_host_binary_and_ancestors')
                    while raw.read(1024**2):
                        pass
                while compressed.read(1024**2):
                    pass
            need(compressed.bytes == descriptor['size'] and 'sha256:' + compressed.hash.hexdigest() == descriptor['digest']
                 and 'sha256:' + raw.hash.hexdigest() == diffs[index], 'complete_original_compressed_and_diff_hashes')
            result['layers'].append({'digest': descriptor['digest'], 'diffID': diffs[index], 'entries': entries})
        need(host is not None, 'host_payload_present')
        result.update(status='host_engine_payload_authenticated', hostEngine=host,
                      hostAllocationBudgetBytes=64 * 1024**2,
                      hostBudgetIncludesDirectoryAndAllocationOverhead=True)
    except Exception as e:
        result.update(status='failed_preserve_metadata', errorType=type(e).__name__)
        raise
    finally:
        with (B / 'host-engine-payload-result.json').open('x') as out:
            json.dump(result, out, indent=2)
    print(json.dumps({'status': result['status'], 'engineBytes': host['bytes'], 'hostBudgetBytes': result['hostAllocationBudgetBytes']}))


if __name__ == '__main__':
    main()
