#!/usr/bin/env python3
"""Check the structure of a locally built lavender diagnostic boot image."""
import struct
import sys


boot_path, image_path = sys.argv[1:]
boot = open(boot_path, "rb").read()
image = open(image_path, "rb").read()
assert boot[:8] == b"ANDROID!", "missing Android boot magic"
ks, ka, rs, ra, ss, sa, ta, page, version, _ = struct.unpack_from("<10I", boot, 8)
assert version == 1, f"expected lavender header v1, got v{version}"
assert page == 4096, f"unexpected page size: {page}"
assert ka == 0x8000 and ra == 0x1000000 and ta == 0x100, "lavender load addresses changed"
assert ss == 0, "diagnostic image must not contain a second stage"
assert boot[64:576].split(b"\0")[0] == b"console=ttyMSM0,115200,n8 earlycon=msm_serial_dm,0xc170000", "unexpected diagnostic cmdline"
assert len(image) == ks, "kernel size/header mismatch"
assert image[0x38:0x40] == b"ARM\x64\0\0\0\0", "missing arm64 Image magic"
assert struct.unpack_from("<Q", image, 0x10)[0] == len(image), "Image size mismatch"
assert b"LAVENDER-DIAG:entry" in image, "diagnostic marker missing"
print(f"OK: Android v{version}, page={page}, kernel={ks}, no embedded DTB")
