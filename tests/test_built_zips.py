"""Exercise the shipped recovery payload against the real ROM XML after a build."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from targets import TARGETS


class BuiltZipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = {(component, mode): ROOT / 'dist' / f'echo-show-{component}-fonts-{mode}.zip'
                     for component in ('cjk', 'latin', 'serif', 'mono') for mode in ('install', 'restore')}
        if not all(path.exists() for path in cls.paths.values()):
            raise unittest.SkipTest('Run mise run build for archive integration tests')
        if not (ROOT / 'build/fonts.original.xml').exists():
            raise unittest.SkipTest('Extracted ROM XML required')
    def test_archive_hashes_and_separate_font_payloads(self):
        manifest = dict(line.split('  ', 1)[::-1] for line in
                        (ROOT / 'dist/SHA256SUMS.txt').read_text().splitlines())
        for (component, mode), path in self.paths.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest[path.name])
            with zipfile.ZipFile(path) as archive:
                report = ROOT / 'dist' / f'echo-show-{component}-fonts-verification.json'
                self.assertEqual(report.read_bytes(), archive.read('verification.json'))
                compatibility = json.loads(report.read_bytes())['compatibility']
                self.assertEqual({r['device']: r['sha256'] for r in compatibility['roms']},
                                 {device: t['sha256'] for device, t in TARGETS.items()})
                self.assertEqual(len(compatibility['stock_font_sha256']), 255)
                for target in TARGETS.values():
                    self.assertIn(target['fingerprint'].encode(), archive.read('META-INF/com/google/android/updater-script'))
                fonts = {name for name in archive.namelist() if name.startswith('system/fonts/')}
                if component == 'latin':
                    self.assertEqual(fonts, {'system/fonts/GoogleSansFlex-Regular.ttf'} if mode == 'install' else set())
                elif component in ('serif', 'mono'):
                    from named_fonts import COMPONENTS
                    expected = {'system/fonts/' + f[0] for f in COMPONENTS[component]['fonts'].values()}
                    self.assertEqual(fonts, expected if mode == 'install' else set())
                else:
                    self.assertEqual(len(fonts), 2)
                    self.assertTrue(all('Noto' in name for name in fonts))
                self.assertNotIn('system/etc/fonts.xml', archive.namelist())
                self.assertEqual(archive.read('patch/format'), b'1\n')
                self.assertEqual(archive.read('patch/font_slots.py'), (ROOT / 'scripts/font_slots.py').read_bytes())
                self.assertEqual(archive.read('patch/font_patch.py'), (ROOT / 'recovery/font_patch.py').read_bytes())
                self.assertNotIn('patch/split-fonts.awk', archive.namelist())
                self.assertNotIn('patch/compose-fonts.sh', archive.namelist())
                runtime = json.loads(archive.read('runtime/verification.json'))
                for name, expected in runtime['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected, name)

    def test_real_rom_transitions_reuse_recovery_workspace(self):
        for device in TARGETS:
            folder = ROOT / 'build' if device == 'cronos' else ROOT / 'build' / device
            with self.subTest(device=device):
                self.check_real_rom_transitions((folder / 'fonts.original.xml').read_bytes())

    def check_real_rom_transitions(self, original):
        from build_cjk import patch_cjk
        from build_latin import patch_latin
        from build_named import patch_named
        from font_slots import OWNERS, compose_xml, split_xml
        patches = {'cjk': patch_cjk(original), 'latin': patch_latin(original),
                   **{key: patch_named(original, key) for key in ('serif', 'mono')}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fonts.xml').write_bytes(original)
            active = set()
            sequence = [('cjk', 'install'), ('latin', 'install'), ('cjk', 'restore'),
                        ('cjk', 'install'), ('latin', 'restore'), ('cjk', 'restore'),
                        ('latin', 'install'), ('latin', 'install'), ('latin', 'restore'), ('latin', 'restore')]
            sequence += [(key, 'install') for key in OWNERS]
            sequence += [('serif', 'install'), ('mono', 'install')]
            sequence += [(key, 'restore') for key in ('latin', 'serif', 'cjk', 'mono')]
            sequence += [('serif', 'restore'), ('mono', 'restore')]
            for component, mode in sequence:
                with zipfile.ZipFile(self.paths[component, mode]) as archive:
                    for name in archive.namelist():
                        if not name.startswith('patch/'):
                            continue
                        path = root / name
                        path.parent.mkdir(exist_ok=True)
                        data = archive.read(name)
                        path.write_bytes(data)
                for action in ('prepare', 'stage'):
                    result = subprocess.run([sys.executable, '-B', 'patch/font_patch.py', action,
                                             'fonts.xml', 'patch', 'work'], cwd=root, capture_output=True, check=False)
                    self.assertEqual(result.returncode, 0, (component, mode, action, result.stderr))
                (root / 'fonts.xml.jpfont-new').replace(root / 'fonts.xml')
                if mode == 'install':
                    active.add(component)
                else:
                    active.discard(component)
                skeleton, slots = split_xml(original)
                for key in active:
                    changed = split_xml(patches[key])[1]
                    for slot in OWNERS[key]:
                        slots[slot] = changed[slot]
                self.assertEqual((root / 'fonts.xml').read_bytes(), compose_xml(skeleton, slots))


if __name__ == '__main__':
    unittest.main()
