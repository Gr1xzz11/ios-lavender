#!/usr/bin/env python3
"""Make the pinned darwin-xnu-build fail closed for project patch failures."""
from pathlib import Path
import argparse


MARKER = 'if [[ "$(basename "$PATCH")" =~ ^[0-9]{4}-.*\\.patch$ ]]; then'
OLD = '            warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"'
NEW = """            if [[ \"$(basename \"$PATCH\")\" =~ ^[0-9]{4}-.*\\.patch$ ]]; then
                error \"Project patch failed: ${PATCH}: ${APPLY_CHECK}\"
                exit 1
            fi
            warning \"Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}\""""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("build_script", type=Path)
    args = parser.parse_args()
    text = args.build_script.read_text(encoding="utf-8")
    if MARKER in text:
        return 0
    if text.count(OLD) != 1:
        raise SystemExit("strictify-dxb: expected one patch warning site")
    args.build_script.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print(f"strictify-dxb: project patch failures are fatal in {args.build_script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
