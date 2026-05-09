#!/usr/bin/env python3
"""Interactive picker — walk through names from master_list.tsv one at a time.

For each name, show all info and choose whether to add it to your shortlist
at data/possible_options.tsv (and a markdown shadow at possible_options.md).

Resumable: state is saved to data/picker_state.json so you can quit and pick
back up where you left off. Newly added/cleared names (e.g. from running
checks on UNKNOWNs) automatically appear in the queue when you continue.

Usage:
    python3 pick_names.py                    # CLEAR only (default)
    python3 pick_names.py --verdicts CLEAR,UNKNOWN
    python3 pick_names.py --verdicts ALL
    python3 pick_names.py --reset            # clear decisions, start over
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
MASTER = DATA / "master_list.tsv"
PICKS_TSV = DATA / "possible_options.tsv"
PICKS_MD = DATA / "possible_options.md"
STATE = DATA / "picker_state.json"

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

PICK_FIELDS = [
    "name", "domain", "category", "rounds",
    "com_status", "price", "renewal", "premium",
    "fed_active", "fed_dissolved", "fed_total", "fed_sample",
    "verdict", "decided_at",
]


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"decided": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def load_master(verdicts):
    if not MASTER.exists():
        sys.exit(f"Missing {MASTER}. Run `python3 build_master_list.py` first.")
    with MASTER.open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if "ALL" not in verdicts:
        rows = [r for r in rows if (r.get("verdict") or "").upper() in verdicts]
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
    md = ["# Possible options — your shortlist", "",
          f"Total picks: **{len(picks)}**", ""]
    md.append("| # | Name | Domain | $/yr | Renew | Premium | "
              "Fed Active | Fed Total | Category | Rounds | Verdict |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, p in enumerate(picks, 1):
        price = f"${p['price']}" if p.get("price") else ""
        renew = f"${p['renewal']}" if p.get("renewal") else ""
        md.append(
            f"| {i} | {p['name']} | {p.get('domain', '')} | {price} | "
            f"{renew} | {p.get('premium', '')} | "
            f"{p.get('fed_active', 0)} | {p.get('fed_total', 0)} | "
            f"{p.get('category', '')} | {p.get('rounds', '')} | "
            f"{p.get('verdict', '')} |"
        )
    md.append("")
    PICKS_MD.write_text("\n".join(md) + "\n")


def render(row, idx, total, n_picks):
    print()
    print(f"{DIM}{'=' * 64}{RESET}")
    print(f"{DIM}[{idx}/{total}]   shortlist so far: "
          f"{GREEN}{n_picks}{RESET}{DIM}{RESET}")
    print(f"{DIM}{'=' * 64}{RESET}")
    print()
    print(f"  {BOLD}{CYAN}{row['name']}{RESET}")
    print(f"  {DIM}{row.get('domain', '')}{RESET}")
    print()

    com = (row.get("com_status") or "").upper()
    com_disp = (f"{GREEN}AVAILABLE{RESET}" if com == "AVAILABLE"
                else f"{RED}TAKEN{RESET}" if com == "TAKEN"
                else f"{YELLOW}unknown{RESET}")
    verdict = (row.get("verdict") or "").upper()
    v_disp = (f"{GREEN}{verdict}{RESET}" if verdict == "CLEAR"
              else f"{RED}{verdict}{RESET}"
              if verdict in ("TAKEN", "CORP_CONFLICT")
              else f"{YELLOW}{verdict}{RESET}")
    premium = (row.get("premium") or "").lower()
    prem_disp = (f"{RED}YES{RESET}" if premium == "yes"
                 else f"{GREEN}no{RESET}" if premium == "no" else "—")

    fed_active = row.get("fed_active") or "0"
    fed_total = row.get("fed_total") or "0"
    fed_diss = row.get("fed_dissolved") or "0"
    fed_active_disp = (f"{GREEN}{fed_active}{RESET}"
                      if str(fed_active) == "0"
                      else f"{RED}{fed_active}{RESET}")

    rows_to_print = [
        ("Verdict",      v_disp),
        (".com",         com_disp),
        ("Reg price",    f"${row['price']}/yr" if row.get('price') else "—"),
        ("Renewal",      f"${row['renewal']}/yr" if row.get('renewal') else "—"),
        ("Premium",      prem_disp),
        ("Fed active",   fed_active_disp),
        ("Fed dissolved", fed_diss),
        ("Fed total",    fed_total),
        ("Fed sample",   row.get("fed_sample") or "—"),
        ("Category",     row.get("category") or "—"),
        ("From rounds",  row.get("rounds") or "—"),
    ]
    for label, val in rows_to_print:
        print(f"    {DIM}{label:<14}{RESET}  {val}")
    print()


def prompt():
    print(f"  {BOLD}[y]{RESET}es  add to shortlist     "
          f"{BOLD}[n]{RESET}o   skip permanently")
    print(f"  {BOLD}[s]{RESET}kip-for-later          "
          f"{BOLD}[u]{RESET}ndo last     "
          f"{BOLD}[q]{RESET}uit & save")
    while True:
        try:
            ans = input(f"  {MAGENTA}>{RESET} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if ans in ("y", "yes"):
            return "y"
        if ans in ("n", "no"):
            return "n"
        if ans in ("s", "skip", ""):
            return "s"
        if ans in ("u", "undo"):
            return "u"
        if ans in ("q", "quit", "exit"):
            return "q"
        print(f"  {YELLOW}? — try y / n / s / u / q{RESET}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdicts", default="CLEAR",
                    help="comma list of verdicts to walk "
                         "(CLEAR,UNKNOWN,TAKEN,CORP_CONFLICT,ALL)")
    ap.add_argument("--reset", action="store_true",
                    help="forget previous decisions (does NOT delete picks)")
    args = ap.parse_args()

    if args.reset and STATE.exists():
        STATE.unlink()
        print(f"{YELLOW}State reset.{RESET}")

    verdicts = [v.strip().upper() for v in args.verdicts.split(",")]
    state = load_state()
    decided = set(state.get("decided", []))
    picks = load_picks()
    pick_names = {p["name"] for p in picks}

    rows = load_master(verdicts)
    queue = [r for r in rows if r["name"] not in decided]
    in_scope = len(rows)

    print(f"{BOLD}Picker — verdicts: {','.join(verdicts)}{RESET}")
    print(f"  in scope:        {in_scope}")
    print(f"  already decided: {in_scope - len(queue)}")
    print(f"  shortlist:       {len(picks)}  -> {PICKS_TSV}")
    print()

    if not queue:
        print(f"{GREEN}Nothing left to review. Picks: {len(picks)}.{RESET}")
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
            pick_names.add(row["name"])
            decided.add(row["name"])
            history.append((row["name"], "y"))
            write_picks(picks)
            state["decided"] = sorted(decided)
            save_state(state)
            print(f"  {GREEN}+ added to shortlist ({len(picks)} total){RESET}")
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
                pick_names.discard(last_name)
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
        print(f"  {DIM}{remaining} still unreviewed in this verdict scope — "
              f"re-run to continue.{RESET}")


if __name__ == "__main__":
    main()
