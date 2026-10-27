#!/usr/bin/env python3
"""Audit the physical layout produced by the current lavender XNU loader.

This is deliberately a preflight, not a boot-image builder.  It reports
unknown ABL relocation/ramdisk placement as blockers instead of selecting an
address for them.
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adt  # noqa: E402
import mkpayload  # noqa: E402

LOW = 0x80000000
LOW_END = 0x85600000
PAGE = 0x4000
FIXED = (
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


def symbols(path):
    b = Path(path).read_bytes()
    _, _, _, _, ncmds, _, _, _ = struct.unpack_from("<8I", b, 0)
    off = 32
    result = {}
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", b, off)
        if cmd == 2:  # LC_SYMTAB
            symoff, nsyms, stroff, strsize = struct.unpack_from("<4I", b, off + 8)
            for i in range(nsyms):
                strx, _, _, _, value = struct.unpack_from("<IBBHQ", b, symoff + i * 16)
                if strx < strsize:
                    end = b.find(b"\0", stroff + strx)
                    name = b[stroff + strx:end].decode("ascii", "replace")
                    if name in {"_intstack_low_guard", "_intstack", "_intstack_top",
                                "_excepstack", "_excepstack_top", "_excepstack_high_guard"}:
                        result[name] = value
        off += size
    return result


def hit(start, end):
    return [name for lo, hi, name in FIXED if start < hi and lo < end]


ap = argparse.ArgumentParser()
ap.add_argument("kernel")
ap.add_argument("adt")
ap.add_argument("--stock-ramdisk-addr", type=lambda x: int(x, 0), default=0x01000000)
ap.add_argument("--abl-base", type=lambda x: int(x, 0),
                help="hypothetical ABL base; absence is a blocker")
a = ap.parse_args()

adt_blob = Path(a.adt).read_bytes()
root, _ = adt.parse(adt_blob)
chosen = next(n for n in root.children if n.name == "chosen")
q = lambda name: struct.unpack("<Q", chosen.prop(name))[0]
assert (q("dram-base"), q("dram-size")) == (LOW, LOW_END - LOW)

kernel = bytearray(Path(a.kernel).read_bytes())
m = mkpayload.parse_macho(kernel)
text = m["segs"][0]
virt = text["vmaddr"] & ~(0x2000000 - 1)
kernel_end = (max(s["vmaddr"] + s["vmsize"] for s in m["segs"]) + PAGE - 1) & ~(PAGE - 1)
load_start = LOW + text["vmaddr"] - virt
load_end = LOW + kernel_end - virt
adt_pa = load_end
ba_pa = (adt_pa + len(adt_blob) + PAGE - 1) & ~(PAGE - 1)
top = ba_pa + PAGE
avail_end = LOW_END

assert load_start >= LOW and top < avail_end
assert not hit(load_start, load_end)
assert not hit(adt_pa, top)
assert m["entry"] >= text["vmaddr"]
entry_pa = LOW + m["entry"] - virt

print(f"kernel: {load_start:#x}..{load_end:#x}")
print(f"ADT: {adt_pa:#x}..{adt_pa + len(adt_blob):#x}")
print(f"boot_args: {ba_pa:#x}..{top:#x}")
print(f"entry: VA {m['entry']:#x} -> PA {entry_pa:#x}")
print(f"avail_end: {avail_end:#x}")

syms = symbols(a.kernel)
for name in ("_intstack_low_guard", "_intstack", "_intstack_top",
             "_excepstack", "_excepstack_top", "_excepstack_high_guard"):
    assert name in syms, f"missing XNU stack symbol {name}"
    pa = LOW + syms[name] - virt
    print(f"{name}: VA {syms[name]:#x} -> PA {pa:#x}")
    assert LOW <= pa < avail_end and not hit(pa, pa + PAGE), name

if a.abl_base is None:
    raise SystemExit("BLOCKED: ABL relocation base is unknown; shim stack and Image PA are unverified")

shim_ramdisk = a.abl_base + a.stock_ramdisk_addr
print(f"hypothetical stock ramdisk: {shim_ramdisk:#x}")
if shim_ramdisk < avail_end and shim_ramdisk + PAGE > LOW:
    raise SystemExit("BLOCKED: hypothetical stock ramdisk overlaps XNU-managed window; verify ABL placement")
print("PASS: XNU payload, stacks and metadata fit; ABL ramdisk hypothesis is disjoint")
