#!/usr/bin/env python3
"""Round 7: programmatically generate ~1000 unique candidates across four
vibes. Dedupes against every name already in data/master_list.tsv.

Categories:
  latin_long_v7    — Latin/Greek-feeling invented stems + suffixes
  short_invented_v7 — Stripe/Plaid/Linear-style 5-7 char invented
  two_word_v7       — natural adj+noun / material+place compounds
  modern_startup_v7 — punchy 5-6 char vowel-rich names
"""
import csv
import itertools
import random
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
MASTER = DATA / "master_list.tsv"
OUT = DATA / "pool_v7.txt"

random.seed(20260508)


def load_used():
    used = set()
    if MASTER.exists():
        with MASTER.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("name"):
                    used.add(r["name"].lower())
    for p in DATA.glob("pool_v*.txt"):
        for line in p.read_text().splitlines():
            if "\t" in line:
                used.add(line.split("\t", 1)[1].lower())
    return used


def pretty(s):
    """Title-case a generated lowercase token."""
    return s[:1].upper() + s[1:]


# ---- Latin/Greek invented long ----
LATIN_PREFIX = [
    "Ar", "Av", "Bel", "Brav", "Cal", "Cel", "Cor", "Dor", "Drev",
    "El", "Elv", "Eron", "Fal", "Fer", "Fren", "Gal", "Gor", "Grav",
    "Hal", "Hev", "Ind", "Ir", "Jor", "Jov", "Kal", "Kar", "Krev",
    "Lav", "Lor", "Lum", "Mal", "Mar", "Mor", "Nev", "Nor", "Olv",
    "Ord", "Orv", "Pal", "Pen", "Pra", "Quor", "Rav", "Ren", "Sol",
    "Sov", "Stel", "Tar", "Trev", "Ulv", "Vel", "Ven", "Ver", "Vor",
    "Wen", "Xen", "Xer", "Yor", "Zel", "Zor",
]
LATIN_SUFFIX_LONG = [
    "aris", "ovic", "andros", "elis", "oris", "anth", "ardel",
    "endra", "uris", "ovel", "anor", "antha", "endro", "ovan",
    "irix", "anth", "ovix", "iren", "etia", "andra", "evis",
    "orin", "ynth",
]


# ---- Short invented ----
SHORT_PREFIX = [
    "Ar", "Av", "Br", "Cal", "Cel", "Cor", "Cre", "Dor", "Dr",
    "El", "Fer", "Gor", "Hal", "Ind", "Jov", "Kal", "Kor", "Lav",
    "Len", "Lor", "Mar", "Mer", "Nor", "Olv", "Ord", "Pal", "Pen",
    "Pr", "Quav", "Rav", "Sol", "Sten", "Tav", "Tev", "Tor", "Trev",
    "Ven", "Ver", "Vor", "Wen", "Xen", "Yor", "Zel",
]
SHORT_SUFFIX = [
    "ax", "ex", "ix", "ox", "ux",
    "in", "an", "on", "en", "or",
    "ic", "ek", "ok", "et",
    "vix", "lex", "tek", "rix", "nix",
    "do", "ro", "vo", "no", "lo",
]


# ---- Two-word ----
ADJ = [
    "North", "South", "East", "West", "Bold", "Quiet", "Clear",
    "Strong", "Swift", "Steady", "True", "Bright", "Still", "Trust",
    "Sturdy", "Sharp", "Brave", "Calm", "Pure", "Solid", "Firm",
    "Quick", "Plain", "Right", "Even",
]
MATERIAL = [
    "Oak", "Pine", "Cedar", "Elm", "Maple", "Birch", "Ash", "Iron",
    "Steel", "Copper", "Granite", "Quartz", "Onyx", "Brass", "Stone",
    "Slate", "Sand", "Coral", "Cobalt", "Marble",
]
PLACE = [
    "brook", "forge", "ridge", "bay", "grove", "path", "port",
    "wright", "field", "gate", "mere", "harbor", "vale", "point",
    "haven", "view", "crest", "creek", "bridge", "anchor", "cove",
    "bluff", "rise", "bend", "shore", "summit",
]


# ---- Modern startup punchy ----
VOWELS = list("aeiou")
CONS = list("bcdfghklmnprstvz")  # avoid awkward "j" "q" "x" "y" "w"


