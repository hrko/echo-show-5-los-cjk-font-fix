"""Pinned official Google Fonts inputs for the serif and monospace patches."""
from typing import TypedDict

from fetch_assets import LATIN_COMMIT, ROOT, fetch_verified, git_blob


class FontConfig(TypedDict):
    family: str
    upstream: str
    label: str
    weights: list[int]
    axes: dict[str, list[float]]
    fixed: dict[str, float]
    stock: list[str]
    fonts: dict[str, tuple[str, str, str, str]]
    licenses: dict[str, tuple[str, str]]


COMPONENTS: dict[str, FontConfig] = {
    'serif': {
        'family': 'serif', 'upstream': 'notoserif', 'label': 'Noto Serif 100-900 normal/italic',
        'weights': list(range(100, 901, 100)),
        'axes': {'wght': [100, 400, 900], 'wdth': [62.5, 100, 100]},
        'fixed': {'wdth': 100},
        'stock': ['NotoSerif-Regular.ttf', 'NotoSerif-Bold.ttf', 'NotoSerif-Italic.ttf', 'NotoSerif-BoldItalic.ttf'],
        'fonts': {
            'normal': ('NotoSerif-VF.ttf', 'NotoSerif%5Bwdth%2Cwght%5D.ttf', '7664d59c95d6c589f7b15017a218f7a42b93f86d', 'Version 2.015'),
            'italic': ('NotoSerif-Italic-VF.ttf', 'NotoSerif-Italic%5Bwdth%2Cwght%5D.ttf', '0e60f3e9248b524e6c9a28d38fbfc147463b1f5a', 'Version 2.013'),
        },
        'licenses': {'NotoSerifLatin-OFL.txt': ('OFL.txt', '6843f31878c9945e1e71e1baa275546b4eefead8')},
    },
    'mono': {
        'family': 'monospace', 'upstream': 'googlesanscode', 'label': 'Google Sans Code 300-800 normal/italic',
        'weights': list(range(300, 801, 100)), 'axes': {'wght': [300, 400, 800]}, 'fixed': {},
        'stock': ['DroidSansMono.ttf'],
        'fonts': {
            'normal': ('GoogleSansCode-VF.ttf', 'GoogleSansCode%5Bwght%5D.ttf', '4b63b009b1f32a2ad99b38790d1e8e87ae7d89df', 'Version 6.001'),
            'italic': ('GoogleSansCode-Italic-VF.ttf', 'GoogleSansCode-Italic%5Bwght%5D.ttf', 'f05ee5febff8ef300edfba3824d0fd35f6d99830', 'Version 6.001'),
        },
        'licenses': {
            'GoogleSansCode-OFL.txt': ('OFL.txt', 'a65b4bbe0f4a1242cc31c1d687996336dceef0eb'),
            'GoogleSansCode-TRADEMARKS.md': ('TRADEMARKS.md', '6ebcf03e0ee242ef24b02aac94da6f5f2152b9ed'),
        },
    },
}


def source_url(config, filename):
    return f"https://raw.githubusercontent.com/google/fonts/{LATIN_COMMIT}/ofl/{config['upstream']}/{filename}"


def verify_blob(path, expected):
    if git_blob(path.read_bytes()) != expected:
        raise ValueError(f'Upstream Git blob mismatch; refusing to use or overwrite: {path}')


def fetch_named_fonts(root=ROOT):
    for config in COMPONENTS.values():
        for filename, upstream, expected, _ in config['fonts'].values():
            fetch_verified(source_url(config, upstream), root / filename,
                           lambda path, expected=expected: verify_blob(path, expected))
        for filename, (_, expected) in config['licenses'].items():
            verify_blob(root / 'licenses' / filename, expected)
