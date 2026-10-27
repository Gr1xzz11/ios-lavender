#!/bin/sh
# Build lavender Image + XNU payload components only.
#
# Android v1 fields for a future wrapper must match backup/lavender-boot.img:
# page=4096, kernel_addr=0x8000, ramdisk_addr=0x1000000, tags_addr=0x100,
# no embedded DTB. A future mkbootimg invocation would use --header_version 1.
# This script intentionally does not create boot.img: ABL
# physical relocation and ramdisk placement are not verified yet.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
out=${3:-"$root/shim/out/lavender-xnu"}
kernel=${1:?usage: $0 KERNEL ADT [OUTDIR]}
adt=${2:?usage: $0 KERNEL ADT [OUTDIR]}
cc=${CC:-clang}
objcopy=${OBJCOPY:-llvm-objcopy}
nm=${NM:-llvm-nm}
cflags="--target=aarch64-none-elf -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
mkdir -p "$out"

for f in lavender_start.S lavender_shim.c lavender_console.c lavender_loader.c fdt.c; do
	"$cc" $cflags -I"$root/shim" -c "$root/shim/$f" -o "$out/${f%.*}.o"
done
"$cc" $cflags -fuse-ld=lld -static -T "$root/shim/lavender.ld" -Wl,--build-id=none \
	-Wl,-N \
	"$out/lavender_start.o" "$out/lavender_shim.o" "$out/lavender_console.o" \
	"$out/lavender_loader.o" "$out/fdt.o" -o "$out/lavender-shim.elf"
"$objcopy" -O binary "$out/lavender-shim.elf" "$out/Image"
image_size=$("$nm" -n "$out/lavender-shim.elf" | awk '$3=="_end" {print strtonum("0x"$1)}')
[ -n "$image_size" ] && truncate -s "$image_size" "$out/Image"

python3 "$root/tools/mkpayload.py" "$kernel" "$adt" "$out/payload.bin"
echo "Built Image and payload.bin. Run preflight-lavender-layout.py separately; Android boot header v1 wrapper is withheld until ABL placement is verified."
