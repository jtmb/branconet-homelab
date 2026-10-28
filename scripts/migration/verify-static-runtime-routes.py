"""Verify the four restored LAN routes with normal Windows certificate trust."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import ssl
import urllib.parse
import urllib.request
import uuid


def main():
    assert os.name == 'nt'
    base = Path(r'\\?\UNC\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
    root = base / 'platform-upstream-review-20261027/longhorn-static-runtime-20261028'
    plan = json.loads((root / 'plan.json').read_text())
    accepted = json.loads((root / 'acceptance.json').read_text())
    assert accepted['status'] == 'four_original_sites_on_new_runtime_with_identical_file_hashes'
    names = ('aplb', 'lucinda-art-gallery', 'minecraft-website', 'santos-web')
    assert [r['name'] for r in plan['records']] == list(names)
    urls = ('https://aplb.branconet.lan/', 'https://lucinda.branconet.lan/',
        'https://mc.branconet.lan/', 'https://santos.branconet.lan/')
    context = ssl.create_default_context()
    rows = []
    for name, url in zip(names, urls, strict=True):
        try:
            with urllib.request.urlopen(url, context=context, timeout=30) as response:
                body = response.read(8 * 1024**2 + 1)
                assert response.status == 200 and 0 < len(body) <= 8 * 1024**2
                assert urllib.parse.urlsplit(response.url).hostname == urllib.parse.urlsplit(url).hostname
                assert urllib.parse.urlsplit(response.url).scheme == 'https'
                rows.append({'site': name, 'URL': url, 'finalURL': response.url, 'HTTPStatus': response.status,
                    'bodyBytes': len(body), 'bodySHA256': hashlib.sha256(body).hexdigest(),
                    'defaultWindowsCertificateTrust': True})
        except (urllib.error.URLError, AssertionError) as error:
            rows.append({'site': name, 'URL': url, 'failure': type(error).__name__,
                'cause': type(getattr(error, 'reason', None)).__name__, 'passed': False})
    value = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'routes': rows,
        'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'runtimeAcceptanceSHA256': hashlib.sha256((root / 'acceptance.json').read_bytes()).hexdigest(),
        'browserAcceptance': False, 'clusterMutationPerformed': False}
    receipt = 'https-routes-' + uuid.uuid4().hex + '.json'
    with (root / receipt).open('x') as out:
        json.dump(value, out, indent=2)
    assert all(r.get('HTTPStatus') == 200 for r in rows), 'route_failure_preserved_in_' + receipt
    print(json.dumps({'status': 'four_default_trust_HTTPS_routes_passed', 'routes': len(rows), 'receipt': receipt}))


if __name__ == '__main__':
    main()
