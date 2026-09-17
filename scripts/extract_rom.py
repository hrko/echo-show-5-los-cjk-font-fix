"""Read a full Android block OTA; never mount or modify the source ROM."""
from pathlib import Path
import hashlib
import zipfile

import brotli
from ext4 import Volume

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "lineage-18.1-20260904-UNOFFICIAL-cronos.zip"
BUILD = ROOT / "build"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract():
    BUILD.mkdir(exist_ok=True)
    image = BUILD / "system.img"
    stamp = BUILD / "rom.sha256"
    digest = sha256(ROM)
    if not (image.exists() and stamp.exists() and stamp.read_text() == digest):
        with zipfile.ZipFile(ROM) as archive:
            lines = archive.read("system.transfer.list").decode().splitlines()
            if lines[0] != "4" or lines[2:4] != ["0", "0"]:
                raise ValueError("Only full version-4 OTAs without stash are supported")
            ranges = []
            written_blocks = 0
            max_block = 0
            for line in lines[4:]:
                command, encoded = line.split()
                if command not in {"new", "zero", "erase"}:
                    raise ValueError(f"Unsupported OTA command: {command}")
                values = list(map(int, encoded.split(",")))
                if values[0] != len(values) - 1 or values[0] % 2:
                    raise ValueError("Invalid block range")
                for start, end in zip(values[1::2], values[2::2]):
                    if not 0 <= start < end:
                        raise ValueError("Invalid block bounds")
                    max_block = max(max_block, end)
                    if command in {"new", "zero"}:
                        written_blocks += end - start
                    if command == "new":
                        ranges.append((start * 4096, end * 4096))
            if written_blocks != int(lines[1]):
                raise ValueError("Transfer-list total does not match new + zero blocks")
            ordered = sorted(ranges)
            if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
                raise ValueError("Overlapping new ranges")
            print("Decompressing ROM and reconstructing ext4 image...", flush=True)
            decoder = brotli.Decompressor()
            index = 0
            offset = ranges[0][0]
            with archive.open("system.new.dat.br") as source, image.open("wb") as target:
                target.truncate(max_block * 4096)
                while chunk := source.read(1024 * 1024):
                    data = memoryview(decoder.process(chunk))
                    while data:
                        if index >= len(ranges):
                            raise ValueError("Excess decompressed data")
                        count = min(len(data), ranges[index][1] - offset)
                        target.seek(offset)
                        target.write(data[:count])
                        data = data[count:]
                        offset += count
                        if offset == ranges[index][1]:
                            index += 1
                            if index < len(ranges):
                                offset = ranges[index][0]
                if not decoder.is_finished() or index != len(ranges):
                    raise ValueError("Truncated Brotli data")
        stamp.write_text(digest)
    with image.open("rb") as stream:
        volume = Volume(stream)
        roots = []
        for prefix in ("", "/system"):
            try:
                inode = volume.inode_at(prefix + "/etc/fonts.xml")
            except (FileNotFoundError, NotADirectoryError):
                continue
            roots.append((prefix, inode.open().read()))
        if len(roots) != 1:
            raise ValueError(f"Ambiguous system layout: {len(roots)} roots")
        prefix, fonts = roots[0]
        (BUILD / "fonts.original.xml").write_bytes(fonts)
        (BUILD / "build.prop").write_bytes(volume.inode_at(prefix + "/build.prop").open().read())
        (BUILD / "system-prefix.txt").write_text(prefix)
        print(f"System prefix inside ext4: {prefix or '/'}")
    with zipfile.ZipFile(ROM) as archive:
        (BUILD / "update-binary").write_bytes(archive.read("META-INF/com/google/android/update-binary"))
        (BUILD / "rom-updater-script").write_bytes(archive.read("META-INF/com/google/android/updater-script"))
    return prefix


if __name__ == "__main__":
    extract()
