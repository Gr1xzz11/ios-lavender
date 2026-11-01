#!/usr/bin/env python3
"""Check the DTB-only lavender pre-loader boot image."""
from pathlib import Path
import argparse, hashlib, struct, zlib

PAGE = 4096
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
ap = argparse.ArgumentParser()
ap.add_argument("boot", type=Path)
ap.add_argument("stock", type=Path)
ap.add_argument("image", type=Path)
a = ap.parse_args()
boot, stock, image = a.boot.read_bytes(), a.stock.read_bytes(), a.image.read_bytes()
bh = struct.unpack_from("<10I", boot, 8)
sh = struct.unpack_from("<10I", stock, 8)
assert boot[:8] == stock[:8] == b"ANDROID!"
assert len(boot) <= 64 * 1024 * 1024 and bh[7] == PAGE and bh[8] == 1
for i in (1, 3, 4, 5, 6, 7, 8, 9):
    assert bh[i] == sh[i]
assert boot[64:1600] == stock[64:1600]
assert boot[1600:1648] == stock[1600:1648]

def parts(blob):
    h = struct.unpack_from("<10I", blob, 8)
    k = blob[h[7]:h[7] + h[0]]
    z = zlib.decompressobj(31)
    raw = z.decompress(k)
    z.flush()
    return h, raw, z.unused_data

_, _, stail = parts(stock)
_, raw, tail = parts(boot)
assert raw[0x38:0x40] == b"ARM\x64\0\0\0\0"
assert struct.unpack_from("<Q", raw, 0x10)[0] == len(raw)
assert tail == stail and tail.startswith(FDT_MAGIC)
f1 = struct.unpack_from(">I", tail, 4)[0]
f2 = struct.unpack_from(">I", tail[f1:], 4)[0]
assert f1 > 0 and f1 + f2 == len(tail)
stock_ro = PAGE + ((sh[0] + PAGE - 1) // PAGE) * PAGE
boot_ro = PAGE + ((bh[0] + PAGE - 1) // PAGE) * PAGE
stock_rd = stock[stock_ro:stock_ro + sh[2]]
rd = boot[boot_ro:boot_ro + bh[2]]
assert rd == stock_rd
assert image[0x38:0x40] == b"ARM\x64\0\0\0\0"
assert struct.unpack_from("<Q", image, 0x10)[0] == len(image)
print(f"boot_sha256={hashlib.sha256(boot).hexdigest()}")
print(f"boot_size={len(boot)} kernel_size={bh[0]} ramdisk_size={bh[2]}")
print(f"preloader_image={len(image)} bytes; stock_ramdisk_sha256={hashlib.sha256(rd).hexdigest()}")
print(f"dtb_tail_sha256={hashlib.sha256(tail).hexdigest()}")
print("PASS: v1/header/gzip/DTB/stock-ramdisk/pre-loader layout checks")
