#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
header = (root / "shim/lavender_diag.h").read_text()
pmsg = (root / "shim/lavender_pmsg.c").read_text()
shim = (root / "shim/lavender_shim.c").read_text()
loader = (root / "shim/lavender_loader.c").read_text()
patcher = (root / "tools/patch-lavender-xnu-entry-pmsg.py").read_text()

assert 'LAVENDER_BUILD_ID "B20261028_2355"' in header
assert "LAVENDER_TAG(\"LAVENDER:SHIM\")" in pmsg
assert "LAVENDER_TAG(\"LAVENDER:CALL_LOADER\")" in shim
assert "LAVENDER_TAG(text)" in loader
assert "@B20261028_2355" in patcher
assert "PHYS_BASE = 0x80000000" in patcher
assert "ENTRY_PA = 0x81487488" in patcher
assert "continuation_pa" in patcher
print("PASS: one build ID tags shim, loader and XNU markers")
