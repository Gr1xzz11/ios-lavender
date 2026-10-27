#!/usr/bin/env python3
"""Regression checks for the generated lavender ADT profile."""
import struct

import mkadt


def props(node):
    return {name: value for name, flags, value in node.props if not flags}


def child(node, name):
    for item in node.children:
        if props(item).get("name", b"").split(b"\0", 1)[0].decode() == name:
            return item
    raise AssertionError(f"missing ADT node {name}")


root = mkadt.build(profile="lavender", seed=b"lavender-test-seed")
rp = props(root)
assert b"xiaomi,lavender\0" in rp["compatible"]
assert b"xiaomi,sweet\0" not in rp["compatible"]

chosen = props(child(root, "chosen"))
assert struct.unpack("<Q", chosen["dram-base"])[0] == 0x80000000
assert struct.unpack("<Q", chosen["dram-size"])[0] == 0x05600000
assert struct.unpack("<Q", chosen["dram-high-base"])[0] == 0x100000000
assert struct.unpack("<Q", chosen["dram-high-size"])[0] == 0x7E4C0000
assert "embedded-panic-log-size" not in chosen

cpus = child(root, "cpus")
cpu_nodes = [item for item in cpus.children if props(item).get("device_type") == b"cpu\0"]
assert [struct.unpack("<I", props(item)["reg"])[0] for item in cpu_nodes] == [
    0, 1, 2, 3, 0x100, 0x101, 0x102, 0x103
]
assert [struct.unpack("<I", props(item)["cluster-id"])[0] for item in cpu_nodes] == [0] * 4 + [1] * 4

arm_io = child(root, "arm-io")
gic = child(arm_io, "gic")
gic_reg = struct.unpack("<4Q", props(gic)["reg"])
assert gic_reg == (0x16A00000, 0x10000, 0x16B00000, 0x100000)

uart = child(arm_io, "uart")
assert struct.unpack("<2Q", props(uart)["reg"]) == (0x0B170000, 0x1000)
emmc = child(arm_io, "emmc")
assert struct.unpack("<4Q", props(emmc)["reg"]) == (
    0x0B0C4000, 0x1000, 0x0B0C5000, 0x1000
)
assert not any(props(item).get("name") == b"sweet-fbcon\0" for item in root.children)
assert not any(props(item).get("name") == b"sweet-ufs\0" for item in root.children)

# The shared SWEET implementation is compiled for lavender for now, but its
# confirmed-sweet early framebuffer path must be preprocessor-disabled.  This
# is a source-level safety invariant, not a claim that the XNU patch series
# has been built on this Linux host.
for patch_name in (
    "xnu/patches/0010-sweet-early-framebuffer-debug.patch",
    "xnu/patches/0012-sweet-keep-debug-console-after-ttbr0.patch",
):
    text = open(patch_name, encoding="utf-8").read()
assert "#if defined(SWEET) && !defined(LAVENDER)" in text, patch_name
print("lavender XNU hardware guard test: PASS")
print("lavender ADT profile test: PASS")
