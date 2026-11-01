#!/usr/bin/env python3
"""Static checks for the lavender-only XNU shim path."""
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "shim"


def main():
    start = (SHIM / "lavender_start.S").read_text(encoding="utf-8")
    loader = (SHIM / "lavender_loader.c").read_text(encoding="utf-8")
    console = (SHIM / "lavender_console.c").read_text(encoding="utf-8")
    build = (SHIM / "build-lavender-xnu.sh").read_text(encoding="utf-8")
    noramdisk = (SHIM / "build-lavender-diag-noramdisk.sh").read_text(encoding="utf-8")
    dtb_build = (SHIM / "build-lavender-diag-dtb-noramdisk.sh").read_text(encoding="utf-8")
    stocklike_build = (SHIM / "build-lavender-diag-stocklike.sh").read_text(encoding="utf-8")

    assert '"ARM\\x64"' in start
    assert "msr\tspsel" in start and "shim_lavender_main" in start
    assert "FB_BASE" not in loader and "ufs" not in loader.lower()
    assert "GIC" not in start and "PSCI" not in start
    assert "UART_BASE" in console and "UART_SR_TX_READY" in console
    assert "--header_version 1" in build
    assert "--dtb" not in build
    assert "build.sh" not in build
    assert "lavender_loader.c" in build
    assert "lavender_console.c" in build
    loader = (SHIM / "lavender_loader.c").read_text(encoding="utf-8")
    assert "LAVENDER_LOADER_PSCI_RESET" in loader
    assert "lavender_loader_checkpoint" in loader
    assert "_head[]" in loader and "_end[]" in loader
    assert "range_intersects" in loader
    assert "ramdisk overlaps loader" in loader
    assert "source_ranges[segment_source_index[j]].start" in loader
    assert "ba->deviceTreeP = kernel_pa;" in loader
    assert "ba->deviceTreeP = kernel_pa - pa_delta" not in loader
    assert "DTB overlaps XNU managed RAM" not in loader
    assert "DTB overlaps loader" in loader
    stage1_build = (SHIM / "build-lavender-loader-stage1-reset.sh").read_text(encoding="utf-8")
    assert "LAVENDER_LOADER_STAGE1_RESET" in stage1_build
    stage2_build = (SHIM / "build-lavender-loader-stage2-reset.sh").read_text(encoding="utf-8")
    assert "LAVENDER_LOADER_STAGE2_RESET" in stage2_build
    final_build = (SHIM / "build-lavender-xnu-boot.sh").read_text(encoding="utf-8")
    assert "lavender_shim.c" in final_build
    assert "LAVENDER_LOADER_PSCI_RESET" not in final_build
    assert "lavender_loader_psci_reset_shim.c" not in final_build
    assert "LAVENDER_LOADER_NO_UART" in final_build
    assert "lavender_console.c" not in final_build
    assert "lavender_loader_diag_reset" in loader
    reset_build = (SHIM / "build-lavender-loader-psci-reset.sh").read_text(encoding="utf-8")
    reset_shim = (SHIM / "lavender_loader_psci_reset_shim.c").read_text(encoding="utf-8")
    reset_impl = (SHIM / "lavender_loader_psci_reset.c").read_text(encoding="utf-8")
    assert "-DLAVENDER_LOADER_PSCI_RESET" in reset_build
    assert "make-lavender-loader-ramdisk.py" in reset_build
    assert "PSCI_SYSTEM_RESET" in reset_impl and "smc #0" in reset_impl
    assert "LOAD ERROR" in reset_shim and "for (;;" in reset_shim
    assert "LAVENDER_LOADER_STAGE1_RESET" in reset_shim
    assert "LAVENDER_LOADER_STAGE1_RESET" in reset_impl and "LAVENDER_LOADER_STAGE2_RESET" in reset_impl
    assert "--header_version 1" in noramdisk
    assert "--ramdisk /dev/null" in noramdisk
    assert "check-lavender-bootv1-noramdisk.py" in noramdisk
    assert "--dtb" not in noramdisk
    assert "make-lavender-diag-dtb.py" in dtb_build
    assert "check-lavender-diag-dtb.py" in dtb_build
    assert "--ramdisk /dev/null" in dtb_build
    assert "make-lavender-diag-stocklike.py" in stocklike_build
    assert "check-lavender-diag-stocklike.py" in stocklike_build
    assert "--ramdisk \"$OUT/ramdisk\"" in stocklike_build
    assert "preserve-lavender-bootv1-fields.py" in stocklike_build
    print("lavender XNU shim static test: PASS")


if __name__ == "__main__":
    main()
