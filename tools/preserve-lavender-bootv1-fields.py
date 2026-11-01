#!/usr/bin/env python3
"""Preserve stock Android v1 metadata while retaining new payload sizes."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("stock", type=Path)
    args = ap.parse_args()
    image = bytearray(args.image.read_bytes())
    stock = args.stock.read_bytes()
    assert image[:8] == b"ANDROID!" and stock[:8] == b"ANDROID!"
    candidate = list(struct.unpack_from("<10I", image, 8))
    reference = struct.unpack_from("<10I", stock, 8)
    assert candidate[4] == reference[4] == 0
    # kernel_size and ramdisk_size belong to the replacement payload. Every
    # other v1 scalar is boot-chain metadata and must match stock exactly.
    for index in (1, 3, 4, 5, 6, 7, 8, 9):
        candidate[index] = reference[index]
    struct.pack_into("<10I", image, 8, *candidate)
    image[64:1600] = stock[64:1600]       # board + cmdline area
    image[1600:1632] = stock[1600:1632]   # v1 id
    image[1632:1648] = stock[1632:1648]   # v1 extension/header_size
    args.image.write_bytes(image)
    print(f"preserved stock v1 metadata; second_addr={candidate[5]:#x}")


if __name__ == "__main__":
    main()
