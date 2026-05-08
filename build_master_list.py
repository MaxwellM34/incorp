#!/usr/bin/env python3
"""Build (and refresh) data/master_list.tsv & master_list.md.

Aggregates every name ever generated across rounds 1..N into a single,
deduplicated table with the best-known check results for each name.

Inputs (auto-discovered):
  - data/pool.txt, pool_v2.txt, pool_v3.txt, pool_v4.txt, pool_v5.txt,
    pool_v6.txt, ... pool_v<N>.txt
  - data/verified.tsv, verified_v2.tsv, verified_v4.tsv, verified_v5.tsv,
    verified_v6.tsv  (Porkbun + fed)
  - data/fast_verified.tsv  (fed only)
  - data/pricing_v<N>.tsv  (Porkbun pricing patches)

Run any time after a new round completes; existing entries are preserved
and freshly verified data overwrites stale fields.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
MASTER_TSV = DATA / "master_list.tsv"
MASTER_MD = DATA / "master_list.md"

FIELDS = [
    "name", "domain", "category", "rounds",
    "com_status",       # AVAILABLE / TAKEN / unknown
    "price",            # Porkbun reg $/yr (if priced)
    "renewal",
    "premium",
    "fed_active",
    "fed_dissolved",
    "fed_total",
    "fed_sample",
    "verdict",          # CLEAR / TAKEN / CONFLICT / UNKNOWN
]


def slug(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def load_pool(path, round_tag):
    """yield (category, name, round_tag) tuples from a pool file."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            yield cat.strip(), name.strip(), round_tag


def read_tsv(path):
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def merge(rows_by_name, key, **patch):
    """Update master row, only overwriting with non-empty new values."""
    cur = rows_by_name.setdefault(key, {f: "" for f in FIELDS})
    for k, v in patch.items():
        if v in (None, ""):
            continue
        if k == "rounds":
            existing = set(filter(None, (cur.get("rounds") or "").split(",")))
            existing.add(v)
            cur["rounds"] = ",".join(sorted(existing))
        else:
            cur[k] = str(v)


def derive_verdict(r):
    com = (r.get("com_status") or "").upper()
    fed_active = int(r.get("fed_active") or 0)
    if com == "AVAILABLE" and fed_active == 0:
        return "CLEAR"
    if com == "TAKEN":
        return "TAKEN"
    if fed_active > 0:
        return "CORP_CONFLICT"
    return "UNKNOWN"


