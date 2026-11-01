#!/usr/bin/env python3
"""Decode a bounded raw lavender ramoops PMSG zone."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

ZONE_SIZE = 0x200000
HEADER_SIZE = 12
CAPACITY = ZONE_SIZE - HEADER_SIZE
SIGNATURE = 0x43474244

def decode(raw: bytes) -> bytes:
    if len(raw) != ZONE_SIZE:
        raise ValueError(f"expected {ZONE_SIZE:#x} bytes, got {len(raw):#x}")
    sig, start, size = struct.unpack_from("<III", raw)
    if sig != SIGNATURE:
        raise ValueError(f"bad signature {sig:#x}, expected {SIGNATURE:#x}")
    if start >= CAPACITY or size > CAPACITY:
        raise ValueError(f"invalid ring indices start={start:#x} size={size:#x}")
    if not size:
        return b""
    data = raw[HEADER_SIZE:]
    end = start + size
    if end <= CAPACITY:
        return data[start:end]
    split = CAPACITY - start
    return data[start:] + data[: size - split]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", type=Path)
    args = ap.parse_args()
    payload = decode(args.raw.read_bytes())
    print(f"payload_size={len(payload)}")
    print(payload.decode("ascii", errors="replace"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
