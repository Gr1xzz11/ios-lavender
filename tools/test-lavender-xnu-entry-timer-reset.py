#!/usr/bin/env python3
"""Static contract for the delayed XNU-entry PSCI diagnostic variant."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "shim" / "lavender_xnu_timer_entry.S"
PATCH = ROOT / "tools" / "patch-lavender-xnu-entry-timer-reset.py"
BUILD = ROOT / "shim" / "build-lavender-xnu-entry-timer-reset.sh"

assert ASM.exists(), "timer-entry assembly is missing"
assert PATCH.exists(), "timer-entry Mach-O patcher is missing"
assert BUILD.exists(), "timer-entry build script is missing"

asm = ASM.read_text(encoding="utf-8")
patch = PATCH.read_text(encoding="utf-8")
build = BUILD.read_text(encoding="utf-8")

for token in ("CurrentEL", "CNTFRQ_EL0", "CNTPCT_EL0", "smc", "#0", "wfe", "fail"):
    assert token in asm, f"timer entry lacks {token}"
assert "0xFFFFFE0007487488" in patch
assert "0x81487488" in patch
assert "llvm-mc" in build or "clang" in build
assert "lavender-xnu-boot-safe2" not in build
assert "LAVENDER_LOADER_PSCI_RESET" not in build
assert "lavender_loader_diag_reset" not in build
assert "make-lavender-diag-stocklike.py" in build
assert "preserve-lavender-bootv1-fields.py" in build
assert "mkpayload.py" in build
assert "check-lavender-loader-psci-reset.py" in build
assert (ROOT / "tools" / "check-lavender-xnu-entry-timer-reset.py").exists()
print("lavender delayed XNU-entry PSCI-reset static test: PASS")
