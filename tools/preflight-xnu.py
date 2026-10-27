#!/usr/bin/env python3
"""Fast, Linux-friendly preflight for the patched XNU build inputs.

This does not compile XNU.  With --xnu-tree it can additionally ask git to
check every project patch against an already prepared source tree.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
PROJECT = re.compile(r"^(\d{4})-.+\.patch$")
REQUIRED_GUARDS = {
    "0017-sweet-device-tree-virtual-timer-irq.patch": (
        "defined(SWEET) || defined(LAVENDER)",
        "defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)",
    ),
    "0043-sweet-console-crash-log.patch": (
        "defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)",
    ),
    "0067-sweet-console-mute.patch": (
        "defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)",
    ),
}


def fail(message: str) -> None:
    raise SystemExit(f"XNU PREFLIGHT ERROR: {message}")


def check_hunks(path: Path) -> None:
    lines = path.read_bytes().decode("utf-8", errors="replace").splitlines()
    found = 0
    for index, line in enumerate(lines):
        match = HUNK.match(line)
        if not match:
            continue
        old_expected = int(match.group(2) or "1")
        new_expected = int(match.group(4) or "1")
        old_count = new_count = 0
        for body in lines[index + 1:]:
            if body.startswith(("@@ ", "diff --git ", "--- ", "+++ ")):
                break
            if body and body[0] in " -":
                old_count += 1
            if body and body[0] in " +":
                new_count += 1
        if (old_count, new_count) != (old_expected, new_expected):
            fail(f"{path.name}: {line} declares {(old_expected, new_expected)} "
                 f"but contains {(old_count, new_count)} lines")
        found += 1
    if not found:
        fail(f"{path.name}: no unified-diff hunks")


def project_patches(patch_dir: Path) -> list[Path]:
    patches = []
    for path in sorted(patch_dir.glob("*.patch")):
        match = PROJECT.match(path.name)
        if match:
            patches.append(path)
    if len(patches) != 82:
        fail(f"expected 82 numbered project patches, found {len(patches)}")
    numbers = [int(PROJECT.match(path.name).group(1)) for path in patches]
    if numbers != list(range(1, 83)):
        fail(f"project patch numbers are not contiguous: {numbers}")
    return patches


def check_static_inputs(patch_dir: Path, machine: str) -> list[Path]:
    patches = project_patches(patch_dir)
    for path in patches:
        check_hunks(path)
    if machine == "LAVENDER":
        board = (patch_dir / "0082-lavender-board-profile.patch").read_text(encoding="utf-8")
        required = (
            "SUPPORTED_ARM64_MACHINE_CONFIGS = BCM2837 T6000 T8101 T8103 VMAPPLE SWEET LAVENDER",
            "MACHINE_FLAGS_ARM64_LAVENDER",
            "config/MASTER.arm64.lavender",
            "MASTER.arm64.sweet",
        )
        for needle in required:
            if needle not in board:
                fail(f"0082 lavender board profile lacks {needle!r}")
        for name, needles in REQUIRED_GUARDS.items():
            text = (patch_dir / name).read_text(encoding="utf-8")
            for needle in needles:
                if needle not in text:
                    fail(f"{name} lacks lavender guard {needle!r}")
        if "sweet_console_muted" not in (patch_dir / "0067-sweet-console-mute.patch").read_text(encoding="utf-8"):
            fail("console mute symbol definition is absent")
        if "sweet_sample_task" not in (patch_dir / "0054-sweet-process-sampler.patch").read_text(encoding="utf-8"):
            fail("process sampler symbol is absent")
    return patches


def check_tools(xnu_tree: Path | None) -> None:
    for tool in ("git", "python3", "bash"):
        if shutil.which(tool) is None:
            fail(f"required host tool is missing: {tool}")
    if xnu_tree is not None:
        if not (xnu_tree / ".git").exists():
            fail(f"XNU tree is not a git checkout: {xnu_tree}")


def check_application(xnu_tree: Path, patches: list[Path]) -> None:
    for path in patches:
        result = subprocess.run(
            ["git", "-C", str(xnu_tree), "apply", "--check", str(path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode:
            fail(f"patch does not apply: {path.name}\n{result.stdout.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-dir", type=Path, default=Path("xnu/patches"))
    parser.add_argument("--machine-config", choices=("SWEET", "LAVENDER"), default="LAVENDER")
    parser.add_argument("--xnu-tree", type=Path, help="optional prepared XNU checkout for git apply --check")
    args = parser.parse_args()
    if not args.patch_dir.is_dir():
        fail(f"patch directory does not exist: {args.patch_dir}")
    check_tools(args.xnu_tree)
    patches = check_static_inputs(args.patch_dir, args.machine_config)
    if args.xnu_tree:
        check_application(args.xnu_tree, patches)
        print(f"XNU preflight: {len(patches)} patches apply cleanly to {args.xnu_tree}")
    else:
        print(f"XNU preflight: {len(patches)} patches, {args.machine_config} config, static checks passed")
        if shutil.which("clang") is None:
            print("XNU preflight: clang unavailable; no local component compile performed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