def gen_latin_long(used, target=400):
    out = []
    seen = set()
    rng = random.Random(1)
    combos = list(itertools.product(LATIN_PREFIX, LATIN_SUFFIX_LONG))
    rng.shuffle(combos)
    for pre, suf in combos:
        # avoid double-vowel collisions like Ar+aris -> Araris (still ok, allow)
        name = pre + suf
        # smooth bridge: if pre ends in vowel and suf starts with vowel,
        # drop one
        if pre[-1].lower() in "aeiou" and suf[0].lower() in "aeiou":
            name = pre + suf[1:]
        if 7 <= len(name) <= 11 and name.isalpha():
            key = name.lower()
            if key in used or key in seen:
                continue
            seen.add(key)
            out.append(name)
            if len(out) >= target:
                break
    return out


def gen_short_invented(used, target=300):
    out = []
    seen = set()
    rng = random.Random(2)
    combos = list(itertools.product(SHORT_PREFIX, SHORT_SUFFIX))
    rng.shuffle(combos)
    for pre, suf in combos:
        name = pre + suf
        if pre[-1].lower() in "aeiou" and suf[0].lower() in "aeiou":
            name = pre + suf[1:]
        if 5 <= len(name) <= 8 and name.isalpha():
            key = name.lower()
            if key in used or key in seen:
                continue
            seen.add(key)
            out.append(name)
            if len(out) >= target:
                break
    return out


def gen_two_word(used, target=200):
    out = []
    seen = set()
    rng = random.Random(3)
    pairs = (list(itertools.product(ADJ, PLACE))
             + list(itertools.product(MATERIAL, PLACE))
             + list(itertools.product(ADJ, MATERIAL)))
    rng.shuffle(pairs)
    for a, b in pairs:
        name = a + b.lower() if b[0].isupper() else a + b
        if 7 <= len(name) <= 14 and name.isalpha():
            key = name.lower()
            if key in used or key in seen:
                continue
            seen.add(key)
            out.append(name)
            if len(out) >= target:
                break
    return out


def gen_modern_startup(used, target=100):
    out = []
    seen = set()
    rng = random.Random(4)
    # CVCVC / CVCV / CVCCV patterns
    patterns = [
        ("CVCVC", lambda: rng.choice(CONS) + rng.choice(VOWELS)
                   + rng.choice(CONS) + rng.choice(VOWELS)
                   + rng.choice(CONS)),
        ("CVCVV", lambda: rng.choice(CONS) + rng.choice(VOWELS)
                   + rng.choice(CONS) + rng.choice(VOWELS)
                   + rng.choice(VOWELS)),
        ("CCVCV", lambda: rng.choice(CONS) + rng.choice(CONS)
                   + rng.choice(VOWELS) + rng.choice(CONS)
                   + rng.choice(VOWELS)),
        ("CVCCVR", lambda: rng.choice(CONS) + rng.choice(VOWELS)
                   + rng.choice(CONS) + rng.choice(CONS)
                   + rng.choice(VOWELS) + "r"),
    ]
    # generate way more than target then filter
    tries = 0
    while len(out) < target and tries < 10000:
        tries += 1
        _, fn = rng.choice(patterns)
        token = fn()
        # enforce: at least one vowel, no triple-consonants
        if not any(c in "aeiou" for c in token):
            continue
        if re.search(r"[bcdfghklmnprstvz]{3,}", token):
            continue
        # avoid double letters in a row
        if re.search(r"(.)\1\1", token):
            continue
        # avoid awkward starts like 'pn'
        if token[:2] in ("pn", "kn", "mn", "ts", "lk", "rt"):
            continue
        name = token.capitalize()
        key = name.lower()
        if key in used or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def main():
    used = load_used()
    print(f"loaded {len(used)} previously seen names")
    long_names = gen_latin_long(used, target=400)
    used.update(n.lower() for n in long_names)
    short_names = gen_short_invented(used, target=300)
    used.update(n.lower() for n in short_names)
    two_word_names = gen_two_word(used, target=200)
    used.update(n.lower() for n in two_word_names)
    modern_names = gen_modern_startup(used, target=100)

    lines = []
    for n in long_names:
        lines.append(f"latin_long_v7\t{n}")
    for n in short_names:
        lines.append(f"short_invented_v7\t{n}")
    for n in two_word_names:
        lines.append(f"two_word_v7\t{n}")
    for n in modern_names:
        lines.append(f"modern_startup_v7\t{n}")

    OUT.write_text("\n".join(lines) + "\n")
    total = len(lines)
    print(f"wrote {total} candidates to {OUT}")
    print(f"  latin_long_v7:    {len(long_names)}")
    print(f"  short_invented_v7:{len(short_names)}")
    print(f"  two_word_v7:      {len(two_word_names)}")
    print(f"  modern_startup_v7:{len(modern_names)}")


if __name__ == "__main__":
    main()
