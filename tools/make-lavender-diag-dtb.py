#!/usr/bin/env python3
"""Append the exact two FDTs from stock lavender to a raw ARM64 Image."""
from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def stock_tail(stock_kernel: bytes) -> bytes:
    stream = zlib.decompressobj(31)
    stream.decompress(stock_kernel)
    stream.flush()
    tail = stream.unused_data
    assert tail.startswith(FDT_MAGIC), "stock kernel has no appended FDT at gzip end"
    return tail


def split_two_fdt(tail: bytes) -> tuple[bytes, bytes]:
    first_size = struct.unpack_from(">I", tail, 4)[0]
    assert first_size >= 40 and first_size <= len(tail)
    second = tail[first_size:]
    assert second.startswith(FDT_MAGIC)
    second_size = struct.unpack_from(">I", second, 4)[0]
    assert second_size >= 40 and first_size + second_size == len(tail)
    return tail[:first_size], second[:second_size]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("stock_boot", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    image = args.image.read_bytes()
    stock = args.stock_boot.read_bytes()
    values = struct.unpack_from("<10I", stock, 8)
    stock_kernel = stock[values[7]:values[7] + values[0]]
    first, second = split_two_fdt(stock_tail(stock_kernel))
    assert image[0x38:0x40] == b"ARM\x64\0\0\0\0"
    image_size = struct.unpack_from("<Q", image, 0x10)[0]
    assert image_size == len(image), "input must be the unappended raw Image"
    combined = image + first + second
    args.output.write_bytes(combined)
    print("appended FDTs:")
    for index, blob in enumerate((first, second), 1):
        print(f"  dtb{index}: size={len(blob)} sha256={hashlib.sha256(blob).hexdigest()}")
    print(f"  combined kernel: {len(combined)} bytes")


if __name__ == "__main__":
    main()
