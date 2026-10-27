#!/usr/bin/env python3
"""Add one fingerprint-pinned public CA to Windows CurrentUser/Root."""
import argparse
import ctypes
from ctypes import wintypes as w
import datetime
import hashlib
import json
import os
from pathlib import Path
import ssl

ROOT = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')


class Context(ctypes.Structure):
    _fields_ = [('encoding', w.DWORD), ('encoded', ctypes.POINTER(w.BYTE)), ('size', w.DWORD),
                ('info', ctypes.c_void_p), ('store', ctypes.c_void_p)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--certificate', required=True, type=Path)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--receipt', required=True, type=Path)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--inspect-only', action='store_true')
    a = p.parse_args()
    assert os.name == 'nt' and a.apply != a.inspect_only and len(a.expected_sha256) == 64
    os.environ.update(TEMP=str(ROOT / 'operator-control/tmp'), TMP=str(ROOT / 'operator-control/tmp'))
    assert set(a.expected_sha256) <= set('0123456789abcdef')
    for path in [a.certificate, a.receipt]:
        assert path.resolve().is_relative_to(ROOT.resolve())
    assert not a.receipt.exists()
    raw = a.certificate.read_bytes()
    assert len(raw) < 32768 and raw.count(b'-----BEGIN CERTIFICATE-----') == 1
    der = ssl.PEM_cert_to_DER_cert(raw.decode('ascii'))
    assert hashlib.sha256(der).hexdigest() == a.expected_sha256
    progress = a.receipt.with_suffix('.progress.jsonl')
    assert not progress.exists()

    def mark(stage):
        with progress.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                     'pid': os.getpid(), 'stage': stage, 'inspectOnly': a.inspect_only}) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    api = ctypes.WinDLL('crypt32.dll', use_last_error=True)
    api.CertOpenStore.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
    api.CertOpenStore.restype = ctypes.c_void_p
    api.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, ctypes.POINTER(Context)]
    api.CertEnumCertificatesInStore.restype = ctypes.POINTER(Context)
    api.CertFreeCertificateContext.argtypes = [ctypes.POINTER(Context)]
    api.CertAddEncodedCertificateToStore.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.BYTE),
                                                    w.DWORD, w.DWORD, ctypes.POINTER(ctypes.POINTER(Context))]
    api.CertAddEncodedCertificateToStore.restype = w.BOOL
    api.CertCloseStore.argtypes = [ctypes.c_void_p, w.DWORD]
    # CERT_STORE_PROV_SYSTEM_W, CURRENT_USER, OPEN_EXISTING. Other stores untouched.
    mark('before-open')
    store = api.CertOpenStore(ctypes.c_void_p(10), 0, None, 0x10000 | 0x4000 | (0x8000 if a.inspect_only else 0),
                              ctypes.cast(ctypes.c_wchar_p('ROOT'), ctypes.c_void_p))
    if not store:
        raise ctypes.WinError(ctypes.get_last_error())
    mark('opened')

    def contains():
        previous = ctypes.POINTER(Context)()
        count = 0
        while True:
            ctypes.set_last_error(0)
            current = api.CertEnumCertificatesInStore(store, previous)
            previous = current
            if not current:
                assert ctypes.get_last_error() & 0xffffffff in [0x80092004, 18]
                return False
            count += 1
            assert count <= 4096
            try:
                assert 0 < current.contents.size <= 128 * 1024
                found = hashlib.sha256(ctypes.string_at(current.contents.encoded, current.contents.size)).hexdigest()
            except BaseException:
                api.CertFreeCertificateContext(current)
                raise
            if found == a.expected_sha256:
                api.CertFreeCertificateContext(current)
                return True

    changed = False
    try:
        present = contains()
        mark('enumeration-complete')
        if not present and not a.inspect_only:
            encoded = (w.BYTE * len(der)).from_buffer_copy(der)
            added = ctypes.POINTER(Context)()
            # ADD_NEW; no replacement, removal or private-key import.
            mark('before-add')
            if not api.CertAddEncodedCertificateToStore(store, 0x10001, encoded, len(der), 1, ctypes.byref(added)):
                raise ctypes.WinError(ctypes.get_last_error())
            api.CertFreeCertificateContext(added)
            changed = True
            mark('add-complete')
        trusted = contains()
        assert a.inspect_only or trusted
    finally:
        api.CertCloseStore(store, 0)
    record = {'passed': True, 'changed': changed, 'trusted': trusted, 'inspectOnly': a.inspect_only,
              'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'rootSHA256': a.expected_sha256, 'store': 'CurrentUser/Root', 'privateKeyImported': False,
              'otherCertificatesRemoved': False, 'windowsExecutionPolicyModified': False,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with a.receipt.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
