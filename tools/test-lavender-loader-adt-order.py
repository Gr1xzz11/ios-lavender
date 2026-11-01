from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "shim/lavender_loader.c").read_text(encoding="utf-8")
payload = ROOT / "research/lavender/.artifacts/seg0-kernel-20261028-0951/payload.bin"

# The ADT source in the recovered payload lies inside the zero-fill tail of
# the final Mach-O segment. It must be consumed before segment destinations
# are written; otherwise the fail-closed source guard rejects segment 9.
blob = payload.read_bytes()
_, version, nsegs = struct.unpack_from("<8sII", blob, 0)
assert version == 1
adt_off, adt_size = struct.unpack_from("<2Q", blob, 0x20)
virt_base = struct.unpack_from("<Q", blob, 0x10)[0]
phys_base = struct.unpack_from("<Q", blob, 0x38)[0]
rd_start = 0x81000000
adt_start = rd_start + adt_off
adt_end = adt_start + ((adt_size + 7) & ~7)
vm, vmsize, _, _ = struct.unpack_from("<4Q", blob, 0x2a8 + 32 * (nsegs - 1))
dst = phys_base + vm - virt_base
assert dst < adt_end and adt_start < dst + vmsize

adt_copy = src.index("copy_overlap_safe(kernel_pa, rd_start + adt_off, adt_size);")
segment_copy = src.index("for (uint32_t i = nsegs; i-- > 0;)")
assert adt_copy < segment_copy, "ADT must be copied before segment destinations"

# Once ADT is consumed first, the segment/source overlap loop must not reject
# this already-consumed ADT source. Destination-vs-ADT-destination protection
# is required separately.
assert "adt_source_index" not in src
assert "range_intersects(kernel_pa, adt_size, dst, s->vmsize)" in src
print("lavender loader ADT-first overlap regression: PASS")
