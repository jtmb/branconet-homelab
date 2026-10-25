"""Import only sealed maintenance application OCI artifacts into the K8s cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile

CTR = ['/opt/containerd-k8s/bin/ctr', '--address', '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']
BASE = Path('/home/james/.local/share/branconet-migration')
NAMES = {'seerr': 'docker.io/library/seerr-security-20261023',
         'ytptube': 'docker.io/library/ytptube-security-20261023',
         'jackett': 'docker.io/library/jackett-security-20261023',
         'pihole': 'docker.io/library/pihole-security-20261023',
         'flaresolverr': 'docker.io/library/flaresolverr-security-20261023',
         'vaultwarden': 'docker.io/library/vaultwarden-security-20261023',
         'tautulli': 'docker.io/library/tautulli-security-20261023',
         'wordpress': 'docker.io/library/wordpress-security-20261023',
         'nginx': 'docker.io/library/nginx-security-20261023',
         'phpmyadmin': 'docker.io/library/phpmyadmin-security-20261023',
         'coredns': 'docker.io/library/coredns-security-20261023',
         'plex': 'docker.io/library/plex-security-20261023',
         'unpackerr': 'docker.io/library/unpackerr-security-20261023',
         'homepage': 'docker.io/library/homepage-security-20261023',
         'http-echo': 'docker.io/library/http-echo-security-20261023',
         'qbittorrent-current': 'docker.io/library/qbittorrent-current-security-20261023',
         'pihole-exporter': 'docker.io/library/pihole-exporter-security-20261023',
         'mealie': 'docker.io/library/mealie-security-20261023',
         'qbit-monitor': 'docker.io/library/qbit-monitor-security-20261023',
         'xteve': 'docker.io/library/xteve-security-20261023',
         'ruckusdb': 'docker.io/library/ruckusdb-security-20261023',
         'jtmb-dev': 'docker.io/library/jtmb-dev-security-20261023',
         'ruckus-bot': 'docker.io/library/ruckus-bot-security-20261023'}
MEDIA = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.oci.image.index.v1+json',
         'application/vnd.docker.distribution.manifest.v2+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}


def sha256_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def invoke(arguments, timeout=60):
    result = subprocess.run(CTR + arguments, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Independent image-cache operation failed; raw output withheld')
    return result.stdout


def image_map():
    rows = invoke(['images', 'list']).decode().splitlines()
    return {parts[0]: parts[2] for row in rows if len(parts := row.split()) >= 3 and parts[2].startswith('sha256:')}


def archive_descriptor(archive, expected):
    with tarfile.open(archive, mode='r:') as bundle:
        names = [m.name for m in bundle.getmembers()]
        if len(names) != len(set(names)) or 'manifest.json' in names:
            raise ValueError('Only an unambiguous OCI archive is accepted')
        layout = json.load(bundle.extractfile('oci-layout'))
        if layout.get('imageLayoutVersion') != '1.0.0':
            raise ValueError('Unexpected OCI layout')
        index_file = bundle.getmember('index.json')
        if index_file.size > 4 * 1024 * 1024:
            raise ValueError('OCI index is oversized')
        index = json.load(bundle.extractfile(index_file))
        descriptors = index.get('manifests', [])
        selected = [d for d in descriptors if d.get('digest') == expected and d.get('mediaType') in MEDIA]
        if len(selected) != 1:
            raise ValueError('Expected immutable image/index descriptor is not unique in the OCI root index')
        member = bundle.getmember('blobs/sha256/' + expected[7:])
        if member.size > 4 * 1024 * 1024:
            raise ValueError('Expected descriptor is oversized')
        blob = bundle.extractfile(member).read()
        if 'sha256:' + hashlib.sha256(blob).hexdigest() != expected or len(blob) != selected[0]['size']:
            raise ValueError('Expected manifest/index bytes do not match their descriptor')
        return descriptors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', choices=sorted(NAMES), required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--manifest-digest', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch('[0-9a-f]{64}', args.archive_sha256) or not re.fullmatch('sha256:[0-9a-f]{64}', args.manifest_digest):
        raise ValueError('Root and exact public artifact digests are required')
    path = args.archive
    if not path.is_absolute() or path.resolve() != path or BASE not in path.parents:
        raise ValueError('Archive must be a real protected per-node operator path')
    for target in (path, path.parent):
        info = target.stat()
        if info.st_uid not in (0, 1000) or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('Archive and containing directory must be protected owner-only inputs')
    if not path.is_file() or sha256_file(path) != args.archive_sha256:
        raise ValueError('Archive checksum mismatch')
    name = NAMES[args.service]
    alias = name + '@' + args.manifest_digest
    descriptors = archive_descriptor(path, args.manifest_digest)
    before = image_map()
    prospective = {name + '@' + d['digest']: d['digest'] for d in descriptors if d.get('mediaType') in MEDIA}
    for descriptor in descriptors:
        for key in ('io.containerd.image.name', 'org.opencontainers.image.ref.name'):
            candidate = descriptor.get('annotations', {}).get(key, '')
            if candidate.startswith(name):
                prospective[candidate] = descriptor['digest']
    for candidate, digest in prospective.items():
        if candidate in before and before[candidate] != digest:
            raise ValueError('An existing image alias differs; replacement is forbidden')
    # --local uses the reviewed ctr import implementation. The explicit base-name
    # filters named foreign references; --digests creates only this app's aliases.
    # All platform content is cached; unpacking is deferred to actual runtime QA.
    invoke(['images', 'import', '--local', '--all-platforms', '--no-unpack', '--digests',
            '--base-name', name, '--label', 'io.cri-containerd.image=managed', str(path)], timeout=1800)
    after = image_map()
    if after.get(alias) != args.manifest_digest:
        raise ValueError('Exact immutable local alias is absent after import')
    if any(after.get(key) != value for key, value in before.items()):
        raise ValueError('An existing image identity changed; stop and preserve evidence')
    if any(not key.startswith(name + '@') and key not in prospective for key in after.keys() - before.keys()):
        raise ValueError('An unexpected image alias was created; stop and preserve evidence')
    blob = invoke(['content', 'get', args.manifest_digest])
    if 'sha256:' + hashlib.sha256(blob).hexdigest() != args.manifest_digest:
        raise ValueError('Cached manifest/index content differs')
    print(json.dumps({'changed': after != before, 'service': args.service, 'archive_sha256': args.archive_sha256,
                      'image': alias, 'manifest_digest': args.manifest_digest,
                      'namespace': 'k8s.io', 'socket': '/run/containerd-k8s/containerd.sock',
                      'verified_present': True, 'unpacked': False, 'application_started': False}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) else 'Preflight or cache operation failed; raw output withheld'
        print(json.dumps({'state': 'refused', 'error_type': type(error).__name__, 'reason': reason}))
        raise SystemExit(1)
