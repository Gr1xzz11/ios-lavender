#!/usr/bin/env python3
"""Bounded static triage for the recovered lavender ABL container.

This is deliberately a scanner, not a decompiler. The supplied ABL has no
section headers/symbols and its load segment contains an FV-like payload. The
report separates observations from conclusions and fails closed when
Android/DTB handoff code is not directly recoverable.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

PT_LOAD = 1
EM_ARM = 40
FV_MAGIC = b"_FVH"
ANDROID_MAGIC = b"ANDROID!"
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def hits(blob: bytes, needle: bytes) -> list[int]:
    out = []
    start = 0
    while True:
        pos = blob.find(needle, start)
        if pos < 0:
            return out
        out.append(pos)
        start = pos + 1


def elf_report(blob: bytes) -> tuple[dict, list[dict]]:
    if blob[:4] != b"\x7fELF" or blob[4] != 1 or blob[5] != 1:
        raise ValueError("expected ELF32 little-endian")
    fields = struct.unpack_from("<16sHHIIIIIHHHHHH", blob, 0)
    _, etype, machine, _, entry, phoff, _, _, ehsize, phentsize, phnum, *_ = fields
    segments = []
    for i in range(phnum):
        off = phoff + i * phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, flags, align = struct.unpack_from(
            "<IIIIIIII", blob, off
        )
        if p_type == PT_LOAD:
            if p_offset + p_filesz > len(blob):
                raise ValueError("PT_LOAD exceeds file")
            segments.append(dict(index=i, offset=p_offset, vaddr=p_vaddr,
                                 paddr=p_paddr, filesz=p_filesz, memsz=p_memsz,
                                 flags=flags, align=align))
    return dict(class_bits=32, machine=machine, type=etype, entry=entry,
                phoff=phoff, phnum=phnum, ehsize=ehsize,
                machine_name="ARM" if machine == EM_ARM else "unknown"), segments


def fv_report(blob: bytes) -> list[dict]:
    result = []
    for sig in hits(blob, FV_MAGIC):
        start = sig - 0x28
        if start < 0 or start + 0x38 > len(blob):
            continue
        length = struct.unpack_from("<Q", blob, start + 0x20)[0]
        header_len = struct.unpack_from("<H", blob, start + 0x30)[0]
        valid = (length >= header_len and start + length <= len(blob) and
                 header_len >= 0x38)
        item = dict(signature=sig, start=start, length=length,
                    header_len=header_len, bounded=valid)
        if valid and start + header_len + 24 <= len(blob):
            ffs = start + header_len
            size = blob[ffs + 20] | (blob[ffs + 21] << 8) | (blob[ffs + 22] << 16)
            standard = set(range(1, 0x10)) | {0xf0}
            item.update(first_ffs_offset=ffs, first_ffs_type=blob[ffs + 18],
                        first_ffs_size=size,
                        first_ffs_type_standard=blob[ffs + 18] in standard)
            section = ffs + 24
            if section + 4 <= len(blob):
                section_size = blob[section] | (blob[section + 1] << 8) | (blob[section + 2] << 16)
                section_type = blob[section + 3]
                item.update(first_section_size=section_size,
                            first_section_type=section_type,
                            first_section_bounded=section_size >= 4 and section + section_size <= ffs + size,
                            first_section_type_standard=section_type in set(range(1, 0x20)))
                if section_type == 0x02 and section + 24 <= len(blob):
                    item.update(guid_section_data_offset=struct.unpack_from("<H", blob, section + 20)[0],
                                guid_section_attributes=struct.unpack_from("<H", blob, section + 22)[0])
        result.append(item)
    return result


def report(path: Path) -> dict:
    blob = path.read_bytes()
    elf, segments = elf_report(blob)
    load = b"".join(blob[s["offset"]:s["offset"] + s["filesz"]] for s in segments)
    needles = {
        "android_magic": ANDROID_MAGIC,
        "fdt_magic": FDT_MAGIC,
        "arm64_image_magic": b"ARM\x64",
        "kernel_addr_0x8000_le": struct.pack("<I", 0x8000),
        "ramdisk_addr_0x1000000_le": struct.pack("<I", 0x1000000),
        "tags_addr_0x100_le": struct.pack("<I", 0x100),
        "uart_0xc170000_le": struct.pack("<I", 0x0C170000),
    }
    scans = {name: hits(load, value) for name, value in needles.items()}
    return {
        "path": str(path),
        "file_size": len(blob),
        "elf": elf,
        "load_segments": segments,
        "fv": fv_report(blob),
        "load_scan_offsets": scans,
        "conclusion": "BLOCKED: Android v1 loader, DTB source, register handoff, and extra shim checks are not recoverable from this stripped/packed payload",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("abl", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = report(args.abl)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"ELF: {result['elf']['machine_name']}32, entry={result['elf']['entry']:#x}, "
          f"PT_LOAD={len(result['load_segments'])}")
    for segment in result["load_segments"]:
        print("LOAD: file=%#x..%#x paddr=%#x..%#x flags=%#x" % (
            segment["offset"], segment["offset"] + segment["filesz"],
            segment["paddr"], segment["paddr"] + segment["memsz"], segment["flags"]))
    print(f"FV candidates: {len(result['fv'])}")
    for item in result["fv"]:
        print("FV: start=%#x length=%#x header=%#x bounded=%s first_ffs_type=%s" % (
            item["start"], item["length"], item["header_len"], item["bounded"],
            hex(item["first_ffs_type"]) if "first_ffs_type" in item else "n/a"))
        if "first_section_type" in item:
            print("FV section: type=%#x size=%#x bounded=%s standard=%s" % (
                item["first_section_type"], item["first_section_size"],
                item["first_section_bounded"], item["first_section_type_standard"]))
            if "guid_section_data_offset" in item:
                print("FV GUID section: data_offset=%#x attributes=%#x" % (
                    item["guid_section_data_offset"], item["guid_section_attributes"]))
    for name, offsets in result["load_scan_offsets"].items():
        print(f"SCAN {name}: {len(offsets)} hit(s)" +
              (" at " + ", ".join(hex(x) for x in offsets[:8]) if offsets else ""))
    print(result["conclusion"])


if __name__ == "__main__":
    main()
