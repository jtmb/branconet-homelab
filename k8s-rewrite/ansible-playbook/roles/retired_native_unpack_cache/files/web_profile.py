"""Read-only cache sizing for the user-retired WordPress stack on one node.

Keep every image record and original blob. Current native containers/leases and
all other image graph parents remain protected by the existing readers. This
command never qualifies or submits a removal.
"""
import argparse
import hashlib
import json
from pathlib import Path

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
NODES = {'masternode': '192.168.0.4', 'workernode2': '192.168.0.5'}


def compose(node):
    original = Path(__file__).with_name('master_profile.py').read_text()
    code = original
    old = "targets &= set(image_rows);assert targets"
    new = "web={d for d,refs in image_rows.items() if any(ref.split('@')[0].split(':')[0] in " + repr(tuple(sorted({
        'docker.io/library/wordpress', 'docker.io/library/mariadb', 'docker.io/library/redis',
        'docker.io/library/phpmyadmin', 'docker.io/phpmyadmin/phpmyadmin',
        'docker.io/library/wordpress-security-20261023', 'docker.io/library/mariadb-security-20261023',
        'docker.io/library/phpmyadmin-security-20261023', 'docker.io/library/redis-security-20261023'}))) + " for ref in refs)};targets=(targets|web)&set(image_rows);assert web,'no_retired_web_image_records'"
    assert code.count(repr(old)) == 1
    code = code.replace(repr(old), repr(new))
    code = code.replace('master-cache-capacity-20261028', 'retired-web-cache-' + node + '-20261028')
    if node != 'masternode':
        code = code.replace('masternode', node).replace('192.168.0.4', NODES[node])
    return original, code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--node', choices=NODES, required=True)
    node = p.parse_args().node
    original, source = compose(node)
    h = F / ('platform-upstream-review-20261027/retired-web-cache-' + node + '-20261028')
    scope = {'__name__': 'bounded_retired_web_profile', '__file__': __file__}
    exec(compile(source, '<composed-read-only-web-profile>', 'exec'), scope)
    try:
        scope['main']()
    finally:
        if h.is_dir():
            with (h / 'reader-composition.json').open('x') as out:
                json.dump({'node': node, 'wrapperSourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'masterReaderSourceSHA256': hashlib.sha256(original.encode()).hexdigest(),
                    'composedReaderSHA256': hashlib.sha256(source.encode()).hexdigest(),
                    'retirementAuthorized': False, 'mutationsPerformed': False}, out, indent=2)


if __name__ == '__main__':
    main()
