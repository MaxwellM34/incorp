#!/usr/bin/env python3
"""Pass 1: WHOIS-only filter on the pool. Fast, no API keys needed.
Output: data/whois_available.txt (one cat\\tname per line)."""
import socket, re, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent
POOL = ROOT / "data" / "pool.txt"
OUT = ROOT / "data" / "whois_available.txt"
OUT_TAKEN = ROOT / "data" / "whois_taken.txt"


def slug(name): return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def whois(name):
    domain = slug(name) + ".com"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(12)
        s.connect(("whois.verisign-grs.com", 43))
        s.sendall((domain + "\r\n").encode())
        chunks = []
        while True:
            d = s.recv(4096)
            if not d: break
            chunks.append(d)
        s.close()
        text = b"".join(chunks).decode(errors="ignore").upper()
        if "NO MATCH FOR" in text or "NOT FOUND" in text:
            return name, domain, "AVAILABLE"
        if "DOMAIN NAME:" in text or "REGISTRAR:" in text:
            return name, domain, "TAKEN"
        return name, domain, "UNKNOWN"
    except Exception as e:
        return name, domain, f"ERR({type(e).__name__})"


def main():
    pairs = []
    for line in POOL.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            pairs.append((cat, name))
    print(f"checking {len(pairs)} names via WHOIS...", file=sys.stderr)
    start = time.time()
    avail, taken = [], []
    with ThreadPoolExecutor(max_workers=15) as pool:
        futs = {pool.submit(whois, n): (cat, n) for cat, n in pairs}
        done = 0
        for fut in as_completed(futs):
            name, domain, status = fut.result()
            cat, _ = futs[fut]
            if status == "AVAILABLE":
                avail.append((cat, name, domain))
            else:
                taken.append((cat, name, domain, status))
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(pairs)} ({time.time()-start:.1f}s)",
                      file=sys.stderr)
    avail.sort()
    taken.sort()
    OUT.write_text("\n".join(f"{c}\t{n}\t{d}" for c, n, d in avail) + "\n")
    OUT_TAKEN.write_text("\n".join(f"{c}\t{n}\t{d}\t{s}" for c, n, d, s in taken) + "\n")
    print(f"\nWHOIS pass done in {time.time()-start:.1f}s")
    print(f"  AVAILABLE: {len(avail)}")
    print(f"  TAKEN/UNKNOWN: {len(taken)}")
    print(f"  -> {OUT}")
    by_cat = {}
    for c, _, _ in avail:
        by_cat[c] = by_cat.get(c, 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat}: {n}")


if __name__ == "__main__":
    main()
