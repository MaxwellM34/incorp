#!/usr/bin/env python3
"""Round 3 pipeline. Reads pool_v3.txt, runs WHOIS filter, then live Porkbun
price + federal corp search on every WHOIS-available name.
Same logic as run_v2.py, just different input/output paths."""
import sys
sys.path.insert(0, "/Users/janchinapoo/max/incorp")
from pathlib import Path

# Reuse run_v2 internals by monkey-patching the module's path constants.
import run_v2

ROOT = Path("/Users/janchinapoo/max/incorp")
DATA = ROOT / "data"

run_v2.POOL = DATA / "pool_v3.txt"
run_v2.WHOIS_OUT = DATA / "whois_available_v3.txt"
run_v2.TSV_OUT = DATA / "verified_v3.tsv"
run_v2.MD_OUT = DATA / "verified_v3.md"

if __name__ == "__main__":
    run_v2.main()
