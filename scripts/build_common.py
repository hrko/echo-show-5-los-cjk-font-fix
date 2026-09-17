"""Shared recovery payload, updater and deterministic ZIP helpers."""
import stat
import zipfile

from extract_rom import ROOT
from font_slots import payload as slot_payload
from targets import SYSTEM_BLOCKS, TARGETS

META = "META-INF/com/google/android/"
MOUNT = "/tmp/jp-font-system"
TARGET = MOUNT + "/system"


def artifact_name(component, kind):
    """Name a distributable ZIP or its component verification report."""
    if component not in ('cjk', 'latin', 'serif', 'mono'):
        raise ValueError(f"Unknown component: {component}")
    if kind not in ('install', 'restore', 'verification'):
        raise ValueError(f"Unknown artifact kind: {kind}")
    suffix = 'json' if kind == 'verification' else 'zip'
    return f'echo-show-{component}-fonts-{kind}.{suffix}'


def check(condition, message):
    if not condition:
        raise ValueError(message)


# Compatibility entry point; all file guards run in the bundled Python.
CHECKER = b'''#!/sbin/sh
exec /sbin/sh /tmp/jp-font-patch/run-python.sh check "$@"
'''


def updater(original, patched, infos, originals, restore=False, component="cjk", retained=None):
    action = "Restore" if restore else "Install"
    from named_fonts import COMPONENTS
    label = {"cjk": "CJK Sans 100-900 / Serif 200-900", "latin": "Google Sans Flex 100-900 normal/italic",
             **{key: config['label'] for key, config in COMPONENTS.items()}}[component]
    patch_dir = "/tmp/jp-font-patch"
    work_dir = "/tmp/jp-font-work"
    xml = TARGET + "/etc/fonts.xml"
    devices = []
    roms = []
    for device, target in TARGETS.items():
        fingerprint = target['fingerprint']
        check(all(c not in device + fingerprint for c in ('"', '\\', '\n', '\r')), 'Unsafe target')
        recovery_device = f'(getprop("ro.product.device") == "{device}" || getprop("ro.build.product") == "{device}")'
        devices.append(recovery_device)
        roms.append(f'({recovery_device} && file_getprop("{TARGET}/build.prop", "ro.product.system.device") == "{device}" && file_getprop("{TARGET}/build.prop", "ro.system.build.fingerprint") == "{fingerprint}")')
    mounts = ' || '.join(f'mount("ext4", "EMMC", "{block}", "{MOUNT}", "rw")' for block in SYSTEM_BLOCKS)
    script = [
        f'ui_print("{action} {label} (Echo Show: checkers / cronos / crown)");',
        f'assert({" || ".join(devices)} || abort("Unsupported device. Requires checkers, cronos or crown."));',
        'assert(package_extract_dir("runtime", "/tmp/jp-font-python"));',
        'set_metadata("/tmp/jp-font-python/lib/ld-musl-armhf.so.1", "uid", 0, "gid", 0, "mode", 0755);',
        f'assert(package_extract_dir("patch", "{patch_dir}"));',
        'assert(package_extract_file("check.sh", "/tmp/jp-font-check.sh"));',
        'assert(run_program("/sbin/sh", "/tmp/jp-font-check.sh", "ready") == "0" || abort("Bundled ARMv7 Python could not start."));',
        f'ifelse(is_mounted("{MOUNT}"), assert(unmount("{MOUNT}")));',
        f'assert({mounts} || abort("Cannot mount system read-write. Unmount System in TWRP and retry."));',
        f'assert({" || ".join(roms)} || abort("Unsupported ROM or device/ROM mismatch."));',
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


def recovery_payload(original, patched, component, restore):
    files = slot_payload(original, patched, component, restore)
    for name in ("run-python.sh", "font_patch.py"):
        files["patch/" + name] = (ROOT / "recovery" / name).read_bytes()
    files["patch/font_slots.py"] = (ROOT / "scripts/font_slots.py").read_bytes()
    return files

