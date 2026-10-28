"""Qualify the complete native RAW backing after the optional RAW copy timed out.

Never changes either image. Preserve the incomplete copy as a lossless recipe
against the independently verified native backing, with bounded literal deltas.
Original invocation failures and verification receipts remain authoritative.
"""
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'platform-upstream-review-20261027/detached-volume-backups-20261027'
I = R / 'ingenium-current'
W = I / 'restore-work'
UNIT = 'branconet-ingenium-partial-raw-preservation'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def ident(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in
            ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']}


def save(name, value):
    with (I / name).open('x') as f:
        json.dump(value, f, indent=2)
    os.chown(I / name, 1000, 1000)


def worker():
    need(os.geteuid() == 1000 and os.environ.get('BRANCONET_PRESERVATION_SCOPE') == UNIT,
         'isolated_owner')
    owner = json.loads((I / 'partial-preservation-ownership.json').read_text())
    need(owner['sourceSHA256'] == sha(Path(__file__)), 'frozen_source')
    old = json.loads((I / 'conversion-completion-ownership.json').read_text())
    paths = [W / 'backup.img', W / 'volume.raw']
    need({str(p): ident(p) for p in paths} == old['originalFiles'], 'unchanged_original_images')
    verified = json.loads((I / 'completed-native-backing-verification.json').read_text())
    need(sha(I / 'completed-native-backing-verification.json') == owner['backingVerificationSHA256']
         and verified['status'] == 'native_restore_and_all_block_checks_passed'
         and verified['verifiedBlocks'] == 4869 and verified['allUnbackedRegionsZero']
         and verified['encryptedHeaderVerified'], 'complete_original_native_checks')
    tools = R / 'independent-restore-tools'
    binding = json.loads((R / 'independent-restore-tools.json').read_text())
    need(all(sha(tools / p) == h for p, h in binding['toolPaths'].items()), 'stock_tools_unchanged')
    p = subprocess.run([str(tools / 'qemu-img'), 'info', '--output=json', str(paths[0])],
                       capture_output=True, timeout=30, check=True)
    info = json.loads(p.stdout)
    need(info['format'] == 'raw' and info['virtual-size'] == verified['backendBytes'],
         'native_backing_is_already_the_required_raw_format')
    size = paths[1].stat().st_size
    ranges, extents = [], []
    partial_hash = hashlib.sha256()
    delta_bytes = 0
    zero = bytes(1024**2)

    def zeros(n, h):
        while n:
            take = min(n, len(zero))
            h.update(zero[:take])
            n -= take

    def append(kind, offset, n, literal_offset=None):
        if ranges and ranges[-1]['kind'] == kind and ranges[-1]['offset'] + ranges[-1]['bytes'] == offset:
            previous = ranges[-1]
            if kind != 'literal' or previous['literalOffset'] + previous['bytes'] == literal_offset:
                previous['bytes'] += n
                return
        row = dict(kind=kind, offset=offset, bytes=n)
        if literal_offset is not None:
            row['literalOffset'] = literal_offset
        ranges.append(row)
        need(len(ranges) < 100000, 'bounded_recipe')

    with paths[0].open('rb', buffering=0) as full, paths[1].open('rb', buffering=0) as partial, \
            (I / 'original-partial-literal-delta.bin').open('xb') as delta:
        cursor = 0
        while cursor < size:
            try:
                begin = os.lseek(partial.fileno(), cursor, os.SEEK_DATA)
            except OSError as e:
                need(e.errno == errno.ENXIO, 'seek_data_supported')
                zeros(size - cursor, partial_hash)
                break
            need(cursor <= begin <= size, 'monotonic_extent')
            zeros(begin - cursor, partial_hash)
            end = min(size, os.lseek(partial.fileno(), begin, os.SEEK_HOLE))
            need(end > begin, 'nonempty_extent')
            extents.append([begin, end - begin])
            for offset in range(begin, end, 1024**2):
                n = min(1024**2, end - offset)
                a = os.pread(partial.fileno(), n, offset)
                b = os.pread(full.fileno(), n, offset)
                need(len(a) == len(b) == n, 'complete_position_independent_read')
                partial_hash.update(a)
                if a == b:
                    append('source', offset, n)
                elif not any(a):
                    pass
                else:
                    for sub in range(0, n, 4096):
                        aa, bb = a[sub:sub + 4096], b[sub:sub + 4096]
                        if aa == bb:
                            append('source', offset + sub, len(aa))
                        elif any(aa):
                            need(delta_bytes + len(aa) <= 16 * 1024**2, 'literal_delta_peak_bound')
                            append('literal', offset + sub, len(aa), delta_bytes)
                            delta.write(aa)
                            delta_bytes += len(aa)
            cursor = end
        delta.flush()
        os.fsync(delta.fileno())
    # Independently reconstruct the complete logical digest without materializing
    # another image; gaps are zero and source reads use original absolute offsets.
    reconstructed = hashlib.sha256()
    with paths[0].open('rb', buffering=0) as full, \
            (I / 'original-partial-literal-delta.bin').open('rb', buffering=0) as delta:
        cursor = 0
        for row in ranges:
            zeros(row['offset'] - cursor, reconstructed)
            fd = full.fileno() if row['kind'] == 'source' else delta.fileno()
            start = row['offset'] if row['kind'] == 'source' else row['literalOffset']
            for pos in range(0, row['bytes'], 1024**2):
                n = min(1024**2, row['bytes'] - pos)
                data = os.pread(fd, n, start + pos)
                need(len(data) == n, 'complete_recipe_read')
                reconstructed.update(data)
            cursor = row['offset'] + row['bytes']
        zeros(size - cursor, reconstructed)
    need(partial_hash.hexdigest() == reconstructed.hexdigest(), 'lossless_partial_reconstruction')
    need({str(p): ident(p) for p in paths} == old['originalFiles'], 'images_never_modified')
    recipe = dict(originalIdentity=ident(paths[1]), originalSHA256=partial_hash.hexdigest(), bytes=size,
                  sourceNativeBackingSHA256=verified['rawSHA256'], originalDataExtents=extents,
                  ranges=ranges, allOtherBytesAreZero=True, literalBytes=delta_bytes,
                  literalDeltaSHA256=sha(I / 'original-partial-literal-delta.bin'),
                  regeneration='Restore the exact original native NAS backup to RAW; create a sparse file of bytes; copy source ranges at identical offsets and literal ranges from the retained delta; verify originalSHA256.')
    save('original-partial-output-lossless-recipe.json', recipe)
    save('native-raw-recovery-acceptance.json', dict(
        status='native_raw_backing_verified_after_optional_conversion_timeout',
        artifact='backup.img', originalNativeToolExit=None, originalFailureCategory='TimeoutExpired',
        originalFailureSHA256=old['originalFailureSHA256'],
        backingVerificationSHA256=owner['backingVerificationSHA256'], backingIdentity=ident(paths[0]),
        rawSHA256=verified['rawSHA256'], backendBytes=verified['backendBytes'], verifiedBlocks=4869,
        allUnbackedRegionsZero=True, encryptedHeaderVerified=True, nativeBackingFormat=info['format'],
        partialRecipeSHA256=sha(I / 'original-partial-output-lossless-recipe.json'),
        partialReconstructionSHA256=reconstructed.hexdigest(), literalBytes=delta_bytes,
        productionRestore=False, decryptedOrMounted=False, NASDownloadedAgain=False,
        optionalConversionCompleted=False, sourceSHA256=owner['sourceSHA256']))
    print(json.dumps(dict(accepted=True, verifiedBlocks=4869, ranges=len(ranges), literalBytes=delta_bytes)))


def main():
    os.umask(0o077)
    if sys.argv[1] == 'worker':
        worker()
        return
    need(os.geteuid() == 0 and F.is_mount() and W.resolve() == W, 'exact_root_full_visibility')
    guard = F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
    need(sha(guard) == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'original_guard')
    scope = {'__name__': 'reference_only'}
    exec(compile(guard.read_bytes(), str(guard), 'exec'), scope)
    scope.update(BASE=F, ATTEMPTS=(str(W.relative_to(F)),))
    with (R / 'operation.lock').open('r+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refs = scope['idle']()
        old = json.loads((I / 'conversion-completion-ownership.json').read_text())
        need({str(p): ident(p) for p in [W / 'backup.img', W / 'volume.raw']} == old['originalFiles'],
             'unchanged_originals')
        proof = json.loads((I / 'conversion-completion-windows-handles.json').read_text())
        need(proof['bothOriginalPathsExclusiveAndClosed'] and
             proof['ownershipSHA256'] == sha(I / 'conversion-completion-ownership.json'), 'original_windows_exclusion')
        save('partial-preservation-ownership.json', dict(
            owner='01a12045-bf7e-73b3-8557-752d17c72ffd', root=str(F),
            physicalFilesystemUUID='3c792469-ea0e-4a2c-98e8-1185b141607b',
            sourceSHA256=sha(Path(__file__)), references=refs,
            backingVerificationSHA256=sha(I / 'completed-native-backing-verification.json'),
            generatedPaths=[str(I / n) for n in ['original-partial-literal-delta.bin',
                'original-partial-output-lossless-recipe.json', 'native-raw-recovery-acceptance.json']],
            maximumAdditionalBytes=32 * 1024**2,
            retainedConsumer='Unique lossless failure recipe plus native recovery acceptance; original NAS data, source, lockfiles and failure logs remain.'))
        props = ['User=brajam', 'Group=brajam', 'MemoryMax=536870912', 'MemorySwapMax=0', 'CPUQuota=100%',
                 'TasksMax=64', 'UMask=0077', 'PrivateNetwork=yes', 'PrivateDevices=yes', 'NoNewPrivileges=yes',
                 'ProtectSystem=strict', 'ReadWritePaths=' + str(I), 'RuntimeMaxSec=1800']
        p = subprocess.run(['systemd-run', '--quiet', '--wait', '--pipe', '--collect', '--unit=' + UNIT,
            '--setenv=BRANCONET_PRESERVATION_SCOPE=' + UNIT, *['--property=' + x for x in props],
            '/usr/bin/python3', '-B', str(Path(__file__).resolve()), 'worker'])
        raise SystemExit(p.returncode)


if __name__ == '__main__':
    main()
