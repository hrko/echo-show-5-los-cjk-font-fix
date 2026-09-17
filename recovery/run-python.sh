#!/sbin/sh
set -eu
ROOT=/tmp/jp-font-python
PATCH=/tmp/jp-font-patch
BB=/sbin/toybox
[ -x "$BB" ] || BB=/sbin/busybox
# Clear inherited Python/loader settings. musl's loader resolves only bundled
# dependencies; Python's home lives entirely in recovery's temporary RAM disk.
exec "$BB" env -i PYTHONHOME="$ROOT/usr" "$ROOT/lib/ld-musl-armhf.so.1" \
    --library-path "$ROOT/lib:$ROOT/usr/lib" "$ROOT/usr/bin/python3.12" \
    -s -S -B "$PATCH/font_patch.py" "$@"
