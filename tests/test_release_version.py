import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.validate_release_version import validate_version


def release(tag, *, draft=False, prerelease=False):
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


class ReleaseVersionTests(unittest.TestCase):
    def test_each_increment(self):
        for version in ("2.0.0", "v1.3.0", "1.2.4"):
            with self.subTest(version=version):
                validate_version(version, [release("v1.2.3")])

    def test_invalid_increments(self):
        for version in ("1.2.3", "1.2.2", "0.9.0", "3.0.0", "1.4.0", "1.2.5", "2.2.3", "1.3.3"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_version(version, [release("v1.2.3")])

    def test_first_release(self):
        for version in ("0.0.1", "0.1.0", "1.0.0"):
            with self.subTest(version=version):
                validate_version(version, [])
        for version in ("0.0.0", "0.2.0", "1.1.0", "2.0.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_version(version, [])

    def test_numeric_maximum_not_api_order(self):
        releases = [release("v1.9.9"), release("v1.10.0"), release("v0.1.0")]
        validate_version("1.10.1", releases)
        with self.assertRaises(ValueError):
            validate_version("1.9.10", releases)

    def test_draft_retry_and_nonversion_tags(self):
        releases = [release("v0.1.0", draft=True), release("nightly"), release("v2.0.0-rc.1")]
        validate_version("0.1.0", releases)
        releases.append(release("v0.1.0"))
        with self.assertRaises(ValueError):
            validate_version("0.1.0", releases)

    def test_published_prerelease_counts(self):
        validate_version("1.1.0", [release("1.0.0", prerelease=True)])

    def test_invalid_format(self):
        for version in ("", "01.0.0", "1.0", "1.0.0-rc.1", "1.0.0\n", "vv1.0.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_version(version, [])

    def test_cli_reads_all_pages_and_returns_failure(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_version.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "releases.json"
            path.write_text(json.dumps([[release("v1.0.0")], [release("v1.2.3")]]), encoding="utf-8")
            for version, code in (("1.2.4", 0), ("1.0.1", 1)):
                result = subprocess.run([sys.executable, str(script), version, str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                if code:
                    self.assertIn("allowed: v2.0.0, v1.3.0, v1.2.4", result.stderr)


if __name__ == "__main__":
    unittest.main()
