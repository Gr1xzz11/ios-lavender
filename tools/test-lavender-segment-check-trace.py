#!/usr/bin/env python3
from pathlib import Path

src = (Path(__file__).resolve().parents[1] / "shim/lavender_loader.c").read_text()
for i in range(10):
    marker = f'PMSG_MARK("LAVENDER:SEG{i}_CHECK_BEGIN")'
    assert marker in src, f"missing pre-read marker for segment {i}"

print("PASS: all ten segment pre-read markers are present")
