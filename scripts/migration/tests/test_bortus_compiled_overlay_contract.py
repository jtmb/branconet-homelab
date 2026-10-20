"""Finite public packaging controls; no transport, daemon, app, or corpus run."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import tarfile
import tempfile
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent.parent
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

c = load('overlay_contract', 'bortus-compiled-overlay-contract.py')
s = load('legacy_stage_controls', 'stage-bortus-release-image.py')
n = load('legacy_node_controls', 'bortus-release-preload-node.py')
def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
def sha(value):
    return hashlib.sha256(value).hexdigest()


class OverlayControls(unittest.TestCase):
    def setUp(self):
        for target in ('subprocess.Popen', 'subprocess.run', 'os.system'):
            guard = mock.patch(target, side_effect=AssertionError('external execution forbidden'))
            guard.start()
            self.addCleanup(guard.stop)
        self.contract = json.loads((HERE / 'contracts/compiled-overlay-7940e9e1-v1.json').read_bytes())
        self.authorities = {k: ('PUBLIC AUTHORITY ' + k).encode() for k in self.contract['authority_sha256']}
        self.contract['authority_sha256'] = {k: sha(v) for k, v in self.authorities.items()}
        self.contract['labels']['io.branconet.bortus.context-sha256'] = self.contract['authority_sha256']['raw_git_context']
        self.contract['labels']['io.branconet.bortus.manifest-sha256'] = self.contract['authority_sha256']['raw_git_manifest']
        self.layers = [gzip.compress(('PUBLIC LAYER ' + str(i)).encode(), mtime=0) for i in range(19)] + [b'PUBLIC APP LAYER']
        self.build()

    def build(self, repeated=False, media_wrong=False):
        if repeated:
            self.layers[1] = self.layers[0]
        self.contract['layers'] = [dict(digest='sha256:' + sha(data), size=len(data),
            mediaType='application/vnd.oci.image.layer.v1.tar' + ('+gzip' if i < 19 else ''))
            for i, data in enumerate(self.layers)]
        if media_wrong:
            self.contract['layers'][0]['mediaType'] = 'application/vnd.oci.image.layer.v1.tar'
        self.contract['ordered_diff_ids'] = ['sha256:' + sha(gzip.decompress(data) if i < 19 else data)
                                              for i, data in enumerate(self.layers)]
        self.config = raw(dict(os='linux', architecture='amd64', config={
            'Labels': self.contract['labels'], 'Env': ['PUBLIC_ENV_SENTINEL=never-return']},
            rootfs=dict(type='layers', diff_ids=self.contract['ordered_diff_ids'])))
        self.contract['raw_config_digest'] = 'sha256:' + sha(self.config)
        self.contract['raw_config_bytes'] = len(self.config)
        self.manifest = raw(dict(schemaVersion=2, mediaType='application/vnd.oci.image.manifest.v1+json',
            config=dict(mediaType='application/vnd.oci.image.config.v1+json',
                        digest=self.contract['raw_config_digest'], size=len(self.config)), layers=self.contract['layers']))
        self.contract['manifest_digest'] = self.contract['local_image_id'] = 'sha256:' + sha(self.manifest)
        self.contract['manifest_bytes'] = len(self.manifest)
        self.index = dict(schemaVersion=2, mediaType='application/vnd.oci.image.index.v1+json', manifests=[dict(
            mediaType='application/vnd.oci.image.manifest.v1+json', digest=self.contract['manifest_digest'], size=len(self.manifest),
            annotations={'io.containerd.image.name': self.contract['canonical_alias'],
                         'org.opencontainers.image.ref.name': self.contract['image_tag'].split(':')[1]})])
        self.files = {'oci-layout': raw({'imageLayoutVersion': '1.0.0'}), 'index.json': raw(self.index),
            'manifest.json': raw([dict(Config='blobs/sha256/' + sha(self.config), RepoTags=[self.contract['image_tag']],
                Layers=['blobs/sha256/' + sha(data) for data in self.layers])]),
            'blobs/sha256/' + sha(self.config): self.config, 'blobs/sha256/' + sha(self.manifest): self.manifest}
        self.files.update({'blobs/sha256/' + sha(data): data for data in self.layers})
        self.archive()

    def archive(self, extra=None, duplicate=False, symlink=False, trailing=False):
        out = io.BytesIO()
        pairs = list(self.files.items()) + (extra or [])
        if duplicate:
            pairs.append(pairs[0])
        with tarfile.open(fileobj=out, mode='w') as tar:
            for name, data in pairs:
                member = tarfile.TarInfo(name)
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
            if symlink:
                member = tarfile.TarInfo('link')
                member.type, member.linkname = tarfile.SYMTYPE, 'index.json'
                tar.addfile(member)
        self.archive_raw = out.getvalue() + (b'NONZERO TRAILING' if trailing else b'')
        self.contract['archive_sha256'] = sha(self.archive_raw)
        self.contract['archive_bytes'] = len(self.archive_raw)

    def verify(self):
        with tempfile.TemporaryFile() as f:
            f.write(self.archive_raw)
            f.seek(0)
            return c.verify_archive(f, self.contract)

    def export(self):
        value = raw(c.expected_export_record(self.contract))
        return value, sha(value)

    def envelope(self):
        value, pin = self.export()
        return c.preload_envelopes(self.contract, value, pin)[0], pin

    def inventory(self, ref=None, root=None):
        return ('REF TYPE DIGEST SIZE PLATFORMS LABELS\n' + (ref or self.contract['image_tag']) +
                ' type ' + (root or self.contract['manifest_digest']) + ' 1 linux/amd64 -\n').encode()

    def observe(self, env=None, inventory=None, manifest=None, config=None):
        envelope, pin = self.envelope()
        return c.verify_node_observation(env if env is not None else envelope, self.contract, pin,
            inventory if inventory is not None else self.inventory(), manifest if manifest is not None else self.manifest,
            config if config is not None else self.config)

    def test_01_exact_public_contract_and_independent_hash_pin(self):
        data = (HERE / 'contracts/compiled-overlay-7940e9e1-v1.json').read_bytes()
        value = c.load_contract(data, 'a47ea88d868bc99e0007ca78af7f393a616db4cbbfd03fd59f62c69c4c397ca1')
        self.assertEqual(value['archive_bytes'], 991697920)
        self.assertEqual(len(value['layers']), 20)
        self.assertNotEqual(value['manifest_digest'], value['raw_config_digest'])
        with self.assertRaises(ValueError):
            c.load_contract(data + b' ', sha(data))

    def test_02_closed_recipe_scope_types_and_source_contract(self):
        changes = [('recipe', 'release-v2'), ('format', 'v1'), ('deployed', True), ('runtime_qualified', 0),
                   ('archive_bytes', True), ('manifest_bytes', 0), ('build_id', '../escape'),
                   ('image_tag', 'bortus:release-' + self.contract['source_commit']),
                   ('local_image_id', self.contract['raw_config_digest'])]
        for key, value in changes:
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate = copy.deepcopy(self.contract)
                candidate[key] = value
                c.validate_contract(candidate)
        for labels in ({}, dict(self.contract['labels'], extra='bad')):
            with self.assertRaises(ValueError):
                c.validate_contract(dict(self.contract, labels=labels))

    def test_03_duplicate_nonfinite_unknown_and_oversize_json(self):
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'x' * (8 * 1024 ** 2 + 1)):
            with self.assertRaises(ValueError):
                c.decode(data)
        with self.assertRaises(ValueError):
            c.validate_contract(dict(self.contract, sudo_password='PUBLIC_SENTINEL'))

    def test_04_separate_authorities_match_and_drift_refuses(self):
        self.assertTrue(c.verify_authorities(self.contract, {k: io.BytesIO(v) for k, v in self.authorities.items()}))
        for key in self.authorities:
            values = {k: io.BytesIO(v + (b'drift' if k == key else b'')) for k, v in self.authorities.items()}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'authority_identity'):
                c.verify_authorities(self.contract, values)
        with self.assertRaises(ValueError):
            c.verify_authorities(self.contract, {})

    def test_05_real_twenty_layer_archive_positive_and_no_env_return(self):
        result = self.verify()
        self.assertEqual(result['purpose'], 'export-contract')
        self.assertIs(result['runtime_qualified'], False)
        self.assertNotIn('PUBLIC_ENV_SENTINEL', json.dumps(result))

    def test_06_archive_checksum_and_config_identity_cannot_be_substituted(self):
        for key, value in [('archive_sha256', '0' * 64), ('raw_config_digest', self.contract['manifest_digest']),
                           ('archive_bytes', len(self.archive_raw) + 1)]:
            old = self.contract[key]
            self.contract[key] = value
            with self.subTest(key=key), self.assertRaises(Exception):
                self.verify()
            self.contract[key] = old

    def test_07_order_count_and_diff_id_changes_refuse(self):
        original = copy.deepcopy(self.contract)
        for change in ('order', 'count', 'diff'):
            self.contract = copy.deepcopy(original)
            if change == 'order':
                self.contract['layers'][0:2] = self.contract['layers'][1::-1]
            elif change == 'count':
                self.contract['layers'].pop()
            else:
                self.contract['ordered_diff_ids'][0] = 'sha256:' + '0' * 64
            with self.subTest(change=change), self.assertRaises(Exception):
                self.verify()

    def test_08_duplicate_path_link_extra_and_trailing_refuse(self):
        for options in ({'duplicate': True}, {'extra': [('../escape', b'x')]}, {'symlink': True},
                        {'extra': [('unselected', b'x')]}, {'trailing': True}):
            self.archive(**options)
            with self.subTest(options=options), self.assertRaises(Exception):
                self.verify()

    def test_09_direct_index_digest_size_annotations_and_ambiguity_refuse(self):
        for kind in ('digest', 'size', 'annotation', 'ambiguous'):
            index = copy.deepcopy(self.index)
            if kind == 'digest': index['manifests'][0]['digest'] = self.contract['raw_config_digest']
            if kind == 'size': index['manifests'][0]['size'] += 1
            if kind == 'annotation': index['manifests'][0]['annotations']['io.containerd.image.name'] = 'wrong:tag'
            if kind == 'ambiguous': index['manifests'].append(index['manifests'][0])
            self.files['index.json'] = raw(index)
            self.archive()
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'archive_index'):
                self.verify()

    def test_10_descriptor_size_and_gzip_media_refuse(self):
        self.build(media_wrong=True)
        with self.assertRaisesRegex(ValueError, 'archive_layer_media'):
            self.verify()
        self.build()
        self.contract['layers'][0]['size'] += 1
        with self.assertRaisesRegex(ValueError, 'archive_manifest'):
            self.verify()

    def test_11_repeated_ordered_layer_overlay_allowed_v1_still_refuses(self):
        self.build(repeated=True)
        self.verify()
        with tempfile.TemporaryFile() as f:
            f.write(self.archive_raw)
            f.seek(0)
            with self.assertRaises(s.b.BuildRefused) as error:
                s.archive_identity(f, self.contract['image_tag'], self.contract['raw_config_digest'], self.contract['labels'])
            self.assertEqual(error.exception.code, 'image_inventory')

    def test_12_export_record_pin_scope_and_unknown_fields_refuse(self):
        data, pin = self.export()
        self.assertEqual(c.verify_export_record(data, pin, self.contract), pin)
        for key, value in [('runtime_qualified', True), ('deployed', 0), ('purpose', 'export'), ('extra', None)]:
            record = json.loads(data)
            record[key] = value
            changed = raw(record)
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.verify_export_record(changed, sha(changed), self.contract)
        with self.assertRaises(ValueError):
            c.verify_export_record(data, '0' * 64, self.contract)

    def test_13_three_fixed_sequential_credential_free_envelopes(self):
        data, pin = self.export()
        values = c.preload_envelopes(self.contract, data, pin)
        self.assertEqual([(v['host'], v['ordinal']) for v in values],
                         [('192.168.0.4', 1), ('192.168.0.5', 2), ('192.168.0.6', 3)])
        self.assertNotIn('sudo_password', json.dumps(values))
        for value in values:
            result = c.verify_node_observation(value, self.contract, pin, self.inventory(), self.manifest, self.config)
            self.assertIs(result['runtime_qualified'], False)
        values[0]['contract']['layers'].clear()
        self.assertEqual(len(values[1]['contract']['layers']), 20)

    def test_14_node_tag_both_spellings_match_exact_manifest(self):
        self.observe()
        self.observe(inventory=self.inventory(ref=self.contract['canonical_alias']))
        self.assertNotIn('PUBLIC_ENV_SENTINEL', json.dumps(self.observe()))

    def test_15_node_envelope_credential_host_ordinal_recipe_and_scope_refuse(self):
        envelope, _ = self.envelope()
        for key, value in [('sudo_password', 'PUBLIC_SENTINEL'), ('host', '192.168.0.7'), ('ordinal', True),
                           ('runtime_qualified', 0), ('deployed', True), ('export_record_sha256', '0' * 64)]:
            candidate = copy.deepcopy(envelope)
            candidate[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.observe(env=candidate)

    def test_16_node_missing_duplicate_changed_tag_and_malformed_inventory_refuse(self):
        for value in (b'REF TYPE DIGEST\n', b'WRONG\n', self.inventory() + self.inventory().split(b'\n')[1] + b'\n',
                      self.inventory(root=self.contract['raw_config_digest']), self.inventory(ref='wrong:tag')):
            with self.subTest(value=value[:32]), self.assertRaises(ValueError):
                self.observe(inventory=value)

    def test_17_node_manifest_config_label_and_platform_byte_drift_refuse(self):
        config = json.loads(self.config)
        config['architecture'] = 'arm64'
        for manifest, config_bytes in ((self.manifest + b' ', self.config), (self.manifest, raw(config)),
                                       (self.config, self.manifest)):
            with self.assertRaises(ValueError):
                self.observe(manifest=manifest, config=config_bytes)

    def test_18_legacy_node_refuses_new_envelope_before_authorization(self):
        envelope, _ = self.envelope()
        authorize = mock.Mock(side_effect=AssertionError('authorization forbidden'))
        with self.assertRaisesRegex(RuntimeError, '^request$'):
            n.receive(envelope, io.BytesIO(self.archive_raw), pathlib.Path('/unselected'), authorize=authorize)
        authorize.assert_not_called()

    def legacy_record(self, release=False):
        labels = {k: self.contract['labels'][k] for k in s.b.LABEL_KEYS}
        if release:
            labels[s.b.BASE_LABEL] = self.contract['labels'][s.b.BASE_LABEL]
        record = dict(scope='Immutable BORTUS image build only; no runtime/deployment acceptance', phase='completed',
            source_commit=self.contract['source_commit'], image_tag='bortus:release-' + self.contract['source_commit'],
            build_exit_code=0, inspect_exit_code=0, **{'tag-check_exit_code': 0}, image_bytes=1234,
            application_tree=self.contract['application_tree'], context_sha256=labels[s.b.LABEL_KEYS[2]],
            manifest_sha256=labels[s.b.LABEL_KEYS[3]], owner=labels[s.b.LABEL_KEYS[4]], labels=labels,
            deployed=False, runtime_accepted=False, runtime_digest_qualified=False, image_manifest_digest=None)
        if release:
            record.update(build_recipe='release-v2', builder_transport='local', dockerfile='Dockerfile.release',
                dockerfile_sha256='1' * 64, runtime_image=labels[s.b.BASE_LABEL], runtime_image_id=self.contract['runtime_base_id'],
                local_image_id=self.contract['local_image_id'], **{'runtime-before_exit_code': 0, 'runtime-after_exit_code': 0})
        else:
            record['config_image_id'] = self.contract['raw_config_digest']
        return record

    def legacy_receipt(self, record, release=False):
        data = raw(record)
        run = types.SimpleNamespace(record={'purpose': 'export', 'image_tag': record['image_tag']},
            copy_input=lambda *a: None, open_input=lambda *a: io.BytesIO(data))
        return s.receipt(run, None, sha(data), self.contract['source_commit'],
                         self.contract['local_image_id'] if release else self.contract['raw_config_digest'])

    def test_19_legacy_v1_and_release_v2_receipts_positive_new_recipe_refuses(self):
        for release in (False, True):
            record = self.legacy_record(release)
            self.legacy_receipt(record, release)
            record['build_recipe'] = 'compiled-overlay-v1'
            with self.assertRaises(s.b.BuildRefused):
                self.legacy_receipt(record, release)
            record = self.legacy_record(release)
            record['labels'].update(self.contract['labels'])
            with self.assertRaises(s.b.BuildRefused):
                self.legacy_receipt(record, release)

    def test_20_readonly_cli_contract_only_and_no_export_preload_flags(self):
        import sys
        with mock.patch.object(sys, 'argv', ['contract', '--contract', str(HERE / 'contracts/compiled-overlay-7940e9e1-v1.json'),
                '--contract-sha256', 'a47ea88d868bc99e0007ca78af7f393a616db4cbbfd03fd59f62c69c4c397ca1']), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(c.main(), 0)
            self.assertIs(json.loads(out.getvalue())['runtime_qualified'], False)
        with mock.patch.object(sys, 'argv', ['contract', 'preload']), mock.patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                c.main()

    def test_21_archive_change_after_initial_hash_refuses(self):
        original = s.archive_identity
        def changed(stream, *args, **kwargs):
            result = original(stream, *args, **kwargs)
            stream.seek(0, 2)
            stream.write(b'\0')
            stream.flush()
            return result
        with mock.patch.object(c, 'archive_module', return_value=s), \
                mock.patch.object(s, 'archive_identity', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'archive_changed'):
                self.verify()

    def test_22_nonregular_archive_refuses_before_parser(self):
        with open('/dev/null', 'rb') as stream, mock.patch.object(c, 'archive_module') as parser:
            with self.assertRaisesRegex(ValueError, 'archive_regular'):
                c.verify_archive(stream, self.contract)
            parser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
