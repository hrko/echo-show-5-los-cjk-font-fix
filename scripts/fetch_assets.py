"""Fetch all external build inputs, pinning the ROM and upstream fonts."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from fetch_fonts import ROOT, main as fetch_fonts

ROM_NAME = "lineage-18.1-20260904-UNOFFICIAL-cronos.zip"
ROM_REPO = "amazon-oss/releases"
ROM_TAG = "lineage-18.1-cronos-v0.4"
ROM_SHA256 = "4c355998061a454792128d4b730932b47ed05a3d2a6d2628599218f44cc84678"


def verify_rom(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch; refusing to use or overwrite: {path}")


def fetch_rom(root=ROOT):
    destination = root / ROM_NAME
    if destination.exists():
        verify_rom(destination)
        print(f"Already verified: {ROM_NAME}")
        return
    # Stage on the destination filesystem. Only verified data gets the final name.
    with tempfile.NamedTemporaryFile(dir=root, prefix=".rom-download-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        subprocess.run([
            "gh", "release", "download", ROM_TAG, "--repo", ROM_REPO,
            "--pattern", ROM_NAME, "--output", str(temporary), "--clobber",
        ], check=True)
        verify_rom(temporary)
        # Atomic publication without overwriting a file created by another process.
        os.link(temporary, destination)
        print(f"Fetched and verified: {ROM_NAME} ({destination.stat().st_size:,} bytes)")
    finally:
        temporary.unlink(missing_ok=True)


def main():
    for name in ("NotoSans-OFL.txt", "NotoSerif-OFL.txt", "FONT-COPYRIGHT.txt"):
        if not (ROOT / "licenses" / name).is_file():
            raise FileNotFoundError(f"Restore the tracked licenses/{name} file from Git")
    fetch_rom()
    fetch_fonts()
    print("All external build assets verified. Run: mise run build")


if __name__ == "__main__":
    main()
