"""Cross-device ROM guards and fail-closed shared-payload validation."""
import io
import itertools
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_assets
from build_common import TARGET, updater
from targets import SYSTEM_BLOCKS, TARGETS, rom_url
from verify_targets import validate_identity, validate_shared


class TargetTests(unittest.TestCase):
    def test_updater_accepts_only_matching_device_system_and_fingerprint(self):
        devices = [*TARGETS, 'unknown']
        fingerprints = [t['fingerprint'] for t in TARGETS.values()] + ['another-build']
        for restore in (False, True):
            script = updater(b'', b'', {}, {}, restore).decode()
            guard = next(line for line in script.splitlines() if 'device/ROM mismatch' in line)
            expression = guard[len('assert('):guard.index(' || abort(')]
            expression = expression.replace('&&', 'and').replace('||', 'or')
            self.assertLess(script.index(guard), script.index('"prepare"'))
            for prop in ('ro.product.device', 'ro.build.product'):
                for recovery_device, system_device, fingerprint in itertools.product(devices, devices, fingerprints):
                    def getprop(key, recovery_device=recovery_device, prop=prop):
                        return recovery_device if key == prop else ''

                    def file_getprop(path, key, system_device=system_device, fingerprint=fingerprint):
                        self.assertEqual(path, TARGET + '/build.prop')
                        return {'ro.product.system.device': system_device,
                                'ro.system.build.fingerprint': fingerprint}[key]

                    actual = eval(expression, {'__builtins__': {}, 'getprop': getprop, 'file_getprop': file_getprop})
                    expected = (recovery_device == system_device and recovery_device in TARGETS and
                                fingerprint == TARGETS[recovery_device]['fingerprint'])
                    self.assertEqual(actual, expected, (restore, prop, recovery_device, system_device, fingerprint))

    def test_identity_rejects_wrong_rom_version_abi_layout_and_partition(self):
        for device, target in TARGETS.items():
            props = {'ro.product.system.device': device, 'ro.system.build.fingerprint': target['fingerprint'],
                     'ro.build.version.sdk': '30', 'ro.lineage.version': '18.1-test',
                     'ro.product.cpu.abilist': 'armeabi-v7a,armeabi'}
            script = f'block_image_update("{SYSTEM_BLOCKS[1]}", other_arguments);'
            validate_identity(device, props, script, '/system')
            for key, value in [('ro.product.system.device', 'other'), ('ro.system.build.fingerprint', 'other'),
                               ('ro.build.version.sdk', '31'), ('ro.lineage.version', '19.1-test'),
                               ('ro.product.cpu.abilist', 'arm64-v8a')]:
                with self.subTest(device=device, key=key), self.assertRaises(ValueError):
                    validate_identity(device, dict(props, **{key: value}), script, '/system')
            for ota, prefix in [(script, ''), (script.replace('system', 'system_a'), '/system'),
                                (script + script, '/system')]:
                with self.assertRaises(ValueError):
                    validate_identity(device, props, ota, prefix)

    def test_rejects_different_stock_xml_fonts_and_external_references(self):
        fonts = {'font.ttf': 'stock-hash'}
        references = ['/system/etc/fonts.xml']
        validate_shared(b'xml', fonts, b'xml', fonts, references)
        for xml, candidate, refs in [(b'changed', fonts, references),
                                     (b'xml', {'font.ttf': 'different-hash'}, references),
                                     (b'xml', {}, references),
                                     (b'xml', fonts, references + ['/system/vendor/etc/fonts.xml'])]:
            with self.assertRaises(ValueError):
                validate_shared(b'xml', fonts, xml, candidate, refs)

    def test_all_rom_downloads_use_their_own_pin_and_reuse_verified_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def verify(path, expected):
                self.assertIn(expected, {t['sha256'] for t in TARGETS.values()})
                self.assertEqual(path.read_bytes().decode(), expected)

            def download(request, timeout):
                target = next(t for t in TARGETS.values() if rom_url(t) == request.full_url)
                return io.BytesIO(target['sha256'].encode())

            with patch.object(fetch_assets, 'verify_rom', side_effect=verify), \
                 patch.object(fetch_assets, 'urlopen', side_effect=download) as request:
                fetch_assets.fetch_roms(root)
                fetch_assets.fetch_roms(root)
                self.assertEqual(request.call_count, len(TARGETS))
            for target in TARGETS.values():
                self.assertEqual((root / target['file']).read_text(), target['sha256'])
                with self.assertRaises(ValueError):
                    fetch_assets.verify_rom(root / target['file'], target['sha256'])
