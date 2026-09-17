"""Recovery entry point. XML ownership logic is shared with the host builder."""
import os
import stat
import sys

from font_slots import OWNERS, SLOTS, compose_xml, digest, split_xml


def regular(path):
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError('Not a regular file: ' + path)


def read(path):
    regular(path)
    with open(path, 'rb') as stream:
        return stream.read()


def file_hash(path):
    import hashlib
    regular(path)
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify(path, expected):
    if file_hash(path) != expected:
        raise ValueError('Unexpected hash: ' + path)


def stageable(path):
    if os.path.lexists(path):
        regular(path)


def write(path, data):
    stageable(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags, 0o600), 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def prepare(source, payload, work):
    if read(payload + '/format') != b'1\n':
        raise ValueError('Unsupported patch format')
    if os.path.lexists(work) and not stat.S_ISDIR(os.lstat(work).st_mode):
        raise ValueError('Unsafe recovery workspace')
    os.makedirs(work, mode=0o700, exist_ok=True)
    # Invalidate any previous successful preparation before checking this input.
    write(work + '/output.sha256', b'')
    original = read(source)
    skeleton, slots = split_xml(original)
    if digest(skeleton) != read(payload + '/skeleton.sha256').decode().strip():
        raise ValueError('Unexpected shared XML structure')
    if compose_xml(skeleton, slots) != original:
        raise ValueError('XML roundtrip changed bytes')
    rows = [line.split() for line in read(payload + '/slots.txt').decode().splitlines()]
    keys = [row[0] for row in rows if len(row) == 4]
    if len(keys) != len(rows) or len(set(keys)) != len(keys) or tuple(keys) not in OWNERS.values():
        raise ValueError('Invalid owned slot manifest')
    for key, stock, patched, desired in rows:
        if key not in SLOTS or desired not in (stock, patched):
            raise ValueError('Invalid desired slot: ' + key)
        if digest(slots[key]) not in (stock, patched):
            raise ValueError('Unexpected owned font family: ' + key)
        fragment = read(payload + '/' + key)
        if digest(fragment) != desired:
            raise ValueError('Unexpected payload hash: ' + key)
        slots[key] = fragment
    output = compose_xml(skeleton, slots)
    for removed in read(payload + '/removed.txt').splitlines():
        if not removed or removed in output:
            raise ValueError('Remaining reference to removed font: ' + removed.decode())
    write(work + '/fonts.xml', output)
    write(work + '/input.sha256', (digest(original) + '\n').encode())
    write(work + '/output.sha256', (digest(output) + '\n').encode())


def stage(source, payload, work):
    verify(source, read(work + '/input.sha256').decode().strip())
    expected = read(work + '/output.sha256').decode().strip()
    data = read(work + '/fonts.xml')
    if digest(data) != expected:
        raise ValueError('Prepared XML changed')
    write(source + '.jpfont-new', data)
    verify(source + '.jpfont-new', expected)


def check(mode, *args):
    if mode == 'ready':
        if digest(b'abc') != 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad':
            raise ValueError('SHA-256 self-test failed')
    elif mode == 'absent':
        if os.path.lexists(args[0]):
            raise ValueError('File still exists: ' + args[0])
    elif mode == 'stageable':
        stageable(args[0])
    elif mode == 'unreferenced':
        if args[1].encode() in read(args[0]):
            raise ValueError('Font is still referenced: ' + args[1])
    elif mode in ('hash', 'optional'):
        if mode == 'optional' and not os.path.lexists(args[0]):
            return
        if file_hash(args[0]) not in args[1:]:
            raise ValueError('Unexpected SHA-256: ' + args[0])
    else:
        raise ValueError('Unknown check: ' + mode)


if __name__ == '__main__':
    try:
        action, *args = sys.argv[1:]
        if action == 'check':
            check(*args)
        elif action == 'prepare':
            prepare(*args)
        elif action == 'stage':
            stage(*args)
        else:
            raise ValueError('Unknown action: ' + action)
    except (OSError, ValueError, UnicodeError) as error:
        print('Font patch: ' + str(error), file=sys.stderr)
        sys.exit(1)
