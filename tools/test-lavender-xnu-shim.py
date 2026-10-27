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
    print("lavender XNU shim static test: PASS")


if __name__ == "__main__":
    main()
