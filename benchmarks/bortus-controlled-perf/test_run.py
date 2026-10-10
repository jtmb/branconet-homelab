import importlib.util
import io
import json
import os
import pathlib
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('controlled_perf_runner', pathlib.Path(__file__).with_name('run.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class SourceProvenanceTests(unittest.TestCase):
    def test_failure_archive_refuses_success_duplicate_and_stale_result_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            result = root / 'candidate-run-1.json'
            step = {'phase': 'candidate-run-1', 'passed': False, 'started_at_unix': 100}
            record = {'passed': False, 'steps': [step]}
            observed = {'passed': False, 'label': 'candidate', 'run': 1, 'failures': [{'kind': 'fixed assertion'}]}
            result.write_text(json.dumps(observed))
            os.utime(result, (101, 101))
            self.assertEqual(runner.failed_runtime_outputs(record, root), [observed])
            record['passed'] = True
            self.assertEqual(runner.failed_runtime_outputs(record, root), [])
            record['passed'] = False
            observed['passed'] = True
            result.write_text(json.dumps(observed))
            self.assertEqual(runner.failed_runtime_outputs(record, root), [])
            observed['passed'] = False
            result.write_text(json.dumps(observed))
            os.utime(result, (99, 99))
            self.assertEqual(runner.failed_runtime_outputs(record, root), [])

    def test_manifest_refuses_windows_eol_conversion_and_missing_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            source = root / 'package.json'
            source.write_bytes(b'{\n"fixture":true\n}\n')
            manifest = runner.source_manifest(root)
            self.assertTrue(runner.unchanged(root, manifest))
            source.write_bytes(b'{\r\n"fixture":true\r\n}\r\n')
            self.assertFalse(runner.unchanged(root, manifest))
            source.unlink()
            self.assertFalse(runner.unchanged(root, manifest))

    def test_extract_rejects_parent_absolute_paths_and_links_before_writing(self):
        for name, kind in [('../escaped', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), ('source-link', tarfile.SYMTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root = pathlib.Path(folder)
                archive = root / 'fixture.tar'
                target = root / 'target'
                target.mkdir()
                with tarfile.open(archive, 'w') as stream:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = '../escaped'
                    member.size = 0
                    stream.addfile(member, io.BytesIO(b''))
                with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                    runner.extract(archive, target)
                self.assertEqual(list(target.iterdir()), [])

    def test_exact_exported_source_bytes_survive_safe_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            target = root / 'target'
            target.mkdir()
            data = b'export const fixture = "metadata";\n'
            archive = root / 'fixture.tar'
            with tarfile.open(archive, 'w') as stream:
                member = tarfile.TarInfo('src/fixture.ts')
                member.mode, member.size = 0o644, len(data)
                stream.addfile(member, io.BytesIO(data))
            runner.extract(archive, target)
            self.assertEqual((target / 'src/fixture.ts').read_bytes(), data)

if __name__ == '__main__':
    unittest.main()
