#!/usr/bin/env python3
"""Combine the long-name picks (data/possible_options.tsv) and the short-name
picks (data/picks_short.tsv) into a single sorted shortlist.

Outputs:
  data/shortlist_combined.tsv
  data/shortlist_combined.md
"""
import csv
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
LONG = DATA / "possible_options.tsv"
SHORT = DATA / "picks_short.tsv"
OUT_TSV = DATA / "shortlist_combined.tsv"
OUT_MD = DATA / "shortlist_combined.md"

FIELDS = ["name", "domain", "length", "price", "renewal", "premium",
          "source", "category_or_style", "rounds", "fed_active",
          "fed_total", "decided_at"]


def load_long():
    if not LONG.exists():
        return []
    out = []
    with LONG.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if not r.get("name"):
                continue
            out.append({
                "name": r["name"],
                "domain": r.get("domain", ""),
                "length": str(len(r["name"])),
                "price": r.get("price", ""),
                "renewal": r.get("renewal", ""),
                "premium": r.get("premium", ""),
                "source": "long",
                "category_or_style": r.get("category", ""),
                "rounds": r.get("rounds", ""),
                "fed_active": r.get("fed_active", "0"),
                "fed_total": r.get("fed_total", "0"),
                "decided_at": r.get("decided_at", ""),
            })
    return out


def load_short():
    if not SHORT.exists():
        return []
    out = []
    with SHORT.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if not r.get("name"):
                continue
            out.append({
                "name": r["name"],
                "domain": r.get("domain", ""),
                "length": r.get("length", str(len(r["name"]))),
                "price": r.get("price", ""),
                "renewal": r.get("renewal", ""),
                "premium": r.get("premium", ""),
                "source": "short",
                "category_or_style": r.get("style", ""),
                "rounds": "",
                "fed_active": "",
                "fed_total": "",
                "decided_at": r.get("decided_at", ""),
            })
    return out


def main():
    rows = load_long() + load_short()
    rows.sort(key=lambda r: (int(r["length"]), r["name"].lower()))

    with OUT_TSV.open("w") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    n_short = sum(1 for r in rows if r["source"] == "short")
    n_long = sum(1 for r in rows if r["source"] == "long")
    by_len = {}
    for r in rows:
        by_len[r["length"]] = by_len.get(r["length"], 0) + 1

    md = ["# Combined shortlist", "",
          f"Total picks: **{len(rows)}**  "
          f"({n_short} short + {n_long} long)", "",
          "By length: " + ", ".join(
              f"{k} letters: {by_len[k]}"
              for k in sorted(by_len, key=int)),
          "",
          "All picks sorted by length, then alphabetically.",
          "",
          "| # | Name | Domain | Len | $/yr | Renew | Prem | "
          "Source | Category / Style | Fed Active |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        price = f"${r['price']}" if r.get("price") else "—"
        renew = f"${r['renewal']}" if r.get("renewal") else "—"
        prem = r.get("premium") or "—"
        fed = r.get("fed_active") or "—"
        md.append(f"| {i} | **{r['name']}** | {r['domain']} | "
                  f"{r['length']} | {price} | {renew} | {prem} | "
                  f"{r['source']} | {r['category_or_style']} | {fed} |")
    md.append("")

    OUT_MD.write_text("\n".join(md) + "\n")
    print(f"Wrote {len(rows)} picks")
    print(f"  TSV: {OUT_TSV}")
    print(f"  MD:  {OUT_MD}")
    print(f"  short: {n_short}, long: {n_long}")
    for k in sorted(by_len, key=int):
        print(f"    {k} letters: {by_len[k]}")


if __name__ == "__main__":
    main()
