#!/usr/bin/env bash
set -euo pipefail

out=${1:-"research/lavender/.artifacts/recovery-pmsg-capture-$(date +%Y%m%d-%H%M%S)"}
mkdir -p "$out"

adb devices >"$out/adb-devices.txt"
adb shell 'uname -a' >"$out/uname.txt" 2>&1 || true
adb shell 'dmesg | tail -n 400' >"$out/dmesg-tail.txt" 2>&1 || true
adb shell 'ls -la /sys/fs/pstore' >"$out/pstore-list.txt" 2>&1 || true
adb shell 'cat /proc/config.gz' >"$out/config.gz" 2>"$out/config.err" || true
adb shell 'ls -l /dev/pmsg0 /dev/pmsg*' >"$out/pmsg-devices.txt" 2>&1 || true
adb shell 'cat /proc/mounts' >"$out/mounts.txt" 2>&1 || true
adb shell 'cat /proc/iomem' >"$out/iomem.txt" 2>&1 || true
adb shell 'cat /sys/module/ramoops/parameters/*' >"$out/ramoops-parameters.txt" 2>&1 || true

for name in pmsg-ramoops-0 console-ramoops-0 dmesg-ramoops-0 ftrace-ramoops-0; do
    adb exec-out "cat /sys/fs/pstore/$name" >"$out/$name" 2>"$out/$name.err" || true
done

sha256sum "$out"/* >"$out/SHA256SUMS" 2>/dev/null || true
echo "$out"
