import hashlib
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# The script imports require the search path configured above.
from build_zip import META, patch_xml, updater, write_zip


class XMLTests(unittest.TestCase):
    ORIGINAL = b'''<?xml version="1.0"?><familyset>
    <!-- Keep comments and unrelated configuration verbatim. -->
    <family lang="en"><font weight="400">Roboto-Regular.ttf</font></family>
    <family lang="zh-Hans">
        <font weight="400" style="normal" index="2">NotoSansCJK-Regular.ttc</font>
        <font weight="400" style="normal" index="2" fallbackFor="serif">NotoSerifCJK-Regular.ttc</font>
    </family>
    <family lang="zh-Hant,zh-Bopo">
        <font weight="400" style="normal" index="3">NotoSansCJK-Regular.ttc</font>
        <font weight="400" style="normal" index="3" fallbackFor="serif">NotoSerifCJK-Regular.ttc</font>
    </family>
    <family lang="ja">
        <font weight="400" style="normal" index="0">NotoSansCJK-Regular.ttc</font>
        <font weight="400" style="normal" index="0" fallbackFor="serif">NotoSerifCJK-Regular.ttc</font>
    </family>
    <family lang="ko">
        <font weight="400" style="normal" index="1">NotoSansCJK-Regular.ttc</font>
        <font weight="400" style="normal" index="1" fallbackFor="serif">NotoSerifCJK-Regular.ttc</font>
    </family>
    <alias name="example" to="sans-serif" />
    </familyset>'''

    def test_preserves_surrounding_bytes_and_uses_real_ranges(self):
        result = patch_xml(self.ORIGINAL)
        before, _rest = self.ORIGINAL.split(b'<family lang="zh-Hans">')
        after = self.ORIGINAL.split(b'<alias', 1)[1]
        self.assertTrue(result.startswith(before))
        self.assertTrue(result.endswith(after))
        self.assertNotIn(b'NotoSansCJK-Regular.ttc', result)
        self.assertNotIn(b'NotoSerifCJK-Regular.ttc', result)
        tree = ET.fromstring(result)
        for lang, index in {'ja': '0', 'ko': '1', 'zh-Hans': '2', 'zh-Hant,zh-Bopo': '3', 'zh-Hant-HK': '4'}.items():
            family = tree.find(f"./family[@lang='{lang}']")
            assert family is not None
            sans = [f for f in family if not f.get("fallbackFor")]
            serif = [f for f in family if f.get("fallbackFor") == "serif"]
            self.assertEqual([int(f.attrib["weight"]) for f in sans], list(range(100, 901, 100)))
            self.assertEqual([int(f.attrib["weight"]) for f in serif], list(range(200, 901, 100)))
            self.assertEqual({f.text for f in sans}, {'NotoSansCJK-VF.ttf.ttc'})
            self.assertEqual({f.text for f in serif}, {'NotoSerifCJK-VF.ttf.ttc'})
            for font in family:
                self.assertEqual(font.get('index'), index)
                axis = font.find("axis")
                assert axis is not None
                self.assertEqual(font.get("weight"), axis.get("stylevalue"))
                self.assertNotIn("postScriptName", font.attrib)

    def test_rejects_unexpected_configuration(self):
        for old in (self.ORIGINAL.replace(b'lang="ja"', b'lang="ko"'),
                    self.ORIGINAL.replace(b'NotoSerifCJK-Regular.ttc', b'CustomSerif.ttf'),
                    self.ORIGINAL.replace(b'</familyset>', b'<family lang="ja" /></familyset>')):
            with self.assertRaises(ValueError):
                patch_xml(old)

    def test_rejects_extra_old_font_reference_and_wrong_region(self):
        for old in (self.ORIGINAL.replace(b'Roboto-Regular.ttf', b'NotoSansCJK-Regular.ttc'),
                    self.ORIGINAL.replace(b'index="2"', b'index="0"')):
            with self.assertRaises(ValueError):
                patch_xml(old)


class UpdaterTests(unittest.TestCase):
    def test_install_restore_order_and_supported_xml_guards(self):
        infos = {k: {'file': f'Noto{f}CJK-VF.ttf.ttc', 'sha256': '1' * 64}
                 for k, f in [('sans', 'Sans'), ('serif', 'Serif')]}
        originals = {k: {'file': f'Noto{f}CJK-Regular.ttc', 'sha256': '2' * 64}
                     for k, f in [('sans', 'Sans'), ('serif', 'Serif')]}
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'build.prop').write_text('ro.system.build.fingerprint=test\n')
            with patch('build_zip.BUILD', Path(directory)):
                install = updater(b'original', b'patched', infos, originals).decode()
                restore = updater(b'original', b'patched', infos, originals, True).decode()
        for script in [install, restore]:
            self.assertLess(script.index('"prepare"'), script.index('package_extract_file("system/'))
            self.assertIn('"stage"', script)
            xml_commit = script.index('assert(rename("/tmp/jp-font-system/system/etc/fonts.xml.jpfont-new"')
            payloads = originals if script == restore else infos
            for info in payloads.values():
                self.assertLess(script.index(f'assert(rename("/tmp/jp-font-system/system/fonts/{info["file"]}.jpfont-new"'), xml_commit)
            for line in script.splitlines():
                if 'delete(' in line:
                    self.assertGreater(script.index(line), xml_commit)
        self.assertIn('"absent", "/tmp/jp-font-system/system/fonts/NotoSansCJK-Regular.ttc"', install)
        # Stock files must be identified before deletion or overwrite, including on restore.
        for script in [install, restore]:
            self.assertLess(script.index('"optional", "/tmp/jp-font-system/system/fonts/NotoSansCJK-Regular.ttc"'),
                            script.index('package_extract_file("system/'))


class ZipTests(unittest.TestCase):
    def test_deterministic_zip_and_unix_executable_mode(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            paths = [Path(directory) / name for name in ("a.zip", "b.zip")]
            entries = {META + "update-binary": b"binary", "system/etc/fonts.xml": b"xml"}
            for path in paths:
                write_zip(path, entries)
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
            with zipfile.ZipFile(paths[0]) as archive:
                self.assertEqual(archive.getinfo(META + "update-binary").external_attr >> 16 & 0o777, 0o755)


class RecoveryHashGuardTests(unittest.TestCase):
    def test_matching_modified_missing_and_alternate_hashes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            path = Path(directory)
            (path / "font").write_bytes(b"correct font contents")
            digest = hashlib.sha256((path / "font").read_bytes()).hexdigest()

            def run(*args):
                return subprocess.run([sys.executable, "-B", str(ROOT / "recovery/font_patch.py"), "check", *args], cwd=path, capture_output=True, check=False, env=dict(__import__("os").environ, PYTHONPATH=str(ROOT / "scripts"))).returncode

            self.assertEqual(run("ready"), 0)
            self.assertEqual(run("hash", "font", digest), 0)
            self.assertEqual(run("hash", "font", "0" * 64, digest), 0)
            self.assertNotEqual(run("hash", "font", "0" * 64), 0)
            self.assertEqual(run("optional", "absent", digest), 0)
            self.assertNotEqual(run("hash", "absent", digest), 0)
            self.assertEqual(run("absent", "absent"), 0)
            self.assertNotEqual(run("absent", "font"), 0)
            (path / "font").write_bytes(b"modified font")
            self.assertNotEqual(run("optional", "font", digest), 0)


if __name__ == "__main__":
    unittest.main()
