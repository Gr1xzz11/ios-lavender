#!/usr/bin/env python3
"""Create stock-like gzip+appended-DTB kernel and exact stock ramdisk."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import struct
import zlib
from pathlib import Path

FDT_MAGIC = b"\xd0\x0d\xfe\xed"
PAGE = 4096


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("stock_boot", type=Path)
    ap.add_argument("kernel_out", type=Path)
    ap.add_argument("ramdisk_out", type=Path)
    ap.add_argument("cmdline_out", type=Path)
    args = ap.parse_args()

    stock = args.stock_boot.read_bytes()
    h = struct.unpack_from("<10I", stock, 8)
    stock_kernel = stock[h[7]:h[7] + h[0]]
    stream = zlib.decompressobj(31)
    stream.decompress(stock_kernel)
    stream.flush()
    tail = stream.unused_data
    assert tail.startswith(FDT_MAGIC)
    first_size = struct.unpack_from(">I", tail, 4)[0]
    second = tail[first_size:]
    second_size = struct.unpack_from(">I", second, 4)[0]
    assert first_size + second_size == len(tail)

    image = args.image.read_bytes()
    assert image[0x38:0x40] == b"ARM\x64\0\0\0\0"
    assert struct.unpack_from("<Q", image, 0x10)[0] == len(image)
    compressed = gzip.compress(image, compresslevel=9, mtime=0)
    kernel = compressed + tail
    ramdisk_offset = h[7] + ((h[0] + PAGE - 1) // PAGE) * PAGE
    ramdisk = stock[ramdisk_offset:ramdisk_offset + h[2]]
    assert len(ramdisk) == h[2]
    cmdline = stock[64:1600].split(b"\0", 1)[0]
    args.kernel_out.write_bytes(kernel)
    args.ramdisk_out.write_bytes(ramdisk)
    args.cmdline_out.write_bytes(cmdline)
    print(f"gzip_kernel={len(compressed)} bytes; appended_dtbs={len(tail)} bytes")
    print(f"kernel_size={len(kernel)} sha256={hashlib.sha256(kernel).hexdigest()}")
    print(f"ramdisk_size={len(ramdisk)} sha256={hashlib.sha256(ramdisk).hexdigest()}")
    print(f"dtb1_size={first_size} dtb2_size={second_size}")


if __name__ == "__main__":
    main()
