#!/usr/bin/env python3
"""Offline compiled-overlay-v1 packaging. Never invokes a build, install or migration.

The worker runs in an externally constrained, read-only container. Its output is
an OCI image archive, preserving the base layers and replacing /app atomically
with an opaque whiteout. The controller must independently verify inputs, output
and container limits before importing this artifact into the local Docker store.
This recipe is deliberately separate from the release-v2 builder/exporter.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for raw in iter(lambda: f.read(65536), b''):
            h.update(raw)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def safe(name):
    p = PurePosixPath(name)
    require(name and not p.is_absolute() and '\\' not in name and
            all(v not in ('', '.', '..') for v in name.split('/')), 'unsafe_path')


def regular(tar, name, raw, mode=0o644, uid=0, gid=0):
    safe(name)
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.uid, info.gid = len(raw), mode, uid, gid
    tar.addfile(info, io.BytesIO(raw))


def assemble(source, base_path, authority_path, output, input_dir=Path('/inputs')):
    require(not output.exists(), 'output_exists')
    a = json.loads(authority_path.read_text())
    require(a['recipe'] == 'compiled-overlay-v1' and a['reviewed'] is True, 'authority')
    require(filehash(base_path) == a['baseArchiveSHA256'], 'base_archive')
    graph = json.loads((input_dir/'compiled-dependency-manifest.json').read_text())
    inputs = json.loads((input_dir/'build-source-manifest.json').read_text(encoding='utf-8-sig'))
    lock = json.loads((source/'package-lock.json').read_text())
    require(filehash(source/'package-lock.json') == inputs['package-lock.json'], 'lock')
    # Select installed production/optional-production packages from the exact lock.
    # Missing optional packages are excluded; required packages must be present.
    packages = {}
    for name, meta in lock['packages'].items():
        if not name or meta.get('dev') or meta.get('devOptional'):
            continue
        safe(name)
        require(name.startswith('node_modules/'), 'package_path')
        if not (source/name).exists():
            require(meta.get('optional') is True, 'missing_production_package')
            continue
        packages[name] = meta
    require('node_modules/prisma' in packages, 'prisma_cli')
    selected = {}
    def choose(dest, rel, expected):
        safe(dest)
        require(dest not in selected, 'duplicate_payload')
        selected[dest] = (rel, expected)
    standalone = '.next/standalone/'
    for rel, expected in graph.items():
        if rel.startswith(standalone) and not rel.startswith(standalone+'node_modules/'):
            choose('app/'+rel[len(standalone):], rel, expected)
        elif rel.startswith('.next/static/'):
            choose('app/'+rel, rel, expected)
        elif rel.startswith('node_modules/'):
            # The deepest package controls nested dev dependencies.
            owners = [p for p in lock['packages'] if p and rel.startswith(p+'/')]
            owner = max(owners, key=len) if owners else None
            if owner in packages or rel.startswith('node_modules/.prisma/'):
                choose('app/'+rel, rel, expected)
            elif rel.startswith('node_modules/.bin/') and 'link' in expected:
                target = os.path.normpath(str(PurePosixPath(rel).parent/expected['link']))
                if any(target.startswith(p+'/') for p in packages):
                    choose('app/'+rel, rel, expected)
    for rel, expected in inputs.items():
        if rel.startswith(('public/', 'prisma/')):
            dest = 'app/'+rel
            if dest in selected:
                require(selected[dest][1].get('sha256') == expected, 'standalone_schema')
            else:
                info = (source/rel).lstat()
                choose(dest, rel, {'sha256':expected, 'mode':stat.S_IMODE(info.st_mode), 'bytes':info.st_size})
    # The entrypoint alone has the same CRLF-to-LF normalization as release-v2.
    entry = (source/'docker-entrypoint.sh').read_bytes()
    require(digest(entry) == inputs['docker-entrypoint.sh'], 'entrypoint')
    entry = entry.replace(b'\r\n', b'\n')
    require('app/node_modules/.bin/prisma' in selected and
            'app/runtime/direct-account-reader-worker.cjs' in selected and
            'app/native/secret-flat-selector.node' in selected, 'runtime_payload')
    require((source/'.next/BUILD_ID').read_text().strip() == a['buildId'], 'build_id')
    layer_path = output.with_suffix('.layer.tar')
    inventory = {}
    with layer_path.open('xb') as f, tarfile.open(fileobj=f, mode='w', format=tarfile.PAX_FORMAT) as tar:
        # OCI opaque marker hides every old /app child, including stale statics.
        regular(tar, 'app/.wh..wh..opq', b'', uid=1000, gid=1000)
        for dest, (rel, expected) in sorted(selected.items()):
            p = source/rel
            info = p.lstat()
            require(stat.S_IMODE(info.st_mode) == expected['mode'], 'payload_mode')
            if 'link' in expected:
                require(p.is_symlink() and os.readlink(p) == expected['link'], 'payload_link')
                require(not os.path.isabs(expected['link']) and
                        os.path.normpath(str(PurePosixPath(dest).parent/expected['link'])).startswith('app/'), 'link_escape')
                t = tarfile.TarInfo(dest)
                t.type, t.linkname, t.mode, t.uid, t.gid = tarfile.SYMTYPE, expected['link'], expected['mode'], 1000, 1000
                tar.addfile(t)
                inventory[dest] = {'link':t.linkname, 'mode':t.mode, 'source':rel}
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_size == expected['bytes'], 'payload_file')
                raw = p.read_bytes()
                require(digest(raw) == expected['sha256'], 'payload_hash')
                regular(tar, dest, raw, expected['mode'], 1000, 1000)
                inventory[dest] = {'sha256':digest(raw), 'bytes':len(raw), 'mode':expected['mode'], 'source':rel}
        regular(tar, 'app/docker-entrypoint.sh', entry, 0o755, 1000, 1000)
        inventory['app/docker-entrypoint.sh'] = {'sha256':digest(entry), 'bytes':len(entry), 'mode':0o755, 'normalization':'CRLF-to-LF only'}
    require(layer_path.stat().st_size < 2*1024**3, 'layer_bound')
    layer_sha = filehash(layer_path)
    # Base export has already passed the original complete OCI/diffID parser.
    # Authenticate its selected chain again when constructing the new descriptor.
    with tarfile.open(base_path) as base:
        def blob(desc):
            raw = base.extractfile('blobs/sha256/'+desc['digest'][7:]).read()
            require(len(raw) == desc['size'] and digest(raw) == desc['digest'][7:], 'base_blob')
            return json.loads(raw)
        top = json.load(base.extractfile('index.json'))
        require(len(top['manifests']) == 1 and top['manifests'][0]['digest'] == a['baseId'], 'base_index')
        index = blob(top['manifests'][0])
        runtime = [d for d in index['manifests'] if d.get('platform') == {'architecture':'amd64','os':'linux'}]
        require(len(runtime) == 1, 'base_platform')
        manifest = blob(runtime[0])
        config = blob(manifest['config'])
        require(config['architecture'] == 'amd64' and config['os'] == 'linux', 'base_config')
        config = copy.deepcopy(config)
        config['config']['Labels'] = a['labels']
        config['history'].append({'created_by':'BORTUS compiled-overlay-v1; offline precompiled payload; no install/build', 'comment':a['sourceCommit']})
        config['rootfs']['diff_ids'].append('sha256:'+layer_sha)
        cfg = encoded(config)
        config_sha = digest(cfg)
        leaf = {'schemaVersion':2, 'mediaType':'application/vnd.oci.image.manifest.v1+json',
                'config':{'mediaType':'application/vnd.oci.image.config.v1+json','digest':'sha256:'+config_sha,'size':len(cfg)},
                'layers':manifest['layers']+[{'mediaType':'application/vnd.oci.image.layer.v1.tar','digest':'sha256:'+layer_sha,'size':layer_path.stat().st_size}]}
        leafraw = encoded(leaf)
        leafsha = digest(leafraw)
        idx = encoded({'schemaVersion':2,'mediaType':'application/vnd.oci.image.index.v1+json',
                       'manifests':[{'mediaType':leaf['mediaType'],'digest':'sha256:'+leafsha,'size':len(leafraw),
                                     'platform':{'architecture':'amd64','os':'linux'},
                                     'annotations':{'org.opencontainers.image.ref.name':a['imageTag']}}]})
        docker = encoded([{'Config':'blobs/sha256/'+config_sha, 'RepoTags':[a['imageTag']],
                           'Layers':['blobs/sha256/'+d['digest'][7:] for d in leaf['layers']]}])
        with output.open('xb') as f, tarfile.open(fileobj=f, mode='w', format=tarfile.PAX_FORMAT) as tar:
            for name, raw in [('oci-layout',b'{"imageLayoutVersion":"1.0.0"}'),('index.json',idx),
                              ('manifest.json',docker),('blobs/sha256/'+config_sha,cfg),('blobs/sha256/'+leafsha,leafraw)]:
                regular(tar,name,raw)
            for name in sorted({'blobs/sha256/'+d['digest'][7:] for d in manifest['layers']}):
                member = base.getmember(name)
                require(member.isfile() and member.size <= 4*1024**3, 'base_layer')
                tar.addfile(member,base.extractfile(member))
            member = tarfile.TarInfo('blobs/sha256/'+layer_sha)
            member.size, member.mode = layer_path.stat().st_size, 0o644
            with layer_path.open('rb') as stream:
                tar.addfile(member,stream)
    result = {'recipe':'compiled-overlay-v1','sourceCommit':a['sourceCommit'], 'buildId':a['buildId'],
              'imageTag':a['imageTag'],'configId':'sha256:'+config_sha,'manifestDigest':'sha256:'+leafsha,
              'archiveSHA256':filehash(output),'archiveBytes':output.stat().st_size,
              'appLayerSHA256':layer_sha,'productionPackages':len(packages),'payloadEntries':len(inventory),
              'baseLayers':len(manifest['layers']),'orderedLayers':len(leaf['layers']),
              'baseConfigPreservedExceptLabelsHistoryRootfs':True,'installed':False,'rebuilt':False,
              'runtimeAccepted':False,'securityAccepted':False,'deployed':False}
    for name, value in [('payload-inventory.json',inventory),('assembly-result.json',result)]:
        with (output.parent/name).open('x') as f:
            json.dump(value,f,indent=2)
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--authority',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    assemble(args.source,args.base,args.authority,args.output)
