import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_assets


class FetchAssetsTests(unittest.TestCase):
    def test_latin_pinned_url_hash_reuse_and_mismatch(self):
        data = b'public Google Sans Flex fixture'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(fetch_assets, 'LATIN_SHA256', hashlib.sha256(data).hexdigest()), \
                 patch.object(fetch_assets, 'urlopen', return_value=io.BytesIO(data)) as download:
                fetch_assets.fetch_latin(root)
                self.assertIn(fetch_assets.LATIN_COMMIT, download.call_args.args[0].full_url)
                self.assertEqual(download.call_args.args[0].full_url, fetch_assets.LATIN_URL)
                fetch_assets.fetch_latin(root)
                self.assertEqual(download.call_count, 1)
                target = root / fetch_assets.LATIN_FILE
                target.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    fetch_assets.fetch_latin(root)
                self.assertEqual(target.read_bytes(), b'changed')
                self.assertEqual(download.call_count, 1)

    def test_existing_rom_reused_and_mismatch_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / fetch_assets.ROM_NAME
            target.write_bytes(b"verified ROM")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            with patch.object(fetch_assets, 'ROM_SHA256', digest), patch.object(fetch_assets, 'urlopen') as run:
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
                def download(request, timeout):
                    self.assertIn(fetch_assets.ROM_TAG, request.full_url)
                    self.assertTrue(request.full_url.startswith('https://'))
                    if mode == 'interrupted':
                        class Interrupted(io.BytesIO):
                            def read(self, size=-1):
                                if self.tell():
                                    raise OSError('connection interrupted')
                                return super().read(4)
                        return Interrupted(b'verified ROM')
                    if mode == 'concurrent':
                        target.write_bytes(b"other process")
                    return io.BytesIO(b"wrong" if mode == 'wrong_hash' else b"verified ROM")
                with patch.object(fetch_assets, 'ROM_SHA256', hashlib.sha256(b"verified ROM").hexdigest()), \
                     patch.object(fetch_assets, 'urlopen', side_effect=download):
                    if mode == 'success':
                        fetch_assets.fetch_rom(root)
                        self.assertEqual(target.read_bytes(), b"verified ROM")
                    else:
                        with self.assertRaises((ValueError, OSError)):
                            fetch_assets.fetch_rom(root)
                        if mode == 'concurrent':
                            self.assertEqual(target.read_bytes(), b"other process")
                        else:
                            self.assertFalse(target.exists())
                self.assertEqual(list(root.glob('.asset-download-*')), [])

    def test_fonts_use_pinned_https_urls_and_verify_before_publishing(self):
        data = b'ttcf test font'
        sources = {'test.ttc': ('Sans', fetch_assets.git_blob(data))}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(fetch_assets, 'SOURCES', sources), \
                 patch.object(fetch_assets, 'urlopen', return_value=io.BytesIO(data)) as download:
                fetch_assets.fetch_fonts(root)
                url = download.call_args.args[0].full_url
                self.assertEqual(url, f'https://raw.githubusercontent.com/notofonts/noto-cjk/{fetch_assets.COMMIT}/Sans/Variable/OTC/test.ttc')
                self.assertEqual((root / 'test.ttc').read_bytes(), data)
                fetch_assets.fetch_fonts(root)
                self.assertEqual(download.call_count, 1)
                (root / 'test.ttc').write_bytes(b'modified')
                with self.assertRaises(ValueError):
                    fetch_assets.fetch_fonts(root)
                self.assertEqual((root / 'test.ttc').read_bytes(), b'modified')
                self.assertEqual(download.call_count, 1)
