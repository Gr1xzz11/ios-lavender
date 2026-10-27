#!/bin/bash
# Stock-like lavender diagnostic candidate: gzip raw Image, stock appended
# FDTs, and the exact stock ramdisk/cmdline. Do not treat as runnable.
set -euo pipefail
cd "$(dirname "$0")"
OUT=${OUT:-out/lavender-diag-stocklike}
STOCK_BOOT=${STOCK_BOOT:-../backup/lavender-boot.img}
BASE_OUT=out/lavender-diag-noramdisk
OUT="$BASE_OUT" ./build-lavender-diag-noramdisk.sh >/dev/null
mkdir -p "$OUT"
python3 ../tools/make-lavender-diag-stocklike.py "$BASE_OUT/Image" "$STOCK_BOOT" \
	"$OUT/kernel.gz-dtb" "$OUT/ramdisk" "$OUT/cmdline"
mkbootimg --header_version 1 --kernel "$OUT/kernel.gz-dtb" --ramdisk "$OUT/ramdisk" \
	--base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 \
	--pagesize 4096 --os_version 10.0.0 --os_patch_level 2021-08 \
	--cmdline "$(cat "$OUT/cmdline")" -o "$OUT/lavender-diag-stocklike-boot.img"
python3 ../tools/preserve-lavender-bootv1-fields.py \
	"$OUT/lavender-diag-stocklike-boot.img" "$STOCK_BOOT"
python3 ../tools/check-lavender-diag-stocklike.py \
	"$OUT/lavender-diag-stocklike-boot.img" "$STOCK_BOOT"
ls -l "$OUT/lavender-diag-stocklike-boot.img" "$OUT/kernel.gz-dtb" "$OUT/ramdisk"
