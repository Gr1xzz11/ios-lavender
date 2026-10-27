#!/usr/bin/env python3
"""Regression tests for the zero-ramdisk v1 structural checker."""
import importlib.util
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check", ROOT / "tools/check-lavender-bootv1-noramdisk.py"
)
CHECK = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECK)


def image(ramdisk_size=0, ramdisk_addr=0):
    page = 4096
    kernel = bytearray(0x100)
    kernel[0x08:0x10] = (0).to_bytes(8, "little")
    kernel[0x10:0x18] = len(kernel).to_bytes(8, "little")
    kernel[0x38:0x40] = b"ARM\x64\0\0\0\0"
    header = bytearray(page)
    header[:8] = b"ANDROID!"
    struct.pack_into("<10I", header, 8, len(kernel), 0x8000,
                     ramdisk_size, ramdisk_addr, 0, 0, 0x100, page, 1, 0)
    struct.pack_into("<IQI", header, 1632, 0, 0, 1648)
    return bytes(header) + bytes(kernel) + bytes(page - len(kernel))


def main():
    with tempfile.TemporaryDirectory() as td:
        good = Path(td) / "good.img"
        good.write_bytes(image())
        result = CHECK.validate(good)
        assert result["ramdisk_size"] == 0

        for name, blob in (("size.img", image(1, 0)),
                           ("addr.img", image(0, 0x1000000))):
            path = Path(td) / name
            path.write_bytes(blob)
            try:
                CHECK.validate(path)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"accepted invalid {name}")
    print("lavender boot v1 zero-ramdisk tests: PASS")


if __name__ == "__main__":
    main()
