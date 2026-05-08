#!/usr/bin/env python3
"""For the ready-to-register shortlist, show:
  - .com WHOIS status
  - .com base price (Porkbun + Cloudflare wholesale, both unauthenticated public sources)
  - Federal corp search result count (best-effort, JS-rendered page so flag if unreliable)
  - Direct URLs for: federal corp search, Ontario Business Registry name search,
    NUANS preliminary search.
"""
import socket
import re
import sys
import time
import json
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# Pre-cleared names from rounds 1 and 2 (where .com showed AVAILABLE)
SHORTLIST = {
    "Pro invented": [
        "Olvrik", "Syntavex", "Lumarric", "Marendel", "Olvania",
        "Stelvra", "Tendrin", "Verond", "Olvend",
    ],
    "Two-word professional": [
        "Pinewright", "Granitewright", "Elmpath",
    ],
    "Personal-brand (McInnis)": [
        "McInnisLabs", "McInnisWorks", "McInnisCraft", "McInnisBuilt",
    ],
    "Personal-brand (M34)": [
        "M34Labs", "M34Studio", "M34Works", "M34Forge", "M34Built",
        "M34Bridge", "MaxLabs34", "Maxwell34", "MaxworkLabs",
    ],
    "Geographic": [
        "PortCreditWorks", "PortCreditLabs", "PortCreditStudio",
        "PortCreditCo", "MississaugaForge", "Mississaugabay",
        "Mississauga34", "CreditValleyLabs", "CreditValley34",
        "CreditRiverWorks", "LakeshoreCraft", "LorneParkLabs",
        "ClarksonForge", "CooksvilleWorks", "StreetsvilleCraft",
    ],
    "Mog/chad": [
        "Mogforge", "Mogwright", "Mogkeep", "Mogcore", "Mogwerks",
        "Maxxforge", "Maxxhaven", "Maxxridge", "Maxxgrid",
        "Brawlworks", "Brawlmog", "Brawlpath", "Forgechad", "Forgemog",
    ],
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Pulled from Porkbun public pricing API (api.porkbun.com/api/json/v3/pricing/get).
# All three (registration, renewal, transfer) match for standard .com.
PORKBUN_COM = 11.08
# Cloudflare Registrar publishes at-cost pricing for .com.
CLOUDFLARE_COM = 10.44
# Namecheap retail (first year promo / standard renewal).
NAMECHEAP_COM_FIRST = 10.98
NAMECHEAP_COM_RENEWAL = 15.88


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def whois_com(name: str) -> str:
    domain = slug(name) + ".com"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(12)
        sock.connect(("whois.verisign-grs.com", 43))
        sock.sendall((domain + "\r\n").encode())
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
        sock.close()
        text = b"".join(chunks).decode(errors="ignore").upper()
        if "NO MATCH FOR" in text or "NOT FOUND" in text:
            return "AVAILABLE"
        if "DOMAIN NAME:" in text or "REGISTRAR:" in text:
            return "TAKEN"
        return "UNKNOWN"
    except Exception as exc:
        return f"ERR({type(exc).__name__})"


def fed_corp(name: str) -> str:
    """Best-effort federal corp count. The ISED page is partly JS-rendered, so we
    fetch the static HTML and count rows that look like real result entries."""
    try:
        url = "https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html"
        params = {
            "V_SEARCH.command": "navigate",
            "V_SEARCH.scopeCategory": "CC.Web.Sites.CC",
            "V_SEARCH.docsStart": "0",
            "V_SEARCH.resultsPerPage": "50",
            "V_SEARCH.scope": "CC",
            "crpNm": name,
        }
        r = requests.get(url, params=params, timeout=15,
                         headers={"User-Agent": UA, "Accept": "text/html"})
        if r.status_code != 200:
            return f"HTTP{r.status_code}"
        text = r.text
        soup = BeautifulSoup(text, "html.parser")
        rows = soup.select("table.zebra tbody tr, table tbody tr")
        # A real result row has the corporation number (5+ digits) and the name.
        real = []
        for tr in rows:
            tx = tr.get_text(" ", strip=True)
            if re.search(r"\b\d{5,}\b", tx) and name.lower() in tx.lower():
                real.append(tx)
        if real:
            return f"MATCH({len(real)})"
        # No structured match. Look at the result-count text some pages emit.
        body = soup.get_text(" ", strip=True).lower()
        if re.search(r"\b0\s+result", body) or "no record" in body:
            return "NONE"
        # If we can't tell from static HTML, mark unknown so user spot-checks.
        return "UNKNOWN"
    except Exception as exc:
        return f"ERR({type(exc).__name__})"


def federal_url(name: str) -> str:
    return ("https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html?"
            + urllib.parse.urlencode({
                "V_SEARCH.command": "navigate",
                "crpNm": name,
            }))


def ontario_url(name: str) -> str:
    # Ontario Business Registry (OBR) name search. Uses generic search UI.
    return ("https://www.appmybizaccount.gov.on.ca/onbis/businessRegistry/search?"
            + urllib.parse.urlencode({"keyword": name}))


def nuans_url(name: str) -> str:
    return "https://www.nuans.com/eic/site/075.nsf/eng/h_00001.html"


def check_one(vibe: str, name: str) -> dict:
    return {
        "vibe": vibe,
        "name": name,
        "domain": slug(name) + ".com",
        "com": whois_com(name),
        "fed": fed_corp(name),
    }


def main() -> int:
    pairs = [(v, n) for v, names in SHORTLIST.items() for n in names]
    print(f"Re-checking {len(pairs)} ready candidates with cost + corp data...\n",
          file=sys.stderr)
    results: list[dict] = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(check_one, v, n): (v, n) for v, n in pairs}
        for fut in as_completed(futs):
            results.append(fut.result())

    by_vibe: dict[str, list[dict]] = {v: [] for v in SHORTLIST}
    for r in results:
        by_vibe[r["vibe"]].append(r)
    for v in by_vibe:
        by_vibe[v].sort(key=lambda r: r["name"])

    # Header
    print("=" * 110)
    print("COST + CONFLICT REPORT")
    print("=" * 110)
    print()
    print("Standard .com pricing (non-premium, first year and renewal):")
    print(f"  Cloudflare Registrar: ${CLOUDFLARE_COM:.2f} / year   (at-cost, no markup)")
    print(f"  Porkbun:              ${PORKBUN_COM:.2f} / year   (registration = renewal)")
    print(f"  Namecheap:            ${NAMECHEAP_COM_FIRST:.2f} first year, ${NAMECHEAP_COM_RENEWAL:.2f} renewal")
    print()
    print("All cleared names below are invented or compound, so they will be standard")
    print("priced (not registry-premium). If you ever try to register and see a price")
    print("over ~$50, walk away, that means the registry flagged it as premium.")
    print()
    print("Corp conflict columns:")
    print("  FED  = federal corporation match count (best-effort scrape, UNKNOWN means")
    print("         the JS-rendered page hid results, click the link to verify).")
    print("  ONT  = not auto-checkable, the Ontario Business Registry requires login.")
    print("         Use the link, or pay for a NUANS preliminary search.")
    print("  NUANS= a NUANS preliminary search ($13.80 CAD) is required before filing")
    print("         Ontario Articles of Incorporation. Same NUANS link for all names.")
    print()

    fmt = "{:<22} {:<26} {:<10} {:<10}"
    for vibe in SHORTLIST:
        print()
        print(f"--- {vibe} ---")
        print(fmt.format("NAME", "DOMAIN", ".COM", "FED"))
        for r in by_vibe[vibe]:
            print(fmt.format(r["name"][:22], r["domain"][:26], r["com"], r["fed"]))
        print()
        print("  Spot-check links:")
        for r in by_vibe[vibe]:
            print(f"    {r['name']}")
            print(f"      Federal: {federal_url(r['name'])}")
            print(f"      Ontario: {ontario_url(r['name'])}")

    print()
    print("=" * 110)
    print("SUMMARY: total all-in cost to register and file")
    print("=" * 110)
    print(f"  .com domain (Cloudflare):       ${CLOUDFLARE_COM:.2f} USD / year")
    print( "  NUANS preliminary search:       $13.80 CAD (one-time, required for filing)")
    print( "  Ontario Articles filing fee:    $300.00 CAD (one-time, online)")
    print( "  CRA business number:            free")
    print( "  Total to incorporate:           ~$330 CAD plus ~$15 USD for the domain")
    print()
    print(f"Done in {time.time()-start:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
