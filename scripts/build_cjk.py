"""Build the independent CJK variable-font patch."""
import copy
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET

from build_common import (
    CHECKER,
    META,
    artifact_name,
    check,
    recovery_payload,
    updater,
    write_zip,
)
from ext4 import EXT4_FT, Volume
from extract_rom import BUILD, ROM, ROOT, sha256
from fetch_assets import COMMIT, SOURCES, git_blob
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTCollection
from python_runtime import runtime_payload

FONTS = {"sans": "NotoSansCJK-VF.ttf.ttc", "serif": "NotoSerifCJK-VF.ttf.ttc"}
ORIGINAL_FONTS = {"sans": "NotoSansCJK-Regular.ttc", "serif": "NotoSerifCJK-Regular.ttc"}
LOCALES = {"ja": 0, "ko": 1, "zh-Hans": 2, "zh-Hant,zh-Bopo": 3}
HK_LOCALE = "zh-Hant-HK"
REGIONS = ["JP", "KR", "SC", "TC", "HK"]
WEIGHTS = {"sans": list(range(100, 901, 100)), "serif": list(range(200, 901, 100))}


def font_info(path, weights, kind):
    data = path.read_bytes()
    blob = git_blob(data)
    check(blob == SOURCES[path.name][1], "Font does not match the verified upstream Git blob")
    faces = []
    collection = TTCollection(io.BytesIO(data), lazy=True, checkChecksums=2)
    check(len(collection.fonts) == 5, "Expected JP/KR/SC/TC/HK collection")
    for index, font in enumerate(collection.fonts):
        names = font["name"]
        check(names.getDebugName(1) == f'Noto {kind.title()} CJK {REGIONS[index]}', "Incorrect locale face mapping")
        check(font.sfntVersion == "\x00\x01\x00\x00", "Expected TrueType outlines")
        check("glyf" in font and "gvar" in font, "Missing TrueType variation tables")
        axes = font["fvar"].axes
        check(len(axes) == 1 and axes[0].axisTag == "wght", "Unexpected font axes")
        axis = axes[0]
        check(axis.minValue == min(weights) and axis.maxValue == max(weights), "Unexpected weight range")
        cmap = font.getBestCmap()
        samples = ["日本語漢字かなカナ骨直令辻", "한국어한글骨直令", "简体中文汉语骨直令",
                   "繁體中文漢語注音骨直令", "香港廣東話骨直令"][index]
        check(all(ord(c) in cmap for c in samples), "Missing locale sample glyphs")
        outlines = {}
        for weight in weights:
            glyphs = font.getGlyphSet(location={"wght": weight})
            pen = RecordingPen()
            for char in samples:
                glyphs[cmap[ord(char)]].draw(pen)
            outlines[str(weight)] = hashlib.sha256(repr(pen.value).encode()).hexdigest()
        check(len(set(outlines.values())) == len(weights), "Weights have duplicate sample outlines")
        faces.append({
            "index": index, "region": REGIONS[index], "family": names.getDebugName(1),
            "version": names.getDebugName(5), "postscript_name": names.getDebugName(6),
            "copyright": names.getDebugName(0),
            "axis": {"tag": "wght", "min": axis.minValue, "default": axis.defaultValue, "max": axis.maxValue},
            "weights": weights, "sample_outline_sha256": outlines,
        })
    collection.close()
    return {"file": path.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "upstream_git_blob": blob, "faces": faces}


def patch_cjk(original):
    text = original.decode("utf-8")
    before = ET.fromstring(original)
    check(not before.findall(f"./family[@lang='{HK_LOCALE}']"), "Unexpected existing HK family")

    def family_xml(lang, index):
        lines = [f'<family lang="{lang}">']
        for kind, filename in FONTS.items():
            fallback = ' fallbackFor="serif"' if kind == "serif" else ""
            for weight in WEIGHTS[kind]:
                lines.append(f'        <font weight="{weight}" style="normal" index="{index}"{fallback}>{filename}'
                             f'<axis tag="wght" stylevalue="{weight}" /></font>')
        return "\n".join(lines + ["    </family>"])

    result = text
    for lang, index in LOCALES.items():
        families = before.findall(f"./family[@lang='{lang}']")
        check(len(families) == 1, f"Expected exactly one {lang} family")
        old = families[0]
        check(old.attrib == {"lang": lang} and len(old) == 2, "Unexpected CJK family contents")
        for kind, font in zip(FONTS, old):
            attrs = {"weight": "400", "style": "normal", "index": str(index)}
            if kind == "serif":
                attrs["fallbackFor"] = "serif"
            check(font.tag == "font" and font.attrib == attrs and len(font) == 0
                  and (font.text or "").strip() == ORIGINAL_FONTS[kind], "Unexpected original CJK font")
        replacement = family_xml(lang, index)
        if index == 3:
            replacement = family_xml(HK_LOCALE, 4) + "\n    " + replacement
        result, count = re.subn(r'<family lang="' + re.escape(lang) + r'">.*?</family>', replacement, result, flags=re.DOTALL)
        check(count == 1, f"Ambiguous {lang} XML replacement")
    check(not any(name in result for name in ORIGINAL_FONTS.values()), "Remaining reference to a removed TTC")
    after = ET.fromstring(result)
    restored = copy.deepcopy(after)
    hk = restored.find(f"./family[@lang='{HK_LOCALE}']")
    if hk is None:
        raise ValueError("Missing generated HK family")
    restored.remove(hk)
    for index, old in enumerate(before):
        if old.tag == "family" and old.get("lang") in LOCALES:
            restored.remove(restored[index])
            restored.insert(index, copy.deepcopy(old))
    check(ET.tostring(restored) == ET.tostring(before), "Non-CJK configuration changed")
    return result.encode("utf-8")


