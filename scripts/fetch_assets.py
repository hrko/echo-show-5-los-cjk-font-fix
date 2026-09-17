"""Fetch all external build inputs, pinning the ROM and upstream fonts."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "f8d157532fbfaeda587e826d4cd5b21a49186f7c"
SOURCES = {
    "NotoSansCJK-VF.ttf.ttc": ("Sans", "cfeab111cec01c491c0120aeb905a86afaecea56"),
    "NotoSerifCJK-VF.ttf.ttc": ("Serif", "f2e98c60cee4f44de9f671d76d900ac84a50da14"),
}
LATIN_COMMIT = "3dc14e61f108f036db84188b9b405a67df9b7c88"
LATIN_FILE = "GoogleSansFlex-Regular.ttf"
LATIN_UPSTREAM_FILE = "GoogleSansFlex%5BGRAD%2CROND%2Copsz%2Cslnt%2Cwdth%2Cwght%5D.ttf"
LATIN_URL = f"https://raw.githubusercontent.com/google/fonts/{LATIN_COMMIT}/ofl/googlesansflex/{LATIN_UPSTREAM_FILE}"
LATIN_SHA256 = "c31a482fbecbf2e07e6890134d20078723aadf732c9b9c6c9a44f86f8265b6fe"
LATIN_VERSION = "Version 4.005;[3fe7d0b9f]"


def verify_latin(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != LATIN_SHA256:
        raise ValueError(f"Google Sans Flex SHA-256 mismatch; refusing to use or overwrite: {path}")


def fetch_latin(root=ROOT):
    fetch_verified(LATIN_URL, root / LATIN_FILE, verify_latin)

ROM_NAME = "lineage-18.1-20260904-UNOFFICIAL-cronos.zip"
ROM_REPO = "amazon-oss/releases"
ROM_TAG = "lineage-18.1-cronos-v0.4"
ROM_SHA256 = "4c355998061a454792128d4b730932b47ed05a3d2a6d2628599218f44cc84678"


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fetch_fonts(root=ROOT):
    for name, (family, expected) in SOURCES.items():
        def verify_font(path):
            data = path.read_bytes()
            if data[:4] != b"ttcf" or git_blob(data) != expected:
                raise ValueError(f"Font differs from upstream; refusing to use or overwrite: {path}")
        url = f"https://raw.githubusercontent.com/notofonts/noto-cjk/{COMMIT}/{family}/Variable/OTC/{name}"
        fetch_verified(url, root / name, verify_font)


def verify_rom(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch; refusing to use or overwrite: {path}")


def fetch_rom(root=ROOT):
    url = f"https://github.com/{ROM_REPO}/releases/download/{ROM_TAG}/{ROM_NAME}"
    fetch_verified(url, root / ROM_NAME, verify_rom)


def fetch_verified(url, destination, verify):
    if destination.exists():
        verify(destination)
        print(f"Already verified: {destination.name}")
        return
    # Stage on the destination filesystem. Only verified data gets the final name.
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".asset-download-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        print(f"Downloading: {destination.name}", flush=True)
        request = Request(url, headers={"User-Agent": "echo-show-5-cjk-font-fix"})
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        verify(temporary)
        # Atomic publication without overwriting a file created by another process.
        os.link(temporary, destination)
        print(f"Fetched and verified: {destination.name} ({destination.stat().st_size:,} bytes)")
    finally:
        temporary.unlink(missing_ok=True)


def main():
    for name in ("NotoSans-OFL.txt", "NotoSerif-OFL.txt", "FONT-COPYRIGHT.txt"):
        if not (ROOT / "licenses" / name).is_file():
            raise FileNotFoundError(f"Restore the tracked licenses/{name} file from Git")
    fetch_rom()
    fetch_fonts()
    fetch_latin()
    from python_runtime import fetch_runtime
    fetch_runtime()
    print("All external build assets verified. Run: mise run build")


if __name__ == "__main__":
    main()
