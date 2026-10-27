#!/usr/bin/env python3
"""Fail-closed preflight for a lavender XNU Mach-O and payload placement.

This check deliberately does not manufacture an ABL load address. It verifies
the arm64 allocator contract from an xnu-8796 source tree, then models the
placement currently implemented by mkpayload.py and rejects intersections with
fixed reserved-memory ranges from the lavender DTS.
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mkpayload  # noqa: E402
import adt  # noqa: E402

ARM64 = 0x0100000C
MH_EXECUTE = 2
MH_PIE = 0x00200000
PAGE = 0x4000

# Fixed, non-reusable ranges copied from candidate-2.dts.  Dynamic
# shared-dma-pool ranges are intentionally not treated as proof of free RAM.
RESERVED = (
    (0x85600000, 0x85700000, "wlan_msa_guard"),
    (0x85700000, 0x85800000, "wlan_msa_mem"),
    (0x85800000, 0x88F00000, "removed_regions"),
    (0x8AC00000, 0x92A00000, "modem_fw_region"),
    (0x92A00000, 0x94800000, "adsp_fw_region"),
    (0x94800000, 0x94A00000, "pil_mba_region"),
    (0x94A00000, 0x95000000, "cdsp_fw_region"),
    (0x9D400000, 0x9F7FF000, "cont_splash_region"),
    (0x9F8FF000, 0x9F900000, "dfps"),
    (0xA0000000, 0xA0400000, "pstore"),
)


def macho(path):
    data = bytearray(Path(path).read_bytes())
    if len(data) < 32:
        raise AssertionError("Mach-O header is truncated")
    magic, cpu, sub, ftype, ncmds, sizeofcmds, flags, _ = struct.unpack_from("<8I", data)
    assert magic == 0xFEEDFACF, "not a 64-bit Mach-O"
    assert cpu == ARM64, f"unexpected cputype {cpu:#x}, expected ARM64"
    assert ftype == MH_EXECUTE, f"unexpected Mach-O filetype {ftype}"
    assert flags & MH_PIE, "XNU kernel must be a PIE"
    assert 32 + sizeofcmds <= len(data), "load commands exceed file"
    segs, entry, fixups = [], None, None
    off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        assert size >= 8 and off + size <= len(data), "invalid Mach-O load command"
        if cmd == mkpayload.LC_SEGMENT_64:
            name = data[off + 8:off + 24].split(b"\0", 1)[0].decode("ascii")
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", data, off + 24)
            assert fileoff + filesize <= len(data), f"{name}: file range exceeds Mach-O"
            # vmaddr is page aligned; the final __LINKEDIT vmsize need not be
            # rounded because kernel_end is rounded below.
            assert not (vmaddr & (PAGE - 1)), f"{name}: vmaddr is not 16K aligned"
            segs.append((name, vmaddr, vmsize, fileoff, filesize))
        elif cmd == mkpayload.LC_UNIXTHREAD:
            entry, = struct.unpack_from("<Q", data, off + 16 + 32 * 8)
        elif cmd == mkpayload.LC_DYLD_CHAINED_FIXUPS:
            fixups = struct.unpack_from("<II", data, off + 8)
        off += size
    assert entry is not None, "Mach-O has no ARM64 entry point"
    assert any(name == "__TEXT_EXEC" and va <= entry < va + size for name, va, size, _, _ in segs), \
        f"entry {entry:#x} is not in __TEXT_EXEC"
    text = next(s for s in segs if s[0] == "__TEXT")
    assert text[3] == 0, "__TEXT must start at file offset zero"
    kernel_end = (max(va + size for _, va, size, _, _ in segs) + PAGE - 1) & ~(PAGE - 1)
    virt_base = text[1] & ~(0x2000000 - 1)
    return data, dict(cputype=cpu, cpusub=sub & 0xff, flags=flags, segs=segs,
                     entry=entry, fixups=fixups, virt_base=virt_base,
                     kernel_end=kernel_end)


def chosen_memory(adt_path):
    root, _ = adt.parse(Path(adt_path).read_bytes())
    chosen = next(n for n in root.children if n.name == "chosen")
    def q(name):
        return struct.unpack("<Q", chosen.prop(name))[0]
    return q("dram-base"), q("dram-size"), q("dram-high-base"), q("dram-high-size")


def overlap(start, end):
    return [(name, max(start, lo), min(end, hi)) for lo, hi, name in RESERVED
            if start < hi and lo < end]


def verify_xnu_memory_model(tree):
    """Verify the source path that turns boot_args into pmap's one interval."""
    root = Path(tree)
    vm = (root / "osfmk/arm64/arm_vm_init.c").read_text(encoding="utf-8")
    init = (root / "osfmk/arm/arm_init.c").read_text(encoding="utf-8")
    pmap = (root / "osfmk/arm/pmap/pmap.c").read_text(encoding="utf-8")
    required = (
        "gPhysBase = args->physBase",
        "gPhysSize = mem_size = ((gPhysBase + args->memSize)",
        "avail_start = args->topOfKernelData",
        "avail_end = gPhysBase + mem_size",
    )
    for marker in required:
        assert marker in vm, f"XNU memory model changed; missing {marker!r}"
    assert 'SecureDTGetProperty(chosen, "dram-base"' in init
    assert 'SecureDTGetProperty(chosen, "dram-size"' in init
    assert "avail_end - first_avail" in pmap


