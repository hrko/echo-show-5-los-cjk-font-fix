"""Pinned, private ARMv7 CPython runtime; no target package manager required."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile

from fetch_assets import fetch_verified

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'build/python-runtime'
BASE = 'https://dl-cdn.alpinelinux.org/alpine/v3.23/main/armv7/'
ASSETS = {
    'python3-3.12.14-r0.apk': (BASE + 'python3-3.12.14-r0.apk',
        '0d1162d728d9f0f6e71447294139e1950d62a7a5f03ea78468bf6490cb82eb42'),
    'musl-1.2.5-r23.apk': (BASE + 'musl-1.2.5-r23.apk',
        '0f2f5029a9f401a4f10ca8c6ef03afe3aa4b521fc0ed44f1d6a2c6911eedc329'),
    'musl-1.2.5.tar.gz': ('https://musl.libc.org/releases/musl-1.2.5.tar.gz',
        'a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4'),
}
HASH_MODULES = ('_md5.', '_sha1.', '_sha2.', '_sha3.', '_blake2.')


def verify(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Runtime input SHA-256 mismatch: {path}')


def fetch_runtime():
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ASSETS.items():
        fetch_verified(url, CACHE / name, lambda path, h=expected: verify(path, h))


def elf_needed(data):
    """Audit ELF32 DT_NEEDED without executing a cross-architecture binary."""
    if data[:6] != b'\x7fELF\x01\x01' or data[18:20] != b'\x28\x00':
        raise ValueError('Runtime must contain little-endian ARM32 ELF')
    offset = struct.unpack_from('<I', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 46)
    sections = [struct.unpack_from('<10I', data, offset + i * size) for i in range(count)]
    result = []
    for section in sections:
        if section[1] != 6:  # SHT_DYNAMIC
            continue
        strings = sections[section[6]]
        for pos in range(section[4], section[4] + section[5], section[9]):
            tag, value = struct.unpack_from('<II', data, pos)
            if tag == 1:
                start = strings[4] + value
                result.append(data[start:data.index(b'\0', start)].decode('ascii'))
    return result


def runtime_payload():
    files = {}
    for name, (_, expected) in ASSETS.items():
        path = CACHE / name
        verify(path, expected)
        with tarfile.open(fileobj=io.BytesIO(path.read_bytes()), ignore_zeros=True) as archive:
            for entry in archive:
                n = entry.name
                if not entry.isfile():
                    continue
                target = None
                if name.startswith('python3-'):
                    if n in ('usr/bin/python3.12', 'usr/lib/libpython3.12.so.1.0'):
                        target = 'runtime/' + n
                    elif n.startswith('usr/lib/python3.12/'):
                        if n.endswith('.py') or n.endswith('/LICENSE.txt'):
                            target = 'runtime/' + n
                        elif n.startswith('usr/lib/python3.12/lib-dynload/') and n.rsplit('/', 1)[1].startswith(HASH_MODULES):
                            target = 'runtime/' + n
                elif name.endswith('.apk') and n == 'lib/ld-musl-armhf.so.1':
                    target = 'runtime/' + n
                elif n == 'musl-1.2.5/COPYRIGHT':
                    target = 'licenses/musl-COPYRIGHT.txt'
                if target:
                    files[target] = archive.extractfile(entry).read()
    # Materialize the libc symlink as regular bytes: recovery ZIP extraction
    # does not reliably preserve symbolic links.
    files['runtime/lib/libc.musl-armv7.so.1'] = files['runtime/lib/ld-musl-armhf.so.1']
    dependencies = {}
    for name, data in files.items():
        if data.startswith(b'\x7fELF'):
            dependencies[name] = elf_needed(data)
            if set(dependencies[name]) - {'libc.musl-armv7.so.1', 'libpython3.12.so.1.0'}:
                raise ValueError(f'Unbundled ELF dependency: {name}: {dependencies[name]}')
    files['licenses/Python-LICENSE.txt'] = files['runtime/usr/lib/python3.12/LICENSE.txt']
    report = {'python': '3.12.14', 'alpine': 'v3.23', 'arch': 'armv7',
              'packages': {n: {'url': u, 'sha256': h} for n, (u, h) in ASSETS.items()},
              'licenses': ['PSF-2.0 (including bundled notices)', 'MIT (musl COPYRIGHT)'],
              'elf_dependencies': dependencies,
              'files': {n: hashlib.sha256(d).hexdigest() for n, d in sorted(files.items())}}
    files['runtime/verification.json'] = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    return files


if __name__ == '__main__':
    fetch_runtime()
    files = runtime_payload()
    destination = CACHE / 'probe'
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f'Verified {len(files)} runtime files in {destination}')
