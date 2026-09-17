"""Build deterministic, ROM-specific install/restore recovery ZIPs using Python."""
import copy
import hashlib
import io
import json
import re
import stat
import xml.etree.ElementTree as ET
import zipfile

from ext4 import EXT4_FT, Volume
from extract_rom import BUILD, ROM, ROOT, extract, sha256
from fetch_assets import COMMIT, SOURCES, git_blob
from font_slots import payload as slot_payload
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTCollection
from python_runtime import runtime_payload

META = "META-INF/com/google/android/"
MOUNT = "/tmp/jp-font-system"
TARGET = MOUNT + "/system"
FONTS = {"sans": "NotoSansCJK-VF.ttf.ttc", "serif": "NotoSerifCJK-VF.ttf.ttc"}
ORIGINAL_FONTS = {"sans": "NotoSansCJK-Regular.ttc", "serif": "NotoSerifCJK-Regular.ttc"}
LOCALES = {"ja": 0, "ko": 1, "zh-Hans": 2, "zh-Hant,zh-Bopo": 3}
HK_LOCALE = "zh-Hant-HK"
REGIONS = ["JP", "KR", "SC", "TC", "HK"]
WEIGHTS = {"sans": list(range(100, 901, 100)), "serif": list(range(200, 901, 100))}


def check(condition, message):
    if not condition:
        raise ValueError(message)


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


def patch_xml(original):
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


# Compatibility entry point; all file guards run in the bundled Python.
CHECKER = b'''#!/sbin/sh
exec /sbin/sh /tmp/jp-font-patch/run-python.sh check "$@"
'''


def updater(original, patched, infos, originals, restore=False, component="cjk", retained=None):
    props = dict(line.split("=", 1) for line in (BUILD / "build.prop").read_text().splitlines()
                 if "=" in line and not line.startswith("#"))
    fingerprint = props["ro.system.build.fingerprint"]
    check('"' not in fingerprint and "\\" not in fingerprint, "Unsafe fingerprint")
    action = "Restore" if restore else "Install"
    label = "CJK Sans 100-900 / Serif 200-900" if component == "cjk" else "Google Sans Flex 100-900 normal/italic"
    patch_dir = "/tmp/jp-font-patch"
    work_dir = "/tmp/jp-font-work"
    xml = TARGET + "/etc/fonts.xml"
    script = [
        f'ui_print("{action} {label} (cronos)");',
        'assert(getprop("ro.product.device") == "cronos" || getprop("ro.build.product") == "cronos" || abort("This ZIP is only for cronos."));',
        'assert(package_extract_dir("runtime", "/tmp/jp-font-python"));',
        'set_metadata("/tmp/jp-font-python/lib/ld-musl-armhf.so.1", "uid", 0, "gid", 0, "mode", 0755);',
        f'assert(package_extract_dir("patch", "{patch_dir}"));',
        'assert(package_extract_file("check.sh", "/tmp/jp-font-check.sh"));',
        'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "ready") == "0" || abort("Bundled ARMv7 Python could not start."));',
        f'ifelse(is_mounted("{MOUNT}"), assert(unmount("{MOUNT}")));',
        f'assert(mount("ext4", "EMMC", "/dev/block/platform/soc/by-name/system", "{MOUNT}", "rw") || mount("ext4", "EMMC", "/dev/block/platform/soc/11230000.mmc/by-name/system", "{MOUNT}", "rw") || abort("Cannot mount system read-write. Unmount System in TWRP and retry."));',
        f'assert(file_getprop("{TARGET}/build.prop", "ro.system.build.fingerprint") == "{fingerprint}" || abort("Wrong ROM build."));',
    ]

    def hash_check(path, expected, optional=False):
        args = ", ".join(f'"{v}"' for v in (["optional" if optional else "hash", path] + expected))
        return f'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", {args}) == "0" || abort("File verification failed: {path}"));'

    script.extend([
        f'assert(run_program("/sbin/sh", "{patch_dir}/run-python.sh", "prepare", "{xml}", "{patch_dir}", "{work_dir}") == "0" || abort("Font configuration verification failed; unsupported structure or modified owned family."));',
    ])
    for info in (retained or {}).values():
        script.append(hash_check(TARGET + "/fonts/" + info["file"], [info["sha256"]]))
    # Never remove or overwrite a user's custom old TTC, even on restore.
    for info in originals.values():
        script.append(hash_check(TARGET + "/fonts/" + info["file"], [info["sha256"]], optional=True))
    if not restore:
        for info in infos.values():
            script.append(hash_check(TARGET + "/fonts/" + info["file"], [info["sha256"]], optional=True))

    def stage(source, target, digest):
        temporary = target + ".jpfont-new"
        script.extend([
            f'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "stageable", "{temporary}") == "0");',
            f'assert(package_extract_file("{source}", "{temporary}") || abort("Extraction failed; check free system space."));',
            hash_check(temporary, [digest]),
            f'set_metadata("{temporary}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:system_file:s0");',
            f'assert(rename("{temporary}", "{target}"));',
        ])

    if not restore:
        for info in infos.values():
            stage("system/fonts/" + info["file"], TARGET + "/fonts/" + info["file"], info["sha256"])
    else:
        # Restore referenced fonts BEFORE returning to the stock XML.
        for info in originals.values():
            stage("system/fonts/" + info["file"], TARGET + "/fonts/" + info["file"], info["sha256"])
    script.extend([
        f'assert(run_program("/sbin/sh", "{patch_dir}/run-python.sh", "stage", "{xml}", "{patch_dir}", "{work_dir}") == "0" || abort("XML staging failed; configuration changed or insufficient space."));',
        f'set_metadata("{xml}.jpfont-new", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:system_file:s0");',
        f'assert(rename("{xml}.jpfont-new", "{xml}"));',
    ])
    if not restore:
        # Every new reference is valid before deleting the old collections.
        for info in originals.values():
            path = TARGET + "/fonts/" + info["file"]
            script.extend([f'delete("{path}");',
                f'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "absent", "{path}") == "0" || abort("Old TTC removal failed."));'])
    if restore:
        for info in infos.values():
            filename, digest = info["file"], info["sha256"]
            path = TARGET + "/fonts/" + filename
            script.append(f'ifelse(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "hash", "{path}", "{digest}") == "0" && run_program("/sbin/sh", "/tmp/jp-font-check.sh", "unreferenced", "{xml}", "{filename}") == "0", delete("{path}"), ui_print("Keeping absent, modified or referenced font: {filename}"));')
    script.extend([f'assert(unmount("{MOUNT}"));', 'ui_print("Done. Reboot system.");'])
    return ("\n".join(script) + "\n").encode()


