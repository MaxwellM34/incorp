#!/usr/bin/env python3
"""Round 2 candidate pool: 200 new names.
  - moggy_sigma: aggressive masculine, sigma/wolf/beast/maxx vibes (50)
  - greek_roman_chad: Atlas, Spartan, Magnus, Praetor, Vulcan, Olympia (50)
  - enterprise_invented: Stripe/Linear/Vercel/Anthropic/Plaid sound (100)

Dedupes against the round-1 pool so we don't re-check anything.
"""
from pathlib import Path

POOL_V2 = {
    "moggy_sigma": [
        "Sigmacore", "Sigmaworks", "Sigmaforge", "Sigmagrid", "Sigmastride",
        "Sigmaridge", "Sigmavault", "Sigmastark", "Sigmaclash", "Sigmaedge",
        "Mogstride", "Mogvault", "Mogedge", "Mogstark", "Mogthrust",
        "Mogiron", "Mogsteel", "Mogclad", "Mogsavage", "Mogfortress",
        "Wolfgrid", "Wolfridge", "Wolfclad", "Wolfthrust", "Wolfsavage",
        "Beastforge", "Beastclad", "Beastvault", "Beastedge", "Beastsavage",
        "Lionforge", "Lionclad", "Lionvault", "Lionsavage",
        "Tigerforge", "Tigerclad",
        "Apexbeast", "Apexridge", "Apexgrid", "Apexstride", "Apexvault",
        "Apexsavage",
        "Maxxsigma", "Maxxstride", "Maxxvault", "Maxxsavage", "Maxxedge",
        "Brawlsigma", "Brawlstride", "Brawlvault",
    ],
    "greek_roman_chad": [
        "Atlasforge", "Atlasworks", "Atlasridge", "Atlasvault", "Atlasclad",
        "Apolloforge", "Apolloworks", "Apollovault",
        "Marsforge", "Marsworks", "Marsridge",
        "Mercuryforge", "Mercuryworks", "Mercuryvault",
        "Triton34", "Tritonworks", "Tritonforge", "Tritonridge",
        "Magnusforge", "Magnusworks", "Magnusridge", "Magnusvault",
        "Maximusforge", "Maximusworks",
        "Spartancore", "Spartanforge", "Spartanvault", "Spartanworks",
        "Praetorian", "Praetorforge", "Praetorworks",
        "Centurionforge", "Centurionworks", "Centurioncore",
        "Achillesforge", "Achillesworks",
        "Heliosforge", "Heliosworks",
        "Olympiaforge", "Olympiaworks",
        "Aegisforge", "Aegisworks", "Aegiscore",
        "Hyperionforge", "Hyperionworks",
        "Heraclesforge",
        "Vulcanforge", "Vulcanworks",
        "Romulusforge", "Romulusworks",
    ],
    "enterprise_invented": [
        # Short, 1 to 2 syllable, Brex/Plaid/Stripe energy
        "Vrexa", "Plyna", "Strynt", "Broxa", "Glexa", "Krenta", "Pravex",
        "Sorenta", "Norelo", "Vespor", "Morexa", "Calexa", "Stelina",
        "Vercive", "Sondor", "Calver", "Solven", "Norvic", "Plevor",
        "Glasten", "Frenta", "Calanta", "Solanta", "Veranta", "Olvanta",
        "Marvanta", "Pelanta", "Stelanta", "Norvanta", "Karvanta",
        "Lumanta", "Vivanta", "Calenta", "Solenta", "Verenta",
        # 3 syllable, Anthropic/Mercury/Lattice gravity
        "Lumeris", "Verandil", "Calveris", "Solveris", "Veridian",
        "Marveris", "Olveris", "Stelveris", "Karveris", "Norveris",
        "Lumandel", "Verandel", "Calandel", "Solandel", "Marandel",
        "Olvandel", "Stelandel", "Norandel", "Karandel", "Plenandel",
        "Cordial", "Lumera", "Vivara", "Cendor", "Praxor",
        "Calvora", "Varenza", "Veranza", "Solenza", "Calenza",
        "Marvenza", "Vinrose", "Solveris", "Marveris",
        # Latin abstract / philosophical
        "Veritor", "Cogitan", "Praxor", "Veridicta", "Maridicta",
        "Solveric", "Calveric", "Marveric", "Olveric", "Stelveric",
        "Veridos", "Calvedos", "Solvedos", "Marvedos", "Olvedos",
        "Stelvedos", "Norvedos", "Karvedos", "Plenedos",
        # Mythology / element-adjacent
        "Cobalta", "Argenta", "Aurelin", "Caltheon", "Solanthe",
        "Veranthos", "Marantha", "Olvarae",
    ],
}


def main():
    out = Path("/Users/janchinapoo/max/incorp/data/pool_v2.txt")
    existing = Path("/Users/janchinapoo/max/incorp/data/pool.txt")
    seen = set()
    if existing.exists():
        for line in existing.read_text().splitlines():
            if "\t" in line:
                seen.add(line.split("\t", 1)[1].lower())
    lines = []
    dropped = 0
    for cat, names in POOL_V2.items():
        for n in names:
            k = n.lower()
            if k in seen:
                dropped += 1
                continue
            seen.add(k)
            lines.append(f"{cat}\t{n}")
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} unique new names to {out}")
    print(f"  dropped {dropped} duplicates of round-1 pool")
    by = {}
    for line in lines:
        cat = line.split("\t")[0]
        by[cat] = by.get(cat, 0) + 1
    for cat, n in by.items():
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
