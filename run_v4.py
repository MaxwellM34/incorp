#!/usr/bin/env python3
"""Round 4: pool_v4 -> WHOIS filter -> live Porkbun + federal corp.
Caps Porkbun pipeline at 100 cleared names so we don't grind through 200+."""
import sys, time
sys.path.insert(0, "/Users/janchinapoo/max/incorp")
from pathlib import Path

import run_v2

ROOT = Path("/Users/janchinapoo/max/incorp")
DATA = ROOT / "data"

run_v2.POOL = DATA / "pool_v4.txt"
run_v2.WHOIS_OUT = DATA / "whois_available_v4.txt"
run_v2.TSV_OUT = DATA / "verified_v4.tsv"
run_v2.MD_OUT = DATA / "verified_v4.md"

# Monkey-patch the loader to cap at 100 names per run
_orig_main = run_v2.main


def capped_main():
    """Runs WHOIS first; if more than 100 cleared, trim to 100 before pipeline."""
    # Reuse the WHOIS step from run_v2 but with our own loop
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from run_v2 import whois, porkbun_price, fed_corp_search, federal_url, ontario_url, load_env, TSV_OUT, MD_OUT, POOL, WHOIS_OUT

    env = load_env()
    pairs = []
    for line in POOL.read_text().splitlines():
        if "\t" in line:
            cat, name = line.split("\t", 1)
            pairs.append((cat, name))
    print(f"=== STEP 1: WHOIS filter on {len(pairs)} names ===", flush=True)
    start = time.time()
    avail = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = {pool.submit(whois, n): (c, n) for c, n in pairs}
        for fut in as_completed(futs):
            c, n = futs[fut]
            _, d, status = fut.result()
            if status == "AVAILABLE":
                avail.append((c, n, d))
    avail.sort(key=lambda x: x[1])
    WHOIS_OUT.write_text("\n".join(f"{c}\t{n}\t{d}" for c, n, d in avail) + "\n")
    print(f"  {len(avail)}/{len(pairs)} cleared WHOIS in {time.time()-start:.1f}s",
          flush=True)
    if len(avail) > 100:
        print(f"  capping at first 100 (had {len(avail)})", flush=True)
        avail = avail[:100]

    if not avail:
        print("Nothing cleared.")
        return

    print(f"\n=== STEP 2: live Porkbun + federal on {len(avail)} ===", flush=True)
    print(f"  rate-limited 1 Porkbun call / 10s, "
          f"expected runtime {len(avail)*10/60:.1f} min", flush=True)
    rows = []
    pipeline_start = time.time()
    for i, (cat, name, domain) in enumerate(avail, 1):
        with ThreadPoolExecutor(max_workers=2) as p:
            f_pork = p.submit(porkbun_price, domain, env)
            f_fed = p.submit(fed_corp_search, name)
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
    md = ["# Round 4: 100 fresh tech-company names verified\n",
          f"_Generated {time.strftime('%Y-%m-%d %H:%M')}._\n",
          "All passed Verisign WHOIS for `.com`, then live Porkbun pricing "
          "and Corporations Canada federal search.\n",
          "\n| Name | Domain | Price/yr | Renewal | Premium | Fed Active | Fed Dissolved | Fed Total | Sample |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: ((x["fed"].get("active") or 99), x["name"])):
        p, f = r["pork"], r["fed"]
        price = f"${p.get('price')}" if p.get("price") else (p.get("error", "")[:15])
        md.append(f"| {r['name']} | {r['domain']} | {price} | "
                  f"{('$' + p['renewal']) if p.get('renewal') else ''} | "
                  f"{p.get('premium') or ''} | {f.get('active') or 0} | "
                  f"{f.get('dissolved') or 0} | {f.get('total') or 0} | "
                  f"{(f.get('samples') or [''])[0][:40] if f.get('samples') else ''} |")
    MD_OUT.write_text("\n".join(md) + "\n")
    print(f"\nDone in {(time.time()-start)/60:.1f} min")
    print(f"  TSV: {TSV_OUT}")
    print(f"  MD:  {MD_OUT}")


if __name__ == "__main__":
    capped_main()
