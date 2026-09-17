import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_zip import CHECKER, META, patch_xml, write_zip, updater, LEGACY_XML_HASH


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
        before, rest = self.ORIGINAL.split(b'<family lang="zh-Hans">')
        after = self.ORIGINAL.split(b'<alias', 1)[1]
        self.assertTrue(result.startswith(before))
        self.assertTrue(result.endswith(after))
        self.assertNotIn(b'NotoSansCJK-Regular.ttc', result)
        self.assertNotIn(b'NotoSerifCJK-Regular.ttc', result)
        tree = ET.fromstring(result)
        for lang, index in {'ja': '0', 'ko': '1', 'zh-Hans': '2', 'zh-Hant,zh-Bopo': '3', 'zh-Hant-HK': '4'}.items():
            family = tree.find(f"./family[@lang='{lang}']")
            sans = [f for f in family if not f.get("fallbackFor")]
            serif = [f for f in family if f.get("fallbackFor") == "serif"]
            self.assertEqual([int(f.get("weight")) for f in sans], list(range(100, 901, 100)))
            self.assertEqual([int(f.get("weight")) for f in serif], list(range(200, 901, 100)))
            self.assertEqual({f.text for f in sans}, {'NotoSansCJK-VF.ttf.ttc'})
            self.assertEqual({f.text for f in serif}, {'NotoSerifCJK-VF.ttf.ttc'})
            for font in family:
                self.assertEqual(font.get('index'), index)
                self.assertEqual(font.get("weight"), font.find("axis").get("stylevalue"))
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
    def test_install_restore_order_and_legacy_upgrade_guards(self):
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
            self.assertIn(LEGACY_XML_HASH, script)
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
    @classmethod
    def setUpClass(cls):
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        cls.shell = str(git_bash) if git_bash.exists() else shutil.which("bash")
        if not cls.shell:
            raise unittest.SkipTest("bash required for host execution of the recovery hash guard")

    def test_matching_modified_missing_and_alternate_hashes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            path = Path(directory)
            # Host shim exposes the same BusyBox applet calling convention.
            # Actual Toybox/BusyBox remains a device-side prerequisite.
            (path / "bb.sh").write_text('#!/bin/sh\nexec "$@"\n', newline="\n")
            (path / "bb.sh").chmod(0o755)
            (path / "check.sh").write_bytes(CHECKER.replace(
                b'BB=/sbin/toybox\n[ -x "$BB" ] || BB=/sbin/busybox', b"BB=./bb.sh"))
            (path / "font").write_bytes(b"correct font contents")
            digest = hashlib.sha256((path / "font").read_bytes()).hexdigest()

            def run(*args):
                return subprocess.run([self.shell, "check.sh", *args], cwd=path, capture_output=True).returncode

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
