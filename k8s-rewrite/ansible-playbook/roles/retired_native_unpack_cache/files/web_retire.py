"""Qualify/retire only unused filesystem caches of the retired web stack.

Original image/content records remain protected. Reuse the unchanged complete
native payload/reference guards, fixed host/UUIDs and no-retry journal protocol.
The composed controller and all source dependencies are hashed independently.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
import sys
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
NODES = {'masternode': ('192.168.0.4', '763cda3d-0777-4b03-a882-9d21060466e3'),
    'workernode2': ('192.168.0.5', '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4')}


def main():
    p = argparse.ArgumentParser(description=__doc__, add_help=False)
    p.add_argument('--node', choices=NODES, required=True)
    args, rest = p.parse_known_args()
    here = Path(__file__).resolve().parent
    reader = runpy.run_path(str(here / 'web_profile.py'))
    _, composed_reader = reader['compose'](args.node)
    matches = [x for x in ast.walk(ast.parse(composed_reader)) if isinstance(x, ast.Call)
        and isinstance(x.func, ast.Attribute) and x.func.attr == 'replace' and len(x.args) == 2
        and isinstance(x.args[0], ast.Constant) and x.args[0].value == 'assert targets<=set(image_rows)']
    assert len(matches) == 1
    statement = ast.literal_eval(matches[0].args[1])
    base = (here / 'master_retire.py').read_text()
    code = base.replace(repr('targets &= set(image_rows);assert targets'), repr(statement))
    assert code != base
    code = code.replace('master-cache-capacity-20261028', 'retired-web-cache-' + args.node + '-20261028')
    if args.node != 'masternode':
        code = code.replace('masternode', args.node).replace('192.168.0.4', NODES[args.node][0])
        code = code.replace(NODES['masternode'][1], NODES[args.node][1])
    prior = F / ('platform-upstream-review-20261027/master-cache-capacity-20261028' if args.node == 'masternode'
        else 'platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification')
    code = code.replace("for path in H.glob('retire-output-*.jsonl'):",
        "for path in [*H.glob('retire-output-*.jsonl'), *Path(" + repr(str(prior)) + ").glob('retire-output-*.jsonl')]:")
    marker = 'source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()'
    assert code.count(marker) == 1
    code = code.replace(marker, 'source = COMPOSED_CONTROLLER_SHA256')
    compiled = compile(code, '<fixed-retired-web-controller>', 'exec')
    h = F / ('platform-upstream-review-20261027/retired-web-cache-' + args.node + '-20261028')
    assert h.is_dir() and (h / 'ownership.json').is_file()
    source_paths = [Path(__file__), here / 'master_retire.py', here / 'web_profile.py', here / 'master_profile.py',
                    here / 'inventory.py', here / 'physical.py', here / 'retire.py']
    manifest = {x.name: hashlib.sha256(x.read_bytes()).hexdigest() for x in source_paths}
    closure = {'node': args.node, 'phaseArgs': rest, 'sources': manifest,
        'composedControllerSHA256': hashlib.sha256(code.encode()).hexdigest(),
        'originalPriorSubmissionJournalDirectory': str(prior),
        'allPriorSubmittedKeysProtected': True, 'nativeImageOrDataDeletionAuthorized': False}
    with (h / ('controller-composition-' + uuid.uuid4().hex + '.json')).open('x') as out:
        json.dump(closure, out, indent=2)
    scope = {'__file__': __file__, '__name__': 'bounded_retired_web_controller',
        'COMPOSED_CONTROLLER_SHA256': closure['composedControllerSHA256']}
    exec(compiled, scope)
    sys.argv = [__file__, *rest]
    import fcntl
    with (h / 'retirement.lock').open('a+b') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        scope['main']()


if __name__ == '__main__':
    main()
