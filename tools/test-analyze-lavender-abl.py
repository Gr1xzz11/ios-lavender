#!/usr/bin/env python3
"""Regression checks for bounded ABL triage."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analyzer", ROOT / "tools/analyze-lavender-abl.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def main():
    result = module.report(ROOT / "research/lavender/firmware/abl.elf")
    assert result["elf"]["machine"] == 40
    assert result["elf"]["entry"] == 0x9FA00000
    assert len(result["load_segments"]) == 1
    assert result["load_segments"][0]["paddr"] == 0x9FA00000
    assert result["fv"][0]["first_ffs_type"] == 0x0B
    assert result["fv"][0]["first_section_bounded"]
    assert result["fv"][0]["first_section_type"] == 0x02
    assert result["fv"][0]["first_section_type_standard"]
    assert result["fv"][0]["guid_section_data_offset"] == 0x18
    assert not result["load_scan_offsets"]["android_magic"]
    assert not result["load_scan_offsets"]["fdt_magic"]
    assert "BLOCKED" in result["conclusion"]
    print("lavender ABL static triage test: PASS")


if __name__ == "__main__":
    main()