ap = argparse.ArgumentParser()
ap.add_argument("kernel")
ap.add_argument("adt")
ap.add_argument("--xnu-tree", required=True,
                help="xnu-8796 source tree used to verify allocator behavior")
ap.add_argument("--sha256", help="expected SHA-256 of the kernel")
a = ap.parse_args()

verify_xnu_memory_model(a.xnu_tree)
blob, m = macho(a.kernel)
digest = hashlib.sha256(blob).hexdigest()
if a.sha256:
    assert digest == a.sha256.lower(), f"SHA-256 mismatch: {digest}"
low, low_size, high, high_size = chosen_memory(a.adt)
adt_blob = Path(a.adt).read_bytes()
assert (low, low_size, high, high_size) == (0x80000000, 0x05600000, 0x100000000, 0x7E4C0000), \
    "unexpected lavender ADT memory map"

# This is exactly mkpayload.py's current mapping: phys = phys_base +
# (vmaddr - virt_base).  It is intentionally checked before any boot image
# can be produced.
load_start = low + next(s[1] for s in m["segs"] if s[0] == "__TEXT") - m["virt_base"]
load_end = low + m["kernel_end"] - m["virt_base"]
kernel_hits = overlap(load_start, load_end)
managed_hits = overlap(low, low + low_size)
metadata_end = (load_end + len(adt_blob) + PAGE - 1) & ~(PAGE - 1)
metadata_end += PAGE
assert metadata_end <= low + low_size, "kernel/ADT/boot_args exceed managed lavender window"
print(f"kernel sha256: {digest}")
print(f"Mach-O: ARM64 entry={m['entry']:#x} virt_base={m['virt_base']:#x} "
      f"kernel_end={m['kernel_end']:#x}")
print(f"current mkpayload placement: {load_start:#x}..{load_end:#x}")
for name, lo, hi in kernel_hits:
    print(f"KERNEL OVERLAP: {name}: {lo:#x}..{hi:#x}")
for name, lo, hi in managed_hits:
    print(f"MANAGED-RAM OVERLAP: {name}: {lo:#x}..{hi:#x}")
if kernel_hits:
    raise SystemExit("BLOCKED: current kernel placement overlaps lavender reserved-memory")
if managed_hits:
    raise SystemExit("BLOCKED: XNU managed RAM includes lavender reserved-memory")
print("PASS: Mach-O and current kernel placement are structurally safe")