def main():
    rows = {}

    pool_files = [
        (DATA / "pool.txt",    "v1"),
        (DATA / "pool_v2.txt", "v2"),
        (DATA / "pool_v3.txt", "v3"),
        (DATA / "pool_v4.txt", "v4"),
        (DATA / "pool_v5.txt", "v5"),
        (DATA / "pool_v6.txt", "v6"),
    ]
    extras = sorted(DATA.glob("pool_v[0-9]*.txt"))
    for p in extras:
        m = re.search(r"pool_v(\d+)", p.name)
        if not m:
            continue
        tag = f"v{m.group(1)}"
        if (p, tag) not in pool_files:
            pool_files.append((p, tag))

    for path, tag in pool_files:
        for cat, name, rt in load_pool(path, tag):
            merge(rows, name, name=name, domain=slug(name) + ".com",
                  category=cat, rounds=rt)

    # verified.tsv: full schema with porkbun + fed
    for r in read_tsv(DATA / "verified.tsv"):
        n = r.get("name")
        if not n:
            continue
        avail = (r.get("porkbun_avail") or "").lower()
        com = ("AVAILABLE" if avail == "yes" else
               "TAKEN" if avail == "no" else "")
        merge(rows, n, name=n, domain=r.get("domain"),
              category=r.get("category"),
              com_status=com,
              price=r.get("porkbun_price"),
              renewal=r.get("porkbun_renewal"),
              premium=r.get("porkbun_premium"),
              fed_active=r.get("fed_active"),
              fed_dissolved=r.get("fed_dissolved"),
              fed_total=r.get("fed_total"),
              fed_sample=(r.get("fed_samples") or
                          (r.get("fed_sample") or "")).split("|")[0])

    # v2/v4/v5: porkbun price implies AVAILABLE (those pipelines pre-filtered)
    for tag, fn in [("v2", "verified_v2.tsv"),
                    ("v4", "verified_v4.tsv"),
                    ("v5", "verified_v5.tsv")]:
        for r in read_tsv(DATA / fn):
            n = r.get("name")
            if not n:
                continue
            com = "AVAILABLE" if r.get("price") else ""
            merge(rows, n, name=n, domain=r.get("domain"),
                  category=r.get("category"),
                  com_status=com,
                  price=r.get("price"),
                  renewal=r.get("renewal"),
                  premium=r.get("premium"),
                  fed_active=r.get("fed_active"),
                  fed_dissolved=r.get("fed_dissolved"),
                  fed_total=r.get("fed_total"),
                  fed_sample=r.get("fed_sample"))

    # v6: full RDAP-based whois_com status
    for r in read_tsv(DATA / "verified_v6.tsv"):
        n = r.get("name")
        if not n:
            continue
        com = (r.get("whois_com") or "").upper()
        if not com.startswith(("AVAILABLE", "TAKEN")):
            com = ""
        else:
            com = "AVAILABLE" if com.startswith("AVAILABLE") else "TAKEN"
        merge(rows, n, name=n, domain=r.get("domain"),
              category=r.get("category"),
              com_status=com,
              fed_active=r.get("fed_active"),
              fed_dissolved=r.get("fed_dissolved"),
              fed_total=r.get("fed_total"),
              fed_sample=r.get("fed_sample"))

    # fast_verified.tsv: fed only
    for r in read_tsv(DATA / "fast_verified.tsv"):
        n = r.get("name")
        if not n:
            continue
        merge(rows, n, name=n, domain=r.get("domain"),
              category=r.get("category"),
              fed_active=r.get("fed_active"),
              fed_dissolved=r.get("fed_dissolved"),
              fed_total=r.get("fed_total"),
              fed_sample=r.get("fed_sample"))

    # pricing_v*.tsv: Porkbun pricing patches
    for p in sorted(DATA.glob("pricing_v*.tsv")):
        for r in read_tsv(p):
            n = r.get("name")
            if not n:
                continue
            avail = (r.get("avail") or "").lower()
            com = ("AVAILABLE" if avail == "yes" else
                   "TAKEN" if avail == "no" else
                   r.get("whois_com") or "")
            merge(rows, n,
                  com_status=com,
                  price=r.get("price"),
                  renewal=r.get("renewal"),
                  premium=r.get("premium"),
                  fed_active=r.get("fed_active"),
                  fed_total=r.get("fed_total"))

    for r in rows.values():
        r["verdict"] = derive_verdict(r)

    sorted_rows = sorted(rows.values(),
                         key=lambda r: (r["name"].lower()))

    with MASTER_TSV.open("w") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for r in sorted_rows:
            w.writerow(r)

    by_verdict = {}
    by_round = {}
    for r in sorted_rows:
        by_verdict.setdefault(r["verdict"], []).append(r)
        for rd in (r.get("rounds") or "").split(","):
            if rd:
                by_round[rd] = by_round.get(rd, 0) + 1

    md = ["# Master list — all names generated across rounds 1..N",
          "",
          f"Total unique names: **{len(sorted_rows)}**",
          ""]
    md.append("## Counts by round")
    md.append("")
    md.append("| Round | Names |")
    md.append("|---|---|")
    for k in sorted(by_round, key=lambda x: int(x[1:])):
        md.append(f"| {k} | {by_round[k]} |")
    md.append("")
    md.append("## Counts by verdict")
    md.append("")
    md.append("| Verdict | Count |")
    md.append("|---|---|")
    for v in ("CLEAR", "TAKEN", "CORP_CONFLICT", "UNKNOWN"):
        md.append(f"| {v} | {len(by_verdict.get(v, []))} |")
    md.append("")
    md.append("## CLEAR (.com available + 0 active fed corp)")
    md.append("")
    md.append("| Name | Domain | $/yr | Renewal | Premium | Fed Total | "
              "Category | Rounds |")
    md.append("|---|---|---|---|---|---|---|---|")
    clear = sorted(by_verdict.get("CLEAR", []), key=lambda r: r["name"])
    for r in clear:
        price = f"${r['price']}" if r.get("price") else ""
        renew = f"${r['renewal']}" if r.get("renewal") else ""
        md.append(f"| {r['name']} | {r['domain']} | {price} | {renew} | "
                  f"{r.get('premium', '')} | {r.get('fed_total', 0)} | "
                  f"{r.get('category', '')} | {r.get('rounds', '')} |")
    md.append("")
    md.append("## All names (alphabetical)")
    md.append("")
    md.append("| Name | Domain | .com | Verdict | Fed Active | $/yr | "
              "Category | Rounds |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in sorted_rows:
        price = f"${r['price']}" if r.get("price") else ""
        md.append(f"| {r['name']} | {r['domain']} | "
                  f"{r.get('com_status', '')} | "
                  f"{r['verdict']} | {r.get('fed_active', 0)} | {price} | "
                  f"{r.get('category', '')} | {r.get('rounds', '')} |")
    md.append("")
    MASTER_MD.write_text("\n".join(md) + "\n")
    print(f"Wrote {MASTER_TSV} ({len(sorted_rows)} unique names)")
    print(f"Wrote {MASTER_MD}")
    print("By verdict:")
    for v in ("CLEAR", "TAKEN", "CORP_CONFLICT", "UNKNOWN"):
        print(f"  {v}: {len(by_verdict.get(v, []))}")


if __name__ == "__main__":
    main()
