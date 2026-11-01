#!/usr/bin/env python3
from pathlib import Path
import argparse
import hashlib
import struct

ap = argparse.ArgumentParser()
ap.add_argument("shim", type=Path)
ap.add_argument("payload", type=Path)
ap.add_argument("image", type=Path)
a = ap.parse_args()
shim = a.shim.read_bytes()
payload = a.payload.read_bytes()
image = a.image.read_bytes()
assert b"LAVENDER:SHIM" in shim
assert b"LAVENDER:LOADER" in shim
for marker in (b"LAVENDER:CALL_LOADER", b"LAVENDER:DTB_OK",
               b"LAVENDER:PAYLOAD_OK", b"LAVENDER:CONTRACT_OK",
               b"LAVENDER:SEGMENTS_BEGIN", b"LAVENDER:SEG0_CHECK_BEGIN",
               b"LAVENDER:SEG0_PRE_OK", b"LAVENDER:SEG0_OK",
               b"LAVENDER:SOURCES_OK", b"LAVENDER:OVERLAP_BEGIN",
               b"LAVENDER:OVERLAP_OK",
               b"LAVENDER:SEG_FAIL_SRC_RANGE",
               b"LAVENDER:COPY_FIRST_BEFORE", b"LAVENDER:COPY_FIRST_AFTER",
               b"LAVENDER:SEG0_COPY_BEGIN", b"LAVENDER:SEG0_COPY_DONE",
               b"LAVENDER:SEGMENTS_OK", b"LAVENDER:MEM_OK",
               b"LAVENDER:COPY", b"LAVENDER:BOOTARGS"):
    assert marker in shim
magic, version, nsegs = struct.unpack_from("<8sII", payload, 0)
assert magic == b"SWEETXNU" and version == 1
payload_parts = []
for i in range(nsegs):
    _, _, off, size = struct.unpack_from("<4Q", payload, 0x2a8 + 32 * i)
    payload_parts.append(payload[off:off + size])
assert b"LAVENDER:XNU_ENTRY" in b"".join(payload_parts)
assert image[:8] == b"ANDROID!"
print("pmsg sequence static check: SHIM -> LOADER -> XNU_ENTRY markers present")
print(f"boot_sha256={hashlib.sha256(image).hexdigest()}")
