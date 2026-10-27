#!/usr/bin/env python3
"""Static regression test for the lavender XNU machine-config patch."""
import re
from pathlib import Path


PATCH = Path(__file__).parents[1] / "xnu/patches/0082-lavender-board-profile.patch"
PREFLIGHT = Path(__file__).parents[1] / "tools/preflight-xnu.py"
STRICTIFY = Path(__file__).parents[1] / "tools/strictify-dxb.py"
WORKFLOW = Path(__file__).parents[1] / ".github/workflows/xnu.yml"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def check_hunks(text):
    lines = text.splitlines()
    checked = 0
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
        assert (old_count, new_count) == (old_expected, new_expected), (
            f"{line}: declared {(old_expected, new_expected)}, "
            f"counted {(old_count, new_count)}"
        )
        checked += 1
    assert checked > 0


text = PATCH.read_text(encoding="utf-8")
assert PREFLIGHT.exists()
assert "--patch-dir" in PREFLIGHT.read_text(encoding="utf-8")
assert "sweet_console_muted" in PREFLIGHT.read_text(encoding="utf-8")
assert "sweet_sample_task" in PREFLIGHT.read_text(encoding="utf-8")
assert STRICTIFY.exists()
assert "Project patch failed" in STRICTIFY.read_text(encoding="utf-8")
assert "PROJECT_PATCH_LOG" in STRICTIFY.read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")
assert "tools/preflight-xnu.py --patch-dir dxb/patches" in workflow
assert "tools/strictify-dxb.py dxb/build.sh" in workflow
assert "dxb/.project-patches-applied" in workflow
assert "reverse --check" not in workflow
check_hunks(text)
assert "SUPPORTED_ARM64_MACHINE_CONFIGS = BCM2837 T6000 T8101 T8103 VMAPPLE SWEET LAVENDER" in text
assert "MACHINE_FLAGS_ARM64_LAVENDER" in text
assert "\\ No newline at end of file" in text
for path in (
    "xnu/patches/0019-sweet-builtin-pthread.patch",
    "xnu/patches/0020-sweet-portable-aes-cbc.patch",
):
    assert "SWEET LAVENDER" in Path(path).read_text(encoding="utf-8"), path
timer_patch = Path("xnu/patches/0017-sweet-device-tree-virtual-timer-irq.patch").read_text(encoding="utf-8")
assert "defined(SWEET) || defined(LAVENDER)" in timer_patch
assert "#if defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)" in timer_patch
crash_patch = Path("xnu/patches/0043-sweet-console-crash-log.patch").read_text(encoding="utf-8")
assert crash_patch.count("defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)") == 2
mute_patch = Path("xnu/patches/0067-sweet-console-mute.patch").read_text(encoding="utf-8")
assert mute_patch.count("defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)") == 2
log_patch = Path("xnu/patches/0047-sweet-persistent-console-log.patch").read_text(encoding="utf-8")
assert log_patch.count("defined(ARM64_BOARD_CONFIG_SWEET) || defined(ARM64_BOARD_CONFIG_LAVENDER)") == 2
for path in (
    "xnu/patches/0019-stage-libpthread.sh",
    "xnu/patches/0020-stage-bearssl.sh",
    "xnu/patches/0026-stage-hfs.sh",
):
    assert "== LAVENDER" in Path(path).read_text(encoding="utf-8"), path
print("XNU lavender machine-config patch test: PASS")
