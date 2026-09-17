import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_assets


class FetchAssetsTests(unittest.TestCase):
    def test_existing_rom_reused_and_mismatch_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / fetch_assets.ROM_NAME
            target.write_bytes(b"verified ROM")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            with patch.object(fetch_assets, 'ROM_SHA256', digest), patch.object(fetch_assets.subprocess, 'run') as run:
                fetch_assets.fetch_rom(root)
                run.assert_not_called()
                target.write_bytes(b"different ROM")
                with self.assertRaises(ValueError):
                    fetch_assets.fetch_rom(root)
                self.assertEqual(target.read_bytes(), b"different ROM")
                run.assert_not_called()

    def test_verified_download_published_and_failures_cleaned_up(self):
        for mode in ('success', 'wrong_hash', 'interrupted', 'concurrent'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / fetch_assets.ROM_NAME
                def download(args, check):
                    self.assertIn(fetch_assets.ROM_TAG, args)
                    temporary = Path(args[args.index('--output') + 1])
                    temporary.write_bytes(b"wrong" if mode == 'wrong_hash' else b"verified ROM")
                    if mode == 'interrupted':
                        raise subprocess.CalledProcessError(1, args)
                    if mode == 'concurrent':
                        target.write_bytes(b"other process")
                with patch.object(fetch_assets, 'ROM_SHA256', hashlib.sha256(b"verified ROM").hexdigest()), \
                     patch.object(fetch_assets.subprocess, 'run', side_effect=download):
                    if mode == 'success':
                        fetch_assets.fetch_rom(root)
                        self.assertEqual(target.read_bytes(), b"verified ROM")
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, FileExistsError)):
                            fetch_assets.fetch_rom(root)
                        if mode == 'concurrent':
                            self.assertEqual(target.read_bytes(), b"other process")
                        else:
                            self.assertFalse(target.exists())
                self.assertEqual(list(root.glob('.rom-download-*')), [])
