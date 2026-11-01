#!/usr/bin/env python3
"""Make the loader input: XNU payload followed by an untouched stock ramdisk."""
from pathlib import Path
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("payload", type=Path)
ap.add_argument("stock_ramdisk", type=Path)
ap.add_argument("output", type=Path)
a = ap.parse_args()
payload = a.payload.read_bytes()
stock = a.stock_ramdisk.read_bytes()
a.output.write_bytes(payload + stock)
print(f"payload={len(payload)} stock_ramdisk={len(stock)} combined={len(payload)+len(stock)}")
