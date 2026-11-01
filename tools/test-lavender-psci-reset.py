#!/usr/bin/env python3
"""Static guard for the lavender PSCI-reset diagnostic variant."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "shim"


def main() -> None:
    start = (SHIM / "lavender_reset_start.S").read_text(encoding="utf-8")
    source = (SHIM / "lavender_reset.c").read_text(encoding="utf-8")
    build = (SHIM / "build-lavender-diag-psci-reset-stocklike.sh").read_text(encoding="utf-8")
    assert "smc #0" in source
    assert "0x84000009" in source
    assert "lavender_reset_main" in start
    assert "make-lavender-diag-stocklike.py" in build
    assert "check-lavender-diag-stocklike.py" in build
    assert "lavender_reset_start.S" in build and "lavender_reset.c" in build
    for forbidden in ("UART", "GIC", "WATCHDOG", "PMIC", "framebuffer", "/dev/block"):
        assert forbidden.lower() not in source.lower()
    print("lavender PSCI reset shim static test: PASS")


if __name__ == "__main__":
    main()
