"""Patch only the scanner-identified provider dependencies and existing locks."""
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
from urllib.request import urlopen

ROOT = Path('/opt/bgutil-provider')
PATCHES = (
    ('follow-redirects', '1.16.0', '1.16.1',
     'sha512-FNvFGzoMLWmE6Yj9spb/zjd7yiNCHiAW9/Tg9CXrQ8wuu32HtlJOwWO11OJafl5FfY3DxTdQ0vj42zU1kvv5jg=='),
    ('ip-address', '10.7.3', '10.7.4',
     'sha512-DWBMKyeM25D70nrIiTkgQth59/G+naKOTep6huF9j+GmeK3DMD60Zvxg5d5qQnz+38AHgou6ean2LECX+lrKDg=='),
)


def rewrite(value, name, old, new, url, integrity, context=''):
    if isinstance(value, list):
        return [rewrite(item, name, old, new, url, integrity, context) for item in value]
    if not isinstance(value, dict):
        if isinstance(value, str):
            if name in context and value == old:
                return new
            return value.replace(name + '@' + old, name + '@' + new).replace(
                name + '-' + old + '.tgz', name + '-' + new + '.tgz')
        return value
    result = {}
    for key, item in value.items():
        new_key = key.replace(name + '@' + old, name + '@' + new)
        result[new_key] = rewrite(item, name, old, new, url, integrity, new_key)
    if context.endswith(name) or context.startswith(name + '@'):
        if 'version' in result:
            result['version'] = new
        if 'resolved' in result:
            result['resolved'] = url
        if 'integrity' in result:
            result['integrity'] = integrity if result['integrity'].startswith('sha512-') else integrity[7:]
    return result


def patch_package(name, old, new, integrity):
    package_dir = ROOT / 'node_modules' / name
    url = f'https://registry.npmjs.org/{name}/-/{name}-{new}.tgz'
    installed = json.loads((package_dir / 'package.json').read_text())
    if installed.get('name') != name or installed.get('version') != old:
        raise SystemExit('Unexpected provider dependency layout/version; review the immutable base')
    with urlopen(url, timeout=90) as response:
        archive = response.read(1024 * 1024)
    actual = base64.b64encode(hashlib.sha512(archive).digest()).decode()
    if actual != integrity[7:]:
        raise SystemExit('Pinned npm package integrity mismatch')
    # This exact directory is fixed above; no source/credential/runtime volume is used.
    shutil.rmtree(package_dir)
    package_dir.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as bundle:
        for member in bundle.getmembers():
            parts = Path(member.name).parts
            if not parts or parts[0] != 'package' or '..' in parts or member.issym() or member.islnk():
                raise SystemExit('Unexpected npm archive member')
            if not member.isfile():
                continue
            target = package_dir.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.extractfile(member).read())
    if json.loads((package_dir / 'package.json').read_text()).get('version') != new:
        raise SystemExit('Patched provider package version mismatch')
    # The upstream Dockerfile copies deno.lock and node_modules (including npm's
    # hidden package lock), but does not promise a root package-lock.json.
    for lock_name in ('deno.lock', 'package-lock.json', 'node_modules/.package-lock.json'):
        path = ROOT / lock_name
        if path.exists():
            updated = json.dumps(rewrite(json.loads(path.read_text()), name, old, new, url, integrity), indent=2) + '\n'
            if name + '@' + old in updated or name + '-' + old + '.tgz' in updated:
                raise SystemExit('An old provider lock reference remains; review lock structure')
            path.write_text(updated)
    package_path = ROOT / 'package.json'
    package = json.loads(package_path.read_text())
    package.setdefault('overrides', {})[name] = new
    package_path.write_text(json.dumps(package, indent=2) + '\n')
    print(f'Patched {name} {new} and existing provider lock metadata')


def main():
    for patch in PATCHES:
        patch_package(*patch)


if __name__ == '__main__':
    main()
