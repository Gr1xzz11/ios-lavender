#!/usr/bin/env python3
from pathlib import Path

shim = Path("shim/lavender_pmsg.c").read_text()
build = Path("shim/build-lavender-xnu-pmsg-shim.sh").read_text()
main = Path("shim/lavender_shim.c").read_text()
assert "0xA0200000ULL" in shim
assert "0x43474244U" in shim
assert "0x1FFFF4U" in shim
assert "LAVENDER:SHIM" in shim
assert "LAVENDER:LOADER" in Path("shim/lavender_loader.c").read_text()
assert "dc cvac" in shim and "dsb sy" in shim
assert "signature != PMSG_SIG" in shim
assert "size > PMSG_CAPACITY" in shim
assert "LAVENDER_PMSG_SHIM" in main
assert "lavender_pmsg.c" in build
assert "LAVENDER_LOADER_PSCI_RESET" not in build
print("lavender pmsg shim static checks: PASS")
