#!/usr/bin/env python3
"""Regression tests for the conservative lavender XNU RAM window."""
import struct
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import adt
import mkadt

LOW_BASE = 0x80000000
FIRST_FIXED_RESERVED = 0x85600000
FIXED_RESERVED = (
    (0x85600000, 0x85700000), (0x85700000, 0x85800000),
    (0x85800000, 0x88F00000), (0x8AC00000, 0x92A00000),
    (0x92A00000, 0x94800000), (0x94800000, 0x94A00000),
    (0x94A00000, 0x95000000), (0x9D400000, 0x9F7FF000),
    (0x9F8FF000, 0x9F900000), (0xA0000000, 0xA0400000),
)


def chosen(blob):
    root, _ = adt.parse(blob)
    node = next(n for n in root.children if n.name == "chosen")
    return {name: struct.unpack("<Q", value)[0]
            for name, flag, value in node.props if name in {
                "dram-base", "dram-size", "dram-high-base", "dram-high-size"}}


def main():
    blob = adt.serialize(mkadt.build(profile="lavender"))
    values = chosen(blob)
    assert values["dram-base"] == LOW_BASE
    # XNU's current arm64 bootstrap only accepts one contiguous interval.
    # It must end before wlan_msa_guard; a larger interval feeds carve-outs to
    # pmap because XNU does not consume /reserved-memory or memory-map ranges.
    assert values["dram-base"] + values["dram-size"] <= FIRST_FIXED_RESERVED, values
    start = values["dram-base"]
    end = start + values["dram-size"]
    assert all(end <= lo or hi <= start for lo, hi in FIXED_RESERVED), values
    assert values["dram-high-base"] == 0x100000000
    assert values["dram-high-size"] == 0x7E4C0000
    print("lavender memory window test: PASS")


if __name__ == "__main__":
    main()
