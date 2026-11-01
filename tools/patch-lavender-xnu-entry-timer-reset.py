#!/usr/bin/env python3
"""Install the delayed timer/PSCI diagnostic in XNU __start.

The input Mach-O is copied to a new file.  Only the NOP padding immediately
following the original __start branch is replaced; no loader code is changed.
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
EXPECTED_ENTRY = 0xFFFFFE0007487488
EXPECTED_ENTRY_PA = 0x81487488


def macho_entry_and_text(data: bytes) -> tuple[int, int, int]:
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
            entry, = struct.unpack_from("<Q", data, off + 16 + 32 * 8)
        off += size
    assert entry is not None and text is not None, "missing entry or __TEXT_EXEC,__text"
    text_addr, text_size, text_fileoff = text
    assert text_fileoff + text_size <= len(data), "__text exceeds file"
    assert text_addr <= entry < text_addr + text_size, "entry is outside __text"
    return entry, text_fileoff + (entry - text_addr), text_fileoff + text_size


def patch(source: Path, code_path: Path, output: Path) -> None:
    data = bytearray(source.read_bytes())
    code = code_path.read_bytes()
    assert len(code) and len(code) % 4 == 0, "timer entry must be non-empty ARM64 words"
    entry, entry_off, text_end = macho_entry_and_text(data)
    assert entry == EXPECTED_ENTRY, f"unexpected XNU entry VA {entry:#x}"
    assert EXPECTED_ENTRY - 0xFFFFFE0006000000 + 0x80000000 == EXPECTED_ENTRY_PA, "entry PA contract changed"
    first, = struct.unpack_from("<I", data, entry_off)
    assert first & BRANCH_MASK == BRANCH, f"unexpected __start instruction {first:#x}"
    assert entry_off + len(code) <= text_end, "timer entry code exceeds __text"
    for off in range(entry_off + 4, entry_off + len(code), 4):
        word, = struct.unpack_from("<I", data, off)
        assert word == NOP, f"__start padding is not NOP at +{off - entry_off:#x}: {word:#x}"
    data[entry_off:entry_off + len(code)] = code
    output.write_bytes(data)
    print(f"entry_va={entry:#x} entry_pa={EXPECTED_ENTRY_PA:#x} file_off={entry_off:#x}")
    print(f"timer_code_bytes={len(code)} output={output}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("timer_code", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    patch(args.source, args.timer_code, args.output)


if __name__ == "__main__":
    main()
