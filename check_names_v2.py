#!/usr/bin/env python3
"""Round 2: 80 additional pro/scaleable candidates only."""
import socket
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

CANDIDATES = {
    "Pro Latin/Greek invented (long)": [
        "Lumeris", "Veridon", "Calendra", "Sorenta", "Verant", "Praxos",
        "Vendant", "Marquen", "Calverra", "Stratoa", "Astera", "Cendora",
        "Veranth", "Korvath", "Lumarric", "Solendra", "Tendrin", "Marvex",
        "Lentris", "Fervana", "Solveria", "Endrika", "Vellaris", "Norvath",
        "Kendris", "Volaris", "Stelvra", "Caldera", "Aquilon", "Marendel",
        "Plenara", "Stradine", "Verdane", "Lentora", "Gralivo", "Veritra",
        "Olvania", "Sendrik", "Calenor", "Trevant",
    ],
    "Pro short invented (Stripe/Plaid style)": [
        "Norvik", "Calmar", "Velden", "Sorinex", "Vendel", "Norden",
        "Lumar", "Calva", "Verond", "Olvend", "Marvic", "Sondra",
        "Strenta", "Vellor", "Norven", "Caldris", "Marvex", "Tenwell",
        "Solenor", "Vendric",
    ],
    "Two-word mature pro": [
        "Northwright", "Kindlebay", "Stoneharbor", "Wellbrook", "Standwell",
        "Oakwright", "Pinegrove", "Cleargate", "Boldgate", "Cedarwright",
        "Winterport", "Elmpath", "Granitewright", "Brassfield", "Ironwright",
        "Steadypath", "Trustworks", "Steelvale", "Quietport", "Stillbay",
    ],
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def check_com(name: str):
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
            return name, domain, "AVAILABLE"
        if "DOMAIN NAME:" in text or "REGISTRAR:" in text:
            return name, domain, "TAKEN"
        return name, domain, "UNKNOWN"
    except Exception as exc:
        return name, domain, f"ERROR({type(exc).__name__})"


def check_corp(name: str) -> str:
    try:
        url = "https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html"
        params = {
            "V_SEARCH.command": "navigate",
            "V_SEARCH.scopeCategory": "CC.Web.Sites.CC",
            "crpNm": name,
            "Action": "Search",
        }
        r = requests.get(url, params=params, timeout=15,
                         headers={"User-Agent": UA, "Accept": "text/html"})
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        text = r.text.lower()
        if any(p in text for p in ("no record", "no records found", "no results", "0 record", "did not return any")):
            return "NO CONFLICT"
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tbody tr")
        real = [tr for tr in rows if re.search(r"\d{5,}", tr.get_text())] if rows else []
        if real:
            return f"POSSIBLE MATCH ({len(real)})"
        return "NO CONFLICT"
    except Exception as exc:
        return f"ERROR({type(exc).__name__})"


def check_one(vibe, name):
    _, domain, com = check_com(name)
    return {"vibe": vibe, "name": name, "domain": domain, "com": com,
            "corp": check_corp(name)}


def main():
    pairs = [(v, n) for v, names in CANDIDATES.items() for n in names]
    print(f"Checking {len(pairs)} additional pro candidates...\n", file=sys.stderr)
    results = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(check_one, v, n): (v, n) for v, n in pairs}
        for fut in as_completed(futs):
            results.append(fut.result())

    by_vibe = {v: [] for v in CANDIDATES}
    for r in results:
        by_vibe[r["vibe"]].append(r)
    for v in by_vibe:
        by_vibe[v].sort(key=lambda r: r["name"])

    print("=" * 78)
    print("PRO CANDIDATES, FULL TABLE")
    print("=" * 78)
    fmt = "{:<22} {:<28} {:<14} {:<20}"
    print(fmt.format("NAME", "DOMAIN", ".COM", "FED CORP"))
    for vibe in CANDIDATES:
        print(f"\n[{vibe}]")
        for r in by_vibe[vibe]:
            print(fmt.format(r["name"][:22], r["domain"][:28], r["com"][:14], r["corp"][:20]))

    print("\n" + "=" * 78)
    print("READY TO REGISTER (.com AVAILABLE)")
    print("=" * 78)
    for vibe in CANDIDATES:
        ready = [r for r in by_vibe[vibe] if r["com"] == "AVAILABLE" and "POSSIBLE MATCH" not in r["corp"]]
        if not ready:
            continue
        print(f"\n[{vibe}]")
        for r in ready:
            print(f"  {r['name']:<22}  {r['domain']}")
    print(f"\nDone in {time.time()-start:.1f}s.")


if __name__ == "__main__":
    main()
