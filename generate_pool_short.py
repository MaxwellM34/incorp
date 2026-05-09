#!/usr/bin/env python3
"""Generate 1500 short (4-6 letter) candidate names mixed across three styles:
pronounceable CV-patterns, random letter combos, and Latin/Greek-feeling roots.
Split: 200 4-letter + 800 5-letter + 500 6-letter."""
import random
import string
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = DATA / "pool_short.txt"

random.seed(42)

# Phonotactically-friendly consonants/vowels for pronounceable names
CONS = list("bcdfghjklmnprstvwz")
CONS_END = list("bcdfgklmnprstvxz")  # ok as terminal
VOW = list("aeiou")
VOW_Y = list("aeiouy")


def pronounceable(n_letters):
    """CVCV (4), CVCVC (5), CVCVCV (6)."""
    if n_letters == 4:
        return (random.choice(CONS) + random.choice(VOW) +
                random.choice(CONS) + random.choice(VOW_Y))
    if n_letters == 5:
        return (random.choice(CONS) + random.choice(VOW) +
                random.choice(CONS) + random.choice(VOW) +
                random.choice(CONS_END))
    # 6 letter CVCVCV
    return (random.choice(CONS) + random.choice(VOW) +
            random.choice(CONS) + random.choice(VOW) +
            random.choice(CONS) + random.choice(VOW_Y))


def random_combo(n_letters):
    """Pure random letters, but reject pure-consonant or pure-vowel runs of 4+."""
    while True:
        s = "".join(random.choices(string.ascii_lowercase, k=n_letters))
        # Reject obvious junk: no vowels at all, or 4+ consonant cluster
        if not any(c in VOW for c in s):
            continue
        # Reject 4+ consecutive identical chars
        if any(s[i] == s[i+1] == s[i+2] for i in range(len(s)-2)):
            continue
        return s


# Short Latin/Greek-feeling roots (2-3 letters), combined to 4-5 letter names
PREFIXES_2 = [
    "ax", "ar", "av", "ax", "ax", "el", "er", "ex", "il", "in",
    "ka", "ky", "lo", "lu", "lyr", "ne", "no", "ny", "ob", "od",
    "or", "pa", "pe", "pi", "po", "py", "qu", "ra", "re", "ri",
    "ro", "sa", "se", "si", "so", "sy", "ta", "te", "ti", "to",
    "ty", "va", "ve", "vi", "vo", "vy", "xa", "xe", "xy", "ya",
    "ze", "zy",
]
SUFFIXES_2 = [
    "ax", "el", "en", "er", "ex", "il", "in", "ix", "on", "or",
    "ox", "us", "yn", "yx", "ar", "as", "es", "is", "os", "ys",
    "an", "om", "um", "id", "od", "ad", "ed", "ud", "al", "ol",
    "ul", "ek", "ik", "ok", "uk",
]
SUFFIXES_3 = [
    "axi", "ari", "ela", "eli", "ema", "ena", "eno", "era", "eri",
    "ero", "eta", "ica", "ico", "ido", "ila", "ima", "ina", "ino",
    "iro", "ira", "ola", "ona", "ono", "ora", "ova", "ulo", "uma",
    "una", "uri", "yna", "yri", "ynx", "ora", "iva", "iza",
]


PREFIXES_3 = [
    "axi", "ari", "bel", "cal", "cor", "del", "elv", "ema", "fer",
    "ger", "hel", "ily", "iro", "kel", "lum", "mar", "nor", "ola",
    "pen", "pyr", "qua", "rho", "sol", "stel", "tar", "tor", "ulm",
    "ven", "ver", "vir", "xen", "yur", "zel", "zyr", "art",
]


def root_based(n_letters):
    """Combine roots to hit the target length."""
    for _ in range(60):
        if n_letters == 4:
            s = random.choice(PREFIXES_2) + random.choice(SUFFIXES_2)
        elif n_letters == 5:
            s = random.choice(PREFIXES_2) + random.choice(SUFFIXES_3)
        else:  # 6
            s = random.choice(PREFIXES_3) + random.choice(SUFFIXES_3)
        if len(s) == n_letters:
            return s
    # fallback
    return pronounceable(n_letters)


def generate():
    out = set()  # dedupe
    rows = []  # (style, name)

    targets = [
        # (style_label, generator, n_letters, count)
        ("pron4", pronounceable, 4, 67),
        ("rand4", random_combo, 4, 67),
        ("root4", root_based, 4, 66),
        ("pron5", pronounceable, 5, 267),
        ("rand5", random_combo, 5, 267),
        ("root5", root_based, 5, 266),
        ("pron6", pronounceable, 6, 167),
        ("rand6", random_combo, 6, 167),
        ("root6", root_based, 6, 166),
    ]

    for style, gen, n, want in targets:
        got = 0
        attempts = 0
        max_attempts = want * 200
        while got < want and attempts < max_attempts:
            s = gen(n)
            attempts += 1
            if s in out:
                continue
            out.add(s)
            rows.append((style, s))
            got += 1
        if got < want:
            print(f"  WARN {style}: got {got}/{want} after {attempts} attempts")

    return rows


def main():
    rows = generate()
    # Capitalize for display consistency with prior pools
    lines = [f"{style}\t{name.capitalize()}" for style, name in rows]
    OUT.write_text("\n".join(lines) + "\n")
    by_style = {}
    for style, _ in rows:
        by_style[style] = by_style.get(style, 0) + 1
    print(f"Wrote {len(rows)} names to {OUT}")
    for style in sorted(by_style):
        print(f"  {style}: {by_style[style]}")


if __name__ == "__main__":
    main()
