import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_zip import CHECKER, META, patch_xml, write_zip


class XMLTests(unittest.TestCase):
    ORIGINAL = b'''<?xml version="1.0"?><familyset>
    <!-- Keep comments and unrelated configuration verbatim. -->
    <family lang="zh-Hans"><font index="2">NotoSansCJK-Regular.ttc</font></family>
    <family lang="ja">
        <font weight="400" style="normal" index="0">NotoSansCJK-Regular.ttc</font>
        <font weight="400" style="normal" index="0" fallbackFor="serif">NotoSerifCJK-Regular.ttc</font>
    </family>
    <alias name="example" to="sans-serif" />
    </familyset>'''

    def test_preserves_surrounding_bytes_and_uses_real_ranges(self):
        result = patch_xml(self.ORIGINAL)
        before, rest = self.ORIGINAL.split(b'<family lang="ja">')
        after = rest.split(b"</family>", 1)[1]
        self.assertTrue(result.startswith(before))
        self.assertTrue(result.endswith(after))
        family = ET.fromstring(result).find("./family[@lang='ja']")
        sans = [f for f in family if not f.get("fallbackFor")]
        serif = [f for f in family if f.get("fallbackFor") == "serif"]
        self.assertEqual([int(f.get("weight")) for f in sans], list(range(100, 901, 100)))
        self.assertEqual([int(f.get("weight")) for f in serif], list(range(200, 901, 100)))
        for font in family:
            self.assertEqual(font.get("weight"), font.find("axis").get("stylevalue"))
            self.assertNotIn("postScriptName", font.attrib)

    def test_rejects_unexpected_configuration(self):
        for old in (self.ORIGINAL.replace(b'lang="ja"', b'lang="ko"'),
                    self.ORIGINAL.replace(b'NotoSerifCJK-Regular.ttc', b'CustomSerif.ttf'),
                    self.ORIGINAL.replace(b'</familyset>', b'<family lang="ja" /></familyset>')):
            with self.assertRaises(ValueError):
                patch_xml(old)


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
            # Actual /sbin/busybox remains a device-side prerequisite.
            (path / "bb.sh").write_text('#!/bin/sh\nexec "$@"\n', newline="\n")
            (path / "bb.sh").chmod(0o755)
            (path / "check.sh").write_bytes(CHECKER.replace(b"BB=/sbin/busybox", b"BB=./bb.sh"))
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
            (path / "font").write_bytes(b"modified font")
            self.assertNotEqual(run("optional", "font", digest), 0)


if __name__ == "__main__":
    unittest.main()
