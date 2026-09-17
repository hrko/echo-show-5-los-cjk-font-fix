"""Validate Android entries, fallback ownership and pinned asset rejection."""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from build_named import patch_named
from font_slots import split_xml
from named_fonts import COMPONENTS, fetch_named_fonts
from test_font_slots import ORIGINAL


class NamedFontTests(unittest.TestCase):
    def test_entries_ranges_styles_and_original_fallback(self):
        for component, config in COMPONENTS.items():
            result = patch_named(ORIGINAL, component)
            tree = ET.fromstring(result)
            family = tree.find(f"./family[@name='{config['family']}']")
            assert family is not None
            self.assertEqual(len(family), 2 * len(config['weights']))
            for weight in config['weights']:
                for style, font in config['fonts'].items():
                    entry = family.find(f"font[@weight='{weight}'][@style='{style}']")
                    assert entry is not None and entry.text is not None
                    self.assertEqual(entry.text.strip(), font[0])
                    self.assertEqual({a.get('tag'): float(a.attrib['stylevalue']) for a in entry},
                                     dict(config['fixed'], wght=weight))
            stock = ET.fromstring(ORIGINAL).find(f"./family[@name='{config['family']}']")
            assert stock is not None
            owned = ET.fromstring(b'<familyset>' + split_xml(result)[1][component] + b'</familyset>')
            fallback = owned.findall(f"./family/font[@fallbackFor='{config['family']}']")
            self.assertEqual(len(fallback), len(stock))
            for old, new in zip(stock, fallback):
                self.assertEqual(old.text, new.text)
                self.assertEqual(dict(old.attrib, fallbackFor=config['family']), new.attrib)
            before, old_slots = split_xml(ORIGINAL)
            after, new_slots = split_xml(result)
            self.assertEqual(before, after)
            for key in old_slots.keys() - {component}:
                self.assertEqual(old_slots[key], new_slots[key])

    def test_unknown_stock_rejected(self):
        for name, component in [('NotoSerif-Regular.ttf', 'serif'), ('DroidSansMono.ttf', 'mono')]:
            with self.assertRaises(ValueError):
                patch_named(ORIGINAL.replace(name.encode(), b'Custom.ttf'), component)

    def test_modified_input_preserved_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / COMPONENTS['serif']['fonts']['normal'][0]
            path.write_bytes(b'modified')
            with patch('fetch_assets.urlopen') as download, self.assertRaises(ValueError):
                fetch_named_fonts(root)
            download.assert_not_called()
            self.assertEqual(path.read_bytes(), b'modified')
