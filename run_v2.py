#!/usr/bin/env python3
"""Round 2 pipeline. Reads pool_v2.txt, runs WHOIS filter, then live Porkbun
price + federal corp search on every WHOIS-available name."""
import socket, re, sys, time, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
POOL = DATA / "pool_v2.txt"
WHOIS_OUT = DATA / "whois_available_v2.txt"
TSV_OUT = DATA / "verified_v2.tsv"
MD_OUT = DATA / "verified_v2.md"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def slug(name): return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


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
            if not d: break
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


def porkbun_price(domain, env, retries=2):
    url = f"https://api.porkbun.com/api/json/v3/domain/checkDomain/{domain}"
    body = {"apikey": env["PORKBUN_API_KEY"], "secretapikey": env["PORKBUN_SECRET_KEY"]}
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
                    "renewal": resp.get("additional", {}).get("renewal", {}).get("price"),
                }
            if d.get("code") == "RATE_LIMIT_EXCEEDED":
                time.sleep(int(d.get("ttlRemaining") or 10) + 1)
                continue
            return {"error": d.get("message", "unknown")}
        except Exception as e:
            if attempt < retries:
                time.sleep(5)
                continue
            return {"error": f"{type(e).__name__}"}
    return {"error": "exhausted_retries"}


def fed_corp_search(name):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    try:
        r1 = s.get("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html",
                   params={"V_SEARCH.command": "navigate", "crpNm": name}, timeout=20)
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
            if not items[i].isdigit(): continue
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
        return {"total": total, "active": active, "dissolved": dissolved, "samples": samples}
    except Exception as e:
        return {"error": f"{type(e).__name__}"}


def federal_url(name):
    return ("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html?"
            + urllib.parse.urlencode({"V_SEARCH.command": "navigate", "crpNm": name}))
def ontario_url(name):
    return ("https://www.appmybizaccount.gov.on.ca/onbis/businessRegistry/search?"
            + urllib.parse.urlencode({"keyword": name}))


def main():
    env = load_env()
    pairs = []
    for line in POOL.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            pairs.append((cat, name))
    print(f"=== STEP 1: WHOIS filter on {len(pairs)} names ===", flush=True)
    start = time.time()
    avail = []
    with ThreadPoolExecutor(max_workers=15) as pool:
        futs = {pool.submit(whois, n): (c, n) for c, n in pairs}
        for fut in as_completed(futs):
            c, n = futs[fut]
            _, d, status = fut.result()
            if status == "AVAILABLE":
                avail.append((c, n, d))
    avail.sort()
    WHOIS_OUT.write_text("\n".join(f"{c}\t{n}\t{d}" for c, n, d in avail) + "\n")
    print(f"  {len(avail)}/{len(pairs)} cleared WHOIS in {time.time()-start:.1f}s", flush=True)
    by_cat = {}
    for c, _, _ in avail:
        by_cat[c] = by_cat.get(c, 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat}: {n}", flush=True)

    if not avail:
        print("Nothing cleared WHOIS.")
        return

    print(f"\n=== STEP 2: live Porkbun + federal corp on {len(avail)} survivors ===", flush=True)
    print(f"  rate-limited to 1 Porkbun call / 10s, expected runtime "
          f"{len(avail)*10/60:.1f} min", flush=True)
    rows = []
    pipeline_start = time.time()
    for i, (cat, name, domain) in enumerate(avail, 1):
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_pork = pool.submit(porkbun_price, domain, env)
            f_fed = pool.submit(fed_corp_search, name)
            t0 = time.time()
            pork = f_pork.result()
            fed = f_fed.result()
        rows.append({"category": cat, "name": name, "domain": domain,
                     "pork": pork, "fed": fed})
        elapsed = time.time() - pipeline_start
        eta = elapsed / i * (len(avail) - i)
        pork_str = (f"${pork.get('price')}/yr prem={pork.get('premium')}"
                    if "error" not in pork
                    else f"PORK_ERR({pork['error'][:30]})")
        fed_str = (f"fed={fed.get('total','?')}" if "error" not in fed
                   else f"fed=ERR({fed['error'][:30]})")
        print(f"[{i:3}/{len(avail)}] {name:<22} {pork_str:<35} {fed_str}  "
              f"(elapsed {elapsed:.0f}s, eta {eta:.0f}s)", flush=True)
        spent = time.time() - t0
        if spent < 10.5 and i < len(avail):
            time.sleep(10.5 - spent)

    # Write outputs
    headers = ["category", "name", "domain", "price", "renewal", "premium",
               "pork_error", "fed_active", "fed_dissolved", "fed_total",
               "fed_sample", "fed_error"]
    with TSV_OUT.open("w") as f:
        f.write("\t".join(headers) + "\n")
        for r in rows:
            p = r["pork"]
            fd = r["fed"]
            f.write("\t".join([
                r["category"], r["name"], r["domain"],
                str(p.get("price") or ""), str(p.get("renewal") or ""),
                str(p.get("premium") or ""), str(p.get("error") or ""),
                str(fd.get("active") or 0), str(fd.get("dissolved") or 0),
                str(fd.get("total") or 0),
                ((fd.get("samples") or [""])[0] if fd.get("samples") else ""),
                str(fd.get("error") or ""),
            ]) + "\n")

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    md = ["# Round 2: 200 new names verified\n",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._\n",
          "All rows passed Verisign WHOIS for `.com`, then live Porkbun pricing "
          "and Corporations Canada federal search.\n"]
    for cat in sorted(by_cat):
        md.append(f"\n## {cat}\n")
        md.append("| Name | Domain | Price/yr | Renewal | Premium | Fed Active | Fed Dissolved | Fed Total | Sample |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        rs = sorted(by_cat[cat], key=lambda r: (r["fed"].get("active") or 99, r["name"]))
        for r in rs:
            p, f = r["pork"], r["fed"]
            price = f"${p.get('price')}" if p.get("price") else (p.get("error", "")[:15])
            md.append(f"| {r['name']} | {r['domain']} | {price} | "
                      f"{('$' + p['renewal']) if p.get('renewal') else ''} | "
                      f"{p.get('premium') or ''} | {f.get('active') or 0} | "
                      f"{f.get('dissolved') or 0} | {f.get('total') or 0} | "
                      f"{(f.get('samples') or [''])[0][:40] if f.get('samples') else ''} |")
        md.append("\nSpot-check links:\n")
        for r in rs:
            md.append(f"- **{r['name']}**: [federal]({federal_url(r['name'])}) | "
                      f"[ontario]({ontario_url(r['name'])})")
    MD_OUT.write_text("\n".join(md) + "\n")
    print(f"\nDone in {(time.time()-start)/60:.1f} min total")
    print(f"  TSV: {TSV_OUT}")
    print(f"  MD:  {MD_OUT}")


if __name__ == "__main__":
    main()
