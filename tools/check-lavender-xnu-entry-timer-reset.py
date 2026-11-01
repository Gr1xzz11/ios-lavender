#!/usr/bin/env python3
"""Validate the delayed timer diagnostic inside the packed XNU payload."""
from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

MAGIC = b"SWEETXNU"
FDT = b"\xd0\x0d\xfe\xed"
EXPECTED_ENTRY = 0xFFFFFE0007487488
EXPECTED_ENTRY_PA = 0x81487488
TIMER_WORDS = (
    0xD5384249, 0xD3420D29, 0xF100053F, 0x54000401,
    0xD53BE001, 0xD2884804, 0xF2A001E4, 0xEB04003F,
    0x54000363, 0xD2994005, 0xF2A77345, 0xEB05003F,
    0x540002E8, 0xD53BE002, 0xEB02003F, 0x54000281,
    0xD53BE022, 0xD2820004, 0xF1000484, 0x54FFFFE1,
    0xD53BE023, 0xEB02007F, 0x540001A3, 0x54000180,
    0xD2800146, 0x9B067C26, 0xD53BE027, 0xCB0200E8,
    0xEB06011F, 0x54FFFFA3, 0x52800120, 0x72B08000,
    0xD4000003, 0xD503205F, 0x17FFFFFF, 0xD503205F,
    0x17FFFFFF,
)
TIMER_CODE = struct.pack(f"<{len(TIMER_WORDS)}I", *TIMER_WORDS)


def payload_from_boot(path: Path) -> tuple[bytes, bytes, bytes]:
    boot = path.read_bytes()
    h = struct.unpack_from("<10I", boot, 8)
    page = h[7]
    kernel_off = page
    kernel = boot[kernel_off:kernel_off + h[0]]
    ramdisk_off = ((kernel_off + h[0] + page - 1) // page) * page
    ramdisk = boot[ramdisk_off:ramdisk_off + h[2]]
    decoder = zlib.decompressobj(31)
    stream = decoder.decompress(kernel) + decoder.flush()
    assert decoder.unused_data.startswith(FDT), "appended DTB tail is missing"
    return stream, kernel, ramdisk


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("boot", type=Path)
    ap.add_argument("stock", type=Path)
    args = ap.parse_args()
    stream, _, ramdisk = payload_from_boot(args.boot)
    stock = args.stock.read_bytes()
    sh = struct.unpack_from("<10I", stock, 8)
    stock_rd_off = ((sh[7] + sh[0] + sh[7] - 1) // sh[7]) * sh[7]
    stock_ramdisk = stock[stock_rd_off:stock_rd_off + sh[2]]
    assert ramdisk.endswith(stock_ramdisk), "stock ramdisk suffix changed"
    assert stream[0x38:0x40] == b"ARM\x64\0\0\0\0", "uncompressed kernel is not ARM64 Image"
    assert ramdisk.startswith(MAGIC), "loader input is not a SWEETXNU payload"
    _, version, nsegs = struct.unpack_from("<8sII", ramdisk, 0)
    assert version == 1 and nsegs == 10
    _, _, _, virt_base, entry, adt_off, adt_size, kernel_end, phys, mem = struct.unpack_from(
        "<8sII7Q", ramdisk, 0
    )
    assert entry == EXPECTED_ENTRY
    assert phys == 0x80000000 and mem == 0x05600000
    entry_file_off = None
    for index in range(nsegs):
        vmaddr, vmsize, file_off, file_size = struct.unpack_from("<4Q", ramdisk, 0x2A8 + 32 * index)
        if vmaddr <= entry < vmaddr + vmsize:
            entry_file_off = file_off + (entry - vmaddr)
            break
    assert entry_file_off is not None, "entry is outside payload segments"
    assert ramdisk[entry_file_off:entry_file_off + len(TIMER_CODE)] == TIMER_CODE
    assert b"lavender_loader_diag_reset" not in stream
    assert b"LAVENDER_LOADER_PSCI_RESET" not in stream
    print(f"entry_pa={EXPECTED_ENTRY_PA:#x} timer_code_offset={entry_file_off:#x}")
    print(f"boot_sha256={hashlib.sha256(args.boot.read_bytes()).hexdigest()}")
    print("PASS: timer/PSCI reset is inside XNU payload; loader has no reset path")


if __name__ == "__main__":
    main()
