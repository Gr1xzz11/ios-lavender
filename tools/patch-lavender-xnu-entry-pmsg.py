#!/usr/bin/env python3
"""Patch a copy of lavender XNU __start with an in-XNU pmsg append."""
from __future__ import annotations

import argparse
import struct
import subprocess
import tempfile
from pathlib import Path

ENTRY = 0xfffffe0007487488
ENTRY_PA = 0x81487488
PHYS_BASE = 0x80000000
VIRT_BASE = 0xfffffe0006000000
PMSG_BASE = 0xA0200000
PMSG_CAPACITY = 0x1FFFF4
MARKER = b"LAVENDER:XNU_ENTRY@B20261028_2355"
BEFORE_FIRST_MARKER = b"LAVENDER:XNU_BEFORE_FIRST@B20261028_2355"
CODE_MARKER = b"LAVENDER:XNU_CODE_REACHED@B20261028_2355"
ARM_INIT_MARKER = b"LAVENDER:XNU_C_ARM_INIT@B20261028_2355"
ARM_VM_DONE_MARKER = b"LAVENDER:XNU_VM_INIT_DONE@B20261028_2355"


def c_marker_asm(marker: bytes, continuation: int, restore_x8: int | None = None,
                 call_phystokv: bool = False) -> str:
    """Append a marker from MMU-on C startup without touching callee-saved regs."""
    restore = ""
    if restore_x8 is not None:
        restore = f"""\
    movz x8, #0x{restore_x8 & 0xffff:04x}
    movk x8, #0x{(restore_x8 >> 16) & 0xffff:04x}, lsl #16
    movk x8, #0x{(restore_x8 >> 32) & 0xffff:04x}, lsl #32
    movk x8, #0x{(restore_x8 >> 48) & 0xffff:04x}, lsl #48
"""
    phystokv = """
    movz x0, #0x0000
    movk x0, #0xa020, lsl #16
"""
    if call_phystokv:
        phystokv += """\
    ldr x17, phystokv_va
    blr x17
"""
    return f"""\
.text
.align 2
.global diag_c_marker
diag_c_marker:
{phystokv}    mov x5, x0
    ldr w10, [x5]
    mov w11, #0x4244
    movk w11, #0x4347, lsl #16
    cmp w10, w11
    b.ne c_done
    ldr w12, [x5, #4]
    ldr w13, [x5, #8]
    mov w14, #0xfff4
    movk w14, #0x001f, lsl #16
    cmp w12, w14
    b.hs c_done
    cmp w13, w14
    b.hi c_done
    mov w7, w14
    sub w7, w7, #{len(marker)}
    cmp w13, w7
    b.ls c_no_overflow
    sub w8, w13, w7
    add w6, w12, w8
    cmp w6, w14
    b.lo c_start_ready
    sub w6, w6, w14
c_start_ready:
    mov w15, w14
    b c_position
c_no_overflow:
    mov w8, wzr
    add w15, w13, #{len(marker)}
c_position:
    add w16, w12, w13
    cmp w16, w14
    b.lo c_pos_ready
    sub w16, w16, w14
c_pos_ready:
    add x9, x5, #12
    add x10, x9, x16
    add x11, x9, x14
    adr x12, c_marker
    mov w13, wzr
c_write_loop:
    add x16, x10, x13
    cmp x16, x11
    b.lo c_write_here
    sub x16, x16, x14
c_write_here:
    ldrb w17, [x12, x13]
    strb w17, [x16]
    dc cvac, x16
    add w13, w13, #1
    cmp w13, #{len(marker)}
    b.lo c_write_loop
    dsb sy
    cbz w8, c_no_start
    str w6, [x5, #4]
c_no_start:
    str w15, [x5, #8]
    dc cvac, x5
    dsb sy
c_done:
{restore}    ldr x17, c_continuation
    br x17
c_marker:
    .ascii "{marker.decode()}"
    .align 3
c_continuation:
    .quad 0x{continuation:016x}
{"phystokv_va:\n    .quad 0xfffffe000747e2f0" if call_phystokv else ""}
"""

