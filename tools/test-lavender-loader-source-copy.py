#!/usr/bin/env python3
"""Static contract for source-only initrd use by the lavender loader."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "shim/lavender_loader.c").read_text(encoding="utf-8")
assert "struct payload_seg segs[32]" in src
assert "source_ranges" in src
assert "static int round8" in src and "round8(s->file_size" in src
assert "ramdisk overlaps XNU managed RAM" not in src
assert "range_intersects(dst, s->vmsize," in src and "source_ranges[segment_source_index[j]].start" in src
assert "source_ranges[i]" in src
print("lavender loader source-copy static test: PASS")
