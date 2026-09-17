"""Build deterministic, ROM-specific install/restore recovery ZIPs using Python."""
from pathlib import Path
import copy
import hashlib
import json
import re
import stat
import xml.etree.ElementTree as ET
import zipfile

from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from ext4 import Volume

from extract_rom import BUILD, ROM, ROOT, extract, sha256

META = "META-INF/com/google/android/"
MOUNT = "/tmp/jp-font-system"
TARGET = MOUNT + "/system"
FONTS = {"sans": "NotoSansCJKjp-VF.ttf", "serif": "NotoSerifCJKjp-VF.ttf"}
WEIGHTS = {"sans": list(range(100, 901, 100)), "serif": list(range(200, 901, 100))}
UPSTREAM_BLOBS = {
    "NotoSansCJKjp-VF.ttf": "1196f022592989cd6a66cac06cddf81043bd53ba",
    "NotoSerifCJKjp-VF.ttf": "d2a12d4fb23c2cfe18942cbf1fea7dceb04dc2c1",
}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def font_info(path, weights):
    data = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    check(blob == UPSTREAM_BLOBS[path.name], "Font does not match the verified upstream Git blob")
    with TTFont(path, checkChecksums=2) as font:
        check(font.sfntVersion == "\x00\x01\x00\x00", "Expected TrueType outlines")
        check("glyf" in font and "gvar" in font, "Missing TrueType variation tables")
        axes = font["fvar"].axes
        check(len(axes) == 1 and axes[0].axisTag == "wght", "Unexpected font axes")
        axis = axes[0]
        check(axis.minValue == min(weights) and axis.maxValue == max(weights), "Unexpected weight range")
        cmap = font.getBestCmap()
        samples = "日本語漢字かなカナ骨直令辻"
        check(all(ord(c) in cmap for c in samples), "Missing sample Japanese glyphs")
        outlines = {}
        for weight in weights:
            glyphs = font.getGlyphSet(location={"wght": weight})
            pen = RecordingPen()
            for char in samples:
                glyphs[cmap[ord(char)]].draw(pen)
            outlines[str(weight)] = hashlib.sha256(repr(pen.value).encode()).hexdigest()
        check(len(set(outlines.values())) == len(weights), "Weights have duplicate sample outlines")
        names = font["name"]
        return {
            "file": path.name, "sha256": sha256(path), "bytes": path.stat().st_size,
            "upstream_git_blob": blob,
            "version": names.getDebugName(5), "postscript_name": names.getDebugName(6),
            "copyright": names.getDebugName(0),
            "axis": {"tag": "wght", "min": axis.minValue, "default": axis.defaultValue, "max": axis.maxValue},
            "weights": weights, "sample_outline_sha256": outlines,
        }


def patch_xml(original):
    text = original.decode("utf-8")
    before = ET.fromstring(original)
    families = before.findall("./family[@lang='ja']")
    check(len(families) == 1, "Expected exactly one Japanese family")
    old = families[0]
    check(len(old) == 2, "Unexpected Japanese family contents")
    check([(f.text.strip(), f.get("fallbackFor")) for f in old] == [
        ("NotoSansCJK-Regular.ttc", None), ("NotoSerifCJK-Regular.ttc", "serif")
    ], "Unexpected original fonts")
    lines = ['<family lang="ja">']
    for kind, filename in FONTS.items():
        fallback = ' fallbackFor="serif"' if kind == "serif" else ""
        for weight in WEIGHTS[kind]:
            lines.append(f'        <font weight="{weight}" style="normal"{fallback}>{filename}'
                         f'<axis tag="wght" stylevalue="{weight}" /></font>')
    lines.append("    </family>")
    result, count = re.subn(r'<family lang="ja">.*?</family>', "\n".join(lines), text, flags=re.S)
    check(count == 1, "Ambiguous Japanese XML replacement")
    after = ET.fromstring(result)
    old_index = list(before).index(old)
    restored = copy.deepcopy(after)
    restored.remove(restored[old_index])
    restored.insert(old_index, copy.deepcopy(old))
    check(ET.tostring(restored) == ET.tostring(before), "Non-Japanese configuration changed")
    return result.encode("utf-8")


# TWRP supplies /sbin/sh and BusyBox. Check availability before touching system.
# No sha1_check/set_perm: neither function exists in the supplied Android 11 updater.
CHECKER = b'''#!/sbin/sh
set -eu
BB=/sbin/busybox
[ -x "$BB" ] || { echo "TWRP /sbin/busybox is required" >&2; exit 1; }
mode="$1"
shift
case "$mode" in
  ready) "$BB" sha256sum /dev/null >/dev/null ;;
  hash|optional)
    file="$1"
    shift
    if [ "$mode" = optional ] && [ ! -e "$file" ] && [ ! -L "$file" ]; then exit 0; fi
    [ -f "$file" ] && [ ! -L "$file" ] || exit 1
    result=$("$BB" sha256sum "$file") || exit 1
    actual=${result%% *}
    for expected in "$@"; do
      [ "$actual" != "$expected" ] || exit 0
    done
    echo "Unexpected SHA-256: $file" >&2
    exit 1 ;;
  *) exit 1 ;;
esac
'''


