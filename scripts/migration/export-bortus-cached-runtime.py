#!/usr/bin/env python3
"""Finite containerd content reader. Never pulls, imports, unpacks or executes an image."""
import argparse
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import tarfile

ROOT = Path('/home/james/.local/share/branconet-migration/bortus-cached-runtime-audit-20261025')
DIGEST = 'sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879'
REF = 'docker.io/library/bortus@' + DIGEST
CTR = ['/usr/bin/ctr', '--address', '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']
INDEX = {'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}
GIB = 1024**3


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def save(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    owner = pwd.getpwnam('james')
    path.chmod(0o440)
    os.chown(path, 0, owner.pw_gid)


def reserve(extra):
    v = os.statvfs(ROOT)
    need(v.f_bavail*v.f_frsize >= 15*GIB+extra, 'node_15GiB_retained_floor')
    need(v.f_favail >= max(250000, v.f_files//10), 'inode_reserve')
    return {'freeBytes': v.f_bavail*v.f_frsize, 'estimatedAdditionalBytes': extra,
            'retainedFloorBytes': 15*GIB}


def limits():
    cg = Path('/proc/self/cgroup').read_text().strip()
    need(cg.startswith('0::/system.slice/branconet-bortus-cache-'), 'owned_unit')
    p = Path('/sys/fs/cgroup')/cg[4:]
    values = {n: (p/n).read_text().strip() for n in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    need(values['memory.max'] == '1073741824' and values['memory.swap.max'] == '0', 'memory_limit')
    q, period = values['cpu.max'].split()
    need(q != 'max' and int(q) <= 2*int(period) and values['pids.max'] == '128', 'cpu_tasks_limit')
    need(os.getpriority(os.PRIO_PROCESS, 0) == 10, 'nice_limit')
    unit = cg.rsplit('/', 1)[1]
    r = subprocess.run(['systemctl', 'show', unit, '-p', 'PrivateNetwork', '-p', 'NoNewPrivileges'],
                       capture_output=True, text=True, timeout=10, check=True)
    need('PrivateNetwork=yes' in r.stdout and 'NoNewPrivileges=yes' in r.stdout, 'offline_unit')
    return values


def descriptor(value):
    need(isinstance(value, dict) and re.fullmatch(r'sha256:[0-9a-f]{64}', value.get('digest', '')), 'digest')
    need(type(value.get('size')) is int and 0 <= value['size'] <= 2*GIB, 'descriptor_size')
    return {k: value[k] for k in ['mediaType', 'digest', 'size']}


def small(digest):
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', digest), 'content_digest')
    # Only exact reachable descriptors are requested; stderr never enters receipts.
    with subprocess.Popen(CTR+['content', 'get', digest], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as p:
        data = p.stdout.read(4*1024**2+1)
        if len(data) > 4*1024**2:
            p.kill()
        need(p.wait(timeout=15) == 0 and len(data) <= 4*1024**2, 'cached_metadata_missing_or_oversize')
    need('sha256:'+hashlib.sha256(data).hexdigest() == digest, 'metadata_digest')
    return data


def graph():
    r = subprocess.run(CTR+['images', 'ls', '-q', 'name=='+REF], capture_output=True, text=True, timeout=20)
    need(r.returncode == 0 and r.stdout.splitlines() == [REF], 'exact_cached_reference_required')
    raw = small(DIGEST)
    obj = json.loads(raw)
    root = descriptor({'digest': DIGEST, 'size': len(raw), 'mediaType': obj.get('mediaType')})
    blobs, runtime = {}, []

    def add(d):
        d = descriptor(d)
        if d['digest'] in blobs:
            need(blobs[d['digest']] == d, 'ambiguous_descriptor')
        blobs[d['digest']] = d
        need(len(blobs) <= 512 and sum(x['size'] for x in blobs.values()) <= 2*GIB-4*1024**2, 'finite_content_limit')
        return d

    def walk(d, depth=0):
        need(depth <= 8, 'index_depth')
        d = add(d)
        data = small(d['digest'])
        need(len(data) == d['size'], 'metadata_size')
        value = json.loads(data)
        if d['mediaType'] in INDEX:
            need(0 < len(value.get('manifests', [])) <= 64, 'index_count')
            for child in value['manifests']:
                walk(child, depth+1)
        else:
            need(d['mediaType'] in MANIFEST and len(value.get('layers', [])) <= 128, 'manifest_scope')
            config = add(value['config'])
            config_raw = small(config['digest'])
            need(len(config_raw) == config['size'], 'config_size')
            cfg = json.loads(config_raw)
            # Never serialize image Env/history/labels/commands or app source.
            if cfg.get('os') == 'linux' and cfg.get('architecture') == 'amd64':
                runtime.append(d['digest'])
            for layer in value.get('layers', []):
                add(layer)
    walk(root)
    need(len(runtime) == 1, 'one_linux_amd64_runtime')
    total = sum(v['size']+512+((-v['size']) % 512) for v in blobs.values())+32768
    need(total <= 2*GIB, 'archive_budget')
    return {'rootDescriptor': root, 'runtimeManifest': runtime[0], 'blobs': sorted(blobs.values(), key=lambda x:x['digest']),
            'projectedArchiveBytes': total, 'contentBytes': sum(x['size'] for x in blobs.values())}


class CheckedReader:
    def __init__(self, pipe, size):
        self.pipe, self.size, self.count, self.hash = pipe, size, 0, hashlib.sha256()

    def read(self, n):
        data = self.pipe.read(min(n, 1024**2))
        self.count += len(data)
        need(self.count <= self.size, 'blob_growth')
        self.hash.update(data)
        return data


def read_blob(d, bundle=None):
    with subprocess.Popen(CTR+['content', 'get', d['digest']], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as child:
        reader = CheckedReader(child.stdout, d['size'])
        if bundle:
            info = tarfile.TarInfo('blobs/sha256/'+d['digest'][7:])
            info.size, info.mode = d['size'], 0o400
            bundle.addfile(info, reader)
        else:
            while reader.read(1024**2):
                pass
        extra = child.stdout.read(1)
        need(child.wait(timeout=15) == 0 and not extra and reader.count == d['size'], 'cached_blob_incomplete')
        need('sha256:'+reader.hash.hexdigest() == d['digest'], 'cached_blob_digest')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['probe', 'export'])
    p.add_argument('--attempt', required=True)
    p.add_argument('--probe-sha256', default='')
    a = p.parse_args()
    os.umask(0o077)
    need(os.getuid() == 0 and re.fullmatch('[0-9a-f]{12}', a.attempt), 'root_fixed_attempt')
    need(ROOT.resolve() == ROOT and ROOT.is_dir(), 'fixed_root')
    target = ROOT/'attempts'/a.attempt
    need(target.resolve() == target and target.is_dir(), 'attempt_directory')
    record = {'sourceKind': 'existing-node-containerd-runtime-cache', 'image': REF, 'node': 'workernode2',
              'attempt': a.attempt, 'phase': a.phase, 'coverage': 'unknown',
              'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'helperSHA256': sha(Path(__file__))}
    try:
        record['limits'] = limits()
        closure = graph()
        record['closure'] = closure
        record['capacity'] = reserve(closure['projectedArchiveBytes'] if a.phase == 'export' else 0)
        if a.phase == 'probe':
            for d in closure['blobs']:
                read_blob(d)
            record['coverage'] = 'complete_cached_root_closure_verified_not_scanned'
        else:
            previous = target/'probe.json'
            need(re.fullmatch('[0-9a-f]{64}', a.probe_sha256) and sha(previous) == a.probe_sha256, 'reviewed_probe_hash')
            prior = json.loads(previous.read_text())
            need(prior['coverage'] == 'complete_cached_root_closure_verified_not_scanned' and prior['closure'] == closure,
                 'unchanged_complete_cache_graph')
            archive = target/'runtime.oci.tar'
            with archive.open('xb') as output, tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as bundle:
                for name, value in [('oci-layout', {'imageLayoutVersion':'1.0.0'}),
                                    ('index.json', {'schemaVersion':2, 'manifests':[closure['rootDescriptor']]})]:
                    data = json.dumps(value, separators=(',', ':')).encode()
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o400
                    bundle.addfile(info, io.BytesIO(data))
                for d in closure['blobs']:
                    reserve(0)
                    read_blob(d, bundle)
            need(archive.stat().st_size <= closure['projectedArchiveBytes'], 'actual_archive_budget')
            need(graph() == closure, 'cache_identity_after_export')
            owner = pwd.getpwnam('james')
            archive.chmod(0o440)
            os.chown(archive, 0, owner.pw_gid)
            record.update(archiveBytes=archive.stat().st_size, archiveSHA256=sha(archive), probeSHA256=a.probe_sha256,
                          coverage='complete_cached_root_closure_exported_not_scanned')
    except Exception as error:
        record['failureCategory'] = str(error) if isinstance(error, ValueError) else type(error).__name__
        raise
    finally:
        record['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(target/(a.phase+'.json'), record)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Cached runtime operation refused; private receipt retained, coverage unknown.')
