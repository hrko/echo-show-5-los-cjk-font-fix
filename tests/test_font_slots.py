"""Run the shipped Python composer, including future patch slots."""
import itertools
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import test_build
from build_latin import AXES, locations, patch_latin
from build_named import patch_named
from build_zip import patch_xml, recovery_payload
from font_slots import OWNERS, compose_xml, payload, split_xml

ORIGINAL = test_build.XMLTests.ORIGINAL.replace(b'    <family lang="en">', b'''    <family name="sans-serif">
        <font weight="400" style="normal">Roboto-Regular.ttf</font>
    </family>
    <family name="sans-serif-condensed">
        <font weight="400" style="normal">RobotoCondensed-Regular.ttf</font>
    </family>
    <family name="serif">
        <font weight="400" style="normal">NotoSerif-Regular.ttf</font>
    </family>
    <family name="monospace">
        <font weight="400" style="normal">DroidSansMono.ttf</font>
    </family>
    <family lang="en">''') + b'\n'


class SlotTests(unittest.TestCase):
    def test_commutes_and_roundtrips_without_changing_other_bytes(self):
        self.assertEqual(patch_latin(patch_xml(ORIGINAL)), patch_xml(patch_latin(ORIGINAL)))
        for data in (ORIGINAL, patch_xml(ORIGINAL), patch_latin(ORIGINAL), patch_latin(patch_xml(ORIGINAL))):
            self.assertEqual(compose_xml(*split_xml(data)), data)
        with self.assertRaises(ValueError):
            payload(ORIGINAL, patch_latin(patch_xml(ORIGINAL)), 'latin')

    def test_android11_explicit_axes_and_preserved_aliases(self):
        tree = ET.fromstring(patch_latin(ORIGINAL))
        self.assertEqual([ET.tostring(x) for x in tree.findall('alias')],
                         [ET.tostring(x) for x in ET.fromstring(ORIGINAL).findall('alias')])
        self.assertEqual(len(list(locations())), 36)
        for family, weight, style, axes in locations():
            font = tree.find(f"./family[@name='{family}']/font[@weight='{weight}'][@style='{style}']")
            assert font is not None
            self.assertEqual(font.attrib, {'weight': str(weight), 'style': style})
            self.assertEqual({a.get('tag'): float(a.attrib['stylevalue']) for a in font}, axes)
            for tag, value in axes.items():
                self.assertLessEqual(AXES[tag][0], value)
                self.assertLessEqual(value, AXES[tag][2])
        self.assertFalse(tree.findall('.//family-list'))
        self.assertNotIn(b'supportedAxes', patch_latin(ORIGINAL))
        # Roboto remains reachable for characters absent from the public font.
        for name in ('sans-serif', 'sans-serif-condensed'):
            stock = ET.fromstring(ORIGINAL).find(f"./family[@name='{name}']")
            assert stock is not None
            fallback = [f for fam in tree.findall('family') if fam.get('name') is None
                        for f in fam if f.get('fallbackFor') == name]
            self.assertEqual(len(stock), len(fallback))
            for before, after in zip(stock, fallback):
                assert before.text is not None and after.text is not None
                self.assertEqual(before.text.strip(), after.text.strip())
                self.assertEqual(dict(before.attrib, fallbackFor=name), after.attrib)


class RecoveryComposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = {
            'cjk': patch_xml(ORIGINAL), 'latin': patch_latin(ORIGINAL),
            'serif': patch_named(ORIGINAL, 'serif'),
            'mono': patch_named(ORIGINAL, 'mono'),
        }

    def run_patch(self, current, component, restore=False, stage=False, mutate=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fonts.xml').write_bytes(current)
            files = recovery_payload(ORIGINAL, self.patches[component], component, restore)
            for name, data in files.items():
                target = root / name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(data)
            def run(mode):
                return subprocess.run([sys.executable, '-B', 'patch/font_patch.py', mode, 'fonts.xml', 'patch', 'work'],
                                      cwd=root, capture_output=True, check=False)
            result = run('prepare')
            if result.returncode:
                return result.returncode, result.stderr
            output = (root / 'work/fonts.xml').read_bytes()
            if stage:
                if mutate:
                    (root / 'fonts.xml').write_bytes(current + b'<!-- concurrent edit -->')
                result = run('stage')
                if result.returncode:
                    self.assertFalse((root / 'fonts.xml.jpfont-new').exists())
                    return result.returncode, result.stderr
                self.assertEqual((root / 'fonts.xml.jpfont-new').read_bytes(), output)
            return 0, output

    def test_all_four_component_orders_and_reverse_restore(self):
        # All four actual patches use the stable ownership contract.
        for order in itertools.permutations(OWNERS):
            current = ORIGINAL
            active = set()
            for component, restore in [(c, False) for c in order] + [(c, True) for c in reversed(order)]:
                status, current = self.run_patch(current, component, restore)
                self.assertEqual(status, 0, (order, component, current))
                if restore:
                    active.remove(component)
                else:
                    active.add(component)
                skeleton, slots = split_xml(ORIGINAL)
                for c in active:
                    changed = split_xml(self.patches[c])[1]
                    for key in OWNERS[c]:
                        slots[key] = changed[key]
                self.assertEqual(current, compose_xml(skeleton, slots))
            self.assertEqual(current, ORIGINAL)

    def test_idempotence_mixed_owned_state_and_stage(self):
        for component in OWNERS:
            for current in (ORIGINAL, self.patches[component]):
                for restore in (False, True):
                    status, data = self.run_patch(current, component, restore, stage=True)
                    self.assertEqual(status, 0, data)
                    self.assertEqual(data, ORIGINAL if restore else self.patches[component])
            skeleton, mixed = split_xml(ORIGINAL)
            first = OWNERS[component][0]
            mixed[first] = split_xml(self.patches[component])[1][first]
            status, data = self.run_patch(compose_xml(skeleton, mixed), component)
            self.assertEqual((status, data), (0, self.patches[component]))
        status, _ = self.run_patch(ORIGINAL, 'latin', stage=True, mutate=True)
        self.assertNotEqual(status, 0)

    def test_rejects_owned_edits_structure_aliases_and_dangling_deleted_fonts(self):
        cases = [
            (ORIGINAL.replace(b'RobotoCondensed-Regular.ttf', b'Custom.ttf'), 'latin'),
            (ORIGINAL.replace(b'to="sans-serif"', b'to="serif"'), 'latin'),
            (ORIGINAL + b'<!-- custom tail -->', 'latin'),
            (ORIGINAL.replace(b'    <family name="serif">', b'    <family name="unknown">'), 'latin'),
            (ORIGINAL.replace(b'NotoSerif-Regular.ttf', b'NotoSansCJK-Regular.ttc'), 'cjk'),
            (ORIGINAL.replace(b'<family name="serif">', b'<family name="serif">\n<family name="bad">'), 'latin'),
        ]
        for data, component in cases:
            with self.subTest(component=component, data=data[:80]):
                status, _ = self.run_patch(data, component)
                self.assertNotEqual(status, 0)


if __name__ == '__main__':
    unittest.main()
