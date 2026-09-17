"""Prove that the pinned ROMs can use one install AND restore payload."""
import hashlib
import json
import re

from ext4 import EXT4_FT, Volume
from extract_rom import BUILD, ROOT, extract, sha256
from fetch_assets import verify_rom
from targets import SYSTEM_BLOCKS, TARGETS, rom_url

OLD_COLLECTIONS = ('NotoSansCJK-Regular.ttc', 'NotoSerifCJK-Regular.ttc')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_identity(device, props, ota_script, prefix):
    target = TARGETS[device]
    require(prefix == '/system', f'{device}: unsupported system layout')
    require(props.get('ro.product.system.device') == device, f'{device}: wrong system device')
    require(props.get('ro.system.build.fingerprint') == target['fingerprint'],
            f'{device}: unexpected fingerprint')
    require(props.get('ro.build.version.sdk') == '30' and
            props.get('ro.lineage.version', '').startswith('18.1-'), f'{device}: not LineageOS 18.1')
    require('armeabi-v7a' in props.get('ro.product.cpu.abilist', '').split(','),
            f'{device}: ARMv7 userspace required')
    blocks = re.findall(r'block_image_update\("([^"]+)"', ota_script)
    require(blocks == [SYSTEM_BLOCKS[1]], f'{device}: unexpected OTA system block devices: {blocks}')


def old_collection_references(volume):
    references = []

    def walk(path):
        for entry, kind in volume.inode_at(path).opendir():
            name = entry.name_str
            if name in ('.', '..'):
                continue
            child = path.rstrip('/') + '/' + name
            if kind == EXT4_FT.DIR:
                walk(child)
            elif kind == EXT4_FT.REG_FILE and name.endswith('.xml'):
                data = volume.inode_at(child).open().read()
                if any(font.encode() in data for font in OLD_COLLECTIONS):
                    references.append(child)

    walk('/')
    return sorted(references)


def font_inventory(volume):
    fonts = {}
    for entry, kind in volume.inode_at('/system/fonts').opendir():
        if kind == EXT4_FT.REG_FILE:
            name = entry.name_str
            fonts[name] = hashlib.sha256(volume.inode_at('/system/fonts/' + name).open().read()).hexdigest()
    require(bool(fonts), 'Empty font inventory')
    return fonts


def validate_shared(reference_xml, reference_fonts, xml, fonts, references):
    require(xml == reference_xml, 'ROMs have different fonts.xml; cannot share v1 payload')
    require(fonts == reference_fonts, 'ROMs have different stock fonts; cannot share restore payload')
    require(references == ['/system/etc/fonts.xml'], f'Other XML references old TTC: {references}')


def verify_targets():
    # Never reuse an old successful report after a failed audit.
    report_path = BUILD / 'compatibility.json'
    report_path.unlink(missing_ok=True)
    baseline_xml = None
    baseline_fonts = None
    roms = []
    for device, target in TARGETS.items():
        rom = ROOT / target['file']
        verify_rom(rom, target['sha256'])
        folder = BUILD if device == 'cronos' else BUILD / device
        prefix = extract(rom, folder)
        props = dict(line.split('=', 1) for line in (folder / 'build.prop').read_text().splitlines()
                     if '=' in line and not line.startswith('#'))
        validate_identity(device, props, (folder / 'rom-updater-script').read_text(), prefix)
        xml = (folder / 'fonts.original.xml').read_bytes()
        with (folder / 'system.img').open('rb') as stream:
            volume = Volume(stream)
            fonts = font_inventory(volume)
            references = old_collection_references(volume)
            for path in ('/system/etc/fonts.xml', *('/system/fonts/' + name for name in OLD_COLLECTIONS)):
                require(dict(volume.inode_at(path).xattrs).get('security.selinux') ==
                        b'u:object_r:system_file:s0\0', f'{device}: unexpected SELinux label: {path}')
        if baseline_xml is None:
            baseline_xml, baseline_fonts = xml, fonts
        validate_shared(baseline_xml, baseline_fonts, xml, fonts, references)
        roms.append(dict(target, device=device, url=rom_url(target), system_prefix=prefix,
                         updater_sha256=sha256(folder / 'update-binary'),
                         old_ttc_xml_references=references, device_tested=False))
        print(f'Compatible ROM: {device} ({len(fonts)} identical regular font files)', flush=True)
    if baseline_xml is None:
        raise ValueError('No ROMs verified')
    report = {'roms': roms, 'reference_device': 'cronos',
              'original_xml_sha256': hashlib.sha256(baseline_xml).hexdigest(),
              'stock_font_sha256': baseline_fonts, 'system_blocks': list(SYSTEM_BLOCKS)}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report
