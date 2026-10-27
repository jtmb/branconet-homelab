"""Prove exact exported ELF files have no competing Windows read handles."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import re
from pathlib import Path

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
C = F / 'operator-control'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--profile', choices=('initial', 'ingenium'), default='initial')
    selection.add_argument('--plan-key', help='Exact 16-hex namespace returned by the bounded Linux stage inventory')
    args = parser.parse_args()
    assert not args.plan_key or re.fullmatch(r'[0-9a-f]{16}', args.plan_key)
    prefix = 'publisher-headroom-' + args.plan_key + '-' if args.plan_key else 'publisher-headroom-ingenium-' if args.profile == 'ingenium' else 'publisher-headroom-'
    expected_count = 6 if args.profile == 'ingenium' else 12
    assert os.name == 'nt'
    os.environ.update(TEMP=str(C / 'tmp'), TMP=str(C / 'tmp'), TMPDIR=str(C / 'tmp'))
    plan = json.loads((C / (prefix + 'plan-20261027.json')).read_text())
    if args.plan_key:
        assert plan['stageProfile'] == 'explicit' and 1 <= len(plan['stages']) <= 8
        stages = {Path(v['stage']).name.removeprefix('local-charts-publish-'): v['sourceSHA'] for v in plan['stages']}
        token = hashlib.sha256(json.dumps(stages, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]
        assert token == args.plan_key
        expected_count = len(stages) * 3
    assert len(plan['targets']) == expected_count // 3 * 4
    assert plan['stageProfile'] == ('explicit' if args.plan_key else args.profile)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    records = []
    for row in plan['targets']:
        if row['kind'] != 'file':
            continue
        path = F / Path(row['relative'])
        assert path.resolve().is_relative_to(F.resolve()) and path.name in plan['originalToolsSHA256']
        handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise OSError(ctypes.get_last_error(), 'exclusive Windows tool read refused')
        try:
            value, count = hashlib.sha256(), 0
            buffer, read = ctypes.create_string_buffer(1024**2), wintypes.DWORD()
            while True:
                assert kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(read), None)
                if not read.value:
                    break
                count += read.value
                value.update(buffer.raw[:read.value])
            assert value.hexdigest() == plan['originalToolsSHA256'][path.name] == row['sha256']
            assert count == row['identity']['size']
            records.append({'relative': row['relative'], 'bytes': count, 'sha256': value.hexdigest(),
                            'exclusiveWindowsReadSucceeded': True})
        finally:
            kernel.CloseHandle(handle)
    assert len(records) == expected_count
    result = {'status': 'completed', 'nativePID': os.getpid(),
              'planSHA256': hashlib.sha256((C / (prefix + 'plan-20261027.json')).read_bytes()).hexdigest(),
              'files': records, 'handlesClosed': True}
    with (C / (prefix + 'windows-proof-20261027.json')).open('x') as out:
        json.dump(result, out, indent=2)
    print(json.dumps({'status': 'completed', 'exclusiveFilesVerified': len(records)}))


if __name__ == '__main__':
    main()
