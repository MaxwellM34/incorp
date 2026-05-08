#!/usr/bin/env python3
"""Generic round runner. Given a pool file, runs:
  1. RDAP .com check (parallel, ~10s)
  2. Corporations Canada federal-corp search (parallel, ~10s)
  3. Porkbun pricing on .com-AVAILABLE survivors (rate-limited, ~10s/name)
  4. Rebuilds data/master_list.{tsv,md}.

Usage:
  python3 run_round.py <pool_file>
  python3 run_round.py data/pool_v7.txt

Pool file format: tab-separated  `<category>\\t<name>` per line.
Outputs land at data/verified_v<N>.tsv, data/pricing_v<N>.tsv,
data/whois_available_v<N>.txt, data/verified_v<N>.md.
"""
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def slug(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def load_env():
    env = {}
    p = ROOT / ".env"
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


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


def fed_corp_search(name):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    try:
        r1 = s.get("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html",
                   params={"V_SEARCH.command": "navigate", "crpNm": name},
                   timeout=20)
        r2 = s.post(r1.url, data={
            "_pageFlowMap": "", "_page": "",
            "corpName": name, "corpNumber": "", "busNumber": "",
            "corpProvince": "", "corpStatus": "", "corpAct": "",
            "buttonNext": "Search",
        }, timeout=25)
        if r2.status_code != 200:
            return {"error": f"HTTP {r2.status_code}"}
        soup = BeautifulSoup(r2.text, "html.parser")
        main = soup.find("main") or soup.find("div", id="maincontent") or soup
        txt = main.get_text(" ", strip=True)
        m = re.search(r"(\d[\d,]*)\s+results?\s+(?:were|was)\s+found",
                      txt, re.I)
        total = int(m.group(1).replace(",", "")) if m else 0
        items = re.split(r"(?:^|\s)(\d+)\.\s+", txt)
        active, dissolved, samples = 0, 0, []
        for i in range(1, len(items) - 1, 2):
            if not items[i].isdigit():
                continue
            chunk = items[i + 1][:400]
            mname = re.match(
                r"(.+?)\s+Status:\s*(.+?)\s+Corporation number:\s*([\d-]+)",
                chunk)
            if mname:
                cstatus = mname.group(2).strip()
                if cstatus.lower().startswith("active"):
                    active += 1
                elif "dissolv" in cstatus.lower() or "inactive" in cstatus.lower():
                    dissolved += 1
                if len(samples) < 2:
                    samples.append(
                        f"{mname.group(1).strip()[:40]} ({cstatus[:20]})")
        return {"total": total, "active": active, "dissolved": dissolved,
                "samples": samples}
    except Exception as e:
        return {"error": f"{type(e).__name__}"}


def porkbun_price(domain, env, retries=3):
    if not env.get("PORKBUN_API_KEY") or not env.get("PORKBUN_SECRET_KEY"):
        return {"error": "no_keys"}
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
                time.sleep(wait)
                continue
            return {"error": d.get("message", "unknown")}
        except Exception as e:
            if attempt < retries:
                time.sleep(5)
                continue
            return {"error": f"{type(e).__name__}"}
    return {"error": "exhausted_retries"}


def run(pool_path):
    pool_path = Path(pool_path)
    if not pool_path.exists():
        print(f"pool file not found: {pool_path}", file=sys.stderr)
        sys.exit(1)
    m = re.search(r"pool_v(\d+)", pool_path.name)
    tag = f"v{m.group(1)}" if m else pool_path.stem.replace("pool_", "")
    verified_tsv = DATA / f"verified_{tag}.tsv"
    pricing_tsv = DATA / f"pricing_{tag}.tsv"
    whois_out = DATA / f"whois_available_{tag}.txt"
    md_out = DATA / f"verified_{tag}.md"

    pairs = []
    for line in pool_path.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            pairs.append((cat.strip(), name.strip()))
    print(f"=== round {tag}: {len(pairs)} names ===", flush=True)

    print(f"[1/3] RDAP .com on {len(pairs)} names...", flush=True)
    rdap = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as p:
        futs = {p.submit(rdap_check, n): (c, n) for c, n in pairs}
        for fut in as_completed(futs):
            _, d, status = fut.result()
            c, n = futs[fut]
            rdap[n] = (d, status)
    print(f"      done in {time.time()-t0:.1f}s", flush=True)

    print(f"[2/3] federal corp on {len(pairs)} names...", flush=True)
    fed = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as p:
        futs = {p.submit(fed_corp_search, n): (c, n) for c, n in pairs}
        for fut in as_completed(futs):
            c, n = futs[fut]
            fed[n] = fut.result()
    print(f"      done in {time.time()-t0:.1f}s", flush=True)

    rows = []
    for c, n in pairs:
        d, status = rdap[n]
        f = fed.get(n, {})
        rows.append({
            "category": c, "name": n, "domain": d, "whois_com": status,
            "fed_active": f.get("active") or 0,
            "fed_dissolved": f.get("dissolved") or 0,
            "fed_total": f.get("total") or 0,
            "fed_sample": ((f.get("samples") or [""])[0]
                           if f.get("samples") else ""),
            "fed_error": f.get("error") or "",
        })

    headers = ["category", "name", "domain", "whois_com",
               "fed_active", "fed_dissolved", "fed_total",
               "fed_sample", "fed_error"]
    with verified_tsv.open("w") as f:
        f.write("\t".join(headers) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(h, "")) for h in headers) + "\n")
    avail_rows = [r for r in rows if r["whois_com"] == "AVAILABLE"]
    whois_out.write_text("\n".join(
        f"{r['category']}\t{r['name']}\t{r['domain']}"
        for r in avail_rows) + "\n")
    print(f"      .com AVAILABLE: {len(avail_rows)}/{len(rows)}", flush=True)

    env = load_env()
    pricing = {}
    if env.get("PORKBUN_API_KEY") and avail_rows:
        print(f"[3/3] Porkbun pricing on {len(avail_rows)} survivors "
              f"(rate-limited 1/10s)...", flush=True)
        for i, r in enumerate(avail_rows, 1):
            t1 = time.time()
            p = porkbun_price(r["domain"], env)
            pricing[r["name"]] = p
            tag2 = (f"${p.get('price')}/yr renew=${p.get('renewal')} "
                    f"prem={p.get('premium')}"
                    if "error" not in p else f"ERR({p['error'][:25]})")
            print(f"   [{i:>3}/{len(avail_rows)}] {r['name']:<16} {tag2}",
                  flush=True)
            spent = time.time() - t1
            if spent < 10.5 and i < len(avail_rows):
                time.sleep(10.5 - spent)
    else:
        print("[3/3] Skipping Porkbun (no keys or no survivors)",
              flush=True)

    if pricing:
        pfields = ["category", "name", "domain", "whois_com", "fed_active",
                   "fed_total", "price", "regular", "renewal", "transfer",
                   "premium", "avail", "pork_error"]
        with pricing_tsv.open("w") as f:
            f.write("\t".join(pfields) + "\n")
            for r in avail_rows:
                p = pricing.get(r["name"], {})
                f.write("\t".join([
                    r["category"], r["name"], r["domain"], r["whois_com"],
                    str(r["fed_active"]), str(r["fed_total"]),
                    str(p.get("price") or ""), str(p.get("regular") or ""),
                    str(p.get("renewal") or ""), str(p.get("transfer") or ""),
                    str(p.get("premium") or ""), str(p.get("avail") or ""),
                    str(p.get("error") or ""),
                ]) + "\n")

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    md = [f"# Round {tag}: {len(rows)} candidates",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._",
          "",
          "Checks: RDAP for `.com`, Corporations Canada federal search, "
          "and Porkbun pricing on survivors.",
          ""]
    for cat in sorted(by_cat):
        md.append(f"## {cat}")
        md.append("")
        md.append("| Name | Domain | .com | $/yr | Renewal | Premium | "
                  "Fed Active | Fed Total | Sample |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        rs = sorted(by_cat[cat], key=lambda r: (
            0 if r["whois_com"] == "AVAILABLE" else 1,
            int(r.get("fed_active") or 0), r["name"]))
        for r in rs:
            p = pricing.get(r["name"], {})
            price = (f"${p.get('price')}"
                     if p.get("price") and "error" not in p else "")
            renew = f"${p.get('renewal')}" if p.get("renewal") else ""
            md.append(f"| {r['name']} | {r['domain']} | {r['whois_com']} | "
                      f"{price} | {renew} | {p.get('premium', '') or ''} | "
                      f"{r['fed_active']} | {r['fed_total']} | "
                      f"{(r['fed_sample'] or '')[:40]} |")
        md.append("")
    md_out.write_text("\n".join(md) + "\n")
    print(f"      wrote {verified_tsv}, {md_out}", flush=True)

    print("[4/4] rebuilding master_list.tsv/md...", flush=True)
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "build_master_list.py")],
                   check=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 run_round.py <pool_file>", file=sys.stderr)
        sys.exit(2)
    run(sys.argv[1])
