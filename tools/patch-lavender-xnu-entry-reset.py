#!/usr/bin/env python3
"""Create a copy of an arm64 XNU Mach-O that resets from __start.

The patch is deliberately confined to the first 16 bytes of the XNU
``__start`` entry.  The original kernel is never modified in place.  The
entry's first instruction is checked to be an unconditional branch and the
following bytes must be NOP padding, as in the lavender kernel artifact.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
LC_SEGMENT_64 = 0x19
LC_UNIXTHREAD = 0x5
BRANCH_MASK = 0xFC000000
BRANCH = 0x14000000
NOP = 0xD503201F

# mov w0, #9; movk w0, #0x8400, lsl #16; smc #0; b .
RESET_CODE = struct.pack("<4I", 0x52800120, 0x72B08000, 0xD4000003, 0x14000000)


def macho_entry_and_text(data: bytes) -> tuple[int, int, int, int]:
    magic, cputype, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from("<8I", data, 0)
    assert magic == MH_MAGIC_64 and cputype == CPU_TYPE_ARM64, "not an arm64 Mach-O"
    command_end = 32 + sizeofcmds
    entry = None
    text = None
    off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        assert size >= 8 and off + size <= command_end, "invalid Mach-O load command"
        if cmd == LC_SEGMENT_64:
            segname = struct.unpack_from("<16s", data, off + 8)[0].rstrip(b"\0").decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", data, off + 24)
            nsects = struct.unpack_from("<I", data, off + 64)[0]
            if segname == "__TEXT_EXEC":
                section_off = off + 72
                for _ in range(nsects):
                    name = struct.unpack_from("<16s", data, section_off)[0].rstrip(b"\0").decode()
                    addr, length = struct.unpack_from("<QQ", data, section_off + 32)
                    file_offset, = struct.unpack_from("<I", data, section_off + 48)
                    if name == "__text":
                        text = (addr, length, file_offset)
                    section_off += 80
            assert fileoff + filesize <= len(data), "segment exceeds file"
        elif cmd == LC_UNIXTHREAD:
            # arm_thread_state64 pc: x0..x28, fp, lr, sp, pc, cpsr.
            entry, = struct.unpack_from("<Q", data, off + 16 + 32 * 8)
        off += size
    assert entry is not None and text is not None, "missing entry or __TEXT_EXEC,__text"
    text_addr, text_size, text_fileoff = text
    assert text_fileoff + text_size <= len(data), "__text exceeds file"
    assert text_addr <= entry < text_addr + text_size, "entry is outside __text"
    entry_off = text_fileoff + (entry - text_addr)
    return entry, entry_off, text_addr, text_fileoff + text_size


def patch(source: Path, output: Path) -> None:
    data = bytearray(source.read_bytes())
    entry, entry_off, _, text_end = macho_entry_and_text(data)
    first, = struct.unpack_from("<I", data, entry_off)
    assert first & BRANCH_MASK == BRANCH, f"unexpected __start instruction {first:#x}"
    assert entry_off + len(RESET_CODE) <= text_end, "entry reset code exceeds __text"
    for off in range(entry_off + 4, entry_off + len(RESET_CODE), 4):
        word, = struct.unpack_from("<I", data, off)
        assert word == NOP, f"__start padding is not NOP at +{off - entry_off:#x}: {word:#x}"
    data[entry_off:entry_off + len(RESET_CODE)] = RESET_CODE
    output.write_bytes(data)
    print(f"entry_va={entry:#x} file_off={entry_off:#x} patched_bytes={len(RESET_CODE)}")
    print(f"psci_function={0x84000009:#x} output={output}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    patch(args.source, args.output)


if __name__ == "__main__":
    main()
