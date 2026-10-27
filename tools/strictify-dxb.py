#!/usr/bin/env python3
"""Make the pinned darwin-xnu-build fail closed for project patch failures."""
from pathlib import Path
import argparse


MARKER = 'if [[ "$(basename "$PATCH")" =~ ^[0-9]{4}-.*\\.patch$ ]]; then'
LOG_MARKER = 'PROJECT_PATCH_LOG="${WORK_DIR}/.project-patches-applied"'
OLD = '            warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"'
LOOP = '        for PATCH in "${PATCH_DIR}"/*.patch; do'
APPLY = '                git apply "$PATCH"'
NEW = """            if [[ \"$(basename \"$PATCH\")\" =~ ^[0-9]{4}-.*\\.patch$ ]]; then
                error \"Project patch failed: ${PATCH}: ${APPLY_CHECK}\"
                exit 1
            fi
            warning \"Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}\""""
LOG_INIT = '        PROJECT_PATCH_LOG="${WORK_DIR}/.project-patches-applied"\n        : > "${PROJECT_PATCH_LOG}"\n' + LOOP
LOG_APPLY = APPLY + "\n                if [[ \"$(basename \"$PATCH\")\" =~ ^[0-9]{4}-.*\\.patch$ ]]; then\n                    printf '%s\\n' \"$(basename \"$PATCH\")\" >> \"${PROJECT_PATCH_LOG}\"\n                fi"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("build_script", type=Path)
    args = parser.parse_args()
    text = args.build_script.read_text(encoding="utf-8")
    if MARKER in text and LOG_MARKER in text:
        return 0
    if text.count(OLD) != 1:
        raise SystemExit("strictify-dxb: expected one patch warning site")
    if text.count(LOOP) != 1 or text.count(APPLY) != 1:
        raise SystemExit("strictify-dxb: expected one patch loop and apply site")
    text = text.replace(LOOP, LOG_INIT, 1)
    text = text.replace(APPLY, LOG_APPLY, 1)
    text = text.replace(OLD, NEW, 1)
    args.build_script.write_text(text, encoding="utf-8")
    print(f"strictify-dxb: project patch failures are fatal in {args.build_script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
