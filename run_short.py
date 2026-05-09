#!/usr/bin/env python3
"""WHOIS + Porkbun pricing pass for the 4-5 letter short pool.
- Step 1: Verisign WHOIS for .com on all 1000 names (20 parallel workers).
- Step 2: Porkbun checkDomain on every WHOIS-AVAILABLE survivor (10s rate
  limit, sequential). Premium-priced names are flagged separately."""
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).parent
DATA = ROOT / "data"
POOL = DATA / "pool_short.txt"
WHOIS_OUT = DATA / "whois_available_short.txt"
TSV_OUT = DATA / "verified_short.tsv"
PRICING_TSV = DATA / "pricing_short.tsv"
PRICING_MD = DATA / "pricing_short.md"


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def slug(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


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
            if not d:
                break
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


def porkbun_price(domain, env, retries=3):
    url = f"https://api.porkbun.com/api/json/v3/domain/checkDomain/{domain}"
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
    pairs = []
    for line in POOL.read_text().splitlines():
        if "\t" in line:
            style, name = line.split("\t", 1)
            pairs.append((style, name))
    print(f"=== STEP 1: WHOIS .com on {len(pairs)} names ===", flush=True)
    start = time.time()
    whois_results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(whois, n): (s, n) for s, n in pairs}
        done = 0
        for fut in as_completed(futs):
            s, n = futs[fut]
            _, d, status = fut.result()
            whois_results[n] = (d, status)
            done += 1
            if done % 100 == 0:
                print(f"  whois {done}/{len(pairs)}  "
                      f"({time.time()-start:.0f}s)", flush=True)

    avail_all = [(s, n, whois_results[n][0]) for s, n in pairs
                 if whois_results[n][1] == "AVAILABLE"]
    avail_all.sort(key=lambda x: x[1])
    WHOIS_OUT.write_text(
        "\n".join(f"{s}\t{n}\t{d}" for s, n, d in avail_all) + "\n")
    # Skip random-letter combos for Porkbun pricing (they're unbrandable)
    avail = [(s, n, d) for s, n, d in avail_all
             if not s.startswith("rand")]
    skipped = len(avail_all) - len(avail)
    print(f"  {len(avail_all)}/{len(pairs)} cleared WHOIS in "
          f"{time.time()-start:.1f}s "
          f"(skipping {skipped} random for Porkbun)", flush=True)
    by_style = {}
    for s, _, _ in avail:
        by_style[s] = by_style.get(s, 0) + 1
    for st, n in sorted(by_style.items()):
        print(f"    {st}: {n}", flush=True)

    # Write full WHOIS TSV
    headers = ["style", "name", "domain", "whois_com", "length"]
    with TSV_OUT.open("w") as f:
        f.write("\t".join(headers) + "\n")
        for s, n in pairs:
            d, status = whois_results[n]
            f.write("\t".join([s, n, d, status, str(len(slug(n)))]) + "\n")

    if not avail:
        print("\nNo .com survivors - skipping Porkbun.")
        return

    print(f"\n=== STEP 2: Porkbun pricing on {len(avail)} survivors "
          f"(1 / 10s rate limit) ===", flush=True)
    print(f"    estimated time: {len(avail) * 10.5 / 60:.1f} min",
          flush=True)
    out = []
    pstart = time.time()
    for i, (s, n, d) in enumerate(avail, 1):
        t0 = time.time()
        p = porkbun_price(d, env)
        out.append({"style": s, "name": n, "domain": d, "pork": p})
        if "error" in p:
            tag = f"ERR({p['error'][:30]})"
        else:
            tag = (f"avail={p.get('avail')} ${p.get('price')}/yr "
                   f"renew=${p.get('renewal')} prem={p.get('premium')}")
        print(f"[{i:3}/{len(avail)}] {n:<8} {d:<14} {tag}", flush=True)
        spent = time.time() - t0
        if spent < 10.5 and i < len(avail):
            time.sleep(10.5 - spent)

    fields = ["style", "name", "domain", "price", "regular", "renewal",
              "transfer", "premium", "avail", "pork_error"]
    with PRICING_TSV.open("w") as f:
        f.write("\t".join(fields) + "\n")
        for r in out:
            p = r["pork"]
            f.write("\t".join([
                r["style"], r["name"], r["domain"],
                str(p.get("price") or ""),
                str(p.get("regular") or ""),
                str(p.get("renewal") or ""),
                str(p.get("transfer") or ""),
                str(p.get("premium") or ""),
                str(p.get("avail") or ""),
                str(p.get("error") or ""),
            ]) + "\n")

    # Build markdown report, splitting standard vs premium
    standard = [r for r in out
                if "error" not in r["pork"]
                and (r["pork"].get("premium") or "").lower() == "no"
                and (r["pork"].get("avail") or "").lower() == "yes"]
    premium = [r for r in out
               if "error" not in r["pork"]
               and (r["pork"].get("premium") or "").lower() == "yes"]
    other = [r for r in out if r not in standard and r not in premium]

    standard.sort(key=lambda r: (float(r["pork"].get("price") or 1e9),
                                 r["name"]))
    premium.sort(key=lambda r: float(r["pork"].get("price") or 1e9))

    md = ["# Short-name (4-5 letter) Porkbun pricing",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._",
          "",
          f"Pool: 1000 names (200 4-letter + 800 5-letter, mixed styles).",
          f"WHOIS .com survivors: **{len(avail)}**.",
          f"Standard-priced (non-premium, available): "
          f"**{len(standard)}**.",
          f"Premium-priced: **{len(premium)}**.",
          ""]
    if standard:
        md += ["## Standard pricing (buy these)",
               "",
               "| Name | Domain | Reg ($/yr) | Renewal | Transfer | "
               "Style |",
               "|---|---|---|---|---|---|"]
        for r in standard:
            p = r["pork"]
            md.append(f"| {r['name']} | {r['domain']} | "
                      f"${p.get('price')} | ${p.get('renewal')} | "
                      f"${p.get('transfer')} | {r['style']} |")
        md.append("")
    if premium:
        md += ["## Premium pricing (high-cost, FYI)",
               "",
               "| Name | Domain | Price ($/yr) | Renewal | Style |",
               "|---|---|---|---|---|"]
        for r in premium:
            p = r["pork"]
            md.append(f"| {r['name']} | {r['domain']} | "
                      f"${p.get('price')} | ${p.get('renewal')} | "
                      f"{r['style']} |")
        md.append("")
    if other:
        md += ["## Errors / unavailable", "",
               "| Name | Domain | Note |", "|---|---|---|"]
        for r in other:
            p = r["pork"]
            note = p.get("error") or f"avail={p.get('avail')}"
            md.append(f"| {r['name']} | {r['domain']} | {note} |")
        md.append("")

    PRICING_MD.write_text("\n".join(md) + "\n")
    print(f"\nDone in {(time.time()-start)/60:.1f} min")
    print(f"  WHOIS survivors:  {len(avail)}")
    print(f"  Standard $:       {len(standard)}")
    print(f"  Premium $:        {len(premium)}")
    print(f"  TSV:              {PRICING_TSV}")
    print(f"  MD:               {PRICING_MD}")


if __name__ == "__main__":
    main()
