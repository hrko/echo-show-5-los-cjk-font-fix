"""Build all independent font patches and their checksum manifest."""
from build_cjk import build_cjk
from build_latin import build_latin
from build_named import build_named
from extract_rom import BUILD, ROOT
from verify_targets import verify_targets


def main():
    compatibility = verify_targets()
    original = (BUILD / "fonts.original.xml").read_bytes()
    binary = (BUILD / "update-binary").read_bytes()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    sums = build_cjk(original, binary, dist, compatibility)
    sums.extend(build_latin(original, binary, dist, compatibility))
    for component in ('serif', 'mono'):
        sums.extend(build_named(original, binary, dist, component, compatibility))
    (dist / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
