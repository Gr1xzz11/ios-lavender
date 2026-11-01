#!/usr/bin/env python3
import ast
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools/patch-lavender-xnu-entry-pmsg.py"
src = path.read_text()
tree = ast.parse(src)
marker = next(
    node.value.value
    for node in ast.walk(tree)
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "MARKER" for target in node.targets)
)
assert "cmp w13, #{len(marker)}" in src, "XNU marker loop is not derived from marker"
assert "mov w6, #{len(marker)}" in src, "XNU marker overflow is not derived from marker"
assert "add w8, w4, #{len(marker)}" in src, "XNU marker size update is not derived from marker"
print(f"PASS: XNU marker length is {len(marker)} bytes")
