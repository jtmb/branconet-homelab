"""Pure reviewed restore spec/identity checks; no API, admission or image proof."""
import copy
import importlib.util
import pathlib
import re
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


health = load('restore_admitted_health', 'bortus-restored-consumer-fence.py')
KINDS = {'storageclass': ('storage.k8s.io/v1', 'StorageClass', None),
         'claim': ('v1', 'PersistentVolumeClaim', 'bortus'), 'pod': ('v1', 'Pod', 'bortus')}


class AdmittedRefused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Restore admitted spec refused: ' + code)


def need(ok, code):
    if not ok:
        raise AdmittedRefused(code)


def _validate(resource, proposal, reply, current, require_ready):
    try:
        need(type(resource) is str and resource in KINDS and type(require_ready) is bool, 'scope')
        for obj in (proposal, reply, current):
            health.bounded(obj)
            need(type(obj) is dict and type(obj.get('metadata')) is dict, 'shape')
        api, kind, ns = KINDS[resource]
        name = proposal['metadata']['name']
        need(type(name) is str and re.fullmatch(r'bortus-restore-[0-9a-f]{12}', name), 'ownership')
        label = {'bortus-restore': name[len('bortus-restore-'):]}
        for obj in (proposal, reply, current):
            need(obj.get('apiVersion') == api and obj.get('kind') == kind and
                 obj['metadata'].get('name') == name and
                 obj['metadata'].get('namespace') in ((None, '') if ns is None else (ns,)) and
                 health.strict_equal(obj['metadata'].get('labels'), label) and
                 not obj['metadata'].get('ownerReferences') and
                 not obj['metadata'].get('deletionTimestamp'), 'ownership')
        created, fresh = health.identity(reply, ns), health.identity(current, ns)
        need(created[:3] == fresh[:3], 'identity')  # Opaque current RV may advance.
        if resource == 'storageclass':
            fields = {'apiVersion', 'kind', 'metadata', 'provisioner', 'parameters',
                      'reclaimPolicy', 'volumeBindingMode', 'allowVolumeExpansion'}
            need(set(proposal) == fields and set(current) == fields and
                 health.strict_equal({k: current[k] for k in fields - {'metadata'}},
                                     {k: proposal[k] for k in fields - {'metadata'}}), 'spec')
        elif resource == 'claim':
            need(set(current) <= {'apiVersion', 'kind', 'metadata', 'spec', 'status'} and
                 current['metadata'].get('annotations', {}).get('helm.sh/resource-policy') == 'keep' and
                 type(current.get('spec')) is dict, 'spec')
            spec = copy.deepcopy(current['spec'])
            if 'volumeMode' in spec:
                need(spec.pop('volumeMode') == 'Filesystem', 'spec')
            if 'volumeName' in spec:
                health.name(spec.pop('volumeName'))  # Binding is independently fenced.
            need(health.strict_equal(spec, proposal.get('spec')), 'spec')
        else:
            need(set(current) <= {'apiVersion', 'kind', 'metadata', 'spec', 'status'}, 'spec')
            spec = proposal['spec']
            image = spec['containers'][0]['image']
            claim = spec['volumes'][0]['persistentVolumeClaim']['claimName']
            node = spec['nodeName']
            need(health.strict_equal(spec, health.holder_spec(image, claim, node)), 'spec')
            health.holder_matches(current, image, claim, node, require_ready=require_ready)
        return fresh, None
    except AdmittedRefused as error:
        return None, error.code
    except Exception:
        return None, 'spec'


def validate(resource, proposal, reply, current, *, require_ready=False):
    """Proposal must already be authorized by MutationAPI; current must be a fresh GET."""
    value, failure = _validate(resource, proposal, reply, current, require_ready)
    if failure:
        raise AdmittedRefused(failure)
    return value


def _absent(collection, owned):
    try:
        health.bounded(collection)
        health.bounded(owned)
        need(type(owned) is dict and set(owned) == {'name', 'namespace', 'uid', 'resourceVersion'}, 'ownership')
        identity = health.identity({'metadata': owned}, 'bortus')
        need(re.fullmatch(r'bortus-restore-[0-9a-f]{12}', identity.name), 'ownership')
        items, rv = health.collection(collection, 'v1', 'Pod', 'bortus')
        # A same-name replacement is unresolved ownership, never a successful cleanup.
        need(not any(obj['metadata']['name'] == identity.name or obj['metadata']['uid'] == identity.uid
                     for obj in items), 'present')
        return rv, None
    except AdmittedRefused as error:
        return None, error.code
    except Exception:
        return None, 'collection'


def holder_absent(collection, owned):
    """Only complete fresh namespace LIST absence; no 404/reply/terminating shortcut."""
    value, failure = _absent(collection, owned)
    if failure:
        raise AdmittedRefused(failure)
    return value