def updater(original, patched, infos, restore=False):
    props = dict(line.split("=", 1) for line in (BUILD / "build.prop").read_text().splitlines()
                 if "=" in line and not line.startswith("#"))
    fingerprint = props["ro.system.build.fingerprint"]
    check('"' not in fingerprint and "\\" not in fingerprint, "Unsafe fingerprint")
    hashes = [hashlib.sha256(data).hexdigest() for data in (original, patched)]
    action = "Restore" if restore else "Install"
    script = [
        f'ui_print("{action} Japanese Sans 100-900 / Serif 200-900 (cronos)");',
        'assert(getprop("ro.product.device") == "cronos" || getprop("ro.build.product") == "cronos" || abort("This ZIP is only for cronos."));',
        'assert(package_extract_file("check.sh", "/tmp/jp-font-check.sh"));',
        'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "ready") == "0" || abort("TWRP BusyBox with sha256sum is required."));',
        f'ifelse(is_mounted("{MOUNT}"), assert(unmount("{MOUNT}")));',
        f'assert(mount("ext4", "EMMC", "/dev/block/platform/soc/by-name/system", "{MOUNT}", "rw") || mount("ext4", "EMMC", "/dev/block/platform/soc/11230000.mmc/by-name/system", "{MOUNT}", "rw") || abort("Cannot mount system read-write. Unmount System in TWRP and retry."));',
        f'assert(file_getprop("{TARGET}/build.prop", "ro.system.build.fingerprint") == "{fingerprint}" || abort("Wrong ROM build."));',
    ]

    def hash_check(path, expected, optional=False):
        args = ", ".join(f'"{v}"' for v in (["optional" if optional else "hash", path] + expected))
        return f'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", {args}) == "0" || abort("File verification failed: {path}"));'

    script.append(hash_check(TARGET + "/etc/fonts.xml", hashes))
    if not restore:
        for info in infos.values():
            script.append(hash_check(TARGET + "/fonts/" + info["file"], [info["sha256"]], optional=True))

    def stage(source, target, digest):
        temporary = target + ".jpfont-new"
        script.extend([
            f'assert(package_extract_file("{source}", "{temporary}") || abort("Extraction failed; check free system space."));',
            hash_check(temporary, [digest]),
            f'set_metadata("{temporary}", "uid", 0, "gid", 0, "mode", 0644, "selabel", "u:object_r:system_file:s0");',
            f'assert(rename("{temporary}", "{target}"));',
        ])

    if not restore:
        for info in infos.values():
            stage("system/fonts/" + info["file"], TARGET + "/fonts/" + info["file"], info["sha256"])
    stage("system/etc/fonts.xml", TARGET + "/etc/fonts.xml", hashes[0 if restore else 1])
    if restore:
        for info in infos.values():
            path = TARGET + "/fonts/" + info["file"]
            script.append(f'ifelse(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "hash", "{path}", "{info["sha256"]}") == "0", delete("{path}"), ui_print("Keeping absent or modified font: {info["file"]}"));')
    script.extend([f'assert(unmount("{MOUNT}"));', 'ui_print("Done. Reboot system.");'])
    return ("\n".join(script) + "\n").encode()


def write_zip(path, contents):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            mode = 0o755 if name.endswith("update-binary") or name.endswith(".sh") else 0o644
            entry.external_attr = (stat.S_IFREG | mode) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        check(archive.testzip() is None, "ZIP CRC validation failed")
        check(set(archive.namelist()) == set(contents), "ZIP entries mismatch")
        for name, data in contents.items():
            check(archive.read(name) == data, f"ZIP content mismatch: {name}")


def main():
    prefix = extract()
    check(prefix == "/system", "This builder expects the verified cronos system-as-root layout")
    original = (BUILD / "fonts.original.xml").read_bytes()
    patched = patch_xml(original)
    infos = {kind: font_info(ROOT / filename, WEIGHTS[kind]) for kind, filename in FONTS.items()}
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
        for font in ET.fromstring(patched).iter("font"):
            filename = font.text.strip()
            if filename not in FONTS.values():
                volume.inode_at("/system/fonts/" + filename)
    (BUILD / "fonts.patched.xml").write_bytes(patched)
    report = {
        "rom": {"file": ROM.name, "sha256": sha256(ROM), "system_prefix": prefix},
        "fonts": infos, "original_xml_sha256": hashlib.sha256(original).hexdigest(),
        "patched_xml_sha256": hashlib.sha256(patched).hexdigest(),
        "updater_sha256": hashlib.sha256(binary).hexdigest(),
        "device_tested": False,
        "serif_upstream_commit": "f8d157532fbfaeda587e826d4cd5b21a49186f7c",
    }
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    shared = {META + "update-binary": binary, "check.sh": CHECKER,
              "verification.json": (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()}
    for required in ("NotoSans-OFL.txt", "NotoSerif-OFL.txt", "FONT-COPYRIGHT.txt"):
        check((ROOT / "licenses" / required).is_file(), f"Missing license notice: {required}")
    for license_file in (ROOT / "licenses").glob("*.txt"):
        shared["licenses/" + license_file.name] = license_file.read_bytes()
    sums = []
    for restore in (False, True):
        contents = dict(shared)
        contents[META + "updater-script"] = updater(original, patched, infos, restore)
        contents["system/etc/fonts.xml"] = original if restore else patched
        if not restore:
            for filename in FONTS.values():
                contents["system/fonts/" + filename] = (ROOT / filename).read_bytes()
        path = dist / ("cronos-jp-fonts-restore.zip" if restore else "cronos-jp-fonts-install.zip")
        write_zip(path, contents)
        sums.append(f"{sha256(path)}  {path.name}")
        print(f"Verified: {path.name} ({path.stat().st_size:,} bytes)")
    (dist / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (dist / "verification.json").write_bytes(shared["verification.json"])


if __name__ == "__main__":
    main()
