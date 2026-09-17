"""Google Sans Flex patch: only the two requested Latin family slots are owned."""
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET

from ext4 import Volume
from extract_rom import BUILD, ROM, ROOT, sha256
from fetch_assets import (
    LATIN_COMMIT,
    LATIN_FILE,
    LATIN_SHA256,
    LATIN_URL,
    LATIN_VERSION,
    git_blob,
    verify_latin,
)
from font_slots import compose_xml, split_xml
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

WIDTHS = {"sans-serif": 100, "sans-serif-condensed": 75}
DEFAULTS = {"opsz": 18, "GRAD": 0, "ROND": 0}
AXES = {"opsz": [6, 18, 144], "wdth": [25, 100, 151], "wght": [1, 400, 1000],
        "GRAD": [0, 0, 100], "ROND": [0, 0, 100], "slnt": [-10, 0, 0]}
LICENSES = {"GoogleSansFlex-OFL.txt": "3e50f6cb72e58f01997d1e608195e8fdbc0eb8b4",
            "GoogleSansFlex-TRADEMARKS.md": "f914a7eba3e7a550c415625d396a72749106e926"}


def locations():
    for family, width in WIDTHS.items():
        for weight in range(100, 901, 100):
            for style, slant in (("normal", 0), ("italic", -10)):
                yield family, weight, style, dict(DEFAULTS, wdth=width, wght=weight, slnt=slant)


def patch_latin(original):
    from build_zip import check
    before = ET.fromstring(original)
    text = original.decode()
    for family in WIDTHS:
        matches = before.findall(f"./family[@name='{family}']")
        check(len(matches) == 1, f"Expected one {family}")
        old = matches[0]
        check(old.attrib == {"name": family}, "Unexpected Latin family attributes")
        prefix = "Roboto-" if family == "sans-serif" else "RobotoCondensed-"
        check(len(old) > 0 and all(f.tag == "font" and len(f) == 0 and
              (f.text or "").strip().startswith(prefix) for f in old), "Unexpected stock Latin fonts")
        lines = [f'<family name="{family}">']
        for name, weight, style, axes in locations():
            if name != family:
                continue
            lines.append(f'        <font weight="{weight}" style="{style}">{LATIN_FILE}')
            lines.extend(f'            <axis tag="{tag}" stylevalue="{value}" />' for tag, value in axes.items())
            lines.append('        </font>')
        lines.append('    </family>')
        key = 'latin-sans' if family == 'sans-serif' else 'latin-condensed'
        lines.extend([f'    <!-- font-slot: {key} fallback -->', '    <family>'])
        for item in old:
            if item.text is None:
                raise ValueError("Missing stock Latin font filename")
            attributes = dict(item.attrib, fallbackFor=family)
            attrs = ' '.join(f'{name}="{value}"' for name, value in attributes.items())
            lines.append(f'        <font {attrs}>{item.text.strip()}</font>')
        lines.append('    </family>')
        text, count = re.subn(r'<family name="' + family + r'">.*?</family>',
                              "\n".join(lines), text, flags=re.DOTALL)
        check(count == 1, "Ambiguous Latin replacement")
    result = text.encode()
    skeleton, stock = split_xml(original)
    changed_skeleton, changed = split_xml(result)
    check(skeleton == changed_skeleton, "Non-family XML changed")
    for key in ("latin-sans", "latin-condensed"):
        changed[key] = stock[key]
    check(compose_xml(skeleton, changed) == original, "Non-Latin configuration changed")
    return result


def font_info(path):
    from build_zip import check
    verify_latin(path)
    with TTFont(path, checkChecksums=2) as font:
        check(font['name'].getDebugName(5) == LATIN_VERSION, "Unexpected font version")
        check(font.sfntVersion == "\x00\x01\x00\x00" and 'glyf' in font and 'gvar' in font,
              "Expected variable TrueType outlines")
        axes = {a.axisTag: [a.minValue, a.defaultValue, a.maxValue] for a in font['fvar'].axes}
        check(axes == AXES, "Unexpected public font axis ranges/defaults")
        cmap = font.getBestCmap()
        if cmap is None:
            raise ValueError("Missing Unicode cmap")
        samples = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?éñÅß"
        check(all(ord(c) in cmap for c in samples), "Missing Latin sample glyphs")
        outlines = {}
        for family, weight, style, location in locations():
            check(all(axes[tag][0] <= value <= axes[tag][2] for tag, value in location.items()),
                  "Axis value outside published range")
            glyphs = font.getGlyphSet(location=location)
            pen = RecordingPen()
            for char in samples:
                glyphs[cmap[ord(char)]].draw(pen)
            outlines[f"{family}/{weight}/{style}"] = hashlib.sha256(repr(pen.value).encode()).hexdigest()
        check(len(set(outlines.values())) == 36, "Duplicate weight/width/slant sample outlines")
        return {"file": LATIN_FILE, "sha256": sha256(path), "bytes": path.stat().st_size,
                "version": LATIN_VERSION, "family": font['name'].getDebugName(1),
                "copyright": font['name'].getDebugName(0), "axes": axes,
                "sample_outline_sha256": outlines}


