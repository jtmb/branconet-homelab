#!/usr/bin/env python3
"""One admitted RAM-only inventory of the exact locked Linux npm inputs.

No HEAD repeats, redirects, retries, extraction, install scripts, dependency
cache or payload files. Counts are inputs/forecasts, not installed/postinstall
or complete compiler-peak qualification.
"""
import argparse
import base64
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import resource
import ssl
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
GROWTH = 33554432
TLS = ssl.create_default_context()
WORKER = threading.local()
OUTPUT = threading.Lock()


def event(kind, **fields):
    with OUTPUT:
        print(json.dumps({'event': kind, **fields}, sort_keys=True), flush=True)


def need(value, message):
    if not value:
        raise RuntimeError(message)


def operator():
    path = Path(__file__).with_name('veyra-linux-build.py')
    spec = importlib.util.spec_from_file_location('veyra_original_operator', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def compatible(values, target):
    if not values:
        return True
    positive = [value for value in values if not value.startswith('!')]
    return '!' + target not in values and (not positive or target in positive)


def selection(app):
    lock = json.loads((app / 'package-lock.json').read_text())
    rows = []
    for path, package in lock['packages'].items():
        if not package.get('integrity'):
            continue
        if not all(compatible(package.get(key), target) for key, target in
                   [('os', 'linux'), ('cpu', 'x64'), ('libc', 'glibc')]):
            continue
        resolved = package.get('resolved', '')
        url = urllib.parse.urlsplit(resolved)
        need(url.scheme == 'https' and url.hostname == 'registry.npmjs.org' and
             not url.username and not url.password and not url.fragment and not url.query,
             'Original public immutable registry URL required')
        # Use the lock fields only. In particular, no musl/GNU filtering by
        # filename when the lock does not declare libc.
        rows.append({'path': path, 'version': package['version'],
                     'resolved': resolved, 'integrity': package['integrity']})
    return sorted(rows, key=lambda row: row['path'])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def inventory(item):
    url, integrity = item
    result = {'resolved': url, 'integrity': integrity, 'passed': False}
    event('original-input-request-starting', resolved=url, integrity=integrity)
    try:
        # SRI may contain multiple alternatives; preserve the strongest
        # supported original authority, never invent a replacement checksum.
        choices = []
        strength = {'sha512': 3, 'sha384': 2, 'sha256': 1, 'sha1': 0}
        for token in integrity.split():
            algorithm, body = token.split('-', 1)
            need(algorithm in strength, 'Unsupported original SRI algorithm')
            choices.append((strength[algorithm], algorithm, base64.b64decode(body, validate=True)))
        strongest, algorithm, _ = max(choices)
        expected = {body for rank, name, body in choices if rank == strongest and name == algorithm}
        need(all(len(body) == hashlib.new(algorithm).digest_size for body in expected), 'Original SRI length changed')
        digest = hashlib.new(algorithm)
        compressed, expanded = 0, 0
        counts = {'entries': 0, 'regularFiles': 0, 'logicalFileBytes': 0,
                  'roundedFileDataBytes': 0, 'directories': 0, 'symlinks': 0,
                  'hardlinks': 0, 'hardlinkLogicalBytes': 0}
        metadata = hashlib.sha256()
        files, links, directory_paths = {}, [], set()
        # Reuse one immutable TLS trust context and one opener per worker;
        # do not repeatedly load OpenSSL CA stores/handler cycles for1087URLs.
        if not hasattr(WORKER, 'opener'):
            WORKER.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=TLS))
        opener = WORKER.opener
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Veyra-locked-input-qualification/1', 'Accept-Encoding': 'identity'})
        with opener.open(request, timeout=45) as response:
            need(response.status == 200 and response.headers.get('Content-Encoding', 'identity') == 'identity',
                 'Unexpected original tarball response or transfer encoding')
            class Compressed:
                def read(self, size=-1):
                    nonlocal compressed
                    need(0 <= size <= 1024 * 1024, 'Unbounded compressed input read')
                    block = response.read(size)
                    compressed += len(block)
                    need(compressed <= 512 * 1024**2, 'One original package exceeded bounded archive input')
                    digest.update(block)
                    return block
            with gzip.GzipFile(fileobj=Compressed(), mode='rb') as zipped:
                class Expanded:
                    def read(self, size=-1):
                        nonlocal expanded
                        need(0 <= size <= 1024 * 1024, 'Unbounded expanded input read')
                        block = zipped.read(size)
                        expanded += len(block)
                        need(expanded <= 2 * 1024**3, 'One original package exceeded bounded expanded input')
                        return block
                stream = Expanded()
                # Use the original bounded TAR metadata decoder, not an
                # extractor. File bodies are streamed/discarded in RAM.
                from registry_layer_inventory import _BoundedTarInfo
                with tarfile.open(fileobj=stream, mode='r|', tarinfo=_BoundedTarInfo) as tar:
                    while True:
                        member = tar.next()
                        if member is None:
                            break
                        path = posixpath.normpath(member.name)
                        need(not path.startswith('/') and '..' not in Path(path).parts and len(path) <= 8192,
                             'Original archive path needs explicit packaging review')
                        parent = posixpath.dirname(path)
                        while parent not in ('', '.'):
                            directory_paths.add(parent)
                            parent = posixpath.dirname(parent)
                        counts['entries'] += 1
                        need(counts['entries'] <= 500000, 'Original archive entry bound exceeded')
                        row = {'path': path, 'mode': member.mode, 'uid': member.uid,
                               'gid': member.gid, 'bytes': member.size}
                        if member.isfile():
                            counts['regularFiles'] += 1
                            counts['logicalFileBytes'] += member.size
                            counts['roundedFileDataBytes'] += ((member.size + 4095) // 4096) * 4096
                            files[path] = member.size
                            row['type'] = 'file'
                        elif member.isdir():
                            counts['directories'] += 1
                            directory_paths.add(path)
                            row['type'] = 'directory'
                        elif member.issym() or member.islnk():
                            key = 'symlinks' if member.issym() else 'hardlinks'
                            counts[key] += 1
                            row.update(type=key[:-1], target=member.linkname)
                            if member.islnk():
                                links.append(posixpath.normpath(member.linkname))
                        else:
                            raise RuntimeError('Original npm archive has an unrepresented special entry')
                        metadata.update(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n')
                        tar.members.clear()
                    while tail := tar.fileobj.read(65536):
                        need(not any(tail), 'Original package has nonzero post-TAR input')
            # Includes any transport bytes not consumed by the gzip reader;
            # the locked SRI always covers the complete actual HTTP body.
            source = Compressed()
            while source.read(65536):
                pass
        need(digest.digest() in expected, 'Actual complete package SRI differs')
        unresolved = [target for target in links if target not in files]
        need(not unresolved, 'Original package hardlink target needs explicit inventory resolution')
        counts['hardlinkLogicalBytes'] = sum(files[target] for target in links)
        counts['directoryPathsIncludingImplicit'] = len(directory_paths)
        result.update(passed=True, compressedBytes=compressed, expandedTarBytes=expanded,
                      sriAlgorithm=algorithm, verifiedSri=True, entryManifestSha256=metadata.hexdigest(), **counts)
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    event('original-input-request-finished', result=result,
          peakSelfRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--lease', required=True, type=Path)
    args = parser.parse_args()
    o = operator()
    event('source-inspection-starting')
    _, _, report = o.inspect(args.revision, o.PHASE / 'windows-source/integrations/browser-extension')
    event('source-inspection-finished', peakSelfRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    lease_path = args.lease.absolute()
    need(os.getuid() == 0 and lease_path.resolve() == lease_path and lease_path.is_relative_to(o.ROOT),
         'Original root-owned confined qualification lease required')
    lease = json.loads(lease_path.read_text())
    age = time.time() - dt.datetime.fromisoformat(lease['at'].replace('Z', '+00:00')).timestamp()
    need(lease['owner'] == o.OWNER and lease['purpose'] == 'locked-npm-input-qualification' and
         lease['platform'] == 'linux' and lease['exclusive'] is True and lease['nativeStageActive'] is False and
         0 <= age < 180 and lease['growthBytes'] == GROWTH, 'Fresh exact bounded qualification lease required')
    need(lease['sourceRevision'] == report['source']['revision'] and
         lease['sourceSha256'] == report['source']['sourceSha256'] and
         lease['extensionSha256'] == report['extension']['sourceSha256'], 'Source qualification identity differs')
    need(type(lease['nativeBudgetBytes']) is int and lease['nativeBudgetBytes'] > 0 and
         o.task_allocated() + lease['nativeBudgetBytes'] + GROWTH <= o.CEILING and
         report['windowsFreeBytes'] - GROWTH >= o.FLOOR and
         report['destinationFreeBytes'] - GROWTH >= o.FLOOR, 'Original complete paired ceiling/floors not admitted')
    cg = next(line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    parent = Path('/sys/fs/cgroup') / cg.lstrip('/')
    memory, cpu = (parent / 'memory.max').read_text().strip(), (parent / 'cpu.max').read_text().split()
    need(memory != 'max' and 0 < int(memory) <= 4 * o.GIB and cpu[0] != 'max' and
         0 < int(cpu[0]) / int(cpu[1]) <= 1.5, 'Original resource-bounded qualification cgroup missing')
    sys.path.insert(0, str(o.APP / 'ops'))
    rows = selection(o.APP)
    objects = {}
    for row in rows:
        objects.setdefault((row['resolved'], row['integrity']), []).append(row['path'])
    need(len(rows) == 1243 and len(objects) == 1087 and report['npmLockSha256'] ==
         '815a980f9932bb0d54da73560e7eec89d270dba482ec325a28076072d96458f8',
         'Current exact source selection differs from independently reviewed header pass')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(inventory, objects))
    for result in results:
        result['installPaths'] = objects[(result['resolved'], result['integrity'])]
    fields = ['compressedBytes', 'expandedTarBytes', 'entries', 'regularFiles', 'logicalFileBytes',
              'roundedFileDataBytes', 'directories', 'directoryPathsIncludingImplicit',
              'symlinks', 'hardlinks', 'hardlinkLogicalBytes']
    passed = [row for row in results if row['passed']]
    output = {'source': report['source'], 'npmLockSha256': report['npmLockSha256'],
        'finishedAt': o.now(), 'selectedInstallPaths': len(rows), 'uniqueObjects': len(objects),
        'selectionSha256': hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'verifiedObjects': len(passed), 'allInputsVerified': len(passed) == len(objects),
        'uniqueTotals': {key: sum(row[key] for row in passed) for key in fields},
        'installPathWeightedTotals': {key: sum(row[key] * len(row['installPaths']) for row in passed) for key in fields},
        'records': results, 'payloadFilesCreated': 0, 'extractionsOrInstallsOrScriptsExecuted': 0,
        'observedInstalledOrPostinstallClosure': False, 'completeCompilerPeakQualified': False,
        'redirectsOrRetriesOrRepeatedHeads': 0}
    print(json.dumps(output, sort_keys=True), flush=True)
    raise SystemExit(0 if output['allInputsVerified'] else 1)


if __name__ == '__main__':
    main()
