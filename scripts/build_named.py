"""Build independent named serif and monospace variable font patches."""
import hashlib
import io
import json
import xml.etree.ElementTree as ET

from ext4 import Volume
from extract_rom import BUILD, ROM, ROOT, sha256
from fetch_assets import LATIN_COMMIT
from font_slots import compose_xml, payload, split_xml
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from named_fonts import COMPONENTS, source_url, verify_blob


def patch_named(original, component):
    config = COMPONENTS[component]
    skeleton, slots = split_xml(original)
    old = ET.fromstring(slots[component])
    if (old.attrib != {'name': config['family']} or not len(old) or
            any(f.tag != 'font' or len(f) or (f.text or '').strip() not in config['stock'] for f in old)):
        raise ValueError(f'Unexpected stock {component} family')
    lines = [f'    <family name="{config["family"]}">']
    for weight in config['weights']:
        for style, (filename, _, _, _) in config['fonts'].items():
            lines.append(f'        <font weight="{weight}" style="{style}">{filename}')
            for tag, value in dict(config['fixed'], wght=weight).items():
                lines.append(f'            <axis tag="{tag}" stylevalue="{value}" />')
            lines.append('        </font>')
    lines.extend(['    </family>', f'    <!-- font-slot: {component} fallback -->', '    <family>'])
    for item in old:
        attributes = dict(item.attrib, fallbackFor=config['family'])
        attrs = ' '.join(f'{key}="{value}"' for key, value in attributes.items())
        lines.append(f'        <font {attrs}>{(item.text or "").strip()}</font>')
    lines.append('    </family>\n')
    slots[component] = '\n'.join(lines).encode()
    patched = compose_xml(skeleton, slots)
    payload(original, patched, component)  # Enforce the v1 ownership contract.
    return patched


def font_info(component, style):
    from build_zip import check
    config = COMPONENTS[component]
    filename, upstream, expected, version = config['fonts'][style]
    path = ROOT / filename
    verify_blob(path, expected)
    with TTFont(path, checkChecksums=2) as font:
        axes = {a.axisTag: [a.minValue, a.defaultValue, a.maxValue] for a in font['fvar'].axes}
        check(axes == config['axes'], 'Unexpected variable font axes')
        check(font['name'].getDebugName(5) == version, 'Unexpected font version')
        check(font.sfntVersion == '\x00\x01\x00\x00' and 'glyf' in font and 'gvar' in font,
              'Expected variable TrueType outlines')
        italic_flag = font['head'].macStyle  # ty: ignore[unresolved-attribute] -- fontTools dynamic table field
        check(bool(italic_flag & 2) == (style == 'italic'), 'Incorrect italic face')
        cmap = font.getBestCmap()
        if cmap is None:
            raise ValueError('Missing Unicode cmap')
        samples = ''.join(chr(cp) for cp in range(32, 127))
        check(all(ord(c) in cmap for c in samples), 'Missing ASCII glyphs')
        outlines = {}
        advances = {}
        for weight in config['weights']:
            glyphs = font.getGlyphSet(location=dict(config['fixed'], wght=weight))
            pen = RecordingPen()
            for char in samples:
                glyphs[cmap[ord(char)]].draw(pen)
            outlines[str(weight)] = hashlib.sha256(repr(pen.value).encode()).hexdigest()
            if component == 'mono':
                widths = {glyphs[cmap[ord(char)]].width for char in samples}
                check(len(widths) == 1, f'Non-monospace ASCII at {style}/{weight}')
                advances[str(weight)] = widths.pop()
        check(len(set(outlines.values())) == len(config['weights']), 'Duplicate weight outlines')
        return {'file': filename, 'sha256': sha256(path), 'bytes': path.stat().st_size,
                'version': version, 'axes': axes, 'upstream_url': source_url(config, upstream),
                'upstream_git_blob': expected, 'sample_outline_sha256': outlines,
                'ascii_advance_widths': advances}


def build_named(original, binary, dist, component):
    from build_zip import CHECKER, META, recovery_payload, updater, write_zip
    from python_runtime import runtime_payload
    config = COMPONENTS[component]
    patched = patch_named(original, component)
    infos = {style: font_info(component, style) for style in config['fonts']}
    retained, coverage = {}, {}
    with (BUILD / 'system.img').open('rb') as stream:
        volume = Volume(stream)
        for name in config['stock']:
            data = volume.inode_at('/system/fonts/' + name).open().read()
            retained[name] = {'file': name, 'sha256': hashlib.sha256(data).hexdigest()}
            with TTFont(io.BytesIO(data)) as old:
                old_cmap = set(old.getBestCmap() or {})
            coverage[name] = {}
            for style, info in infos.items():
                with TTFont(ROOT / info['file']) as new:
                    coverage[name][style] = [f'U+{cp:04X}' for cp in sorted(old_cmap - set(new.getBestCmap() or {}))]
        added = {info['file'] for info in infos.values()}
        for item in ET.fromstring(patched).iter('font'):
            filename = (item.text or '').strip()
            if filename not in added:
                volume.inode_at('/system/fonts/' + filename)
    report = {'component': component, 'device_tested': False, 'fonts': infos,
              'rom': {'file': ROM.name, 'sha256': sha256(ROM)}, 'upstream_commit': LATIN_COMMIT,
              'weights': config['weights'], 'fixed_axes': config['fixed'],
              'retained_fonts': retained, 'codepoints_missing_vs_stock': coverage,
              'missing_codepoints_fallback': f"Original fonts via fallbackFor={config['family']}",
              'ownership_format': 1, 'owned_slots': [component],
              'original_xml_sha256': hashlib.sha256(original).hexdigest(),
              'patched_xml_sha256': hashlib.sha256(patched).hexdigest()}
    shared = {META + 'update-binary': binary, 'check.sh': CHECKER,
              'verification.json': (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()}
    shared.update(runtime_payload())
    for filename, (_, expected) in config['licenses'].items():
        path = ROOT / 'licenses' / filename
        verify_blob(path, expected)
        shared['licenses/' + filename] = path.read_bytes()
    sums = []
    for restore in (False, True):
        files = dict(shared)
        files.update(recovery_payload(original, patched, component, restore))
        files[META + 'updater-script'] = updater(original, patched, infos, {}, restore,
                                                component=component, retained=retained)
        if not restore:
            for info in infos.values():
                files['system/fonts/' + info['file']] = (ROOT / info['file']).read_bytes()
        path = dist / f"cronos-{component}-fonts-{'restore' if restore else 'install'}.zip"
        write_zip(path, files)
        sums.append(f'{sha256(path)}  {path.name}')
        print(f'Verified: {path.name} ({path.stat().st_size:,} bytes)')
    (BUILD / f'fonts.{component}.xml').write_bytes(patched)
    (dist / f'{component}-verification.json').write_bytes(shared['verification.json'])
    return sums