def marker_asm(marker: bytes, first_instruction: str, continuation: int) -> str:
    return f"""\
.text
.align 2
.global diag_entry
diag_entry:
    {first_instruction}
    mov x20, x0
    movz x1, #0x0000
    movk x1, #0xa020, lsl #16
    ldr w2, [x1]
    mov w14, #0x4244
    movk w14, #0x4347, lsl #16
    cmp w2, w14
    b.ne fail
    ldr w3, [x1, #4]
    ldr w4, [x1, #8]
    mov w14, #0xfff4
    movk w14, #0x001f, lsl #16
    cmp w3, w14
    b.hs fail
    cmp w4, w14
    b.hi fail
    add w5, w3, w4
    cmp w5, w14
    b.lo position_ok
    sub w5, w5, w14
position_ok:
    mov w6, #{len(marker)}
    sub w7, w14, w6
    cmp w4, w7
    b.ls no_overflow
    sub w6, w4, w7
    add w7, w3, w6
    cmp w7, w14
    b.lo overflow_ready
    sub w7, w7, w14
overflow_ready:
    b size_full
no_overflow:
    mov w6, wzr
    add w8, w4, #{len(marker)}
    b size_ready
size_full:
    mov w8, w14
size_ready:
    movz x9, #0x0000
    movk x9, #0xa020, lsl #16
    add x9, x9, #12
    add x10, x9, x5
    add x11, x9, x14
    adr x12, marker
    mov w13, wzr
write_loop:
    add x15, x10, x13
    cmp x15, x11
    b.lo write_here
    sub x15, x15, x14
write_here:
    ldrb w16, [x12, x13]
    strb w16, [x15]
    dc cvac, x15
    add w13, w13, #1
    cmp w13, #{len(marker)}
    b.lo write_loop
    dsb sy
    cbz w6, no_start_update
    str w7, [x1, #4]
no_start_update:
    str w8, [x1, #8]
    dc cvac, x1
    dsb sy
fail:
    mov x0, x20
    ldr x1, continuation
    br x1
marker:
    .ascii "{marker.decode()}"
    .align 3
continuation:
    .quad 0x{continuation:016x}
"""


