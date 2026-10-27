#!/usr/bin/env python3
"""Validate a lavender v1 raw-Image plus stock appended-DTB candidate."""
from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

FDT_MAGIC = b"\xd0\x0d\xfe\xed"
PAGE = 4096
BOOT_LIMIT = 64 * 1024 * 1024
RAM_BASE = 0x80000000
RAM_END = 0x85600000


def stock_tail(stock_kernel: bytes) -> bytes:
    stream = zlib.decompressobj(31)
    stream.decompress(stock_kernel)
    stream.flush()
    return stream.unused_data


def fdt(blob: bytes, offset: int) -> bytes:
    assert blob[offset:offset + 4] == FDT_MAGIC
    total = struct.unpack_from(">I", blob, offset + 4)[0]
    assert total >= 40 and offset + total <= len(blob)
    off_struct, off_strings = struct.unpack_from(">II", blob, offset + 8)
    size_strings, size_struct = struct.unpack_from(">II", blob, offset + 32)
    assert off_struct + size_struct <= total
    assert off_strings + size_strings <= total
    return blob[offset:offset + total]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("boot", type=Path)
    ap.add_argument("stock_boot", type=Path)
    ap.add_argument("--ram-base", type=lambda x: int(x, 0), default=0x80000000)
    args = ap.parse_args()
    boot = args.boot.read_bytes()
    stock_boot = args.stock_boot.read_bytes()
    stock_values = struct.unpack_from("<10I", stock_boot, 8)
    stock_kernel = stock_boot[stock_values[7]:stock_values[7] + stock_values[0]]
    assert boot[:8] == b"ANDROID!" and len(boot) <= BOOT_LIMIT
    h = struct.unpack_from("<10I", boot, 8)
    recovery_size, recovery_offset, header_size = struct.unpack_from("<IQI", boot, 1632)
    assert (h[7], h[8], h[1], h[6], h[2], h[3], h[4], recovery_size, header_size) == (
        PAGE, 1, 0x8000, 0x100, 0, 0, 0, 0, 1648)
    kernel = boot[PAGE:PAGE + h[0]]
    image_size = struct.unpack_from("<Q", kernel, 0x10)[0]
    assert kernel[0x38:0x40] == b"ARM\x64\0\0\0\0"
    assert image_size > 0x40 and image_size <= len(kernel)
    appended = kernel[image_size:]
    assert appended == stock_tail(stock_kernel), "appended DTB bytes differ from stock"
    first = fdt(appended, 0)
    second = fdt(appended, len(first))
    assert len(first) + len(second) == len(appended)
    load = args.ram_base + h[1]
    end = load + len(kernel)
    assert load >= RAM_BASE and end <= RAM_END
    assert end < 0x85700000
    print(f"OK: raw Image + 2 stock FDTs; kernel={len(kernel)} bytes; "
          f"dtb1={len(first)} bytes; dtb2={len(second)} bytes")
    print(f"SHA256 boot={hashlib.sha256(boot).hexdigest()}")
    print(f"SHA256 dtb1={hashlib.sha256(first).hexdigest()}")
    print(f"SHA256 dtb2={hashlib.sha256(second).hexdigest()}")
    print(f"hypothetical load={load:#x}..{end:#x}; ABL base remains unconfirmed")


if __name__ == "__main__":
    main()
