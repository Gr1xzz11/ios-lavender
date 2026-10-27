#!/usr/bin/env python3
"""Preflight the stock-like lavender diagnostic boot image."""
from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

PAGE = 4096
BOOT_LIMIT = 64 * 1024 * 1024
RAM_BASE = 0x80000000
RAM_END = 0x85600000
XNU_END = 0x85600000
FIXED = ((0x85600000, 0x85700000), (0x85700000, 0x85800000),
         (0x85800000, 0x88F00000), (0x8AC00000, 0x92A00000),
         (0x92A00000, 0x94800000), (0x94800000, 0x94A00000),
         (0x94A00000, 0x95000000), (0x9D400000, 0x9F7FF000),
         (0x9F8FF000, 0x9F900000), (0xA0000000, 0xA0400000))


def align(value: int) -> int:
    return (value + PAGE - 1) & ~(PAGE - 1)


def fdt(blob: bytes, offset: int) -> tuple[bytes, int]:
    assert blob[offset:offset + 4] == b"\xd0\x0d\xfe\xed"
    total = struct.unpack_from(">I", blob, offset + 4)[0]
    assert total >= 40 and offset + total <= len(blob)
    struct_off, strings_off = struct.unpack_from(">II", blob, offset + 8)
    strings_size, struct_size = struct.unpack_from(">II", blob, offset + 32)
    assert struct_off + struct_size <= total and strings_off + strings_size <= total
    return blob[offset:offset + total], offset + total


def stock_parts(stock: bytes) -> tuple[dict, bytes, bytes, bytes]:
    h = struct.unpack_from("<10I", stock, 8)
    k = stock[h[7]:h[7] + h[0]]
    rd_off = h[7] + align(h[0])
    rd = stock[rd_off:rd_off + h[2]]
    z = zlib.decompressobj(31)
    z.decompress(k); z.flush()
    return dict(values=h, cmdline=stock[64:1600].split(b"\0", 1)[0],
                ext=struct.unpack_from("<IQI", stock, 1632)), k, rd, z.unused_data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("boot", type=Path)
    ap.add_argument("stock", type=Path)
    ap.add_argument("--base", type=lambda x: int(x, 0), default=RAM_BASE)
    args = ap.parse_args()
    boot = args.boot.read_bytes(); stock = args.stock.read_bytes()
    sh, sk, srd, stail = stock_parts(stock)
    assert boot[:8] == b"ANDROID!" and len(boot) <= BOOT_LIMIT
    h = struct.unpack_from("<10I", boot, 8)
    ext = struct.unpack_from("<IQI", boot, 1632)
    assert h[1:2] == (0x8000,)
    assert h[9] == sh["values"][9]
    assert h[3] == 0x1000000 and h[6] == 0x100 and h[7] == PAGE and h[8] == 1
    assert h[2] == len(srd) and ext == sh["ext"] and boot[64:1600].split(b"\0", 1)[0] == sh["cmdline"]
    assert h[4] == 0 and ext[0] == 0 and ext[2] == 1648
    kernel = boot[PAGE:PAGE + h[0]]
    z = zlib.decompressobj(31); raw = z.decompress(kernel); z.flush()
    assert raw[0x38:0x40] == b"ARM\x64\0\0\0\0"
    assert struct.unpack_from("<Q", raw, 0x10)[0] == len(raw)
    assert z.unused_data == stail
    first, next_off = fdt(z.unused_data, 0)
    second, end_off = fdt(z.unused_data, next_off)
    assert end_off == len(z.unused_data)
    assert boot[PAGE + h[0]:PAGE + h[0] + 1]  # non-empty kernel
    rd_flash = PAGE + align(h[0])
    assert boot[rd_flash:rd_flash + h[2]] == srd
    load = args.base + h[1]; kernel_end = load + h[0]
    rd_start = args.base + h[3]; rd_end = rd_start + h[2]
    assert load >= RAM_BASE and kernel_end <= RAM_END
    assert kernel_end <= rd_start or rd_end <= load
    assert all(kernel_end <= lo or hi <= load for lo, hi in FIXED)
    assert all(rd_end <= lo or hi <= rd_start for lo, hi in FIXED)
    print(f"OK: gzip+2 stock FDTs+stock ramdisk; boot={len(boot)} bytes")
    print(f"SHA256 boot={hashlib.sha256(boot).hexdigest()}")
    print(f"SHA256 ramdisk={hashlib.sha256(srd).hexdigest()}")
    print(f"SHA256 dtb1={hashlib.sha256(first).hexdigest()} SHA256 dtb2={hashlib.sha256(second).hexdigest()}")
    print(f"hypothetical shim={load:#x}..{kernel_end:#x}; ramdisk={rd_start:#x}..{rd_end:#x}")
    print(f"BLOCKED: ramdisk lies in XNU-managed window {rd_start:#x}..{rd_end:#x} < {XNU_END:#x}")


if __name__ == "__main__":
    main()
