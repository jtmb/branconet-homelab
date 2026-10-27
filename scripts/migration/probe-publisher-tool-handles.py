"""Prove exact exported ELF files have no competing Windows read handles."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
C = F / 'operator-control'


def main():
    assert os.name == 'nt'
    os.environ.update(TEMP=str(C / 'tmp'), TMP=str(C / 'tmp'), TMPDIR=str(C / 'tmp'))
    plan = json.loads((C / 'publisher-headroom-plan-20261027.json').read_text())
    assert len(plan['targets']) == 16
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
    assert len(records) == 12
    result = {'status': 'completed', 'nativePID': os.getpid(),
              'planSHA256': hashlib.sha256((C / 'publisher-headroom-plan-20261027.json').read_bytes()).hexdigest(),
              'files': records, 'handlesClosed': True}
    with (C / 'publisher-headroom-windows-proof-20261027.json').open('x') as out:
        json.dump(result, out, indent=2)
    print(json.dumps({'status': 'completed', 'exclusiveFilesVerified': len(records)}))


if __name__ == '__main__':
    main()
