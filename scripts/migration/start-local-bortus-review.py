#!/usr/bin/env python3
"""Run the existing qualified BORTUS image for loopback-only visual review."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import time
import urllib.request

SOURCE = '12dce115006877fed2c674cad1ffd40805932974'
ARCHIVE_SHA = 'cf0d950a263b4ae63911f51560980fdce2211f7836852495bc2f189523e934dc'
MANIFEST = 'sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
STORE = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files')
ARCHIVE = STORE / 'release-v2-12dce115-inputs' / 'candidate-pod-summary-root.oci.tar'
RUNTIME = STORE / 'shared-docker-runtime'
REVIEW = RUNTIME / 'bortus-review'
NAME = 'bortus-review-12dce115'
URL = 'http://127.0.0.1:21087'


def run(args, timeout=30):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout).stdout


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Local root required for private H review state')
    if run(['docker', 'info', '--format', '{{.DockerRootDir}}']).strip() != str(RUNTIME / 'docker'):
        raise RuntimeError('Docker is not using the approved H store')
    if os.stat(RUNTIME / 'docker').st_dev != os.stat(STORE).st_dev:
        raise RuntimeError('Docker physical backing differs')
    if ARCHIVE.is_symlink() or os.stat(ARCHIVE).st_dev != os.stat(STORE).st_dev:
        raise RuntimeError('Qualified input is not a regular file on the approved H filesystem')
    if not json.loads((RUNTIME / 'source-retirement.json').read_text()).get('state') == 'completed':
        raise RuntimeError('Old system-disk data retirement must finish first')
    if REVIEW.exists() or run(['docker', 'ps', '-aq', '--filter', 'name=^/' + NAME + '$']).strip():
        raise RuntimeError('Review state already exists; reconcile the existing consumer')
    h = hashlib.sha256()
    with ARCHIVE.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    if h.hexdigest() != ARCHIVE_SHA:
        raise RuntimeError('Qualified archive identity changed')
    with tarfile.open(ARCHIVE, 'r:') as t:
        index = json.load(t.extractfile('index.json'))
        if len(index['manifests']) != 1 or index['manifests'][0]['digest'] != MANIFEST:
            raise RuntimeError('Qualified manifest differs')
        manifest = json.load(t.extractfile('blobs/sha256/' + MANIFEST.split(':')[1]))
        config_id = manifest['config']['digest']
        config = json.load(t.extractfile('blobs/sha256/' + config_id.split(':')[1]))
    if config['config']['Labels']['org.opencontainers.image.revision'] != SOURCE:
        raise RuntimeError('Qualified source differs')
    baseline = run(['docker', 'image', 'ls', '-aq', '--no-trunc']).splitlines()
    REVIEW.mkdir(mode=0o700)
    record = {'owner': 'BORTUS Delivery and Cluster Operations', 'source': SOURCE,
              'archive_sha256': ARCHIVE_SHA, 'manifest': MANIFEST, 'url': URL,
              'baseline_image_ids': sorted(set(baseline)), 'state': 'starting',
              'container_name': NAME, 'root': str(REVIEW), 'production_data_used': False,
              'remaining_consumer': 'James visual review and original acceptance before production',
              'cleanup_end_condition': 'Remove owned review container and exclusively owned local image after production verification'}
    def save():
        p = REVIEW / 'review.json'
        p.write_text(json.dumps(record, indent=2) + '\n')
        p.chmod(0o600)
    save()
    with (REVIEW / 'image-load.log').open('w') as log:
        subprocess.run(['docker', 'load', '--input', str(ARCHIVE)], check=True, stdout=log, stderr=log, timeout=900)
    matches = []
    for image in set(run(['docker', 'image', 'ls', '-aq', '--no-trunc']).splitlines()):
        obj = json.loads(run(['docker', 'image', 'inspect', image]))[0]
        if (obj.get('Id') in (MANIFEST, config_id) or obj.get('Descriptor', {}).get('digest') == MANIFEST):
            if obj.get('RootFS', {}).get('Layers') == config['rootfs']['diff_ids'] and obj['Config'].get('Labels', {}).get('org.opencontainers.image.revision') == SOURCE:
                matches.append(image)
    if len(matches) != 1:
        raise RuntimeError('Loaded qualified image is not unique')
    record.update(image_id=matches[0], image_preexisting=matches[0] in baseline)
    save()
    for name in ['data', 'tmp', 'home']:
        p = REVIEW / name
        p.mkdir(mode=0o700)
        os.chown(p, 1000, 1000)
    env = REVIEW / 'review.env'
    env.write_text('BOTRUS_JWT_SECRET=' + secrets.token_hex(32) + '\nBOTRUS_SECRETS_KEY=' + secrets.token_hex(32) + '\nBORTUS_DISABLE_PROVISIONING=true\nKUBECONFIG=/dev/null\nHOME=/home/shell\n')
    env.chmod(0o600)
    try:
        cid = run(['docker', 'create', '--name', NAME, '--label', 'io.branconet.owner=bortus-local-review',
                   '--restart=no', '--read-only', '--cpus=2', '--memory=1g', '--memory-swap=1g',
                   '--pids-limit=256', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                   '--log-driver=json-file', '--log-opt=max-size=10m', '--log-opt=max-file=2',
                   '--publish', '127.0.0.1:21087:4000', '--env-file', str(env),
                   '--mount', 'type=bind,src=' + str(REVIEW / 'data') + ',dst=/data',
                   '--mount', 'type=bind,src=' + str(REVIEW / 'tmp') + ',dst=/tmp',
                   '--mount', 'type=bind,src=' + str(REVIEW / 'home') + ',dst=/home/shell', matches[0]]).strip()
        record['container_id'] = cid
        save()
    finally:
        env.unlink()
    run(['docker', 'start', cid])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(URL + '/api/health/live', timeout=3) as response:
                if response.status == 200:
                    record.update(state='ready', ready_unix=time.time())
                    save()
                    print(json.dumps({'state': 'ready', 'url': URL, 'image_reused': True, 'built': False}))
                    return
        except (OSError, ValueError):
            time.sleep(1)
    record['state'] = 'startup-failed-preserved'
    save()
    raise RuntimeError('Review did not become healthy; exact container and logs retained for diagnosis')


if __name__ == '__main__':
    main()
