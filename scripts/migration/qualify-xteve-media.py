#!/usr/bin/env python3
"""Finite synthetic xTeVe media qualification. Plan-only unless --execute.

Run on the cluster master with its existing kubectl context. No production
configuration, media, credentials, entrypoints, volumes or service endpoints.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

OLD = 'docker.io/alturismo/xteve:latest@sha256:7885f2759c0da3c5f2c72b2e45ba4b602bdd7d6f04cc6abba201091f11c93a95'
NEW = 'docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'
READER = 'ghcr.io/alexta69/metube@sha256:afd3fa2b229e3e6d4c8750618fe148af33a1f70b32af4441ecbd2d08f29d8221'
URL = 'http://127.0.0.1:18080/input.ts'
KEY = 'branconet.net/xteve-media-fixture'
SERVER = '''import http.server,functools
class Handler(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  if self.path not in ('/input.ts','/new-ffmpeg.ts'): self.send_error(404); return
  super().do_GET()
http.server.ThreadingHTTPServer(('127.0.0.1',18080),functools.partial(Handler,directory='/fixture')).serve_forever()
'''


def documents(run):
    labels = {KEY: run}
    ns = 'xteve-media-' + run
    metadata = {'name': 'media', 'namespace': ns, 'labels': labels}
    security = {'runAsNonRoot': False, 'runAsUser': 0, 'runAsGroup': 0,
                'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                'capabilities': {'drop': ['ALL']}, 'seccompProfile': {'type': 'RuntimeDefault'}}
    containers = []
    for name, image in [('old', OLD), ('new', NEW), ('reader', READER)]:
        containers.append({
            'name': name, 'image': image, 'imagePullPolicy': 'Never',
            'command': ['python3', '-u', '-c', SERVER] if name == 'reader' else ['/bin/sh', '-c', 'exec sleep 900'],
            'securityContext': security,
            'env': [{'name': 'HOME', 'value': '/tmp'}, {'name': 'TMPDIR', 'value': '/tmp'}],
            'resources': {'requests': {'cpu': '25m', 'memory': '32Mi', 'ephemeral-storage': '32Mi'},
                          'limits': {'cpu': '100m' if name == 'reader' else '1',
                                     'memory': '128Mi' if name == 'reader' else '384Mi',
                                     'ephemeral-storage': '128Mi'}},
            'volumeMounts': [{'name': 'fixture', 'mountPath': '/fixture'},
                             {'name': 'tmp-' + name, 'mountPath': '/tmp'}]})
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': metadata,
           'spec': {'nodeSelector': {'kubernetes.io/hostname': 'workernode2'},
                    'automountServiceAccountToken': False, 'enableServiceLinks': False,
                    'hostNetwork': False, 'hostPID': False, 'hostIPC': False,
                    'restartPolicy': 'Never', 'activeDeadlineSeconds': 900,
                    'terminationGracePeriodSeconds': 10,
                    'securityContext': {'fsGroup': 0, 'fsGroupChangePolicy': 'OnRootMismatch'},
                    'containers': containers,
                    'volumes': [{'name': 'fixture', 'emptyDir': {'sizeLimit': '64Mi'}}] +
                               [{'name': 'tmp-' + c, 'emptyDir': {'sizeLimit': '16Mi'}} for c in ('old', 'new', 'reader')]}}
    return [
        {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns, 'labels': labels}},
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
         'metadata': {'name': 'deny-all', 'namespace': ns, 'labels': labels},
         'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}, pod]


def packet_summary(probe):
    result = {}
    for stream in probe['streams']:
        kind = stream.get('codec_type')
        if kind not in ('video', 'audio'):
            continue
        if kind in result:
            raise ValueError('unexpected duplicate stream')
        packets = [p for p in probe['packets'] if p['stream_index'] == stream['index']]
        if not packets:
            raise ValueError('empty stream')
        pts = [float(p['pts_time']) for p in packets]
        dts = [float(p['dts_time']) for p in packets]
        ends = [float(p['pts_time']) + float(p['duration_time']) for p in packets]
        if not all(math.isfinite(v) for v in pts + dts + ends):
            raise ValueError('nonfinite timestamps')
        result[kind] = {k: stream.get(k) for k in ('codec_name', 'channels', 'sample_rate', 'width', 'height', 'r_frame_rate')}
        result[kind].update(start=min(pts), end=max(ends), duration=max(ends)-min(pts),
                            packets=len(packets), monotonic_dts=all(b >= a for a, b in zip(dts, dts[1:])))
    if set(result) != {'audio', 'video'}:
        raise ValueError('missing audio/video')
    result['av_start_offset'] = result['audio']['start'] - result['video']['start']
    result['av_end_offset'] = result['audio']['end'] - result['video']['end']
    return result


def frame_hashes(data):
    rows = [line.split(',') for line in data.decode().splitlines() if line and not line.startswith('#')]
    if not rows or any(len(row) != 6 for row in rows):
        raise ValueError('invalid decoded frame hash output')
    return [row[-1].strip() for row in rows]


class Run:
    def __init__(self, output, run, ffmpeg_only=False):
        self.output = output
        self.run = run
        self.ns = 'xteve-media-' + run
        self.owned = []
        self.backends = ('ffmpeg',) if ffmpeg_only else ('ffmpeg', 'vlc')
        self.receipt = {'run': run, 'namespace': self.ns, 'images': {'old': OLD, 'new': NEW, 'reader': READER},
                        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        'status': 'started', 'owned': self.owned, 'commands': [], 'cleanup': []}
        self.receipt['qualified_backends'] = self.backends

    def save(self):
        (self.output / 'receipt.json').write_text(json.dumps(self.receipt, indent=2) + '\n')

    def kubectl(self, args, data=None, timeout=60, label=None):
        label = label or 'command-' + str(len(self.receipt['commands']))
        record = {'label': label, 'args': args, 'timeout_seconds': timeout}
        self.receipt['commands'].append(record)
        self.save()
        try:
            p = subprocess.run(['kubectl', '--request-timeout=30s'] + args,
                               input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            record['returncode'] = p.returncode
            (self.output / (label + '.stderr')).write_bytes(p.stderr)
            self.save()
            if p.returncode:
                (self.output / (label + '.stdout')).write_bytes(p.stdout)
                raise RuntimeError('kubectl failed: ' + label)
            return p.stdout
        except subprocess.TimeoutExpired as e:
            (self.output / (label + '.stderr')).write_bytes(e.stderr or b'')
            (self.output / (label + '.stdout')).write_bytes(e.stdout or b'')
            record['timeout'] = True
            self.save()
            raise RuntimeError('kubectl timed out: ' + label) from e

    def execute(self, container, argv, label, timeout=60):
        return self.kubectl(['-n', self.ns, 'exec', 'media', '-c', container, '--'] + argv,
                            label=label, timeout=timeout)

    def create(self, doc):
        kind = doc['kind']
        obj = json.loads(self.kubectl(['create', '-f', '-', '-o', 'json'], json.dumps(doc).encode(), label='create-' + kind))
        if obj['metadata'].get('labels', {}).get(KEY) != self.run:
            raise RuntimeError('ownership label mismatch')
        self.owned.append({'kind': kind, 'name': obj['metadata']['name'], 'uid': obj['metadata']['uid']})
        self.save()

    def cleanup(self):
        # Raw DELETE sends real API UID preconditions; a name-only delete is not sufficient.
        for obj in reversed(self.owned):
            kind, name, uid = obj['kind'], obj['name'], obj['uid']
            try:
                if kind == 'Namespace':
                    # A namespace can acquire foreign objects. Retain it unless only the
                    # standard namespace-controller defaults remain after our deletions.
                    resources = self.kubectl(['api-resources', '--verbs=list', '--namespaced=true', '-o', 'name'], label='cleanup-resource-types').decode().splitlines()
                    for resource in resources:
                        names = self.kubectl(['-n', self.ns, 'get', resource, '-o', 'name'], label='cleanup-list-' + resource).decode().splitlines()
                        for item in names:
                            item_name = item.rsplit('/', 1)[-1]
                            standard = ((resource == 'serviceaccounts' and item_name == 'default') or
                                        (resource == 'configmaps' and item_name == 'kube-root-ca.crt') or
                                        resource in ('events', 'events.events.k8s.io'))
                            if not standard:
                                raise RuntimeError('namespace has a retained or foreign resource; leave namespace and isolation intact')
                    uri = '/api/v1/namespaces/' + name
                elif kind == 'Pod':
                    uri = '/api/v1/namespaces/' + self.ns + '/pods/' + name
                else:
                    # A Pod create might have succeeded while its response was lost.
                    # Preserve isolation if any Pod remains, even without a recorded UID.
                    if self.kubectl(['-n', self.ns, 'get', 'pods', '-o', 'name'], label='cleanup-pods-before-policy').strip():
                        raise RuntimeError('Pod remains; retain deny policy and namespace')
                    uri = '/apis/networking.k8s.io/v1/namespaces/' + self.ns + '/networkpolicies/' + name
                self.kubectl(['delete', '--raw', uri, '-f', '-'],
                             json.dumps({'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': uid}, 'gracePeriodSeconds': 10}).encode(),
                             label='delete-' + kind)
                if kind == 'Pod':
                    self.kubectl(['-n', self.ns, 'wait', '--for=delete', 'pod/' + name, '--timeout=45s'], timeout=55, label='wait-delete-Pod')
                self.receipt['cleanup'].append({'kind': kind, 'uid': uid, 'deleted': True})
            except Exception as e:
                self.receipt['cleanup'].append({'kind': kind, 'uid': uid, 'deleted': False, 'error': str(e)})
                # Do not remove the deny policy or namespace if Pod deletion fails.
                self.save()
                break
            self.save()

    def retain_fixture_files(self):
        # Explicit file allowlist from this synthetic emptyDir; never enumerate app data.
        if not any(o['kind'] == 'Pod' for o in self.owned):
            return
        for name in ('input.ts', 'old-ffmpeg.ts', 'new-ffmpeg.ts', 'old-vlc.ts', 'new-vlc.ts',
                     'old-ffmpeg.log', 'new-ffmpeg.log', 'old-vlc.log', 'new-vlc.log'):
            if 'vlc' in name and 'vlc' not in self.backends:
                continue
            try:
                code = "from pathlib import Path; import sys; p=Path('/fixture')/sys.argv[1]; assert p.is_file() and p.stat().st_size<=8388608; sys.stdout.buffer.write(p.read_bytes())"
                data = self.execute('reader', ['python3', '-c', code, name], 'retain-' + name)
                (self.output / name).write_bytes(data)
            except Exception:
                pass  # Receipt records missing files/errors; retain all available evidence.

    def qualify(self):
        for doc in documents(self.run):
            self.create(doc)
        self.kubectl(['-n', self.ns, 'wait', '--for=condition=Ready', 'pod/media', '--timeout=120s'], timeout=135, label='ready')
        actual = json.loads(self.kubectl(['-n', self.ns, 'get', 'pod/media', '-o', 'json'], label='pod-identity'))
        expected = documents(self.run)[-1]['spec']
        spec = actual['spec']
        if actual['metadata']['uid'] != next(o['uid'] for o in self.owned if o['kind'] == 'Pod'):
            raise RuntimeError('Pod UID changed')
        if spec.get('nodeName') != 'workernode2' or spec.get('automountServiceAccountToken') is not False:
            raise RuntimeError('placement/token drift')
        if spec.get('initContainers') or spec.get('ephemeralContainers') or spec.get('hostNetwork') or spec.get('hostPID') or spec.get('hostIPC'):
            raise RuntimeError('unexpected admission-added execution/network surface')
        if len(spec['containers']) != 3 or any(set(v) != {'name', 'emptyDir'} for v in spec['volumes']):
            raise RuntimeError('unexpected container or non-emptyDir volume')
        for got, want in zip(spec['containers'], expected['containers']):
            for key in ('name', 'image', 'command', 'imagePullPolicy', 'securityContext', 'volumeMounts', 'env', 'resources'):
                if got[key] != want[key]:
                    raise RuntimeError('admission changed fixture contract: ' + key)
        policies = json.loads(self.kubectl(['-n', self.ns, 'get', 'networkpolicies', '-o', 'json'], label='isolation-policy'))['items']
        if len(policies) != 1 or policies[0]['metadata']['uid'] != next(o['uid'] for o in self.owned if o['kind'] == 'NetworkPolicy'):
            raise RuntimeError('unexpected network policy membership')
        policy = policies[0]['spec']
        if policy.get('podSelector') != {} or set(policy['policyTypes']) != {'Ingress', 'Egress'} or policy.get('ingress') or policy.get('egress'):
            raise RuntimeError('deny-all policy drift')
        self.receipt['pod_identity'] = {'uid': actual['metadata']['uid'], 'node': spec['nodeName'],
            'containers': [{k: c.get(k) for k in ('name', 'image', 'imageID', 'containerID')} for c in actual['status']['containerStatuses']]}
        self.save()
        for c in ('old', 'new'):
            for binary in ('ffmpeg', 'cvlc'):
                argv = ['/usr/bin/ffmpeg', '-version'] if binary == 'ffmpeg' else [
                    '/bin/sh', '-c', '/usr/bin/cvlc --version & child=$!; wait "$child"; status=$?; exit "$status"']
                data = self.execute(c, argv, c + '-' + binary + '-version')
                (self.output / (c + '-' + binary + '-version.txt')).write_bytes(data)
        generate = ['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=320x180:rate=25:duration=4', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=4', '-c:v', 'libx264', '-preset', 'ultrafast',
                    '-crf', '18', '-pix_fmt', 'yuv420p', '-g', '25', '-bf', '0', '-threads', '1',
                    '-c:a', 'aac', '-ac', '2', '-ar', '48000', '-f', 'mpegts', '-t', '4', '/fixture/input.ts']
        self.execute('new', generate, 'generate', timeout=90)
        probe_server = "import urllib.request; r=urllib.request.urlopen('" + URL + "',timeout=5); assert r.status==200; print(r.headers.get('Content-Length'))"
        self.execute('reader', ['python3', '-c', probe_server], 'localhost-http')
        for backend in self.backends:
            for c in ('old', 'new'):
                argv = (['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', URL,
                         '-c', 'copy', '-c:a', 'ac3', '-f', 'mpegts', 'pipe:1'] if backend == 'ffmpeg' else
                        ['/usr/bin/cvlc', '-I', 'dummy', 'http://127.0.0.1:18080/new-ffmpeg.ts', '--sout', '#std{mux=ts,access=file,dst=-}', 'vlc://quit'])
                prefix = '/fixture/' + c + '-' + backend
                pipeline = shlex.join(argv) + ' >' + prefix + '.ts 2>' + prefix + '.log'
                if backend == 'vlc':
                    # Both vendor binaries substitute getppid for the root check.
                    # A direct exec can see PPID 0 across a PID namespace boundary.
                    # Background + wait guarantees a live in-container shell parent;
                    # do not replace this with exec or an optimizable final command.
                    script = 'umask 022; ' + pipeline + ' & child=$!; wait "$child"; status=$?; exit "$status"'
                else:
                    script = 'umask 022; exec ' + pipeline
                self.execute(c, ['/bin/sh', '-c', script], c + '-' + backend, timeout=45)
        summaries, hashes = {}, {}
        stems = ['input'] + [c + '-' + b for b in self.backends for c in ('old', 'new')]
        for stem in stems:
            path = '/fixture/' + stem + '.ts'
            data = self.execute('new', ['/usr/bin/ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_packets', '-of', 'json', path], 'probe-' + stem)
            (self.output / (stem + '-probe.json')).write_bytes(data)
            summaries[stem] = packet_summary(json.loads(data))
            data = self.execute('new', ['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror', '-threads', '1', '-i', path,
                                      '-map', '0:v:0', '-an', '-vsync', '0', '-pix_fmt', 'yuv420p', '-f', 'framemd5', 'pipe:1'], 'decode-' + stem)
            (self.output / (stem + '-framemd5.txt')).write_bytes(data)
            hashes[stem] = frame_hashes(data)
            self.execute('new', ['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror', '-threads', '1', '-i', path,
                                 '-map', '0:a:0', '-vn', '-f', 'null', '-'], 'decode-audio-' + stem)
        checks = {}
        for stem, s in summaries.items():
            expected_audio = 'aac' if stem == 'input' else 'ac3'
            checks[stem] = {
                'video_codec': s['video']['codec_name'] == 'h264',
                'audio_codec': s['audio']['codec_name'] == expected_audio,
                'dimensions': (s['video']['width'], s['video']['height']) == (320, 180),
                'frame_rate': s['video']['r_frame_rate'] == '25/1',
                'audio_channels_rate': (s['audio']['channels'], s['audio']['sample_rate']) == (2, '48000'),
                'duration': all(abs(s[k]['duration'] - 4) <= .15 for k in ('audio', 'video')),
                'av_timing': abs(s['av_start_offset']) <= .12 and abs(s['av_end_offset']) <= .12,
                'monotonic_dts': all(s[k]['monotonic_dts'] for k in ('audio', 'video')),
                'decoded_frames': len(hashes[stem]) == 100 and hashes[stem] == hashes['input']}
        for backend in self.backends:
            a, b = summaries['old-' + backend], summaries['new-' + backend]
            checks[backend + '-comparison'] = {
                'duration_delta': all(abs(a[k]['duration'] - b[k]['duration']) <= .08 for k in ('audio', 'video')),
                'av_offset_delta': all(abs(a[k] - b[k]) <= .08 for k in ('av_start_offset', 'av_end_offset'))}
        self.receipt.update(summaries=summaries, checks=checks,
                            status='passed' if all(v for group in checks.values() for v in group.values()) else 'failed')
        self.save()
        if self.receipt['status'] != 'passed':
            raise RuntimeError('media acceptance checks failed')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute', action='store_true', help='Create isolated resources and run the finite fixture')
    ap.add_argument('--configured-ffmpeg-only', action='store_true', help='Qualify the measured production FFmpeg pipeline only; no VLC acceptance claim')
    ap.add_argument('--output-dir', type=Path, help='New receipt directory on the master; no existing directory is reused')
    args = ap.parse_args()
    run = uuid.uuid4().hex[:12]
    if not args.execute:
        print(json.dumps({'mode': 'plan-only', 'documents': documents(run)}, indent=2))
        return 0
    if args.output_dir is None:
        ap.error('--execute requires --output-dir')
    os.umask(0o077)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    runner = Run(args.output_dir, run, args.configured_ffmpeg_only)
    runner.save()
    try:
        runner.qualify()
    except (Exception, KeyboardInterrupt) as e:
        runner.receipt.update(status='failed', error=str(e))
        runner.save()
    finally:
        runner.retain_fixture_files()
        runner.cleanup()
        runner.receipt['files'] = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                   for p in args.output_dir.iterdir() if p.is_file() and p.name != 'receipt.json'}
        runner.save()
    print(json.dumps({'status': runner.receipt['status'], 'receipt': str(args.output_dir / 'receipt.json'),
                      'cleanup': runner.receipt['cleanup']}))
    return 0 if runner.receipt['status'] == 'passed' and len(runner.receipt['cleanup']) == 3 and all(c['deleted'] for c in runner.receipt['cleanup']) else 1


if __name__ == '__main__':
    sys.exit(main())
