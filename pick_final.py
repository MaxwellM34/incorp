#!/usr/bin/env python3
"""Second-pass picker — walk the combined shortlist and narrow it further.

Reads data/shortlist_combined.tsv (run `python3 compile_picks.py` first)
and lets you y/n through every pick. Selected names go to data/final_picks.tsv
+ .md. Resumable via data/picker_state_final.json.

Usage:
    python3 pick_final.py
    python3 pick_final.py --reset
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SOURCE = DATA / "shortlist_combined.tsv"
PICKS_TSV = DATA / "final_picks.tsv"
PICKS_MD = DATA / "final_picks.md"
STATE = DATA / "picker_state_final.json"

BOLD = "\033[1m"; DIM = "\033[2m"
GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"
CYAN = "\033[36m"; MAGENTA = "\033[35m"; RESET = "\033[0m"

PICK_FIELDS = ["name", "domain", "length", "price", "renewal", "premium",
               "source", "category_or_style", "fed_active", "decided_at"]


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"decided": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def load_source():
    if not SOURCE.exists():
        sys.exit(f"Missing {SOURCE}. Run `python3 compile_picks.py` first.")
    with SOURCE.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


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
    md = ["# Final picks", "",
          f"Total: **{len(picks)}**", "",
          "| # | Name | Domain | Len | $/yr | Renew | Source | "
          "Category / Style |",
          "|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(picks, 1):
        price = f"${p['price']}" if p.get("price") else "—"
        renew = f"${p['renewal']}" if p.get("renewal") else "—"
        md.append(f"| {i} | **{p['name']}** | {p['domain']} | "
                  f"{p['length']} | {price} | {renew} | "
                  f"{p.get('source', '')} | "
                  f"{p.get('category_or_style', '')} |")
    md.append("")
    PICKS_MD.write_text("\n".join(md) + "\n")


def render(row, idx, total, n_picks):
    print()
    print(f"{DIM}{'=' * 56}{RESET}")
    print(f"{DIM}[{idx}/{total}]   final list: "
          f"{GREEN}{n_picks}{RESET}{DIM}{RESET}")
    print(f"{DIM}{'=' * 56}{RESET}")
    print()
    print(f"  {BOLD}{CYAN}{row['name']}{RESET}  "
          f"{DIM}({row['length']} letters, {row.get('source', '')} / "
          f"{row.get('category_or_style', '')}){RESET}")
    print(f"  {DIM}{row['domain']}{RESET}")
    print()
    price = row.get("price")
    renew = row.get("renewal")
    prem = (row.get("premium") or "").lower()
    prem_disp = (f"{RED}YES{RESET}" if prem == "yes"
                 else f"{GREEN}no{RESET}" if prem == "no" else "—")
    fed_active = row.get("fed_active") or "—"
    fed_disp = (f"{GREEN}{fed_active}{RESET}"
                if fed_active in ("0", "—")
                else f"{RED}{fed_active}{RESET}")
    print(f"    {DIM}Reg price{RESET}    "
          f"${price}/yr" if price else f"    {DIM}Reg price{RESET}    —")
    print(f"    {DIM}Renewal{RESET}      "
          f"${renew}/yr" if renew else f"    {DIM}Renewal{RESET}      —")
    print(f"    {DIM}Premium{RESET}      {prem_disp}")
    print(f"    {DIM}Fed active{RESET}   {fed_disp}")
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
    ap.add_argument("--reset", action="store_true",
                    help="forget previous decisions (does NOT delete picks)")
    args = ap.parse_args()

    if args.reset and STATE.exists():
        STATE.unlink()
        print(f"{YELLOW}State reset.{RESET}")

    state = load_state()
    decided = set(state.get("decided", []))
    picks = load_picks()
    rows = load_source()
    queue = [r for r in rows if r["name"] not in decided]
    in_scope = len(rows)

    print(f"{BOLD}Final-pass picker{RESET}  "
          f"{DIM}(walking {SOURCE.name}){RESET}")
    print(f"  in scope:        {in_scope}")
    print(f"  already decided: {in_scope - len(queue)}")
    print(f"  final list:      {len(picks)}  -> {PICKS_TSV}")
    print()

    if not queue:
        print(f"{GREEN}Nothing left to review. Final picks: "
              f"{len(picks)}.{RESET}")
        return

    history = []
    i = 0
    while i < len(queue):
        row = queue[i]
        if row["name"] in decided:
            i += 1
            continue
        position = in_scope - len(queue) + i + 1
        render(row, position, in_scope, len(picks))
        ans = prompt()

        if ans == "y":
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            picks.append({**row, "decided_at": stamp})
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
    print(f"{GREEN}Saved {len(picks)} final picks to {PICKS_TSV}{RESET}")
    print(f"  view: {PICKS_MD}")
    remaining = sum(1 for r in queue if r["name"] not in decided)
    if remaining:
        print(f"  {DIM}{remaining} unreviewed — re-run to continue.{RESET}")


if __name__ == "__main__":
    main()
