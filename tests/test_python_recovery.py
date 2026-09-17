"""Fail-closed preparation/staging and runtime dependency regressions."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from build_cjk import patch_cjk
from build_common import recovery_payload
from python_runtime import ASSETS, CACHE, runtime_payload, verify
from test_font_slots import ORIGINAL

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('font_patch', ROOT / 'recovery/font_patch.py')
assert spec is not None and spec.loader is not None
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class PythonRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'fonts.xml'
        self.source.write_bytes(ORIGINAL)
        self.args = tuple(str(self.root / p) for p in ('fonts.xml', 'patch', 'work'))
        for name, data in recovery_payload(ORIGINAL, patch_cjk(ORIGINAL), 'cjk', False).items():
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)

    def test_failed_retry_invalidates_previous_preparation(self):
        recovery.prepare(*self.args)
        self.source.write_bytes(ORIGINAL + b'<!-- modified skeleton -->')
        with self.assertRaises(ValueError):
            recovery.prepare(*self.args)
        self.source.write_bytes(ORIGINAL)
        with self.assertRaises(ValueError):
            recovery.stage(*self.args)
        self.assertFalse(Path(str(self.source) + '.jpfont-new').exists())

    def test_corrupt_payload_and_prepared_output_are_rejected(self):
        fragment = self.root / 'patch/cjk-ja'
        original = fragment.read_bytes()
        fragment.write_bytes(original + b'corrupt')
        with self.assertRaises(ValueError):
            recovery.prepare(*self.args)
        fragment.write_bytes(original)
        recovery.prepare(*self.args)
        (self.root / 'work/fonts.xml').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            recovery.stage(*self.args)
        self.assertFalse(Path(str(self.source) + '.jpfont-new').exists())

    def test_rejects_directory_staging_target(self):
        recovery.prepare(*self.args)
        Path(str(self.source) + '.jpfont-new').mkdir()
        with self.assertRaises(ValueError):
            recovery.stage(*self.args)

    def test_preserves_unowned_comments_and_noncanonical_line_endings(self):
        data = ORIGINAL.replace(b'DroidSansMono.ttf', b'CustomMono.ttf\r\n        <!-- untouched -->')
        self.source.write_bytes(data)
        recovery.prepare(*self.args)
        recovery.stage(*self.args)
        self.assertEqual(Path(str(self.source) + '.jpfont-new').read_bytes(), patch_cjk(data))

    def test_rejects_duplicate_and_traversal_manifest_keys(self):
        path = self.root / 'patch/slots.txt'
        original = path.read_bytes()
        for bad in (original + original.splitlines()[0] + b'\n', original.replace(b'cjk-ja', b'../fonts.xml')):
            path.write_bytes(bad)
            with self.assertRaises(ValueError):
                recovery.prepare(*self.args)


class PythonRuntimeTests(unittest.TestCase):
    def test_rejects_corrupted_download(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'runtime.apk'
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError):
                verify(path, '0' * 64)

    def test_runtime_is_self_contained_and_has_notices(self):
        if not all((CACHE / n).exists() for n in ASSETS):
            self.skipTest('Run mise run fetch-assets to fetch pinned runtime inputs')
        files = runtime_payload()
        report = json.loads(files['runtime/verification.json'])
        self.assertIn('licenses/Python-LICENSE.txt', files)
        self.assertIn('licenses/musl-COPYRIGHT.txt', files)
        self.assertIn('runtime/usr/bin/python3.12', report['elf_dependencies'])
        provided = {Path(p).name for p in report['elf_dependencies']}
        for needed in report['elf_dependencies'].values():
            self.assertTrue(set(needed) <= provided)
        for name, expected in report['files'].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), expected)
        self.assertFalse(any('_hashlib.' in n or n.endswith('.pyc') for n in files))


if __name__ == '__main__':
    unittest.main()
