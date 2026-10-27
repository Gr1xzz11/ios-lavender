#!/usr/bin/env python3
"""Pure arithmetic regressions for the lavender first-launch layout."""
from pathlib import Path

LOW = 0x80000000
LOW_END = 0x85600000
KERNEL_START = 0x81004000
KERNEL_END = 0x820AC000
ADT_END = 0x820ADE00
BOOT_ARGS = 0x820B0000
TOP = 0x820B4000
STOCK_RAMDISK_HYPOTHESIS = 0x81000000


def overlaps(start, end, other_start, other_end):
    return start < other_end and other_start < end


def main():
    assert LOW <= KERNEL_START < KERNEL_END <= ADT_END <= BOOT_ARGS < TOP <= LOW_END
    assert overlaps(STOCK_RAMDISK_HYPOTHESIS, STOCK_RAMDISK_HYPOTHESIS + 0x1000,
                    LOW, LOW_END)
    # The loader must continue to reject a ramdisk that falls in the managed
    # interval; removing this guard would make the stock-address hypothesis
    # overwrite the destination while copying the payload.
    loader = Path("shim/loader.c").read_text(encoding="utf-8")
    assert "ramdisk overlaps kernel memory" in loader
    # The regular sweet build is not a lavender build: it embeds a sweet DTB,
    # uses Android v2 and links sweet-only framebuffer/UFS sources.
    build = Path("shim/build.sh").read_text(encoding="utf-8")
    assert "--header_version 2" in build and "../dtb/boot_unpacked/dtb" in build
    assert "console.c" in build and "ufs.c" in build
    print("lavender layout conflict test: PASS (ABL placement remains required)")


if __name__ == "__main__":
    main()
