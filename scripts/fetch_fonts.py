"""Fetch pinned, unmodified upstream TrueType variable collections using gh."""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "f8d157532fbfaeda587e826d4cd5b21a49186f7c"
SOURCES = {
    "NotoSansCJK-VF.ttf.ttc": ("Sans", "cfeab111cec01c491c0120aeb905a86afaecea56"),
    "NotoSerifCJK-VF.ttf.ttc": ("Serif", "f2e98c60cee4f44de9f671d76d900ac84a50da14"),
}


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main():
    for name, (family, expected) in SOURCES.items():
        path = ROOT / name
        if path.exists():
            if git_blob(path.read_bytes()) != expected:
                raise ValueError(f"Existing font differs from upstream: {path}")
            print(f"Already verified: {name}")
            continue
        endpoint = f"repos/notofonts/noto-cjk/contents/{family}/Variable/OTC/{name}?ref={COMMIT}"
        data = subprocess.run(["gh", "api", endpoint, "-H", "Accept: application/vnd.github.raw"],
                              stdout=subprocess.PIPE, check=True).stdout
        if data[:4] != b"ttcf" or git_blob(data) != expected:
            raise ValueError(f"Upstream font verification failed: {name}")
        with path.open("xb") as stream:
            stream.write(data)
        print(f"Fetched and verified: {name} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
