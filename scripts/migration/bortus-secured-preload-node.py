#!/usr/bin/env python3
"""Receive only the qualified secured image; no rebuild, deploy or disk archive.

The operator sends one JSON credential envelope, then the verified secured OCI archive.
Archive bytes are hashed and sealed in an anonymous memory file before import.
Only the existing containerd runtime is changed; no credentials are retained.
"""
import fcntl
import hashlib
import json
import os
import pathlib
import select
import subprocess
import sys
import time

SOURCE = '34b8fa18c34576721ff4fb064923f1499598481d'
MANIFEST = 'sha256:e7539b9e79aebe0024f0cfc70dc0a8f2fe89354ab7ffcf9df7a822ffcc343f77'
CONFIG = 'sha256:850c9d016c9bfe04225994d1eff3324bebd8e3ebb7c16f4d49d35ec99de52a80'
ARCHIVE_SHA = '21344ae4891f47adfbf071ed45b4288bc0738d10f8569c4de617d7dfe2f1d983'
ARCHIVE_BYTES = 686269440
# Recorded content + rounded files + per-entry metadata is below 3.62 GB.
# 4 decimal GB bounds import peak without storing a second disk archive.
MAX_IMPORT_BYTES = 973058568
REFERENCE = 'docker.io/jtmb92/bortus@' + MANIFEST
CTR = ['sudo', '-n', '/opt/containerd-k8s/bin/ctr', '--address',
       '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']


def need(ok):
    if not ok:
        raise RuntimeError('qualified_image_preload_failed')


