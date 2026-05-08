#!/usr/bin/env python3
"""Round 3 candidate pool: ~100 new names for general tech company use.
Stripe / Linear / Vercel / Plaid / Mercury / Anthropic energy. Dedupes
against round 1 + round 2 pools."""
from pathlib import Path

POOL_V3 = {
    "tech_short": [
        # 1 to 2 syllable, Brex/Plaid/Stripe/Glex feel
        "Veox", "Plyx", "Brux", "Glex", "Strynt", "Krenta", "Vexa", "Brexa",
        "Plyma", "Vanto", "Plendo", "Stelo", "Norvo", "Lumvo", "Sorvo",
        "Mireo", "Preno", "Calvox", "Marvox", "Olvox",
        "Vexora", "Brexora", "Plyxora", "Strexora", "Kalvora",
        "Marvora", "Solvora", "Olvora", "Stelora", "Norora",
        "Krenora", "Plenora", "Vendara", "Vendora", "Calbria",
    ],
    "tech_mid": [
        # 2 to 3 syllable, Lattice/Carta/Ramp/Linear gravity
        "Verita", "Lumera", "Callum", "Pelica", "Vanora", "Solera",
        "Marila", "Olvana", "Solanthe", "Cobalta", "Argenta",
        "Aurelin", "Marantha", "Caradel", "Sondell", "Marivell",
        "Praxos", "Cendore", "Calidor", "Marador", "Solvador",
        "Helixor", "Quantix", "Synthex", "Vortexa", "Datrix",
        "Calidex", "Calandor", "Marandor", "Solandor",
        "Olvandor", "Stelandor", "Norandor",
    ],
    "tech_latin_abstract": [
        # Greek/Latin philosophical / scientific tone
        "Cogitos", "Praxara", "Veritalis", "Lumitas", "Solveritas",
        "Marveritas", "Calveritas", "Olveritas", "Stelveritas",
        "Norveritas", "Karveritas", "Lumveritas", "Plenveritas",
        "Stenveritas", "Coraxis", "Soraxis", "Calraxis", "Marraxis",
        "Olvraxis", "Stelraxis", "Norraxis", "Plenraxis",
        "Lumraxis", "Karraxis", "Hyperia", "Triada", "Quintos",
        "Helixar", "Synthar", "Pegasos",
    ],
    "tech_modern": [
        # Modern, brand-shaped, Notion/Figma/Linear adjacency
        "Norant", "Polant", "Calant", "Vorant", "Marant", "Solant",
        "Olvant", "Stelant", "Krenant", "Plenant",
        "Verlare", "Calare", "Marare", "Solare", "Olvare",
        "Stelare", "Norvare", "Krenare", "Plenare",
        "Vidanti", "Caldanti", "Mardanti", "Soldanti", "Olvdanti",
        "Steldanti", "Norvdanti", "Krendanti", "Plendanti",
        "Pengrid", "Marbase", "Solbase", "Olvbase", "Stelbase",
    ],
}


def main():
    out = Path("/Users/janchinapoo/max/incorp/data/pool_v3.txt")
    seen = set()
    for prev in ["pool.txt", "pool_v2.txt"]:
        p = Path(f"/Users/janchinapoo/max/incorp/data/{prev}")
        if p.exists():
            for line in p.read_text().splitlines():
                if "\t" in line:
                    seen.add(line.split("\t", 1)[1].lower())
    lines = []
    dropped = 0
    for cat, names in POOL_V3.items():
        for n in names:
            k = n.lower()
            if k in seen:
                dropped += 1
                continue
            seen.add(k)
            lines.append(f"{cat}\t{n}")
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} unique new names to {out}")
    print(f"  dropped {dropped} duplicates")
    by = {}
    for line in lines:
        cat = line.split("\t")[0]
        by[cat] = by.get(cat, 0) + 1
    for cat, n in by.items():
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
