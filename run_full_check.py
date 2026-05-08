#!/usr/bin/env python3
"""Full verification pipeline for the 92 WHOIS-available names.

For each name, fetches:
  1. Live .com price + premium flag from Porkbun API (authenticated, real)
  2. Federal corp match count from Corporations Canada search (form-post scrape,
     authoritative, no API key needed)

Ontario provincial corp check has no public API, so each row gets a direct OBR
spot-check URL. NUANS preliminary search is the authoritative Ontario check.

Output:
  data/verified.tsv         tab-separated full results
  data/verified.md          human-readable markdown table
"""
import os, re, json, socket, sys, time, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def porkbun_price(domain: str, env: dict) -> dict:
    """Returns dict with avail / price / premium flag, or error."""
    url = f"https://api.porkbun.com/api/json/v3/domain/checkDomain/{domain}"
    body = {
        "apikey": env["PORKBUN_API_KEY"],
        "secretapikey": env["PORKBUN_SECRET_KEY"],
    }
    try:
        r = requests.post(url, json=body, timeout=30)
        d = r.json()
        if d.get("status") == "SUCCESS":
            resp = d["response"]
            return {
                "avail": resp.get("avail"),
                "price": resp.get("price"),
                "regular_price": resp.get("regularPrice"),
                "premium": resp.get("premium"),
                "first_year_promo": resp.get("firstYearPromo"),
                "renewal_price": resp.get("additional", {}).get("renewal", {}).get("price"),
                "transfer_price": resp.get("additional", {}).get("transfer", {}).get("price"),
            }
        if d.get("code") == "RATE_LIMIT_EXCEEDED":
            return {"error": "rate_limited", "ttl": d.get("ttlRemaining")}
        return {"error": d.get("message", "unknown")}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def fed_corp_search(name: str) -> dict:
    """Real federal corporation search via Corporations Canada form post.
    Returns dict with total / active_matches / dissolved_matches / sample_names."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    try:
        r1 = s.get("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html",
                   params={"V_SEARCH.command": "navigate", "crpNm": name},
                   timeout=20)
        r2 = s.post(
            r1.url,
            data={
                "_pageFlowMap": "", "_page": "",
                "corpName": name, "corpNumber": "", "busNumber": "",
                "corpProvince": "", "corpStatus": "", "corpAct": "",
                "buttonNext": "Search",
            },
            timeout=25,
        )
        if r2.status_code != 200:
            return {"error": f"HTTP {r2.status_code}"}
        soup = BeautifulSoup(r2.text, "html.parser")
        main = soup.find("main") or soup.find("div", id="maincontent") or soup
        txt = main.get_text(" ", strip=True)
        # "X results were found, Y returned."
        m = re.search(r"(\d[\d,]*)\s+results?\s+(?:were|was)\s+found", txt, re.I)
        if m:
            total = int(m.group(1).replace(",", ""))
        else:
            total = 0
            if "no record" in txt.lower() or "no result" in txt.lower():
                total = 0
            elif re.search(r"\bcould not be conducted\b", txt, re.I):
                return {"error": "form_validation_error"}
        # Parse the numbered result list. Each entry has format:
        #  "1. Name Inc. Status: Active Corporation number: 1234567-8 ..."
        items = re.split(r"(?:^|\s)(\d+)\.\s+", txt)
        # items is [prefix, '1', 'rest...', '2', 'rest...', ...]
        active, dissolved, samples = 0, 0, []
        for i in range(1, len(items) - 1, 2):
            seq, body = items[i], items[i + 1]
            if not seq.isdigit():
                continue
            chunk = body[:400]
            # Cut at next item boundary (heuristic: "Status:" then status then "Corporation number:")
            mname = re.match(r"(.+?)\s+Status:\s*(.+?)\s+Corporation number:\s*([\d-]+)", chunk)
            if mname:
                cname, cstatus, cnum = mname.group(1).strip(), mname.group(2).strip(), mname.group(3).strip()
                if cstatus.lower().startswith("active"):
                    active += 1
                elif "dissolv" in cstatus.lower() or "inactive" in cstatus.lower():
                    dissolved += 1
                if len(samples) < 3:
                    samples.append(f"{cname} ({cstatus[:20]})")
        return {
            "total": total,
            "active": active,
            "dissolved": dissolved,
            "samples": samples,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def ontario_url(name: str) -> str:
    return ("https://www.appmybizaccount.gov.on.ca/onbis/businessRegistry/search?"
            + urllib.parse.urlencode({"keyword": name}))


def federal_search_url(name: str) -> str:
    return ("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html?"
            + urllib.parse.urlencode({"V_SEARCH.command": "navigate", "crpNm": name}))


def load_available():
    pairs = []
    for line in (DATA / "whois_available.txt").read_text().splitlines():
        if "\t" in line:
            cat, name, domain = line.split("\t")
            pairs.append((cat, name, domain))
    return pairs


def main():
    env = load_env()
    available = load_available()
    print(f"Pipeline running on {len(available)} WHOIS-available names",
          file=sys.stderr)
    print("Porkbun rate limit: 1 check / 10s. Estimated runtime: "
          f"{len(available)*10/60:.1f} min.", file=sys.stderr)

    rows = []
    start = time.time()

    for i, (cat, name, domain) in enumerate(available, 1):
        # Run federal in parallel with Porkbun rate-limit wait
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_pork = pool.submit(porkbun_price, domain, env)
            f_fed = pool.submit(fed_corp_search, name)
            t0 = time.time()
            pork = f_pork.result()
            fed = f_fed.result()

        # Retry Porkbun once if rate-limited
        if pork.get("error") == "rate_limited":
            wait = max(int(pork.get("ttl") or 10), 10)
            time.sleep(wait + 1)
            pork = porkbun_price(domain, env)

        rows.append({
            "category": cat,
            "name": name,
            "domain": domain,
            "porkbun_price": pork.get("price"),
            "porkbun_renewal": pork.get("renewal_price"),
            "porkbun_premium": pork.get("premium"),
            "porkbun_avail": pork.get("avail"),
            "porkbun_error": pork.get("error"),
            "fed_total": fed.get("total"),
            "fed_active": fed.get("active"),
            "fed_dissolved": fed.get("dissolved"),
            "fed_samples": " | ".join(fed.get("samples") or []),
            "fed_error": fed.get("error"),
        })

        # Progress report
        elapsed = time.time() - start
        eta = elapsed / i * (len(available) - i)
        fed_str = (f"fed={fed.get('total','?')}" if "error" not in fed
                   else f"fed=ERR({fed['error'][:30]})")
        pork_str = (f"${pork.get('price')}/yr prem={pork.get('premium')}"
                    if "error" not in pork
                    else f"PORK_ERR({pork['error'][:30]})")
        print(f"[{i:2}/{len(available)}] {name:<22} {pork_str:<35} {fed_str}  "
              f"(elapsed {elapsed:.0f}s, eta {eta:.0f}s)",
              file=sys.stderr)

        # Honor Porkbun rate limit (1 / 10s per key per IP)
        spent = time.time() - t0
        if spent < 10.5 and i < len(available):
            time.sleep(10.5 - spent)

    # Write outputs
    tsv = DATA / "verified.tsv"
    md = DATA / "verified.md"

    headers = list(rows[0].keys())
    with tsv.open("w") as f:
        f.write("\t".join(headers) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(h, "")) for h in headers) + "\n")

    # Markdown report
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)

    lines = []
    lines.append("# Verified Name Candidates")
    lines.append("")
    lines.append(f"Generated {time.strftime('%Y-%m-%d %H:%M')} local time. ")
    lines.append("Sources: Verisign WHOIS for .com availability, Porkbun API for live "
                 "registration price and premium flag, Corporations Canada federal "
                 "registry for federal corp matches. Ontario Business Registry "
                 "requires login so each row links out for manual verification.")
    lines.append("")
    lines.append("## Filter recommendation")
    lines.append("")
    lines.append("Strongest signal: rows where `fed_active=0` and `premium=no`. "
                 "Those are .com clear, standard-priced, no active federal corp uses "
                 "this name. Then click the Ontario link on your 3 to 5 favourites "
                 "before paying for NUANS preliminary search.")
    lines.append("")
    lines.append("---")
    lines.append("")

    for cat in sorted(by_cat):
        lines.append(f"## {cat}")
        lines.append("")
        lines.append("| Name | Domain | Price (yr) | Renewal | Premium | Fed Active | Fed Dissolved | Fed Total | Sample Fed Match |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        rs = sorted(by_cat[cat], key=lambda r: (r["fed_active"] or 99, r["name"]))
        for r in rs:
            price = f"${r['porkbun_price']}" if r["porkbun_price"] else f"ERR"
            renewal = f"${r['porkbun_renewal']}" if r["porkbun_renewal"] else ""
            premium = r["porkbun_premium"] or ""
            fed_a = r["fed_active"] if r["fed_active"] is not None else "?"
            fed_d = r["fed_dissolved"] if r["fed_dissolved"] is not None else "?"
            fed_t = r["fed_total"] if r["fed_total"] is not None else "?"
            sample = (r["fed_samples"] or "")[:80]
            lines.append(f"| {r['name']} | {r['domain']} | {price} | {renewal} | {premium} | {fed_a} | {fed_d} | {fed_t} | {sample} |")
        lines.append("")
        lines.append("Spot-check links:")
        lines.append("")
        for r in rs:
            fed_url = federal_search_url(r["name"])
            ont_url = ontario_url(r["name"])
            lines.append(f"- **{r['name']}**: [federal]({fed_url}) | [ontario obr]({ont_url})")
        lines.append("")

    md.write_text("\n".join(lines) + "\n")
    print(f"\nDone in {(time.time()-start)/60:.1f} min")
    print(f"  TSV: {tsv}")
    print(f"  MD:  {md}")


if __name__ == "__main__":
    sys.exit(main() or 0)
