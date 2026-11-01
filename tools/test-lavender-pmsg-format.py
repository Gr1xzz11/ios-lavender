#!/usr/bin/env python3
"""Check lavender_pmsg.c against Linux persistent_ram_write ring semantics."""
from pathlib import Path

CAP = 0x1FFFF4

def linux_write(buf: bytearray, start: int, size: int, data: bytes):
    # Linux truncates an oversized write to the final buffer_size bytes.
    if len(data) > CAP:
        data = data[-CAP:]
    old_start = start
    new_size = min(CAP, size + len(data))
    for i, value in enumerate(data):
        buf[(old_start + i) % CAP] = value
    new_start = (old_start + len(data)) % CAP
    return new_start, new_size

def reader(buf: bytes, start: int, size: int) -> bytes:
    # persistent_ram_save_old(): data[start:size] then data[0:start].
    if not size:
        return b""
    return buf[start:size] + buf[:start]

def shim_write_fixed(buf: bytearray, start: int, size: int, data: bytes):
    if len(data) > CAP:
        data = data[-CAP:]
    old_start = start
    for i, value in enumerate(data):
        buf[(old_start + i) % CAP] = value
    return (old_start + len(data)) % CAP, min(CAP, size + len(data))

def old_shim_write(buf: bytearray, start: int, size: int, data: bytes):
    # Former implementation: append at start+size and advance start only on overflow.
    position = (start + size) % CAP
    overflow = max(0, size - (CAP - len(data)))
    for i, value in enumerate(data):
        buf[(position + i) % CAP] = value
    return (start + overflow) % CAP, min(CAP, size + len(data))

def main():
    src = (Path(__file__).resolve().parents[1] / "shim/lavender_pmsg.c").read_text()
    assert "position = start;" in src
    assert "header[1] = new_start;" in src
    assert "position = (start + size) % PMSG_CAPACITY" not in src
    a = bytearray(CAP); b = bytearray(CAP)
    sa = sb = sizea = sizeb = 0
    for payload in (b"abc", b"DEF", b"ghi"):
        sa, sizea = linux_write(a, sa, sizea, payload)
        sb, sizeb = shim_write_fixed(b, sb, sizeb, payload)
    assert (sa, sizea) == (sb, sizeb)
    assert reader(a, sa, sizea) == b"abcDEFghi"
    assert reader(b, sb, sizeb) == b"abcDEFghi"
    # Full-buffer append: Linux overwrites at the current write pointer and
    # leaves start unchanged when the appended write is exactly CAP bytes.
    a = bytearray(b"A" * CAP); b = bytearray(b"A" * CAP)
    sa = sb = 12345
    sa, sizea = linux_write(a, sa, CAP, b"B" * 7)
    sb, sizeb = shim_write_fixed(b, sb, CAP, b"B" * 7)
    assert (sa, sizea) == (sb, sizeb)
    assert reader(a, sa, sizea) == reader(b, sb, sizeb)
    old = bytearray(CAP)
    so, sizeo = 0, 0
    for payload in (b"abc", b"DEF"):
        so, sizeo = old_shim_write(old, so, sizeo, payload)
    assert (so, sizeo) != (sa, sizea) or reader(old, so, sizeo) != b"abcDEF"
    print("PASS: shim ring model matches persistent_ram_write/save_old for append, wrap, full buffer")

if __name__ == "__main__":
    main()
