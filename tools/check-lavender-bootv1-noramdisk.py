#!/usr/bin/env python3
"""Validate an experimental lavender Android boot-header v1 image.

This checker deliberately distinguishes a structurally valid container from a
bootloader-compatible image.  AOSP documents the v1 ramdisk as required, so a
zero-ramdisk image is experimental and must not be treated as runnable.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path


BOOT_HEADER_SIZE = 1648
BOOT_PARTITION_SIZE = 64 * 1024 * 1024
IMAGE_MAGIC = b"ARM\x64\0\0\0\0"


def align(value: int, page: int) -> int:
    return (value + page - 1) & ~(page - 1)


def parse(path: Path) -> tuple[bytes, dict[str, int]]:
    blob = path.read_bytes()
    if len(blob) < 4096 or blob[:8] != b"ANDROID!":
        raise AssertionError(f"{path}: invalid Android boot image")
    values = struct.unpack_from("<10I", blob, 8)
    recovery_size, recovery_offset, header_size = struct.unpack_from(
        "<IQI", blob, 1632
    )
    header = dict(
        kernel_size=values[0], kernel_addr=values[1], ramdisk_size=values[2],
        ramdisk_addr=values[3], second_size=values[4], second_addr=values[5],
        tags_addr=values[6], page_size=values[7], version=values[8],
        recovery_dtbo_size=recovery_size, recovery_dtbo_offset=recovery_offset,
        header_size=header_size,
    )
    return blob, header


def validate(path: Path, stock: Path | None = None) -> dict[str, int | str]:
    blob, h = parse(path)
    assert h["version"] == 1, f"expected v1, got v{h['version']}"
    assert h["page_size"] == 4096, f"unexpected page size {h['page_size']:#x}"
    assert h["header_size"] == BOOT_HEADER_SIZE
    assert h["kernel_addr"] == 0x8000
    assert h["tags_addr"] == 0x100
    assert h["ramdisk_size"] == 0, "image is not a zero-ramdisk image"
    # AOSP mkbootimg intentionally clears this address when the file is empty.
    assert h["ramdisk_addr"] == 0, (
        "zero ramdisk must have ramdisk_addr=0 as emitted by AOSP mkbootimg"
    )
    assert h["second_size"] == 0
    assert h["recovery_dtbo_size"] == 0
    kernel_off = h["page_size"]
    kernel_end = kernel_off + h["kernel_size"]
    expected_end = align(kernel_end, h["page_size"])
    assert len(blob) == expected_end, (
        f"unexpected trailing data: {len(blob):#x} != {expected_end:#x}"
    )
    assert len(blob) <= BOOT_PARTITION_SIZE
    image = blob[kernel_off:kernel_end]
    assert image[:0x40][0x38:0x40] == IMAGE_MAGIC
    assert struct.unpack_from("<Q", image, 0x10)[0] == len(image)
    assert struct.unpack_from("<Q", image, 0x08)[0] == 0
    # The ARM64 Image flags are informational here; do not infer an ABL base.
    assert len(image) >= 0x40

    if stock is not None:
        _, s = parse(stock)
        for key in ("kernel_addr", "tags_addr", "page_size", "version",
                    "header_size", "recovery_dtbo_size"):
            assert h[key] == s[key], f"stock mismatch {key}: {h[key]:#x} != {s[key]:#x}"

    return {
        "kernel_size": h["kernel_size"],
        "image_size": len(blob),
        "kernel_addr": h["kernel_addr"],
        "ramdisk_size": h["ramdisk_size"],
        "ramdisk_addr": h["ramdisk_addr"],
        "status": "BLOCKED: v1/AOSP requires a non-empty ramdisk and does not encode DTB handoff",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--stock", type=Path)
    args = ap.parse_args()
    result = validate(args.image, args.stock)
    print(
        "OK: structural Android v1 zero-ramdisk candidate; "
        f"kernel={result['kernel_size']} bytes, image={result['image_size']} bytes, "
        f"kernel_addr={result['kernel_addr']:#x}, ramdisk_addr={result['ramdisk_addr']:#x}"
    )
    print(result["status"])


if __name__ == "__main__":
    main()
