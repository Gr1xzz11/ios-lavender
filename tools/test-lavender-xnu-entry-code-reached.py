#!/usr/bin/env python3
from pathlib import Path

src = (Path(__file__).resolve().parents[1] / "tools/patch-lavender-xnu-entry-pmsg.py").read_text()
assert 'CODE_MARKER = b"LAVENDER:XNU_CODE_REACHED@B20261028_2355"' in src
assert "original_first" in src
assert "original_target + 4" in src
assert "code_cave" in src
print("PASS: XNU_CODE_REACHED is instrumented after the original first instruction")