def build_latin(original, binary, dist):
    from build_zip import CHECKER, META, check, recovery_payload, updater, write_zip
    patched = patch_latin(original)
    info = font_info(ROOT / LATIN_FILE)
    stock = ET.fromstring(original)
    retained = {}
    coverage = {}
    with TTFont(ROOT / LATIN_FILE) as new, (BUILD / 'system.img').open('rb') as stream:
        volume = Volume(stream)
        new_cmap = new.getBestCmap()
        if new_cmap is None:
            raise ValueError("Missing Unicode cmap")
        cmap = set(new_cmap)
        for family in WIDTHS:
            stock_family = stock.find(f"./family[@name='{family}']")
            if stock_family is None:
                raise ValueError(f"Missing stock family: {family}")
            for item in stock_family:
                if item.text is None:
                    raise ValueError("Missing stock font filename")
                name = item.text.strip()
                data = volume.inode_at('/system/fonts/' + name).open().read()
                retained[name] = {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
                with TTFont(io.BytesIO(data)) as old:
                    old_cmap = old.getBestCmap()
                    if old_cmap is None:
                        raise ValueError(f"Missing Unicode cmap: {name}")
                    missing = sorted(set(old_cmap) - cmap)
                    coverage[name] = [f"U+{cp:04X}" for cp in missing]
        # All unchanged file references must still resolve in the stock image.
        for item in ET.fromstring(patched).iter('font'):
            if item.text is None:
                raise ValueError("Missing font filename")
            if item.text.strip() != LATIN_FILE:
                volume.inode_at('/system/fonts/' + item.text.strip())
    report = {"component": "latin", "device_tested": False,
              "rom": {"file": ROM.name, "sha256": sha256(ROM)}, "font": info,
              "upstream": {"url": LATIN_URL, "commit": LATIN_COMMIT, "license": "SIL OFL 1.1",
                           "sha256": LATIN_SHA256},
              "widths": WIDTHS, "fixed_axes": DEFAULTS, "weights": list(range(100, 901, 100)),
              "slant": {"normal": 0, "italic": -10},
              "retained_roboto": retained, "codepoints_missing_vs_roboto": coverage,
              "missing_codepoints_fallback": "Original Roboto/RobotoCondensed via family-specific fallbackFor",
              "original_xml_sha256": hashlib.sha256(original).hexdigest(),
              "patched_xml_sha256": hashlib.sha256(patched).hexdigest(),
              "ownership_format": 1, "owned_slots": ["latin-sans", "latin-condensed"]}
    shared = {META + 'update-binary': binary, 'check.sh': CHECKER,
              'verification.json': (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()}
    from python_runtime import runtime_payload
    shared.update(runtime_payload())
    for name, expected in LICENSES.items():
        data = (ROOT / 'licenses' / name).read_bytes()
        check(git_blob(data) == expected, f"Upstream license/notice mismatch: {name}")
        shared['licenses/' + name] = data
    sums = []
    for restore in (False, True):
        files = dict(shared)
        files.update(recovery_payload(original, patched, 'latin', restore))
        files[META + 'updater-script'] = updater(original, patched, {"latin": info}, {}, restore,
                                                component='latin', retained=retained)
        if not restore:
            files['system/fonts/' + LATIN_FILE] = (ROOT / LATIN_FILE).read_bytes()
        path = dist / f"cronos-latin-fonts-{'restore' if restore else 'install'}.zip"
        write_zip(path, files)
        sums.append(f"{sha256(path)}  {path.name}")
        print(f"Verified: {path.name} ({path.stat().st_size:,} bytes)")
    (BUILD / 'fonts.latin.xml').write_bytes(patched)
    (dist / 'latin-verification.json').write_bytes(shared['verification.json'])
    return sums
