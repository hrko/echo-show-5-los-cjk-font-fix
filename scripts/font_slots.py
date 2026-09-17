"""Composable, explicitly owned fonts.xml slots; no state combination enumeration."""
import hashlib
import re

# These ownership boundaries are a recovery format contract. Existing ZIPs can
# preserve future serif/monospace patches without knowing their font versions.
SLOTS = {
    "latin-sans": 'name="sans-serif"',
    "latin-condensed": 'name="sans-serif-condensed"',
    "serif": 'name="serif"',
    "mono": 'name="monospace"',
    "cjk-sc": 'lang="zh-Hans"',
    "cjk-tc": 'lang="zh-Hant,zh-Bopo"',
    "cjk-ja": 'lang="ja"',
    "cjk-ko": 'lang="ko"',
}
OWNERS = {"latin": ("latin-sans", "latin-condensed"),
          "cjk": ("cjk-sc", "cjk-tc", "cjk-ja", "cjk-ko"),
          "serif": ("serif",), "mono": ("mono",)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def split_xml(data):
    text = data.decode("utf-8")
    slots = {}
    for key, attribute in SLOTS.items():
        pattern = r'^    <family ' + re.escape(attribute) + r'>\n.*?^    </family>\n'
        pattern += (r'(?:^    <!-- font-slot: ' + re.escape(key) +
                    r' fallback -->\n^    <family>\n.*?^    </family>\n)?')
        if key == "cjk-tc":
            pattern = r'(?:^    <family lang="zh-Hant-HK">\n.*?^    </family>\n)?' + pattern
        def replace(match):
            fragment = match[0]
            families = 1 + int('<!-- font-slot: ' + key + ' fallback -->' in fragment)
            if key == 'cjk-tc' and fragment.startswith('    <family lang="zh-Hant-HK">'):
                families += 1
            if len(re.findall(r'</?family\b', fragment)) != families * 2:
                raise ValueError(f'Invalid family boundary: {key}')
            slots[key] = match[0].encode()
            return f"@@FONT-SLOT {key}@@\n"
        text, count = re.subn(pattern, replace, text, flags=re.M | re.S)
        if count != 1:
            raise ValueError(f"Expected exactly one slot: {key}")
    return text.encode(), slots


def compose_xml(skeleton, slots):
    for key in SLOTS:
        skeleton = skeleton.replace(f"@@FONT-SLOT {key}@@\n".encode(), slots[key])
    return skeleton


def payload(original, patched, component, restore=False):
    skeleton, stock = split_xml(original)
    changed_skeleton, changed = split_xml(patched)
    if skeleton != changed_skeleton:
        raise ValueError("Unowned XML structure changed")
    owned = OWNERS[component]
    for key in SLOTS:
        if key not in owned and stock[key] != changed[key]:
            raise ValueError(f"Unowned slot changed: {key}")
    files = {"patch/skeleton.sha256": (digest(skeleton) + "\n").encode(), "patch/format": b"1\n"}
    manifest = []
    for key in owned:
        desired = stock[key] if restore else changed[key]
        files[f"patch/{key}"] = desired
        manifest.append(f"{key} {digest(stock[key])} {digest(changed[key])} {digest(desired)}")
    files["patch/slots.txt"] = ("\n".join(manifest) + "\n").encode()
    # This is checked against the composed output BEFORE a CJK font is deleted.
    removed = ["NotoSansCJK-Regular.ttc", "NotoSerifCJK-Regular.ttc"] if component == "cjk" and not restore else []
    files["patch/removed.txt"] = ("\n".join(removed) + ("\n" if removed else "")).encode()
    return files
