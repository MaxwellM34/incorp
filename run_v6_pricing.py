#!/usr/bin/env python3
"""Porkbun pricing pass for v6 .com-AVAILABLE survivors."""
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent
DATA = ROOT / "data"
TSV = DATA / "verified_v6.tsv"
PRICING_TSV = DATA / "pricing_v6.tsv"
PRICING_MD = DATA / "pricing_v6.md"


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def porkbun_price(domain, env, retries=3):
    url = (f"https://api.porkbun.com/api/json/v3/domain/checkDomain/"
           f"{domain}")
    body = {"apikey": env["PORKBUN_API_KEY"],
            "secretapikey": env["PORKBUN_SECRET_KEY"]}
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=body, timeout=30)
            d = r.json()
            if d.get("status") == "SUCCESS":
                resp = d["response"]
                return {
                    "avail": resp.get("avail"),
                    "price": resp.get("price"),
                    "premium": resp.get("premium"),
                    "regular": resp.get("regularPrice"),
                    "renewal": (resp.get("additional", {}) or {})
                                  .get("renewal", {}).get("price"),
                    "transfer": (resp.get("additional", {}) or {})
                                  .get("transfer", {}).get("price"),
                }
            if d.get("code") == "RATE_LIMIT_EXCEEDED":
                wait = int(d.get("ttlRemaining") or 10) + 1
                print(f"    rate-limit, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            return {"error": d.get("message", "unknown")}
        except Exception as e:
            if attempt < retries:
                time.sleep(5)
                continue
            return {"error": f"{type(e).__name__}"}
    return {"error": "exhausted_retries"}


def main():
    env = load_env()
    rows = []
    with TSV.open() as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            r = dict(zip(header, parts))
            if r.get("whois_com") == "AVAILABLE":
                rows.append(r)
    print(f"=== Porkbun pricing on {len(rows)} survivors "
          f"(rate-limited 1 / 10s) ===", flush=True)
    out = []
    start = time.time()
    for i, r in enumerate(rows, 1):
        t0 = time.time()
        p = porkbun_price(r["domain"], env)
        out.append({**r, "pork": p})
        if "error" in p:
            tag = f"ERR({p['error'][:30]})"
        else:
            tag = (f"avail={p.get('avail')} ${p.get('price')}/yr "
                   f"renew=${p.get('renewal')} prem={p.get('premium')}")
        print(f"[{i:2}/{len(rows)}] {r['name']:<14} {r['domain']:<20} "
              f"{tag}", flush=True)
        spent = time.time() - t0
        if spent < 10.5 and i < len(rows):
            time.sleep(10.5 - spent)

    fields = ["category", "name", "domain", "whois_com", "fed_active",
              "fed_total", "price", "regular", "renewal", "transfer",
              "premium", "avail", "pork_error"]
    with PRICING_TSV.open("w") as f:
        f.write("\t".join(fields) + "\n")
        for r in out:
            p = r["pork"]
            f.write("\t".join([
                r.get("category", ""), r["name"], r["domain"],
                r.get("whois_com", ""), r.get("fed_active") or "0",
                r.get("fed_total") or "0",
                str(p.get("price") or ""),
                str(p.get("regular") or ""),
                str(p.get("renewal") or ""),
                str(p.get("transfer") or ""),
                str(p.get("premium") or ""),
                str(p.get("avail") or ""),
                str(p.get("error") or ""),
            ]) + "\n")

    md = ["# v6 Porkbun pricing (25 .com-AVAILABLE survivors)",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._",
          "",
          "| Name | Domain | Reg ($/yr) | Renewal | Transfer | Premium | "
          "Avail | Category |",
          "|---|---|---|---|---|---|---|---|"]
    out.sort(key=lambda r: (
        float(r["pork"].get("price") or 1e9),
        r["name"]))
    for r in out:
        p = r["pork"]
        if "error" in p:
            md.append(f"| {r['name']} | {r['domain']} | "
                      f"`{p['error'][:25]}` |  |  |  |  | "
                      f"{r.get('category', '')} |")
            continue
        md.append(f"| {r['name']} | {r['domain']} | "
                  f"${p.get('price')} | "
                  f"${p.get('renewal')} | "
                  f"${p.get('transfer')} | "
                  f"{p.get('premium')} | "
                  f"{p.get('avail')} | "
                  f"{r.get('category', '')} |")
    PRICING_MD.write_text("\n".join(md) + "\n")
    print(f"\nDone in {(time.time()-start)/60:.1f} min")
    print(f"  TSV: {PRICING_TSV}")
    print(f"  MD:  {PRICING_MD}")


if __name__ == "__main__":
    main()
