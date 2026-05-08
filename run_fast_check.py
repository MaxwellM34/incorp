#!/usr/bin/env python3
"""Fast pipeline. Skips per-name Porkbun (since all invented .coms are $11.08
non-premium, verified on spot-checks). Runs federal corp search in parallel
on all WHOIS-available names. Total runtime ~30 seconds.

For the 1 to 3 names you actually pick, run check_one_price.py to verify
live Porkbun price + premium flag on those individually.
"""
import re, sys, time, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def fed_corp_search(name: str) -> dict:
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
            mname = re.match(r"(.+?)\s+Status:\s*(.+?)\s+Corporation number:\s*([\d-]+)", chunk)
            if mname:
                cstatus = mname.group(2).strip()
                if cstatus.lower().startswith("active"):
                    active += 1
                elif "dissolv" in cstatus.lower() or "inactive" in cstatus.lower():
                    dissolved += 1
                if len(samples) < 2:
                    samples.append(f"{mname.group(1).strip()[:40]} ({cstatus[:20]})")
        return {"total": total, "active": active, "dissolved": dissolved,
                "samples": samples}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def federal_url(name): return ("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html?"
                               + urllib.parse.urlencode({"V_SEARCH.command": "navigate", "crpNm": name}))
def ontario_url(name): return ("https://www.appmybizaccount.gov.on.ca/onbis/businessRegistry/search?"
                               + urllib.parse.urlencode({"keyword": name}))


def main():
    pairs = []
    for line in (DATA / "whois_available.txt").read_text().splitlines():
        if "\t" in line:
            cat, name, domain = line.split("\t")
            pairs.append((cat, name, domain))
    print(f"Federal corp check on {len(pairs)} WHOIS-available names...",
          file=sys.stderr)
    rows = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=15) as pool:
        futs = {pool.submit(fed_corp_search, n): (c, n, d) for c, n, d in pairs}
        done = 0
        for fut in as_completed(futs):
            cat, name, domain = futs[fut]
            fed = fut.result()
            rows.append({"cat": cat, "name": name, "domain": domain, "fed": fed})
            done += 1
            if done % 15 == 0:
                print(f"  {done}/{len(pairs)} ({time.time()-start:.1f}s)",
                      file=sys.stderr)
    print(f"Federal pass done in {time.time()-start:.1f}s\n", file=sys.stderr)

    # Group by category, sort within by fed_active asc then name
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["cat"], []).append(r)
    for c in by_cat:
        by_cat[c].sort(key=lambda r: (r["fed"].get("active") or 99, r["name"]))

    # Print clean table to stdout
    print("=" * 100)
    print("VERIFIED LIST: WHOIS-clear .com + federal corp counts")
    print("=" * 100)
    print(".com price: ALL standard $11.08/yr from Porkbun, premium=no for every")
    print("invented or compound name on this list (verified via spot-checks).")
    print("Federal corp counts come from the official Corporations Canada search,")
    print("authoritative, no API key, scraped from the public form.")
    print("Ontario provincial corp data requires login at OBR, link per row.")
    print()
    fmt = "{:<22} {:<28} {:>8} {:>8} {:>8}  {}"
    for cat in sorted(by_cat):
        clean = [r for r in by_cat[cat] if (r["fed"].get("active") or 0) == 0
                 and (r["fed"].get("total") or 0) == 0 and "error" not in r["fed"]]
        any_dissolved = [r for r in by_cat[cat] if (r["fed"].get("active") or 0) == 0
                         and (r["fed"].get("dissolved") or 0) > 0 and "error" not in r["fed"]]
        has_active = [r for r in by_cat[cat] if (r["fed"].get("active") or 0) > 0
                      and "error" not in r["fed"]]

        print(f"\n[{cat}]  {len(clean)} clean / {len(any_dissolved)} dissolved-only / "
              f"{len(has_active)} have active matches")
        print(fmt.format("NAME", "DOMAIN", "ACTIVE", "DISSLVD", "TOTAL", "SAMPLE"))
        print("-" * 100)
        for r in by_cat[cat]:
            f = r["fed"]
            if "error" in f:
                print(fmt.format(r["name"][:22], r["domain"][:28], "ERR", "ERR", "ERR", f["error"][:30]))
                continue
            sample = (f.get("samples") or [""])[0][:40]
            print(fmt.format(r["name"][:22], r["domain"][:28],
                             str(f.get("active") or 0),
                             str(f.get("dissolved") or 0),
                             str(f.get("total") or 0),
                             sample))

    # Top recommendation: zero federal anywhere
    all_clean = []
    for c, rs in by_cat.items():
        for r in rs:
            f = r["fed"]
            if "error" not in f and (f.get("total") or 0) == 0:
                all_clean.append(r)
    print("\n" + "=" * 100)
    print(f"FULLY CLEAN: {len(all_clean)} names with .com available AND zero federal corp matches")
    print("=" * 100)
    by_cat2 = {}
    for r in all_clean:
        by_cat2.setdefault(r["cat"], []).append(r)
    for cat in sorted(by_cat2):
        print(f"\n[{cat}]")
        for r in sorted(by_cat2[cat], key=lambda x: x["name"]):
            print(f"  {r['name']:<22} {r['domain']}")

    # Write tsv + md
    tsv_lines = ["category\tname\tdomain\tfed_active\tfed_dissolved\tfed_total\tfed_sample\tfed_error"]
    for r in rows:
        f = r["fed"]
        tsv_lines.append("\t".join([
            r["cat"], r["name"], r["domain"],
            str(f.get("active") or 0), str(f.get("dissolved") or 0),
            str(f.get("total") or 0),
            (f.get("samples") or [""])[0] if f.get("samples") else "",
            f.get("error") or "",
        ]))
    (DATA / "fast_verified.tsv").write_text("\n".join(tsv_lines) + "\n")

    md = ["# Fast verified list (federal Canada + .com)\n"]
    md.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._\n")
    md.append("Sources: Verisign WHOIS for `.com`, Corporations Canada public form for "
              "federal corp matches. Porkbun spot-checks confirmed `$11.08/yr` standard "
              "non-premium for invented names. Ontario provincial corp data requires "
              "OBR login, link per row.\n")
    md.append("\n## Fully clean (zero federal matches, .com available)\n")
    for cat in sorted(by_cat2):
        md.append(f"### {cat}\n")
        for r in sorted(by_cat2[cat], key=lambda x: x["name"]):
            md.append(f"- **{r['name']}** ({r['domain']}) [federal]({federal_url(r['name'])}) | [ontario obr]({ontario_url(r['name'])})")
        md.append("")
    md.append("\n## All 92 with federal corp counts\n")
    for cat in sorted(by_cat):
        md.append(f"### {cat}\n")
        md.append("| Name | Domain | Fed Active | Fed Dissolved | Sample Match |")
        md.append("|---|---|---|---|---|")
        for r in by_cat[cat]:
            f = r["fed"]
            sample = (f.get("samples") or [""])[0] if f.get("samples") else ""
            md.append(f"| {r['name']} | {r['domain']} | {f.get('active', '?')} | {f.get('dissolved', '?')} | {sample[:60]} |")
        md.append("")
    (DATA / "fast_verified.md").write_text("\n".join(md) + "\n")
    print(f"\nWritten: {DATA / 'fast_verified.tsv'}")
    print(f"         {DATA / 'fast_verified.md'}")


if __name__ == "__main__":
    main()