def macho_segments(blob: bytes):
    magic, _, _, _, ncmds, _, _, _ = struct.unpack_from("<8I", blob)
    assert magic == 0xfeedfacf, "not arm64 Mach-O"
    segments = []
    entry = None
    off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", blob, off)
        if cmd == 0x19:
            name = blob[off + 8:off + 24].split(b"\0", 1)[0].decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", blob, off + 24)
            segments.append((name, vmaddr, vmsize, fileoff, filesize))
        elif cmd == 5:
            entry = struct.unpack_from("<Q", blob, off + 16 + 32 * 8)[0]
        off += size
    assert entry == ENTRY, hex(entry or 0)
    return segments


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kernel", type=Path)
    ap.add_argument("output", type=Path)
    a = ap.parse_args()
    blob = bytearray(a.kernel.read_bytes())
    segments = macho_segments(blob)
    text_exec = next(s for s in segments if s[0] == "__TEXT_EXEC")
    _, vmaddr, vmsize, fileoff, filesize = text_exec
    entry_off = fileoff + (ENTRY - vmaddr)
    original, = struct.unpack_from("<I", blob, entry_off)
    assert original & 0xfc000000 == 0x14000000, hex(original)
    original_target = ENTRY + ((original & 0x03ffffff) << 2)
    if original & 0x02000000:
        original_target -= 0x10000000

    original_first_off = fileoff + (original_target - vmaddr)
    original_first, = struct.unpack_from("<I", blob, original_first_off)
    # clang/llvm encodes ``msr OSLAR_EL1, xzr`` as 0xD510109F in this
    # recovered arm64 Mach-O.  Check the actual instruction, rather than a
    # guessed encoding, before inserting the post-instruction trampoline.
    assert original_first == 0xD510109F, hex(original_first)

    ARM_INIT = 0xfffffe0007abe5ec
    ARM_INIT_POST_ARG = 0xfffffe0007abe614
    ARM_INIT_POST_ARG_CONT = 0xfffffe0007abe618
    ARM_VM_RETURN = 0xfffffe0007abee40
    ARM_VM_RETURN_CONT = 0xfffffe0007abee44
    ARM_VM_RESTORED_X8 = 0xfffffe0007168000

    def va_to_pa(va: int) -> int:
        assert va >= VIRT_BASE, hex(va)
        return PHYS_BASE + (va - VIRT_BASE)

    assert va_to_pa(ENTRY) == ENTRY_PA
    original_target_pa = va_to_pa(original_target)
    original_continuation_pa = va_to_pa(original_target + 4)

    def assemble(asm_text: str, td: Path, name: str) -> bytes:
        asm = td / f"{name}.S"
        obj = td / f"{name}.o"
        raw = td / f"{name}.bin"
        asm.write_text(asm_text)
        subprocess.run(["clang", "--target=aarch64-none-elf", "-c", str(asm), "-o", str(obj)], check=True)
        subprocess.run(["llvm-objcopy", "-O", "binary", "-j", ".text", str(obj), str(raw)], check=True)
        return raw.read_bytes()

    def find_cave(min_size: int, after: int = 0) -> int:
        run_start = None
        for off in range(max(fileoff, after), search_end):
            if blob[off] == 0:
                run_start = off if run_start is None else run_start
                if off + 1 - run_start >= min_size and run_start % 4 == 0:
                    return run_start
            else:
                run_start = None
        raise AssertionError("no executable zero cave")

    search_end = fileoff + filesize
    with tempfile.TemporaryDirectory(prefix="lavender-xnu-pmsg-") as td_name:
        td = Path(td_name)
        entry_code = assemble(marker_asm(MARKER, "nop", original_target_pa), td, "entry")
        before_first_template = assemble(
            marker_asm(BEFORE_FIRST_MARKER, "nop", 0), td, "before-first-template"
        )
        code_reached = assemble(
            marker_asm(CODE_MARKER, "msr OSLAR_EL1, xzr", original_continuation_pa),
            td,
            "code-reached",
        )
        arm_init_marker = assemble(
            c_marker_asm(ARM_INIT_MARKER, ARM_INIT_POST_ARG_CONT),
            td,
            "arm-init-marker",
        )
        arm_vm_done_marker = assemble(
            c_marker_asm(
                ARM_VM_DONE_MARKER,
                ARM_VM_RETURN_CONT,
                restore_x8=ARM_VM_RESTORED_X8,
                call_phystokv=True,
            ),
            td,
            "arm-vm-done-marker",
        )

        cave = find_cave(len(entry_code))
        before_first_cave = find_cave(
            len(before_first_template), cave + len(entry_code)
        )
        code_cave = find_cave(
            len(code_reached), before_first_cave + len(before_first_template)
        )
        arm_init_cave = find_cave(
            len(arm_init_marker), code_cave + len(code_reached)
        )
        arm_vm_done_cave = find_cave(
            len(arm_vm_done_marker), arm_init_cave + len(arm_init_marker)
        )
        cave_va = vmaddr + (cave - fileoff)
        before_first_cave_va = vmaddr + (before_first_cave - fileoff)
        code_cave_va = vmaddr + (code_cave - fileoff)
        code_cave_pa = va_to_pa(code_cave_va)
        arm_init_cave_va = vmaddr + (arm_init_cave - fileoff)
        arm_vm_done_cave_va = vmaddr + (arm_vm_done_cave - fileoff)
        before_first = assemble(
            marker_asm(BEFORE_FIRST_MARKER, "nop", code_cave_pa),
            td,
            "before-first",
        )

    def branch_word(source: int, target: int) -> int:
        delta = target - source
        assert delta % 4 == 0 and -(1 << 27) <= delta < (1 << 27)
        return 0x14000000 | ((delta >> 2) & 0x03ffffff)

    blob[entry_off:entry_off + 4] = struct.pack("<I", branch_word(ENTRY, cave_va))
    blob[original_first_off:original_first_off + 4] = struct.pack(
        "<I", branch_word(original_target, before_first_cave_va)
    )
    arm_init_post_arg_off = fileoff + (ARM_INIT_POST_ARG - vmaddr)
    arm_vm_return_off = fileoff + (ARM_VM_RETURN - vmaddr)
    arm_init_original, = struct.unpack_from("<I", blob, arm_init_post_arg_off)
    arm_vm_original, = struct.unpack_from("<I", blob, arm_vm_return_off)
    assert arm_init_original == 0xD503201F, hex(arm_init_original)
    assert arm_vm_original == 0xD0FFB548, hex(arm_vm_original)
    blob[arm_init_post_arg_off:arm_init_post_arg_off + 4] = struct.pack(
        "<I", branch_word(ARM_INIT_POST_ARG, arm_init_cave_va)
    )
    blob[arm_vm_return_off:arm_vm_return_off + 4] = struct.pack(
        "<I", branch_word(ARM_VM_RETURN, arm_vm_done_cave_va)
    )
    blob[cave:cave + len(entry_code)] = entry_code
    blob[before_first_cave:before_first_cave + len(before_first)] = before_first
    blob[code_cave:code_cave + len(code_reached)] = code_reached
    blob[arm_init_cave:arm_init_cave + len(arm_init_marker)] = arm_init_marker
    blob[arm_vm_done_cave:arm_vm_done_cave + len(arm_vm_done_marker)] = arm_vm_done_marker
    a.output.write_bytes(blob)
    print(f"entry={ENTRY:#x}/{ENTRY_PA:#x} original_target={original_target:#x}/{original_target_pa:#x}")
    print(f"entry_cave={cave_va:#x} fileoff={cave:#x} bytes={len(entry_code)}")
    print(
        f"before_first_cave={before_first_cave_va:#x} "
        f"fileoff={before_first_cave:#x} pa={va_to_pa(before_first_cave_va):#x} bytes={len(before_first)}"
    )
    print(f"code_cave={code_cave_va:#x} fileoff={code_cave:#x} pa={code_cave_pa:#x} bytes={len(code_reached)}")
    print(f"arm_init_cave={arm_init_cave_va:#x} fileoff={arm_init_cave:#x} bytes={len(arm_init_marker)}")
    print(f"arm_vm_done_cave={arm_vm_done_cave_va:#x} fileoff={arm_vm_done_cave:#x} bytes={len(arm_vm_done_marker)}")
    print(f"markers={MARKER!r},{BEFORE_FIRST_MARKER!r},{CODE_MARKER!r},{ARM_INIT_MARKER!r},{ARM_VM_DONE_MARKER!r}")


if __name__ == "__main__":
    main()
