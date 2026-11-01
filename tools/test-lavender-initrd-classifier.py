#!/usr/bin/env python3
"""Static checks for the no-UART initrd-placement classifier."""
from pathlib import Path

root = Path(__file__).parents[1]
src = (root / "shim/lavender_preloader_psci_reset.c").read_text()
build = (root / "shim/build-lavender-initrd-classifier.sh").read_text()
check = (root / "tools/check-lavender-initrd-classifier.py").read_text()

assert "linux,initrd-start" in src and "linux,initrd-end" in src
assert "cntfrq_el0" in src and "cntpct_el0" in src
assert "LAVENDER_PRELOADER_CLASSIFIER" in src
assert "XNU_WINDOW_START" in src and "XNU_WINDOW_END" in src
assert "PSCI_SYSTEM_RESET" in src and '"smc #0"' in src
assert "lavender_loader_boot" not in src
assert "lavender_console.c" not in build
assert "--ramdisk \"$OUT/stock-ramdisk\"" in build
assert "make-lavender-diag-stocklike.py" in build
assert "XNU_WINDOW_START" in src and "XNU_WINDOW_END" in src
print("lavender initrd classifier static test: PASS")
