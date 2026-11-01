#!/usr/bin/env python3
from pathlib import Path

src = (Path(__file__).resolve().parents[1] / "tools/patch-lavender-xnu-entry-pmsg.py").read_text()
assert 'BEFORE_FIRST_MARKER = b"LAVENDER:XNU_BEFORE_FIRST@B20261028_2355"' in src
assert 'marker_asm(BEFORE_FIRST_MARKER' in src
assert 'marker_asm(CODE_MARKER' in src
assert 'msr OSLAR_EL1, xzr' in src
print("PASS: first-instruction trace has a pre-msr and post-msr boundary")
