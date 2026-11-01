#!/usr/bin/env python3
import importlib.util
import struct
from pathlib import Path

tool = Path(__file__).with_name("extract-lavender-pmsg-raw.py")
spec = importlib.util.spec_from_file_location("pmsg_raw", tool)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def fixture(start, payload):
    raw = bytearray(mod.ZONE_SIZE)
    struct.pack_into("<III", raw, 0, mod.SIGNATURE, start, len(payload))
    data = memoryview(raw)[mod.HEADER_SIZE:]
    for i, value in enumerate(payload):
        data[(start + i) % mod.CAPACITY] = value
    return bytes(raw)

assert mod.decode(fixture(0, b"LAVENDER:XNU_CODE_REACHED")) == b"LAVENDER:XNU_CODE_REACHED"
wrapped = b"before|LAVENDER:XNU_ENTRY|after"
assert mod.decode(fixture(mod.CAPACITY - 5, wrapped)) == wrapped
for bad in (b"", b"x" * (mod.ZONE_SIZE - 1)):
    try:
        mod.decode(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("short raw zone was accepted")
raw = bytearray(mod.ZONE_SIZE)
struct.pack_into("<III", raw, 0, 0, 0, 1)
try:
    mod.decode(bytes(raw))
except ValueError:
    pass
else:
    raise AssertionError("bad signature was accepted")
print("PASS: raw PMSG bounds, signature and wrapped-ring order")
