#!/usr/bin/env python3
"""Round 6 part B: RDAP-based .com availability check (port 43 blocked).
Merges into existing verified_v6.tsv and rewrites markdown."""
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ROOT = Path(__file__).parent
DATA = ROOT / "data"
POOL = DATA / "pool_v6.txt"
TSV = DATA / "verified_v6.tsv"
WHOIS_OUT = DATA / "whois_available_v6.txt"
MD_OUT = DATA / "verified_v6.md"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def slug(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def rdap_check(name):
    domain = slug(name) + ".com"
    url = f"https://rdap.verisign.com/com/v1/domain/{domain}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=15,
                             headers={"User-Agent": UA,
                                      "Accept": "application/rdap+json"})
            if r.status_code == 404:
                return name, domain, "AVAILABLE"
            if r.status_code == 200:
                return name, domain, "TAKEN"
            if r.status_code == 503:
                time.sleep(2 ** attempt)
                continue
            return name, domain, f"HTTP {r.status_code}"
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return name, domain, f"ERR({type(e).__name__})"
    return name, domain, "UNKNOWN"


def main():
    pairs = []
    for line in POOL.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            pairs.append((cat, name))
    print(f"=== RDAP .com check on {len(pairs)} names ===", flush=True)
    start = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(rdap_check, n): (c, n) for c, n in pairs}
        done = 0
        for fut in as_completed(futs):
            _, d, status = fut.result()
            c, n = futs[fut]
            results[n] = (d, status)
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(pairs)}  ({time.time()-start:.0f}s)",
                      flush=True)

    avail = [(c, n, results[n][0]) for c, n in pairs
             if results[n][1] == "AVAILABLE"]
    avail.sort(key=lambda x: x[1])
    WHOIS_OUT.write_text(
        "\n".join(f"{c}\t{n}\t{d}" for c, n, d in avail) + "\n")
    by_status = {}
    for n in results:
        s = results[n][1]
        by_status[s] = by_status.get(s, 0) + 1
    print(f"  done in {time.time()-start:.1f}s")
    for s, c in sorted(by_status.items()):
        print(f"    {s}: {c}")

    rows = []
    with TSV.open() as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            row = dict(zip(header, parts))
            row["whois_com"] = results.get(row["name"], ("", ""))[1]
            rows.append(row)

    with TSV.open("w") as f:
        f.write("\t".join(header) + "\n")
        for r in rows:
            f.write("\t".join(r.get(h, "") for h in header) + "\n")

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    md = ["# Round 6: 100 fresh tech-name candidates",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._",
          "",
          "Checks: RDAP for `.com` registration and Corporations Canada "
          "federal search.",
          ""]
    for cat in sorted(by_cat):
        md.append(f"## {cat}")
        md.append("")
        md.append("| Name | Domain | .com | Fed Active | Fed Dissolved | "
                  "Fed Total | Sample |")
        md.append("|---|---|---|---|---|---|---|")
        rs = sorted(by_cat[cat], key=lambda r: (
            0 if r["whois_com"] == "AVAILABLE" else 1,
            int(r.get("fed_active") or 0),
            r["name"]))
        for r in rs:
            md.append(f"| {r['name']} | {r['domain']} | {r['whois_com']} | "
                      f"{r.get('fed_active') or 0} | "
                      f"{r.get('fed_dissolved') or 0} | "
                      f"{r.get('fed_total') or 0} | "
                      f"{(r.get('fed_sample') or '')[:40]} |")
        md.append("")

    md.append("## Top picks (.com AVAILABLE + 0 active federal corp)")
    md.append("")
    md.append("| Name | Domain | Category | Fed Total |")
    md.append("|---|---|---|---|")
    clean = [r for r in rows
             if r["whois_com"] == "AVAILABLE"
             and int(r.get("fed_active") or 0) == 0]
    for r in sorted(clean, key=lambda x: (int(x.get("fed_total") or 0),
                                          x["name"])):
        md.append(f"| {r['name']} | {r['domain']} | {r['category']} | "
                  f"{r.get('fed_total') or 0} |")
    md.append("")

    MD_OUT.write_text("\n".join(md) + "\n")
    print(f"\n  TSV: {TSV}")
    print(f"  MD:  {MD_OUT}")
    print(f"  AVAILABLE + 0 active fed: {len(clean)}")


if __name__ == "__main__":
    main()
