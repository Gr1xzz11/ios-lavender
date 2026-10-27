#!/usr/bin/env python3
"""Static preflight for the lavender diagnostic boot image."""
import argparse
import struct
import subprocess


def header(path):
    b = open(path, "rb").read()
    assert b[:8] == b"ANDROID!", f"{path}: bad Android magic"
    values = struct.unpack_from("<10I", b, 8)
    rds, rdo, hs = struct.unpack_from("<IQI", b, 1632)
    return b, dict(kernel_size=values[0], kernel_addr=values[1], ramdisk_size=values[2],
                    ramdisk_addr=values[3], second_size=values[4], second_addr=values[5],
                    tags_addr=values[6], page_size=values[7], version=values[8],
                    os_version=values[9], recovery_dtbo_size=rds, recovery_dtbo_offset=rdo,
                    header_size=hs)


def symbols(path, nm):
    out = subprocess.check_output([nm, "-n", path], text=True)
    result = {}
    for line in out.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in {"_head", "_start", "_end", "_stack_top"}:
            result[fields[2]] = int(fields[0], 16)
    return result


ap = argparse.ArgumentParser()
ap.add_argument("stock_boot")
ap.add_argument("diag_boot")
ap.add_argument("diag_elf")
ap.add_argument("--nm", default="llvm-nm")
ap.add_argument("--ram-base", type=lambda x: int(x, 0), default=0x80000000)
ap.add_argument("--reserved-start", type=lambda x: int(x, 0), default=0x85700000)
a = ap.parse_args()

stock_blob, stock = header(a.stock_boot)
diag_blob, diag = header(a.diag_boot)
for key in ("kernel_addr", "ramdisk_addr", "second_size", "tags_addr", "page_size", "version",
            "recovery_dtbo_size", "header_size"):
    assert diag[key] == stock[key], f"header mismatch {key}: {diag[key]:#x} != {stock[key]:#x}"
assert diag["version"] == 1 and diag["second_size"] == 0
assert diag_blob[64:576].split(b"\0")[0] == b"console=ttyMSM0,115200,n8 earlycon=msm_serial_dm,0xc170000"

image_off = diag["page_size"]
image = diag_blob[image_off:image_off + diag["kernel_size"]]
assert image[0x38:0x40] == b"ARM\x64\0\0\0\0"
assert struct.unpack_from("<Q", image, 0x10)[0] == len(image)

syms = symbols(a.diag_elf, a.nm)
assert syms["_head"] == 0
assert 0 < syms["_start"] < syms["_end"]
assert syms["_stack_top"] == syms["_end"]
assert syms["_end"] == len(image)
load = a.ram_base + diag["kernel_addr"]
end = load + len(image)
assert end < a.reserved_start, f"image ends in reserved-memory: {end:#x}"
print(f"OK: v1 fields match stock; load={load:#x}..{end:#x}; "
      f"entry={load + syms['_head']:#x}; _start={load + syms['_start']:#x}; "
      f"stack={load + syms['_stack_top']:#x}; "
      f"reserved-start={a.reserved_start:#x}")
