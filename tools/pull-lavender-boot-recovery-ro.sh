#!/usr/bin/env bash
# Pull lavender boot from an already-running recovery, read-only.
# This script never reboots, remounts, writes a device node, or uses adb push.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-/tmp/lavender-boot-from-recovery.img}
REFERENCE=${2:-$ROOT/backup/lavender-boot.img}

if [ -e "$OUT" ]; then
    echo "refusing to overwrite existing output: $OUT" >&2
    exit 2
fi

devices=$(adb devices -l)
printf '%s\n' "$devices"
count=$(printf '%s\n' "$devices" | awk '$2 == "device" || $2 == "recovery" { n++ } END { print n + 0 }')
if [ "$count" -ne 1 ]; then
    echo "expected exactly one ready recovery ADB device, found $count" >&2
    exit 3
fi

adb shell true

boot_path=$(adb shell 'for p in /dev/block/by-name/boot /dev/block/bootdevice/by-name/boot /dev/block/platform/*/by-name/boot; do if [ -e "$p" ] && [ -r "$p" ]; then printf "%s\\n" "$p"; exit 0; fi; done; exit 1' | tr -d '\r' | sed -n '1p')
if [ -z "$boot_path" ]; then
    echo "no readable boot block device found" >&2
    exit 4
fi
printf 'boot path: %s\n' "$boot_path"

resolved=$(adb shell "readlink -f '$boot_path'" | tr -d '\r' | sed -n '1p')
size=$(adb shell "blockdev --getsize64 '$boot_path'" | tr -d '\r' | sed -n '1p')
case "$size" in
    ''|*[!0-9]*) echo "invalid boot size: $size" >&2; exit 5 ;;
esac
printf 'resolved: %s\nsize: %s bytes\n' "$resolved" "$size"

adb exec-out dd "if=$boot_path" bs=4M status=none > "$OUT"
actual=$(wc -c < "$OUT")
if [ "$actual" -ne "$size" ]; then
    echo "short read: expected $size bytes, got $actual" >&2
    exit 6
fi

sha256sum "$OUT"
if [ -f "$REFERENCE" ]; then
    printf 'reference: '
    sha256sum "$REFERENCE"
    if cmp -s "$OUT" "$REFERENCE"; then
        echo 'comparison: MATCH'
    else
        echo 'comparison: DIFFERENT'
    fi
fi
printf 'saved local copy: %s\n' "$OUT"
