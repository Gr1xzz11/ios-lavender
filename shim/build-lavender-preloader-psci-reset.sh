#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
IMAGE=${1:?usage: $0 IMAGE [OUTDIR] [STOCK_BOOT]}
OUT=${2:-out/lavender-preloader-psci-reset}
STOCK_BOOT=${3:-../backup/lavender-boot.img}
CC=${CC:-clang}; OBJCOPY=${OBJCOPY:-llvm-objcopy}; NM=${NM:-llvm-nm}; MKBOOTIMG=${MKBOOTIMG:-mkbootimg}
CFLAGS="--target=aarch64-none-elf -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
mkdir -p "$OUT"
for f in lavender_start.S lavender_preloader_psci_reset_shim.c lavender_preloader_psci_reset.c lavender_console.c fdt.c; do
	"$CC" $CFLAGS -I"$ROOT/shim" -c "$ROOT/shim/$f" -o "$OUT/${f%.*}.o"
done
"$CC" $CFLAGS -fuse-ld=lld -static -T "$ROOT/shim/lavender.ld" -Wl,--build-id=none -Wl,-N \
	"$OUT/lavender_start.o" "$OUT/lavender_preloader_psci_reset_shim.o" \
	"$OUT/lavender_preloader_psci_reset.o" "$OUT/lavender_console.o" "$OUT/fdt.o" \
	-o "$OUT/preloader-psci-reset.elf"
"$OBJCOPY" -O binary "$OUT/preloader-psci-reset.elf" "$OUT/Image"
size=$($NM -n "$OUT/preloader-psci-reset.elf" | awk '$3=="_end" {print strtonum("0x"$1)}')
truncate -s "$size" "$OUT/Image"
python3 "$ROOT/tools/make-lavender-diag-stocklike.py" "$OUT/Image" "$STOCK_BOOT" \
	"$OUT/kernel.gz-dtb" "$OUT/stock-ramdisk" "$OUT/cmdline"
"$MKBOOTIMG" --header_version 1 --kernel "$OUT/kernel.gz-dtb" --ramdisk "$OUT/stock-ramdisk" \
	--base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 \
	--pagesize 4096 --os_version 10.0.0 --os_patch_level 2021-08 \
	--cmdline "$(cat "$OUT/cmdline")" -o "$OUT/lavender-preloader-psci-reset-boot.img"
python3 "$ROOT/tools/preserve-lavender-bootv1-fields.py" "$OUT/lavender-preloader-psci-reset-boot.img" "$STOCK_BOOT"
python3 "$ROOT/tools/check-lavender-preloader-psci-reset.py" \
	"$OUT/lavender-preloader-psci-reset-boot.img" "$STOCK_BOOT" "$OUT/Image"