def write_zip(path, contents):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            mode = 0o755 if name.endswith(("update-binary", ".sh")) else 0o644
            entry.external_attr = (stat.S_IFREG | mode) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        check(archive.testzip() is None, "ZIP CRC validation failed")
        check(set(archive.namelist()) == set(contents), "ZIP entries mismatch")
        for name, data in contents.items():
            check(archive.read(name) == data, f"ZIP content mismatch: {name}")


def main():
    from build_latin import build_latin
    from fetch_assets import verify_rom
    verify_rom(ROM)
    prefix = extract()
    check(prefix == "/system", "This builder expects the verified cronos system-as-root layout")
    original = (BUILD / "fonts.original.xml").read_bytes()
    patched = patch_xml(original)
    infos = {kind: font_info(ROOT / filename, WEIGHTS[kind], kind) for kind, filename in FONTS.items()}
    original_data = {}
    original_notices = []
    binary = (BUILD / "update-binary").read_bytes()
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
    (BUILD / "fonts.patched.xml").write_bytes(patched)
    report = {
        "rom": {"file": ROM.name, "sha256": sha256(ROM), "system_prefix": prefix},
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
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
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
        path = dist / ("cronos-cjk-fonts-restore.zip" if restore else "cronos-cjk-fonts-install.zip")
        write_zip(path, contents)
        sums.append(f"{sha256(path)}  {path.name}")
        print(f"Verified: {path.name} ({path.stat().st_size:,} bytes)")
    sums.extend(build_latin(original, binary, dist))
    (dist / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (dist / "cjk-verification.json").write_bytes(shared["verification.json"])


def recovery_payload(original, patched, component, restore):
    files = slot_payload(original, patched, component, restore)
    for name in ("run-python.sh", "font_patch.py"):
        files["patch/" + name] = (ROOT / "recovery" / name).read_bytes()
    files["patch/font_slots.py"] = (ROOT / "scripts/font_slots.py").read_bytes()
    return files


if __name__ == "__main__":
    main()
