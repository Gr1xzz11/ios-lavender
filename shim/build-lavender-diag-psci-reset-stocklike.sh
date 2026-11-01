#!/bin/bash
# Build the separate lavender PSCI SYSTEM_RESET diagnostic candidate.
set -euo pipefail
cd "$(dirname "$0")"
CC=${CC:-clang}
OBJCOPY=${OBJCOPY:-llvm-objcopy}
NM=${NM:-llvm-nm}
MKBOOTIMG=${MKBOOTIMG:-mkbootimg}
OUT=${OUT:-out/lavender-diag-psci-reset-stocklike}
STOCK_BOOT=${STOCK_BOOT:-../backup/lavender-boot.img}
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
TARGET_FLAGS=()
if [ "${CC##*/}" = clang ]; then
	TARGET_FLAGS+=(--target=aarch64-none-elf -fuse-ld=lld)
fi
mkdir -p "$OUT"

"$CC" "${TARGET_FLAGS[@]}" $CFLAGS -c lavender_reset_start.S -o "$OUT/reset_start.o"
"$CC" "${TARGET_FLAGS[@]}" $CFLAGS -c lavender_reset.c -o "$OUT/reset.o"
"$CC" "${TARGET_FLAGS[@]}" $CFLAGS -static -T diag.ld -Wl,--build-id=none -Wl,-N \
	"$OUT/reset_start.o" "$OUT/reset.o" -o "$OUT/reset.elf"
"$OBJCOPY" -O binary "$OUT/reset.elf" "$OUT/Image"
size=$($NM "$OUT/reset.elf" | awk '$3=="_end"{print "0x"$1}' | xargs printf '%d')
truncate -s "$size" "$OUT/Image"

python3 ../tools/make-lavender-diag-stocklike.py "$OUT/Image" "$STOCK_BOOT" \
	"$OUT/kernel.gz-dtb" "$OUT/ramdisk" "$OUT/cmdline"
"$MKBOOTIMG" --header_version 1 --kernel "$OUT/kernel.gz-dtb" --ramdisk "$OUT/ramdisk" \
	--base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 \
	--pagesize 4096 --os_version 10.0.0 --os_patch_level 2021-08 \
	--cmdline "$(cat "$OUT/cmdline")" -o "$OUT/lavender-diag-psci-reset-stocklike-boot.img"
python3 ../tools/preserve-lavender-bootv1-fields.py \
	"$OUT/lavender-diag-psci-reset-stocklike-boot.img" "$STOCK_BOOT"
python3 ../tools/check-lavender-diag-stocklike.py \
	"$OUT/lavender-diag-psci-reset-stocklike-boot.img" "$STOCK_BOOT"
ls -l "$OUT/Image" "$OUT/lavender-diag-psci-reset-stocklike-boot.img"
