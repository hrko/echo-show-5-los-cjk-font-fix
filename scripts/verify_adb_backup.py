"""Validate TWRP v3 ADB backup framing, CRCs, payload MD5s and gzip CRCs.

Format: TeamWin/android_bootable_recovery adbbu/twadbstream.h and twrpback.cpp.
Reads only; writes a sidecar report after the entire stream passes validation.
"""
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def control(block, crc_offset, trailer=False):
    require(len(block) == 512 and block[:8] == b"TWRP\0\0\0\0", "Invalid or truncated control block")
    expected = struct.unpack_from("<I", block, crc_offset)[0]
    copy = bytearray(block)
    copy[crc_offset:crc_offset + 4] = bytes(4)
    if trailer:
        copy[28:32] = bytes(4)
    require(zlib.crc32(copy) == expected, "Control block CRC mismatch")
    return block[8:24].split(b"\0", 1)[0].decode("ascii")


def verify(path):
    entries = []
    with path.open("rb") as stream:
        first = stream.read(512)
        require(control(first, 40) == "twstreamheader", "Not a TWRP ADB stream")
        count, version = struct.unpack_from("<QQ", first, 24)
        require(version == 3, "Unsupported TWRP backup version")
        while True:
            header = stream.read(512)
            kind = header[8:24].split(b"\0", 1)[0]
            if kind == b"twendadb":
                control(header, 24)
                require(not stream.read(1), "Unexpected bytes after stream end")
                break
            require(control(header, 40) in {"twfilename", "twimage"}, "Unexpected file header")
            size, compressed = struct.unpack_from("<QQ", header, 24)
            # twrpback.cpp explicitly treats TWIMG as raw regardless of the flag.
            compressed = bool(compressed) and kind == b"twfilename"
            name = header[44:].split(b"\0", 1)[0].decode()
            digest = hashlib.md5()
            unzip = zlib.decompressobj(31) if compressed else None
            payload_bytes = 0
            uncompressed_bytes = 0
            while True:
                block = stream.read(512)
                kind = control(block, 24, trailer=block[8:18] == b"md5trailer")
                if kind == "md5trailer":
                    expected = block[32:72].split(b"\0", 1)[0].decode()
                    require(digest.hexdigest() == expected, f"Payload MD5 mismatch: {name}")
                    ident = bytearray(block)
                    expected_ident = struct.unpack_from("<I", ident, 28)[0]
                    ident[28:32] = bytes(4)
                    require(zlib.crc32(struct.pack("<Q", size), zlib.crc32(ident)) == expected_ident,
                            f"Trailer identity CRC mismatch: {name}")
                    break
                require(kind == "twdatablock", f"Unexpected data control: {kind}")
                data = stream.read(1048576 - 512)
                require(len(data) == 1048576 - 512, "Truncated data chunk")
                digest.update(data)
                if unzip:
                    if unzip.eof:
                        require(not any(data), "Nonzero gzip trailing padding")
                    else:
                        uncompressed_bytes += len(unzip.decompress(data))
                        if unzip.eof:
                            require(not any(unzip.unused_data), "Nonzero gzip trailing bytes")
                else:
                    if payload_bytes + len(data) > size:
                        require(not any(data[max(0, size - payload_bytes):]), "Nonzero image padding")
                payload_bytes += len(data)
            if unzip:
                require(unzip.eof, f"Truncated gzip payload: {name}")
            else:
                require(payload_bytes >= size, "Truncated image payload")
            entry = {"name": name, "declared_size": size, "compressed": bool(compressed),
                     "payload_bytes_with_padding": payload_bytes, "md5": digest.hexdigest(),
                     "uncompressed_bytes": uncompressed_bytes if compressed else size}
            entries.append(entry)
            print(f"Verified payload: {name.rsplit('/', 1)[-1]}", flush=True)
        require(len(entries) == count, "Partition count mismatch")
    with path.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256,
              "format_version": version, "partition_count": count, "entries": entries}
    path.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Complete backup verified: {sha256}")
    return report


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
