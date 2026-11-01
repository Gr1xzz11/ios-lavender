#!/usr/bin/env python3
"""Static contract for the lavender XNU-entry PSCI diagnostic variant."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "patch-lavender-xnu-entry-reset.py"
BUILD = ROOT / "shim" / "build-lavender-xnu-entry-reset.sh"
TEST = ROOT / "tools" / "test-lavender-xnu-entry-reset.py"

assert TOOL.exists(), "entry-reset Mach-O patcher is missing"
assert BUILD.exists(), "entry-reset build script is missing"
source = TOOL.read_text(encoding="utf-8")
build = BUILD.read_text(encoding="utf-8")
assert "LC_UNIXTHREAD" in source
assert "__start" in source
assert "0x84000009" in source
assert "smc #0" in source
assert "NOP" in source
assert "mkpayload.py" in build
assert "preserve-lavender-bootv1-fields.py" in build
assert "lavender_loader_psci_reset" not in build
assert "lavender_loader_diag_reset" not in build
assert TEST.exists()
assert "entry_file_off" in (ROOT / "tools" / "check-lavender-xnu-entry-reset.py").read_text(encoding="utf-8")
print("lavender XNU-entry PSCI-reset static test: PASS")
