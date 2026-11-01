#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
BASE=${BASE:-/tmp/lavender-xnu-boot-safe2}
OUT=${OUT:-$ROOT/research/lavender/.artifacts/lavender-handoff-probe-20261029-$(date +%H%M%S)}
STOCK_BOOT=${STOCK_BOOT:-$ROOT/backup/lavender-boot.img}
CC=${CC:-clang}; OBJCOPY=${OBJCOPY:-llvm-objcopy}; NM=${NM:-llvm-nm}; MKBOOTIMG=${MKBOOTIMG:-mkbootimg}
CFLAGS="--target=aarch64-none-elf -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
DEFS='-DLAVENDER_PMSG_SHIM -DLAVENDER_LOADER_NO_UART -DLAVENDER_HANDOFF_PROBE -DLAVENDER_BUILD_ID="B20261029_HANDOFF"'
mkdir -p "$OUT"
for f in lavender_start.S lavender_shim.c lavender_loader.c fdt.c lavender_pmsg.c; do
	"$CC" $CFLAGS $DEFS -I"$ROOT/shim" -c "$ROOT/shim/$f" -o "$OUT/${f%.*}.o"
done
"$CC" $CFLAGS -fuse-ld=lld -static -T "$ROOT/shim/lavender.ld" -Wl,--build-id=none -Wl,-N \
	"$OUT/lavender_start.o" "$OUT/lavender_shim.o" "$OUT/lavender_loader.o" \
	"$OUT/fdt.o" "$OUT/lavender_pmsg.o" -o "$OUT/lavender-handoff-probe.elf"
"$OBJCOPY" -O binary "$OUT/lavender-handoff-probe.elf" "$OUT/Image"
size=$($NM -n "$OUT/lavender-handoff-probe.elf" | awk '$3=="_end" {print strtonum("0x"$1)}')
truncate -s "$size" "$OUT/Image"
python3 "$ROOT/tools/make-lavender-diag-stocklike.py" "$OUT/Image" "$STOCK_BOOT" "$OUT/kernel.gz-dtb" "$OUT/stock-ramdisk" "$OUT/cmdline"
python3 "$ROOT/tools/make-lavender-loader-ramdisk.py" "$BASE/payload.bin" "$OUT/stock-ramdisk" "$OUT/ramdisk"
"$MKBOOTIMG" --header_version 1 --kernel "$OUT/kernel.gz-dtb" --ramdisk "$OUT/ramdisk" --base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 --pagesize 4096 --os_version 10.0.0 --os_patch_level 2021-08 --cmdline "$(cat "$OUT/cmdline")" -o "$OUT/lavender-handoff-probe.img"
python3 "$ROOT/tools/preserve-lavender-bootv1-fields.py" "$OUT/lavender-handoff-probe.img" "$STOCK_BOOT"
printf '%s\n' "$OUT/lavender-handoff-probe.img"
