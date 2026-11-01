#!/usr/bin/env python3
"""Validate the loader-PSCI-reset stock-like Android v1 candidate."""
from pathlib import Path
import argparse
import hashlib
import struct
import zlib

PAGE = 4096
RAM_BASE = 0x80000000
RAM_END = 0x85600000

ap = argparse.ArgumentParser()
ap.add_argument("boot", type=Path)
ap.add_argument("stock", type=Path)
ap.add_argument("loader_image", type=Path)
ap.add_argument("payload", type=Path)
a = ap.parse_args()
boot, stock = a.boot.read_bytes(), a.stock.read_bytes()
assert boot[:8] == stock[:8] == b"ANDROID!"
sh = struct.unpack_from("<10I", stock, 8)
bh = struct.unpack_from("<10I", boot, 8)
assert len(boot) <= 64 * 1024 * 1024 and bh[7] == PAGE and bh[8] == 1
for i in (1, 3, 4, 5, 6, 7, 8, 9):
    assert bh[i] == sh[i], (i, bh[i], sh[i])
assert boot[64:1600] == stock[64:1600]
assert boot[1600:1648] == stock[1600:1648]

def kernel_parts(blob):
    h = struct.unpack_from("<10I", blob, 8)
    off = h[7]
    k = blob[off:off + h[0]]
    z = zlib.decompressobj(31)
    raw = z.decompress(k); z.flush()
    return h, k, raw, z.unused_data

sh, sk, sraw, stail = kernel_parts(stock)
bh, bk, braw, btail = kernel_parts(boot)
assert btail == stail and braw[0x38:0x40] == b"ARM\x64\0\0\0\0"
assert struct.unpack_from("<Q", braw, 0x08)[0] == struct.unpack_from("<Q", sraw, 0x08)[0] == 0x80000
assert bk[:10] == sk[:10], (bk[:10].hex(), sk[:10].hex())
assert struct.unpack_from("<Q", braw, 0x10)[0] == len(braw)
stock_ro = PAGE + ((sh[0] + PAGE - 1) // PAGE) * PAGE
stock_rd = stock[stock_ro:stock_ro + sh[2]]
boot_ro = PAGE + ((bh[0] + PAGE - 1) // PAGE) * PAGE
ramdisk = boot[boot_ro:boot_ro + bh[2]]
payload = a.payload.read_bytes()
assert ramdisk == payload + stock_rd

magic, version, nsegs = struct.unpack_from("<8sII", payload, 0)
assert magic == b"SWEETXNU" and version == 1 and 0 < nsegs <= 32
virt, entry, adt_off, adt_size, kernel_end, phys, mem = struct.unpack_from("<7Q", payload, 0x10)
assert adt_off >= 0x2a8 + 32 * nsegs
assert adt_off + adt_size <= len(payload)
assert phys == RAM_BASE and mem == RAM_END - RAM_BASE
loader = a.loader_image.read_bytes()
assert loader[0x38:0x40] == b"ARM\x64\0\0\0\0"
loader_start, loader_end = RAM_BASE + 0x8000, RAM_BASE + 0x8000 + len(loader)
assert loader_end < RAM_BASE + bh[3]
for i in range(nsegs):
    vmaddr, vmsize, file_off, file_size = struct.unpack_from("<4Q", payload, 0x2a8 + 32 * i)
    assert file_size <= vmsize and file_off + file_size <= len(payload)
    dst = phys + vmaddr - virt
    assert RAM_BASE <= dst and dst + vmsize <= RAM_END
    assert dst + vmsize <= loader_start or loader_end <= dst
print(f"boot_sha256={hashlib.sha256(boot).hexdigest()}")
print(f"boot_size={len(boot)} kernel_size={bh[0]} ramdisk_size={bh[2]}")
print(f"loader={loader_start:#x}..{loader_end:#x}")
print(f"payload={len(payload)} segments={nsegs} entry_pa={phys + entry - virt:#x}")
print(f"stock_ramdisk_sha256={hashlib.sha256(stock_rd).hexdigest()}")
print(f"dtb_tail_sha256={hashlib.sha256(btail).hexdigest()}")
print("runtime policy: loader consumes only payload segment file ranges and ADT; stock ramdisk suffix is not required")
print("runtime policy: every XNU/ADT/boot_args destination is checked against all consumed source ranges")
print("PASS: loader/image/payload/DTB/stock-ramdisk layout checks")
