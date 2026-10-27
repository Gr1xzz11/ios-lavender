#!/bin/bash
# Build an experimental Android v1 candidate with ramdisk_size=0.
# This is intentionally separate from build-lavender-diag.sh.  It is a
# structural artifact only: AOSP specifies a non-empty v1 ramdisk, and the
# closed lavender ABL's acceptance and DTB handoff are not established.
set -euo pipefail
cd "$(dirname "$0")"
CC=${CC:-clang}
OBJCOPY=${OBJCOPY:-llvm-objcopy}
NM=${NM:-llvm-nm}
MKBOOTIMG=${MKBOOTIMG:-mkbootimg}
OUT=${OUT:-out/lavender-diag-noramdisk}
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
TARGET_FLAGS=()
if [ "${CC##*/}" = clang ]; then
	TARGET_FLAGS+=(--target=aarch64-none-elf -fuse-ld=lld)
fi
mkdir -p "$OUT"

"$CC" "${TARGET_FLAGS[@]}" $CFLAGS -c diag_start.S -o "$OUT/diag_start.o"
"$CC" "${TARGET_FLAGS[@]}" $CFLAGS -c diag.c -o "$OUT/diag.o"
"$CC" "${TARGET_FLAGS[@]}" $CFLAGS -static -T diag.ld -Wl,--build-id=none -Wl,-N \
	"$OUT/diag_start.o" "$OUT/diag.o" -o "$OUT/diag.elf"
"$OBJCOPY" -O binary "$OUT/diag.elf" "$OUT/Image"
size=$($NM "$OUT/diag.elf" | awk '$3=="_end"{print "0x"$1}' | xargs printf '%d')
truncate -s "$size" "$OUT/Image"

# /dev/null is deliberate: AOSP mkbootimg emits ramdisk_size=0 and
# ramdisk_addr=0 for an empty input.  No DTB is supplied because v1 has no DTB
# field; the eventual ABL handoff remains an explicit blocker.
"$MKBOOTIMG" --header_version 1 --kernel "$OUT/Image" --ramdisk /dev/null \
	--base 0 --kernel_offset 0x8000 --tags_offset 0x100 --pagesize 4096 \
	--os_version 12.0.0 --os_patch_level 2022-01 \
	--cmdline "console=ttyMSM0,115200,n8 earlycon=msm_serial_dm,0xc170000" \
	-o "$OUT/lavender-diag-boot-noramdisk.img"
python3 ../tools/check-lavender-bootv1-noramdisk.py \
	"$OUT/lavender-diag-boot-noramdisk.img" --stock ../backup/lavender-boot.img
ls -l "$OUT/Image" "$OUT/lavender-diag-boot-noramdisk.img"