def metadata(args):
    result = subprocess.run(CTR + args, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    need(result.returncode == 0 and len(result.stdout) <= 8 * 1024**2)
    return result.stdout


def content(digest):
    raw = metadata(['content', 'get', digest])
    need('sha256:' + hashlib.sha256(raw).hexdigest() == digest)
    return json.loads(raw)


def image_digest():
    rows = metadata(['images', 'list']).decode().splitlines()
    need(rows and rows[0].split()[:3] == ['REF', 'TYPE', 'DIGEST'])
    matches = [row.split() for row in rows[1:] if row.split() and row.split()[0] == REFERENCE]
    need(len(matches) <= 1)
    return matches[0][2] if matches else None


def ensure_manifest_reference():
    if image_digest() == MANIFEST:
        return
    need(image_digest() is None)
    tagged = 'docker.io/jtmb92/bortus:release-' + SOURCE
    rows = [r.split() for r in metadata(['images', 'list']).decode().splitlines()[1:] if r.split() and r.split()[0] == tagged]
    need(len(rows) == 1 and rows[0][2] == MANIFEST)
    manifest = content(MANIFEST)
    config = content(CONFIG)
    need(manifest['config']['digest'] == CONFIG and len(manifest['layers']) == 19 and config['config']['Labels']['org.opencontainers.image.revision'] == SOURCE)
    need(tagged in metadata(['images', 'check', '--quiet']).decode().splitlines())
    # containerd's --digests creates the OCI index alias, not the child-manifest alias.
    # Bind the already verified named manifest explicitly; no pull or force overwrite.
    metadata(['images', 'tag', tagged, REFERENCE])
    need(image_digest() == MANIFEST)


def verify_runtime():
    need(image_digest() == MANIFEST)
    manifest = content(MANIFEST)
    need(manifest.get('schemaVersion') == 2 and manifest.get('config', {}).get('digest') == CONFIG
         and len(manifest.get('layers', [])) == 19)
    config = content(CONFIG)
    need(config.get('os') == 'linux' and config.get('architecture') == 'amd64'
         and config.get('config', {}).get('Labels', {}).get('org.opencontainers.image.revision') == SOURCE)
    need(REFERENCE in metadata(['images', 'check', '--quiet']).decode().splitlines())
    # The manifest digest binds every layer descriptor; verify actual content bytes too.
    for layer in manifest['layers']:
        process = subprocess.Popen(CTR + ['content', 'get', layer['digest']],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        try:
            hashed, count = hashlib.sha256(), 0
            deadline = time.monotonic() + 300
            while True:
                remaining = deadline - time.monotonic()
                need(remaining > 0 and select.select([process.stdout], [], [], remaining)[0])
                block = os.read(process.stdout.fileno(), 1024 * 1024)
                if not block:
                    break
                count += len(block)
                need(count <= layer['size'])
                hashed.update(block)
            need(process.wait(timeout=30) == 0 and count == layer['size']
                 and 'sha256:' + hashed.hexdigest() == layer['digest'])
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


def receive_archive(source):
    available = next(int(line.split()[1]) * 1024 for line in
                     pathlib.Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    need(available > ARCHIVE_BYTES + 512 * 1024**2)
    fd = os.memfd_create('bortus-qualified-image', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        hashed, count = hashlib.sha256(), 0
        with os.fdopen(os.dup(fd), 'wb') as out:
            while block := source.read(min(1024 * 1024, ARCHIVE_BYTES - count + 1)):
                count += len(block)
                need(count <= ARCHIVE_BYTES)
                hashed.update(block)
                out.write(block)
        need(count == ARCHIVE_BYTES and hashed.hexdigest() == ARCHIVE_SHA)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                    fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd)
        raise


def main():
    need(os.name == 'posix' and os.uname().nodename in ('node01', 'node02', 'node03'))
    raw = sys.stdin.buffer.readline(8193)
    need(len(raw) <= 8192)
    request = json.loads(raw)
    need(set(request) == {'protocol', 'image_reference', 'sudo_password'}
         and request['protocol'] == 'bortus-qualified-preload/v1'
         and request['image_reference'] == REFERENCE)
    password = request.pop('sudo_password')
    need(type(password) is str and 0 < len(password.encode()) <= 4096
         and not any(c in password for c in '\0\r\n'))
    try:
        auth = subprocess.run(['sudo', '-S', '-p', '', '-v'], input=password.encode() + b'\n',
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        need(auth.returncode == 0)
    finally:
        password = None
    # Full source identity is checked even if the exact image is already available.
    fd = receive_archive(sys.stdin.buffer)
    try:
        existing = image_digest()
        need(existing in (None, MANIFEST))
        if existing is None:
            parent_ref = 'docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
            need(parent_ref in metadata(['images', 'check', '--quiet']).decode().splitlines())
            parent = content(parent_ref.split('@')[1])
            need(parent['config']['digest'] == 'sha256:42e3a1a9e6fe5cd3c9912262b0cbeaca9a8cdff7b7b1891392eb100127d84698' and len(parent['layers']) == 9)
            space = os.statvfs('/var/lib/containerd-k8s')
            pressure_floor = (space.f_blocks * space.f_frsize * 15 + 99) // 100
            need(space.f_bavail * space.f_frsize > max(15 * 1024**3, pressure_floor) + MAX_IMPORT_BYTES)
            result = subprocess.run(CTR + ['images', 'import', '--platform', 'linux/amd64',
                '--base-name', 'docker.io/jtmb92/bortus', '--digests',
                '/proc/' + str(os.getpid()) + '/fd/' + str(fd)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, timeout=1200)
            if result.returncode:raise RuntimeError('containerd_import_failed:'+result.stderr.decode(errors='replace')[-1600:])
            need(result.returncode == 0)
        ensure_manifest_reference()
        verify_runtime()
        print(json.dumps({'protocol': request['protocol'], 'source_commit': SOURCE,
            'image_reference': REFERENCE, 'manifest_digest': MANIFEST, 'config_digest': CONFIG,
            'archive_sha256': ARCHIVE_SHA, 'archive_bytes': ARCHIVE_BYTES,
            'all_layer_blobs_verified': True, 'image_preexisting': existing is not None,
            'fully_downloaded_and_unpacked': True,
            'disk_archive_created': False, 'deployed': False}))
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        import traceback
        print(json.dumps({'receiver_failed':type(error).__name__,'reason':str(error)[:1800],'lines':[f.lineno for f in traceback.extract_tb(error.__traceback__)]}),file=sys.stderr)
        raise SystemExit(1)
