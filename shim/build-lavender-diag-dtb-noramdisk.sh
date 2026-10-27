#!/bin/bash
# Build raw ARM64 Image + the exact two stock lavender appended FDTs.
# ramdisk_size remains zero; this is an experimental, non-runnable claim.
set -euo pipefail
cd "$(dirname "$0")"
OUT=${OUT:-out/lavender-diag-dtb-noramdisk}
STOCK_BOOT=${STOCK_BOOT:-../backup/lavender-boot.img}
BASE_OUT=out/lavender-diag-noramdisk
mkdir -p "$OUT"
BASE_OUT="$BASE_OUT" OUT="$BASE_OUT" ./build-lavender-diag-noramdisk.sh >/dev/null
python3 ../tools/make-lavender-diag-dtb.py "$BASE_OUT/Image" "$STOCK_BOOT" "$OUT/Image-with-dtb"
mkbootimg --header_version 1 --kernel "$OUT/Image-with-dtb" --ramdisk /dev/null \
	--base 0 --kernel_offset 0x8000 --tags_offset 0x100 --pagesize 4096 \
	--os_version 12.0.0 --os_patch_level 2022-01 \
	--cmdline "console=ttyMSM0,115200,n8 earlycon=msm_serial_dm,0xc170000" \
	-o "$OUT/lavender-diag-dtb-boot-noramdisk.img"
python3 ../tools/check-lavender-diag-dtb.py \
	"$OUT/lavender-diag-dtb-boot-noramdisk.img" "$STOCK_BOOT"
ls -l "$OUT/Image-with-dtb" "$OUT/lavender-diag-dtb-boot-noramdisk.img"