def build_cjk(original, binary, dist, compatibility):
    patched = patch_cjk(original)
    infos = {kind: font_info(ROOT / filename, WEIGHTS[kind], kind) for kind, filename in FONTS.items()}
    original_data = {}
    original_notices = []
    check(binary[:4] == b"\x7fELF" and binary[4] == 1 and binary[18:20] == b"\x28\x00", "Expected ARM32 ELF updater")
    # String presence is only a sanity check, not a proof of registered functions.
    # Short literals can be synthesized as instructions by the compiler.
    for function in ("set_metadata", "run_program", "file_getprop"):
        check(function.encode() + b"\0" in binary, f"Updater lacks {function}")
    with (BUILD / "system.img").open("rb") as stream:
        volume = Volume(stream)
        for path in ("/system/etc/fonts.xml", "/system/fonts/NotoSansCJK-Regular.ttc", "/system/fonts/NotoSerifCJK-Regular.ttc"):
            attrs = dict(volume.inode_at(path).xattrs)
            check(attrs["security.selinux"] == b"u:object_r:system_file:s0\0", "Unexpected SELinux label")
        for kind, filename in ORIGINAL_FONTS.items():
            original_data[filename] = volume.inode_at("/system/fonts/" + filename).open().read()
            old = TTCollection(io.BytesIO(original_data[filename]), lazy=True)
            original_notices.append(filename + "\n" + "\n".join(sorted({
                font["name"].getDebugName(0) or "" for font in old.fonts})))
            new = TTCollection(ROOT / FONTS[kind], lazy=True)
            for index in LOCALES.values():
                missing = set(old.fonts[index].getBestCmap()) - set(new.fonts[index].getBestCmap())
                check(not missing, f"Lost cmap coverage for {kind}/{REGIONS[index]}: {sorted(missing)}")
            old.close()
            new.close()
        # Audit all standalone XML configuration files in this ROM for references
        # that would be broken by deleting either old collection.
        audited_xml = []
        def audit_xml(path):
            for entry, kind in volume.inode_at(path).opendir():
                name = entry.name_str
                if name in (".", ".."):
                    continue
                child = path.rstrip("/") + "/" + name
                if kind == EXT4_FT.DIR:
                    audit_xml(child)
                elif kind == EXT4_FT.REG_FILE and name.endswith(".xml"):
                    data = volume.inode_at(child).open().read()
                    if any(font.encode() in data for font in ORIGINAL_FONTS.values()):
                        audited_xml.append(child)
        audit_xml("/")
        check(audited_xml == ["/system/etc/fonts.xml"], f"Other XML references old TTC: {audited_xml}")
        for font in ET.fromstring(patched).iter("font"):
            if font.text is None:
                raise ValueError("Missing font filename")
            filename = font.text.strip()
            if filename not in FONTS.values():
                volume.inode_at("/system/fonts/" + filename)
    originals = {kind: {"file": name, "bytes": len(original_data[name]),
                       "sha256": hashlib.sha256(original_data[name]).hexdigest()}
                 for kind, name in ORIGINAL_FONTS.items()}
    (BUILD / "fonts.cjk.xml").write_bytes(patched)
    report = {
        "compatibility": compatibility,
        "rom": {"file": ROM.name, "sha256": sha256(ROM), "system_prefix": "/system"},
        "fonts": infos, "original_xml_sha256": hashlib.sha256(original).hexdigest(),
        "original_collections": originals, "old_ttc_xml_references": audited_xml,
        "locales": {**LOCALES, HK_LOCALE: 4},
        "patched_xml_sha256": hashlib.sha256(patched).hexdigest(),
        "updater_sha256": hashlib.sha256(binary).hexdigest(),
        "device_tested": False,
        "upstream_commit": COMMIT,
        "ownership_format": 1,
        "owned_slots": ["cjk-sc", "cjk-tc", "cjk-ja", "cjk-ko"],
    }
    shared = {META + "update-binary": binary, "check.sh": CHECKER,
              "verification.json": (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()}
    shared.update(runtime_payload())
    for required in ("NotoSans-OFL.txt", "NotoSerif-OFL.txt", "FONT-COPYRIGHT.txt"):
        check((ROOT / "licenses" / required).is_file(), f"Missing license notice: {required}")
    for name in ("NotoSans-OFL.txt", "NotoSerif-OFL.txt", "FONT-COPYRIGHT.txt"):
        shared["licenses/" + name] = (ROOT / "licenses" / name).read_bytes()
    sums = []
    for restore in (False, True):
        contents = dict(shared)
        contents[META + "updater-script"] = updater(original, patched, infos, originals, restore)
        contents.update(recovery_payload(original, patched, "cjk", restore))
        if not restore:
            for filename in FONTS.values():
                contents["system/fonts/" + filename] = (ROOT / filename).read_bytes()
        else:
            for filename, data in original_data.items():
                contents["system/fonts/" + filename] = data
            contents["licenses/ROM-CJK-COPYRIGHT.txt"] = ("\n\n".join(original_notices) + "\n").encode()
        path = dist / artifact_name("cjk", "restore" if restore else "install")
        write_zip(path, contents)
        sums.append(f"{sha256(path)}  {path.name}")
        print(f"Verified: {path.name} ({path.stat().st_size:,} bytes)")
    (dist / artifact_name("cjk", "verification")).write_bytes(shared["verification.json"])
    return sums
