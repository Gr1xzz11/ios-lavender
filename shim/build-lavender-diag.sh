#!/bin/bash
# Build the non-destructive lavender diagnostic image.
# The v1 boot header intentionally has no embedded DTB: lavender's ABL passes
# its live FDT in x0, unlike the sweet v2 path which embeds a synthetic DTB.
set -euo pipefail
cd "$(dirname "$0")"
CC=${CC:-aarch64-linux-gnu-gcc}
OBJCOPY=${OBJCOPY:-aarch64-linux-gnu-objcopy}
NM=${NM:-aarch64-linux-gnu-nm}
OUT=${OUT:-out/lavender-diag}
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

(cd "$OUT" && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
mkbootimg --header_version 1 --kernel "$OUT/Image" --ramdisk "$OUT/ramdisk.bin" \
	--base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
	--tags_offset 0x100 --pagesize 4096 --os_version 12.0.0 \
	--os_patch_level 2022-01 \
	--cmdline "console=ttyMSM0,115200,n8 earlycon=msm_serial_dm,0xc170000" \
	-o "$OUT/lavender-diag-boot.img"
python3 ../tools/check-lavender-diag.py "$OUT/lavender-diag-boot.img" "$OUT/Image"
python3 ../tools/preflight-lavender-diag.py ../backup/lavender-boot.img \
	"$OUT/lavender-diag-boot.img" "$OUT/diag.elf" --nm "$NM"
ls -l "$OUT/Image" "$OUT/lavender-diag-boot.img"
