"""Build all independent font patches and their checksum manifest."""
from build_cjk import build_cjk
from build_common import check
from build_latin import build_latin
from build_named import build_named
from extract_rom import BUILD, ROM, ROOT, extract
from fetch_assets import verify_rom


def main():
    verify_rom(ROM)
    prefix = extract()
    check(prefix == "/system", "This builder expects the verified cronos system-as-root layout")
    original = (BUILD / "fonts.original.xml").read_bytes()
    binary = (BUILD / "update-binary").read_bytes()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    sums = build_cjk(original, binary, dist)
    sums.extend(build_latin(original, binary, dist))
    for component in ('serif', 'mono'):
        sums.extend(build_named(original, binary, dist, component))
    (dist / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
