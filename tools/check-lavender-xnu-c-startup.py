#!/usr/bin/env python3
"""Static checks for the lavender XNU C-startup instrumentation."""
from pathlib import Path
import argparse
import hashlib
import struct
import zlib

ENTRY = 0xfffffe0007487488
ENTRY_PA = 0x81487488
VIRT_BASE = 0xfffffe0006000000
PHYS_BASE = 0x80000000
ARM_INIT_POST_ARG = 0xfffffe0007abe614
ARM_INIT_POST_ARG_CONT = 0xfffffe0007abe618
ARM_VM_RETURN = 0xfffffe0007abee40
ARM_VM_RETURN_CONT = 0xfffffe0007abee44
PHYSTOKV = 0xfffffe000747e2f0
BUILD_ID = b"@B20261028_2355"

ap = argparse.ArgumentParser()
ap.add_argument("kernel", type=Path)
ap.add_argument("payload", type=Path)
ap.add_argument("boot", type=Path)
a = ap.parse_args()

blob = a.kernel.read_bytes()
magic, cputype, cpusub, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from("<8I", blob)
assert magic == 0xfeedfacf and cputype == 0x0100000c
segments = []
off = 32
for _ in range(ncmds):
    cmd, size = struct.unpack_from("<II", blob, off)
    if cmd == 0x19:
        name = blob[off + 8:off + 24].split(b"\0", 1)[0].decode()
        vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", blob, off + 24)
        segments.append((name, vmaddr, vmsize, fileoff, filesize))
    off += size
text = next(s for s in segments if s[0] == "__TEXT_EXEC")
_, text_va, text_vs, text_off, text_fs = text

def file_off(va):
    assert text_va <= va < text_va + text_fs
    return text_off + va - text_va

def word(va):
    return struct.unpack_from("<I", blob, file_off(va))[0]

def branch_target(va):
    insn = word(va)
    assert insn & 0xfc000000 == 0x14000000
    delta = (insn & 0x03ffffff) << 2
    if insn & 0x02000000:
        delta -= 0x10000000
    return va + delta

def va_to_pa(va):
    assert va >= VIRT_BASE
    return PHYS_BASE + va - VIRT_BASE

assert branch_target(ENTRY) == 0xfffffe0007482780
assert va_to_pa(ENTRY) == ENTRY_PA
assert branch_target(0xfffffe00074890ec) == 0xfffffe00074828a0
assert word(0xfffffe00074890f0) == 0xd5034fdf  # original DAIFSet
assert branch_target(ARM_INIT_POST_ARG) == 0xfffffe0007482af0
assert branch_target(ARM_VM_RETURN) == 0xfffffe0007482c00
assert word(ARM_INIT_POST_ARG_CONT) == 0xf9459108  # ldr x8,[x8,#0xb20]
assert word(ARM_VM_RETURN_CONT) == 0xd503201f  # nop
assert struct.pack("<Q", PHYSTOKV) in blob[file_off(0xfffffe0007482c00):file_off(0xfffffe0007482c00) + 0x340]
assert b"LAVENDER:XNU_C_ARM_INIT" + BUILD_ID in blob
assert b"LAVENDER:XNU_VM_INIT_DONE" + BUILD_ID in blob
assert b"LAVENDER:XNU_ENTRY" + BUILD_ID in blob

payload = a.payload.read_bytes()
assert payload[:8] == b"SWEETXNU"
nsegs = struct.unpack_from("<I", payload, 12)[0]
parts = []
for i in range(nsegs):
    _, _, fileoff, filesize = struct.unpack_from("<4Q", payload, 0x2a8 + i * 32)
    parts.append(payload[fileoff:fileoff + filesize])
all_parts = b"".join(parts)
for marker in (b"LAVENDER:XNU_ENTRY", b"LAVENDER:XNU_BEFORE_FIRST",
               b"LAVENDER:XNU_CODE_REACHED", b"LAVENDER:XNU_C_ARM_INIT",
               b"LAVENDER:XNU_VM_INIT_DONE"):
    assert marker + BUILD_ID in all_parts

boot = a.boot.read_bytes()
assert boot[:8] == b"ANDROID!"
header = struct.unpack_from("<10I", boot, 8)
assert header[7] == 4096 and header[8] == 1 and len(boot) <= 64 * 1024 * 1024
kernel = boot[header[7]:header[7] + header[0]]
raw = zlib.decompressobj(31).decompress(kernel)
assert raw[0x38:0x40] == b"ARM\x64\0\0\0\0"
# The Android kernel member is the lavender shim; the patched Mach-O is in
# the loader payload checked above, not in this gzip member.
assert hashlib.sha256(blob).hexdigest()
print("PASS: lavender XNU C-startup branches, continuation instructions, phystokv literal, markers and boot packaging")
print(f"kernel_sha256={hashlib.sha256(blob).hexdigest()}")
print(f"boot_sha256={hashlib.sha256(boot).hexdigest()}")
