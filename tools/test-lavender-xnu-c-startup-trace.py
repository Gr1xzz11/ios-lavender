from pathlib import Path

src = Path("tools/patch-lavender-xnu-entry-pmsg.py").read_text()
for marker in ("ARM_INIT_MARKER", "ARM_VM_DONE_MARKER"):
    assert marker in src
assert "ARM_INIT_POST_ARG = 0xfffffe0007abe614" in src
assert "ARM_VM_RETURN = 0xfffffe0007abee40" in src
assert "call_phystokv=True" in src
assert "assert arm_init_original == 0xD503201F" in src
assert "assert arm_vm_original == 0xD0FFB548" in src
print("PASS: XNU C-startup checkpoints are anchored to verified arm_init sites")
