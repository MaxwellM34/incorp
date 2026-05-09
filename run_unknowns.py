#!/usr/bin/env python3
"""Run all checks on every UNKNOWN name in master_list.tsv.

Pipeline:
  STEP A — WHOIS .com (Verisign socket, 20 parallel workers)
  STEP B — Federal corp search (Corporations Canada, 8 parallel workers)
  STEP C — Write data/verified_v7.tsv  (v6 schema: whois_com + fed)
  STEP D — Porkbun pricing on AVAILABLE survivors  (rate-limited 1 / 10.5s)
  STEP E — Write data/pricing_v7.tsv
  STEP F — Refresh master via build_master_list.py

After this finishes, every UNKNOWN will be reclassified as CLEAR / TAKEN /
CORP_CONFLICT (or remain UNKNOWN only on transient errors), and any new
CLEAR rows will appear in the picker queue automatically.
"""
import csv
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
MASTER = DATA / "master_list.tsv"
VERIFIED_OUT = DATA / "verified_v7.tsv"
PRICING_OUT = DATA / "pricing_v7.tsv"
LOG = DATA / "run_unknowns.log"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

PORKBUN_GAP_S = 10.5  # API allows ~1 req / 10s


def slug(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


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
        m = re.search(r"(\d[\d,]*)\s+results?\s+(?:were|was)\s+found", txt, re.I)
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


def load_unknowns():
    rows = []
    with MASTER.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            verdict = (r.get("verdict") or "").strip().upper()
            if verdict == "UNKNOWN":
                rows.append({
                    "name": r["name"],
                    "domain": r.get("domain") or slug(r["name"]) + ".com",
                    "category": r.get("category") or "",
                })
    return rows


def main():
    env = load_env()
    rows = load_unknowns()
    print(f"[run_unknowns] loaded {len(rows)} UNKNOWN names from master",
          flush=True)
    if not rows:
        print("nothing to do — exiting")
        return

    # ------------------------------------------------------------------
    # STEP A — WHOIS
    # ------------------------------------------------------------------
    t0 = time.time()
    print(f"\n=== STEP A: WHOIS .com on {len(rows)} names ===", flush=True)
    whois_results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(whois, r["name"]): r for r in rows}
        done = 0
        for fut in as_completed(futs):
            r = futs[fut]
            _, dom, status = fut.result()
            whois_results[r["name"]] = (dom, status)
            done += 1
            if done % 100 == 0:
                print(f"  whois {done}/{len(rows)}  "
                      f"({time.time()-t0:.0f}s)", flush=True)
    avail = sum(1 for v in whois_results.values() if v[1] == "AVAILABLE")
    taken = sum(1 for v in whois_results.values() if v[1] == "TAKEN")
    err = len(whois_results) - avail - taken
    print(f"  whois done in {time.time()-t0:.1f}s  "
          f"AVAILABLE={avail}  TAKEN={taken}  other={err}", flush=True)

    # ------------------------------------------------------------------
    # STEP B — Federal corp search
    # ------------------------------------------------------------------
    t1 = time.time()
    print(f"\n=== STEP B: federal corp search on {len(rows)} names ===",
          flush=True)
    fed_results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fed_corp_search, r["name"]): r for r in rows}
        done = 0
        for fut in as_completed(futs):
            r = futs[fut]
            fed_results[r["name"]] = fut.result()
            done += 1
            if done % 25 == 0:
                print(f"  fed {done}/{len(rows)}  "
                      f"({time.time()-t1:.0f}s)", flush=True)
    print(f"  fed done in {time.time()-t1:.1f}s", flush=True)

    # ------------------------------------------------------------------
    # STEP C — Write verified_v7.tsv (v6 schema)
    # ------------------------------------------------------------------
    headers = ["category", "name", "domain", "whois_com",
               "fed_active", "fed_dissolved", "fed_total",
               "fed_sample", "fed_error"]
    with VERIFIED_OUT.open("w") as f:
        f.write("\t".join(headers) + "\n")
        for r in rows:
            d, status = whois_results.get(r["name"], (r["domain"], ""))
            fd = fed_results.get(r["name"], {}) or {}
            samples = fd.get("samples") or []
            sample = samples[0] if samples else ""
            f.write("\t".join([
                r["category"], r["name"], d, status,
                str(fd.get("active") or 0),
                str(fd.get("dissolved") or 0),
                str(fd.get("total") or 0),
                sample,
                str(fd.get("error") or ""),
            ]) + "\n")
    print(f"  wrote {VERIFIED_OUT}", flush=True)

    # ------------------------------------------------------------------
    # STEP D — Porkbun pricing on AVAILABLE survivors with 0 active fed
    # ------------------------------------------------------------------
    survivors = []
    for r in rows:
        _, st = whois_results.get(r["name"], ("", ""))
        fd = fed_results.get(r["name"], {}) or {}
        if st == "AVAILABLE" and (fd.get("active") or 0) == 0:
            survivors.append(r)
    print(f"\n=== STEP D: Porkbun pricing on {len(survivors)} survivors "
          f"(rate-limited 1 / {PORKBUN_GAP_S:.1f}s, "
          f"~{len(survivors) * PORKBUN_GAP_S / 60:.1f} min) ===", flush=True)

    pricing_rows = []
    t2 = time.time()
    for i, r in enumerate(survivors, 1):
        t_start = time.time()
        d, _ = whois_results[r["name"]]
        p = porkbun_price(d, env)
        fd = fed_results.get(r["name"], {}) or {}
        pricing_rows.append({
            **r, "domain": d, "fed_active": fd.get("active") or 0,
            "fed_total": fd.get("total") or 0, "pork": p,
        })
        if "error" in p:
            tag = f"ERR({p['error'][:30]})"
        else:
            tag = (f"avail={p.get('avail')} ${p.get('price')}/yr "
                   f"renew=${p.get('renewal')} prem={p.get('premium')}")
        print(f"  [{i:3}/{len(survivors)}] {r['name']:<18} "
              f"{d:<28} {tag}", flush=True)
        spent = time.time() - t_start
        if spent < PORKBUN_GAP_S and i < len(survivors):
            time.sleep(PORKBUN_GAP_S - spent)
    print(f"  pricing done in {(time.time()-t2)/60:.1f} min", flush=True)

    fields = ["category", "name", "domain", "whois_com", "fed_active",
              "fed_total", "price", "regular", "renewal", "transfer",
              "premium", "avail", "pork_error"]
    with PRICING_OUT.open("w") as f:
        f.write("\t".join(fields) + "\n")
        for r in pricing_rows:
            p = r["pork"]
            f.write("\t".join([
                r.get("category", ""), r["name"], r["domain"],
                "AVAILABLE", str(r.get("fed_active") or 0),
                str(r.get("fed_total") or 0),
                str(p.get("price") or ""),
                str(p.get("regular") or ""),
                str(p.get("renewal") or ""),
                str(p.get("transfer") or ""),
                str(p.get("premium") or ""),
                str(p.get("avail") or ""),
                str(p.get("error") or ""),
            ]) + "\n")
    print(f"  wrote {PRICING_OUT}", flush=True)

    # ------------------------------------------------------------------
    # STEP E — refresh master so picker sees the new CLEARs
    # ------------------------------------------------------------------
    print("\n=== STEP E: refreshing master_list ===", flush=True)
    res = subprocess.run(
        [sys.executable, str(ROOT / "build_master_list.py")],
        cwd=str(ROOT), capture_output=True, text=True)
    print(res.stdout, end="", flush=True)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr, flush=True)
        sys.exit(res.returncode)

    print(f"\nALL DONE in {(time.time()-t0)/60:.1f} min total", flush=True)
    print(f"  verified TSV: {VERIFIED_OUT}")
    print(f"  pricing  TSV: {PRICING_OUT}")
    print(f"  master refreshed — re-run pick_names.py to see new CLEARs.")


if __name__ == "__main__":
    main()
