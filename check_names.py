#!/usr/bin/env python3
"""Check .com availability and Canadian federal corp conflicts for candidate company names."""
import socket
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

CANDIDATES = {
    "Pro invented": [
        # shortlist
        "Vaxora", "Stelvor", "Traxivo", "Syntavex", "Olvrik", "Nuvrex", "Drelvix",
        # new
        "Krexon", "Velnora", "Praxen", "Zelvora", "Stradex", "Olvex", "Nyvora",
        "Krellix", "Vendrix", "Strenova", "Plexora", "Quortex", "Velmar",
        "Trovex", "Stenwick", "Vyrnax", "Caltrex",
    ],
    "Two-word professional": [
        # shortlist
        "Driftbay", "Quietcraft", "Harboredge",
        # new
        "Northbay", "Slatework", "Stillpath", "Anchorline", "Northforge",
        "Lakeshift", "Brightwater", "Tidehaven", "Pinewright", "Coppermill",
        "Glassbay", "Stonehaven", "Riverwright", "Cleardrift", "Grayport",
        "Steelhaven", "Quietbay",
    ],
    "Chad-bankable": [
        # new
        "Ironkeel", "Bronzefield", "Steelharbor", "Coreaxis", "Boldworks",
        "Granitebay", "Steelridge", "Anvilworks", "Steelbridge", "Hardpath",
        "Forgepath", "Coreworks", "Steelcraft", "Boldforge", "Stoneworks",
        "Steellabs", "Steelmark",
    ],
    "Pure mog/chad": [
        # shortlist
        "Mogforge", "Maxxcore", "Maxxlabs", "Brawlworks", "Forgemog", "Mogwright",
        # new
        "Maxxforge", "Mogbridge", "Brawlmog", "Maxxbay", "Mogcore", "Forgemax",
        "Maxxworks", "Brawlforge", "Mogwerks", "Maxxhaven", "Brawlcore",
        "Mogkeep", "Maxxridge", "Forgechad", "Brawlpath", "Maxxgrid", "Mogworks",
    ],
    "Personal-brand": [
        # shortlist
        "M34",
        # new
        "M34Labs", "McInnisCo", "Maxwell34", "M34Works", "McInnisWorks",
        "MaxLabs34", "McInnisLabs", "M34Forge", "McInnisCraft", "MaxBuilt",
        "M34Studio", "McInnisStudio", "MaxworkLabs", "M34Built", "McInnisBuilt",
        "M34Bridge",
    ],
    "Geographic": [
        # new
        "PortCreditWorks", "MississaugaForge", "CreditValleyLabs",
        "LakeshoreCraft", "PortCreditLabs", "Mississauga34", "LakeshoreWorks",
        "CreditRiverWorks", "PortCreditCo", "ClarksonForge",
        "StreetsvilleCraft", "LorneParkLabs", "CooksvilleWorks",
        "PortCreditStudio", "Mississaugabay", "CreditValley34",
    ],
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def check_com(name: str) -> tuple[str, str, str]:
    """Return (name, domain, status). Status one of AVAILABLE / TAKEN / ERROR."""
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
        text = b"".join(chunks).decode(errors="ignore")
        upper = text.upper()
        if "NO MATCH FOR" in upper or "NOT FOUND" in upper:
            return name, domain, "AVAILABLE"
        if "DOMAIN NAME:" in upper or "REGISTRAR:" in upper:
            return name, domain, "TAKEN"
        return name, domain, "UNKNOWN"
    except Exception as exc:
        return name, domain, f"ERROR({type(exc).__name__})"


def check_corp(name: str) -> str:
    """Best-effort federal corp conflict check via the public ISED search page."""
    try:
        url = "https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html"
        params = {
            "V_SEARCH.command": "navigate",
            "V_SEARCH.scopeCategory": "CC.Web.Sites.CC",
            "crpNm": name,
            "Action": "Search",
        }
        r = requests.get(
            url, params=params, timeout=15,
            headers={"User-Agent": UA, "Accept": "text/html"},
        )
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        text = r.text
        lower = text.lower()
        # Look for "no record(s) found" / "no results" patterns ISED uses.
        no_hit_phrases = [
            "no record", "no records found", "no results",
            "0 record", "did not return any",
        ]
        if any(p in lower for p in no_hit_phrases):
            return "NO CONFLICT"
        # Try to count result rows
        soup = BeautifulSoup(text, "html.parser")
        result_rows = soup.select("table tbody tr")
        if result_rows and len(result_rows) > 0:
            # Heuristic: filter rows that actually contain corp number text
            real = [tr for tr in result_rows if re.search(r"\d{5,}", tr.get_text())]
            if real:
                return f"POSSIBLE MATCH ({len(real)})"
            return "NO CONFLICT"
        # Fallback: if the corp name appears verbatim outside of input fields
        if name.lower() in lower and "value=\"" + name.lower() not in lower:
            return "CHECK MANUALLY"
        return "NO CONFLICT"
    except Exception as exc:
        return f"ERROR({type(exc).__name__})"


def check_one(vibe: str, name: str) -> dict:
    _, domain, com_status = check_com(name)
    corp_status = check_corp(name)
    return {
        "vibe": vibe,
        "name": name,
        "domain": domain,
        "com": com_status,
        "corp": corp_status,
    }


def main() -> int:
    pairs = [(vibe, n) for vibe, names in CANDIDATES.items() for n in names]
    total = len(pairs)
    print(f"Checking {total} candidates across {len(CANDIDATES)} vibes...\n")

    results: list[dict] = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(check_one, vibe, n): (vibe, n) for vibe, n in pairs}
        done = 0
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 10 == 0:
                print(f"  ...{done}/{total} done ({time.time()-start:.1f}s)", file=sys.stderr)

    by_vibe: dict[str, list[dict]] = {v: [] for v in CANDIDATES}
    for r in results:
        by_vibe[r["vibe"]].append(r)
    for v in by_vibe:
        by_vibe[v].sort(key=lambda r: r["name"])

    # Full table
    print("\n" + "=" * 78)
    print("FULL RESULTS TABLE")
    print("=" * 78)
    fmt = "{:<22} {:<28} {:<14} {:<20}"
    print(fmt.format("NAME", "DOMAIN", ".COM", "FED CORP"))
    print("-" * 78)
    for vibe in CANDIDATES:
        print(f"\n[{vibe}]")
        for r in by_vibe[vibe]:
            print(fmt.format(r["name"][:22], r["domain"][:28], r["com"][:14], r["corp"][:20]))

    # Ready to register: .com AVAILABLE and corp NO CONFLICT
    print("\n" + "=" * 78)
    print("READY TO REGISTER (.com AVAILABLE + no federal conflict)")
    print("=" * 78)
    any_ready = False
    for vibe in CANDIDATES:
        ready = [r for r in by_vibe[vibe]
                 if r["com"] == "AVAILABLE" and r["corp"] == "NO CONFLICT"]
        if not ready:
            continue
        any_ready = True
        print(f"\n[{vibe}]")
        for r in ready:
            print(f"  {r['name']:<22}  {r['domain']}")
    if not any_ready:
        print("\n  (none cleared both checks; review POSSIBLE MATCH / UNKNOWN rows above)")

    print(f"\nDone in {time.time()-start:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
