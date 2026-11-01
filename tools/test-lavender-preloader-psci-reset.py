#!/usr/bin/env python3
"""Static regression checks for the DTB-only lavender pre-loader."""
from pathlib import Path

root = Path(__file__).parents[1]
source = (root / "shim/lavender_preloader_psci_reset.c").read_text()
shim = (root / "shim/lavender_preloader_psci_reset_shim.c").read_text()
build = (root / "shim/build-lavender-preloader-psci-reset.sh").read_text()
checker = (root / "tools/check-lavender-preloader-psci-reset.py").read_text()

assert "fdt_blob_size" in source
assert "fdt_chosen_u64" in source
assert "*end <= *start" in source
assert "UINT64_MAX - *start" in source
assert "PSCI_SYSTEM_RESET" in source
assert '"smc #0"' in source
assert "lavender_loader_boot" not in source + shim
assert "mkpayload.py" not in build
assert "kernel.gz-dtb" in build and "ramdisk" in build
assert "FDT_MAGIC" in checker and "linux,initrd-start" in source
assert "ramdisk_addr" not in source
print("lavender pre-loader PSCI-reset static test: PASS")
