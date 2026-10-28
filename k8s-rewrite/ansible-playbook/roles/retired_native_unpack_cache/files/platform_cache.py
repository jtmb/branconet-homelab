"""Retire only unused cache of superseded cluster platform and retired web images.

Preserve every current desired/running image, image record, compressed OCI blob,
lease/container and data volume. Complete native/physical/payload/reference
qualification and per-node permanent no-retry journals remain mandatory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
NODES = {'masternode': ('192.168.0.4', '763cda3d-0777-4b03-a882-9d21060466e3'),
    'workernode2': ('192.168.0.5', '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4')}
PREFIXES = ('docker.io/longhornio/', 'registry.k8s.io/sig-storage/', 'quay.io/calico/',
    'docker.io/calico/', 'ghcr.io/fluxcd/', 'quay.io/jetstack/cert-manager',
    'registry.k8s.io/kube-', 'registry.k8s.io/coredns/', 'registry.k8s.io/etcd', 'registry.k8s.io/pause')
WEB = ('docker.io/library/wordpress', 'docker.io/library/mariadb', 'docker.io/library/redis',
    'docker.io/library/phpmyadmin', 'docker.io/phpmyadmin/phpmyadmin',
    'docker.io/library/wordpress-security-20261023', 'docker.io/library/mariadb-security-20261023',
    'docker.io/library/phpmyadmin-security-20261023', 'docker.io/library/redis-security-20261023')
FUTURE = ('sha256:a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7',
    'sha256:a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86')


def current_images(repo):
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
    lib['controls']()
    refs, roots = set(), set(FUTURE)

    def take(spec):
        refs.update(c['image'] for c in spec.get('initContainers', []) + spec.get('containers', []))

    for pod in lib['get']('pods', namespace=None):
        if pod['status'].get('phase') in ('Running', 'Pending') and not pod['metadata'].get('deletionTimestamp'):
            take(pod['spec'])
            for c in pod['status'].get('containerStatuses', []) + pod['status'].get('initContainerStatuses', []):
                digest = c.get('imageID', '').split('@')[-1]
                if re.fullmatch('sha256:[0-9a-f]{64}', digest):
                    roots.add(digest)
    for kind in ('deployments', 'statefulsets', 'daemonsets'):
        for obj in lib['get'](kind, namespace=None):
            if kind == 'daemonsets' or obj['spec'].get('replicas', 1) > 0:
                take(obj['spec']['template']['spec'])
    for ref in refs:
        if '@' in ref:
            digest = ref.split('@')[-1]
            assert re.fullmatch('sha256:[0-9a-f]{64}', digest)
            roots.add(digest)
    return {'roots': sorted(roots), 'references': sorted(refs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--node', choices=NODES, required=True)
    parser.add_argument('--family', choices=['platform', 'mysql'], default='platform')
    a, rest = parser.parse_known_args()
    assert rest and rest[0] in ('qualify', 'retire') and os.geteuid() == 1000 and F.is_mount()
    os.umask(0o077)
    here = Path(__file__).resolve().parent
    repo = here.parents[4]
    protected = current_images(repo)
    cohort = 'retired-' + a.family + '-cache-' + a.node + '-20261028'
    h = O / cohort
    if not h.exists():
        assert rest[0] == 'qualify'
        h.mkdir(mode=0o700)
        with (h / 'ownership.json').open('x') as out:
            json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
                'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b',
                'generatedPaths': [str(h)], 'peakBytes': 128 * 1024**2,
                'purpose': 'Headroom for two scanned official image security updates',
                'regeneration': 'Preserved complete original OCI graph and pinned offline native unpack',
                'protected': 'All current/desired/future image caches, every original image/blob/lease/container/data object and prior failed/submitted keys'}, out, indent=2)
        with (h / 'protected-images.json').open('x') as out:
            json.dump(protected, out, indent=2)
    assert h.resolve() == h and json.loads((h / 'protected-images.json').read_text()) == protected, 'current_workload_image_contract_changed'
    inv = runpy.run_path(str(here / 'inventory.py'))['REMOTE']
    inv = inv.replace('workernode2', a.node)
    inv = inv.replace('assert targets<=set(image_rows)', 'legacy=set(targets);targets=set(image_rows)')
    marker = "assert not unresolved,('unresolved_image_graphs_preserve_all_caches',unresolved)"
    assert inv.count(marker) == 1
    selection = '\ncurrent_roots=set(' + repr(tuple(protected['roots'])) + ');current_refs=set(' + repr(tuple(protected['references'])) + ')\n'
    selection += 'targets={d for d,g in graphs.items() if (d in legacy or any(ref.startswith(' + repr(PREFIXES) + ') or ref.split("@")[0].split(":")[0] in ' + repr(WEB) + ' for ref in image_rows[d])) and not ({d,g["manifestDigest"],g["configDigest"]}&current_roots or set(image_rows[d])&current_refs)}\nassert targets,"no_superseded_platform_graphs"\n'
    if a.family == 'mysql':
        selection = '\ncurrent_roots=set(' + repr(tuple(protected['roots'])) + ');current_refs=set(' + repr(tuple(protected['references'])) + ')\n'
        selection += 'targets={d for d,g in graphs.items() if d=="sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69" and not ({d,g["manifestDigest"],g["configDigest"]}&current_roots or set(image_rows[d])&current_refs)}\nassert targets,"prior_mysql_still_current_or_absent"\n'
    inv = inv.replace(marker, marker + selection)
    base = (here / 'master_retire.py').read_text()
    start = base.index("    inventory = runpy.run_path(str(here / 'inventory.py'))['REMOTE']")
    end = base.index('    physical = ', start)
    code = base[:start] + '    inventory = ' + repr(inv) + '\n' + base[end:]
    code = code.replace('master-cache-capacity-20261028', cohort)
    if a.node != 'masternode':
        code = code.replace('masternode', a.node).replace('192.168.0.4', NODES[a.node][0]).replace(NODES['masternode'][1], NODES[a.node][1])
    insert = "    guard = (F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py').read_bytes()"
    assert code.count(insert) == 1
    code = code.replace(insert, "    remote = remote.replace('1<=len(candidates)<=71', '1<=len(candidates)<=256')\n" + insert)
    prior = [O / ('retired-web-cache-' + a.node + '-20261028')]
    prior += [O / ('retired-platform-cache-' + a.node + '-20261028')]
    prior += [O / ('retired-mysql-cache-' + a.node + '-20261028')]
    prior += [O / 'master-cache-capacity-20261028'] if a.node == 'masternode' else [O / 'longhorn-application-batch-20261028/native-cache-qualification']
    code = code.replace("for path in H.glob('retire-output-*.jsonl'):",
        "for path in [*H.glob('retire-output-*.jsonl'), " + ', '.join('*Path(' + repr(str(p)) + ").glob('retire-output-*.jsonl')" for p in prior) + ']:')
    source_marker = 'source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()'
    assert code.count(source_marker) == 1
    code = code.replace(source_marker, 'source = COMPOSED_CONTROLLER_SHA256')
    compiled = compile(code, '<fixed-superseded-platform-controller>', 'exec')
    sha = hashlib.sha256(code.encode()).hexdigest()
    with (h / ('composition-' + uuid.uuid4().hex + '.json')).open('x') as out:
        json.dump({'node': a.node, 'phaseArgs': rest, 'composedControllerSHA256': sha,
            'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), here / 'master_retire.py', here / 'inventory.py', here / 'physical.py', here / 'retire.py')},
            'currentImagesProtected': protected, 'priorJournalDirectories': [str(p) for p in prior],
            'maxCacheCandidates': 256, 'imageContentOrDataDeletionAuthorized': False}, out, indent=2)
    scope = {'__file__': __file__, '__name__': 'bounded_superseded_platform_controller', 'COMPOSED_CONTROLLER_SHA256': sha}
    exec(compiled, scope)
    sys.argv = [__file__, *rest]
    import fcntl
    with (h / 'retirement.lock').open('a+b') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        scope['main']()


if __name__ == '__main__':
    main()
