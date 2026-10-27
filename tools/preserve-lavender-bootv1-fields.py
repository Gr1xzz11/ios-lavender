#!/usr/bin/env python3
"""Preserve stock Android v1 address fields omitted by mkbootimg defaults."""
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
    candidate[5] = reference[5]
    struct.pack_into("<10I", image, 8, *candidate)
    args.image.write_bytes(image)
    print(f"preserved second_addr={candidate[5]:#x}")


if __name__ == "__main__":
    main()
