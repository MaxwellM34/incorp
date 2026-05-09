#!/usr/bin/env python3
"""Interactive picker for the short-name (4-6 letter) batch.

Reads WHOIS-AVAILABLE survivors from data/whois_available_short.txt and
walks them one at a time. Pricing is read live from data/pricing_short.tsv
if present, or parsed from data/run_short.log while the Porkbun pass is
still running.

Resumable via data/picker_state_short.json. Saves picks to
data/picks_short.tsv + .md.

Usage:
    python3 pick_short.py                  # priced-only (default while run live)
    python3 pick_short.py --all            # walk every WHOIS survivor
    python3 pick_short.py --include-rand   # also walk random combos
    python3 pick_short.py --reset
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
WHOIS = DATA / "whois_available_short.txt"
PRICING = DATA / "pricing_short.tsv"
LOG = DATA / "run_short.log"
PICKS_TSV = DATA / "picks_short.tsv"
PICKS_MD = DATA / "picks_short.md"
STATE = DATA / "picker_state_short.json"

# Matches: "[127/209] Ropuv    ropuv.com      avail=yes $11.08/yr renew=$11.08 prem=no"
LOG_LINE = re.compile(
    r"^\[\s*\d+/\s*\d+\]\s+(\S+)\s+(\S+)\s+"
    r"avail=(\S+)\s+\$([\d.]+)/yr\s+renew=\$?([\d.]+)\s+prem=(\S+)")
# Matches the error variant: "ERR(...)"
LOG_ERR = re.compile(
    r"^\[\s*\d+/\s*\d+\]\s+(\S+)\s+(\S+)\s+ERR\(([^)]+)\)")

BOLD = "\033[1m"; DIM = "\033[2m"
GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"
CYAN = "\033[36m"; MAGENTA = "\033[35m"; RESET = "\033[0m"

PICK_FIELDS = ["name", "domain", "style", "length",
               "price", "renewal", "premium", "decided_at"]


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"decided": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def load_pricing():
    """Return dict[domain] -> {price, renewal, premium, ...}.
    Prefers pricing_short.tsv; falls back to parsing run_short.log so the
    picker has live data while the Porkbun pass is still running."""
    out = {}
    if PRICING.exists():
        with PRICING.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                out[r["domain"]] = r
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            m = LOG_LINE.match(line)
            if m:
                name, domain, avail, price, renew, prem = m.groups()
                out.setdefault(domain, {
                    "name": name, "domain": domain,
                    "avail": avail, "price": price,
                    "renewal": renew, "premium": prem,
                    "pork_error": "",
                })
                continue
            me = LOG_ERR.match(line)
            if me:
                name, domain, err = me.groups()
                out.setdefault(domain, {
                    "name": name, "domain": domain,
                    "pork_error": err,
                })
    return out


def load_queue(include_rand, priced_only, pricing):
    if not WHOIS.exists():
        sys.exit(f"Missing {WHOIS}. Run `python3 run_short.py` first.")
    rows = []
    for line in WHOIS.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        style, name, domain = parts
        if not include_rand and style.startswith("rand"):
            continue
        if priced_only and domain not in pricing:
            continue
        rows.append({"style": style, "name": name, "domain": domain,
                     "length": str(len(name))})
    rows.sort(key=lambda r: (r["length"], r["style"], r["name"]))
    return rows


def load_picks():
    if not PICKS_TSV.exists():
        return []
    with PICKS_TSV.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_picks(picks):
    with PICKS_TSV.open("w") as f:
        w = csv.DictWriter(f, fieldnames=PICK_FIELDS,
                           delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for p in picks:
            w.writerow(p)
    md = ["# Short-name picks (4-6 letter)", "",
          f"Total picks: **{len(picks)}**", "",
          "| # | Name | Domain | Len | $/yr | Renew | Premium | Style |",
          "|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(picks, 1):
        price = f"${p['price']}" if p.get("price") else "—"
        renew = f"${p['renewal']}" if p.get("renewal") else "—"
        md.append(f"| {i} | {p['name']} | {p['domain']} | {p['length']} | "
                  f"{price} | {renew} | {p.get('premium', '—')} | "
                  f"{p['style']} |")
    md.append("")
    PICKS_MD.write_text("\n".join(md) + "\n")


def render(row, idx, total, n_picks, pricing):
    print()
    print(f"{DIM}{'=' * 56}{RESET}")
    print(f"{DIM}[{idx}/{total}]   shortlist: "
          f"{GREEN}{n_picks}{RESET}{DIM}{RESET}")
    print(f"{DIM}{'=' * 56}{RESET}")
    print()
    print(f"  {BOLD}{CYAN}{row['name']}{RESET}  "
          f"{DIM}({row['length']} letters, {row['style']}){RESET}")
    print(f"  {DIM}{row['domain']}{RESET}")
    print()

    p = pricing.get(row["domain"])
    if p:
        prem = (p.get("premium") or "").lower()
        prem_disp = (f"{RED}YES{RESET}" if prem == "yes"
                     else f"{GREEN}no{RESET}" if prem == "no" else "—")
        if p.get("pork_error"):
            print(f"    {DIM}Reg price{RESET}     {RED}ERR: "
                  f"{p['pork_error']}{RESET}")
        else:
            print(f"    {DIM}Reg price{RESET}     "
                  f"${p.get('price') or '?'}/yr")
            print(f"    {DIM}Renewal{RESET}       "
                  f"${p.get('renewal') or '?'}/yr")
            print(f"    {DIM}Premium{RESET}       {prem_disp}")
    else:
        print(f"    {DIM}Pricing{RESET}       "
              f"{YELLOW}PENDING{RESET}  "
              f"{DIM}(~$11.08/yr expected if non-premium){RESET}")
    print()


def prompt():
    print(f"  {BOLD}[y]{RESET}es  add  "
          f"{BOLD}[n]{RESET}o  skip-perm  "
          f"{BOLD}[s]{RESET}kip-later  "
          f"{BOLD}[u]{RESET}ndo  "
          f"{BOLD}[q]{RESET}uit")
    while True:
        try:
            ans = input(f"  {MAGENTA}>{RESET} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if ans in ("y", "yes"): return "y"
        if ans in ("n", "no"): return "n"
        if ans in ("s", "skip", ""): return "s"
        if ans in ("u", "undo"): return "u"
        if ans in ("q", "quit", "exit"): return "q"
        print(f"  {YELLOW}? — try y / n / s / u / q{RESET}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="walk every WHOIS survivor (default: priced-only)")
    ap.add_argument("--include-rand", action="store_true",
                    help="also walk random-letter combos (default: skip)")
    ap.add_argument("--reset", action="store_true",
                    help="forget previous decisions (does NOT delete picks)")
    args = ap.parse_args()

    if args.reset and STATE.exists():
        STATE.unlink()
        print(f"{YELLOW}State reset.{RESET}")

    state = load_state()
    decided = set(state.get("decided", []))
    picks = load_picks()
    pricing = load_pricing()
    priced_only = not args.all
    rows = load_queue(args.include_rand, priced_only, pricing)
    queue = [r for r in rows if r["name"] not in decided]
    in_scope = len(rows)

    mode = ("priced-only" if priced_only else "all WHOIS survivors")
    rand = " + random" if args.include_rand else ""
    print(f"{BOLD}Short-name picker{RESET}  "
          f"{DIM}({mode}, speakable{rand}){RESET}")
    print(f"  priced so far:   {len(pricing)}")
    print(f"  in scope:        {in_scope}")
    print(f"  already decided: {in_scope - len(queue)}")
    print(f"  shortlist:       {len(picks)}  -> {PICKS_TSV}")
    print()

    if not queue:
        print(f"{GREEN}Nothing left to review. Picks: {len(picks)}.{RESET}")
        return

    history = []
    i = 0
    while True:
        if i >= len(queue):
            # Refresh pricing + queue: maybe new names got priced since start
            if priced_only:
                pricing = load_pricing()
                fresh = load_queue(args.include_rand, priced_only, pricing)
                new_rows = [r for r in fresh
                            if r["name"] not in decided
                            and r["name"] not in {q["name"] for q in queue}]
                if new_rows:
                    queue.extend(new_rows)
                    in_scope = len(fresh)
                    print(f"  {DIM}+ {len(new_rows)} newly priced names "
                          f"appended to queue{RESET}")
                    continue
            break
        row = queue[i]
        if row["name"] in decided:
            i += 1
            continue
        # Re-read pricing each iteration so live updates show as run progresses
        pricing = load_pricing()
        position = in_scope - len(queue) + i + 1
        render(row, position, in_scope, len(picks), pricing)
        ans = prompt()

        if ans == "y":
            p = pricing.get(row["domain"], {})
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            picks.append({**row,
                          "price": p.get("price", ""),
                          "renewal": p.get("renewal", ""),
                          "premium": p.get("premium", ""),
                          "decided_at": stamp})
            decided.add(row["name"])
            history.append((row["name"], "y"))
            write_picks(picks)
            state["decided"] = sorted(decided)
            save_state(state)
            print(f"  {GREEN}+ added ({len(picks)} total){RESET}")
            i += 1
        elif ans == "n":
            decided.add(row["name"])
            history.append((row["name"], "n"))
            state["decided"] = sorted(decided)
            save_state(state)
            i += 1
        elif ans == "s":
            i += 1
        elif ans == "u":
            if not history:
                print(f"  {YELLOW}nothing to undo{RESET}")
                continue
            last_name, last_action = history.pop()
            decided.discard(last_name)
            if last_action == "y":
                picks = [p for p in picks if p["name"] != last_name]
                write_picks(picks)
            state["decided"] = sorted(decided)
            save_state(state)
            print(f"  {YELLOW}undid '{last_action}' on {last_name}{RESET}")
            for j, q in enumerate(queue):
                if q["name"] == last_name:
                    i = j
                    break
        elif ans == "q":
            break

    print()
    print(f"{GREEN}Saved {len(picks)} picks to {PICKS_TSV}{RESET}")
    print(f"  view: {PICKS_MD}")
    remaining = sum(1 for r in queue if r["name"] not in decided)
    if remaining:
        print(f"  {DIM}{remaining} unreviewed — re-run to continue.{RESET}")


if __name__ == "__main__":
    main()
