#!/usr/bin/env python3
"""Round 6: WHOIS .com + federal corp search for 100 fresh names.
Skips Porkbun (no API secret available)."""
import socket
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
POOL = DATA / "pool_v6.txt"
WHOIS_OUT = DATA / "whois_available_v6.txt"
TSV_OUT = DATA / "verified_v6.tsv"
MD_OUT = DATA / "verified_v6.md"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


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


def main():
    pairs = []
    for line in POOL.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            pairs.append((cat, name))
    print(f"=== STEP 1: WHOIS .com on {len(pairs)} names ===", flush=True)
    start = time.time()
    whois_results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(whois, n): (c, n) for c, n in pairs}
        for fut in as_completed(futs):
            c, n = futs[fut]
            _, d, status = fut.result()
            whois_results[n] = (d, status)
    avail = [(c, n, whois_results[n][0]) for c, n in pairs
             if whois_results[n][1] == "AVAILABLE"]
    avail.sort(key=lambda x: x[1])
    WHOIS_OUT.write_text(
        "\n".join(f"{c}\t{n}\t{d}" for c, n, d in avail) + "\n")
    print(f"  {len(avail)}/{len(pairs)} cleared WHOIS in "
          f"{time.time()-start:.1f}s", flush=True)
    by_cat = {}
    for c, _, _ in avail:
        by_cat[c] = by_cat.get(c, 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat}: {n}", flush=True)

    print(f"\n=== STEP 2: federal corp search on ALL {len(pairs)} names ===",
          flush=True)
    fed_results = {}
    fed_start = time.time()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fed_corp_search, n): (c, n) for c, n in pairs}
        done = 0
        for fut in as_completed(futs):
            c, n = futs[fut]
            fed_results[n] = fut.result()
            done += 1
            if done % 10 == 0:
                print(f"  fed {done}/{len(pairs)}  "
                      f"({time.time()-fed_start:.0f}s)", flush=True)
    print(f"  fed search done in {time.time()-fed_start:.1f}s", flush=True)

    rows = []
    for c, n in pairs:
        d, status = whois_results[n]
        fed = fed_results.get(n, {})
        rows.append({"category": c, "name": n, "domain": d,
                     "whois": status, "fed": fed})

    headers = ["category", "name", "domain", "whois_com",
               "fed_active", "fed_dissolved", "fed_total",
               "fed_sample", "fed_error"]
    with TSV_OUT.open("w") as f:
        f.write("\t".join(headers) + "\n")
        for r in rows:
            fd = r["fed"]
            f.write("\t".join([
                r["category"], r["name"], r["domain"], r["whois"],
                str(fd.get("active") or 0), str(fd.get("dissolved") or 0),
                str(fd.get("total") or 0),
                ((fd.get("samples") or [""])[0]
                    if fd.get("samples") else ""),
                str(fd.get("error") or ""),
            ]) + "\n")

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    md = ["# Round 6: 100 fresh tech-name candidates",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._",
          "",
          "Checks: Verisign WHOIS for `.com` and Corporations Canada "
          "federal search.", ""]
    for cat in sorted(by_cat):
        md.append(f"## {cat}")
        md.append("")
        md.append("| Name | Domain | .com | Fed Active | Fed Total | Sample |")
        md.append("|---|---|---|---|---|---|")
        rs = sorted(by_cat[cat], key=lambda r: (
            0 if r["whois"] == "AVAILABLE" else 1,
            r["fed"].get("active") or 99,
            r["name"]))
        for r in rs:
            f = r["fed"]
            sample = ((f.get("samples") or [""])[0][:40]
                      if f.get("samples") else "")
            md.append(f"| {r['name']} | {r['domain']} | {r['whois']} | "
                      f"{f.get('active') or 0} | "
                      f"{f.get('total') or 0} | {sample} |")
        md.append("")

    md.append("## Top picks (.com AVAILABLE + 0 active federal corp)")
    md.append("")
    md.append("| Name | Domain | Category |")
    md.append("|---|---|---|")
    clean = [r for r in rows
             if r["whois"] == "AVAILABLE"
             and (r["fed"].get("active") or 0) == 0
             and not r["fed"].get("error")]
    for r in sorted(clean, key=lambda x: x["name"]):
        md.append(f"| {r['name']} | {r['domain']} | {r['category']} |")
    md.append("")

    MD_OUT.write_text("\n".join(md) + "\n")
    print(f"\nDone in {(time.time()-start)/60:.1f} min total")
    print(f"  TSV: {TSV_OUT}")
    print(f"  MD:  {MD_OUT}")
    print(f"  clean picks: {len(clean)}")


if __name__ == "__main__":
    main()
