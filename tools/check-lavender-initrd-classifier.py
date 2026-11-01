#!/usr/bin/env python3
"""Validate the no-UART initrd-placement classifier image."""
from pathlib import Path
import argparse, hashlib, struct, zlib

PAGE = 4096
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
XNU_WINDOW_START = 0x80000000
XNU_WINDOW_END = 0x85600000
ap = argparse.ArgumentParser()
ap.add_argument("boot", type=Path)
ap.add_argument("stock", type=Path)
ap.add_argument("image", type=Path)
a = ap.parse_args()
boot, stock, image = a.boot.read_bytes(), a.stock.read_bytes(), a.image.read_bytes()
bh = struct.unpack_from("<10I", boot, 8)
sh = struct.unpack_from("<10I", stock, 8)
assert boot[:8] == stock[:8] == b"ANDROID!" and bh[7] == PAGE and bh[8] == 1
assert len(boot) <= 64 * 1024 * 1024
for i in (1, 3, 4, 5, 6, 7, 8, 9):
    assert bh[i] == sh[i]
assert boot[64:1600] == stock[64:1600]
assert boot[1600:1648] == stock[1600:1648]

def unpack(blob):
    h = struct.unpack_from("<10I", blob, 8)
    k = blob[h[7]:h[7] + h[0]]
    z = zlib.decompressobj(31)
    raw = z.decompress(k)
    z.flush()
    return h, raw, z.unused_data

_, _, stock_tail = unpack(stock)
_, raw, tail = unpack(boot)
assert raw[0x38:0x40] == b"ARM\x64\0\0\0\0"
assert struct.unpack_from("<Q", raw, 0x10)[0] == len(raw)
assert tail == stock_tail and tail.startswith(FDT_MAGIC)
first = struct.unpack_from(">I", tail, 4)[0]
second = struct.unpack_from(">I", tail[first:], 4)[0]
assert first > 0 and first + second == len(tail)
stock_rd_off = PAGE + ((sh[0] + PAGE - 1) // PAGE) * PAGE
boot_rd_off = PAGE + ((bh[0] + PAGE - 1) // PAGE) * PAGE
stock_rd = stock[stock_rd_off:stock_rd_off + sh[2]]
assert boot[boot_rd_off:boot_rd_off + bh[2]] == stock_rd
assert image[0x38:0x40] == b"ARM\x64\0\0\0\0"
assert struct.unpack_from("<Q", image, 0x10)[0] == len(image)
print(f"boot_sha256={hashlib.sha256(boot).hexdigest()}")
print(f"boot_size={len(boot)} kernel_size={bh[0]} ramdisk_size={bh[2]}")
print(f"classifier_image={len(image)} bytes; stock_ramdisk_sha256={hashlib.sha256(stock_rd).hexdigest()}")
print(f"dtb_tail_sha256={hashlib.sha256(tail).hexdigest()}")
print("runtime: overlap => 2s generic-timer delay; disjoint => immediate PSCI")
print("PASS: v1/header/gzip/DTB/stock-ramdisk/classifier checks")
