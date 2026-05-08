#!/usr/bin/env python3
"""Generate a 300-name candidate pool, biased professional.
Output: data/pool.txt (one name per line, deduped, sorted by category)."""
from pathlib import Path

POOL = {
    # Latin/Greek roots, calm consonants, 5 to 9 letters
    "pro_invented_short": [
        "Olvrik", "Syntavex", "Lumarric", "Marendel", "Olvania", "Stelvra",
        "Tendrin", "Verond", "Olvend",
        "Karven", "Velnix", "Sorven", "Caldenor", "Marvell", "Stradon",
        "Vernath", "Stelven", "Plendor", "Calenza", "Verendel",
        "Tendora", "Lumendel", "Stenwell", "Velorra", "Caltris",
        "Sondrik", "Vermont", "Stradyne", "Olvert", "Marvox",
        "Stelmar", "Verith", "Caldwin", "Solvant", "Endwell",
        "Vellum", "Praxion", "Veldris", "Stelnor", "Calveth",
        "Marquit", "Vendora", "Olverra", "Strandel", "Velmark",
    ],
    # Long Latin/Greek invented, gravitas
    "pro_invented_long": [
        "Veranthia", "Stradenia", "Olvarith", "Calverian", "Meredelin",
        "Sondaria", "Verendel", "Lumarrick", "Stelvonia", "Tendrium",
        "Calveria", "Maridelle", "Veranthor", "Solendrik", "Karvendel",
        "Olverith", "Strathmore", "Calantrix", "Verendola", "Solvendor",
        "Marideth", "Vermarrick", "Caldwellan", "Stelvarra", "Endrelith",
    ],
    # Two-word professional, calm and durable
    "two_word_pro": [
        "Pinewright", "Granitewright", "Elmpath",
        "Holdwell", "Standford", "Cedarline", "Oakreach", "Linenfield",
        "Standpath", "Wellfield", "Cleargate", "Branchwell", "Holdwright",
        "Ironbench", "Cedarpath", "Brightwell", "Trustline", "Stoneline",
        "Clearwright", "Maplewright", "Northwright", "Stillgate", "Wellpath",
        "Truewright", "Patientwell", "Steadwright", "Steadyline", "Holdfield",
    ],
    # Surname-anchored (McInnis + variations)
    "personal_brand": [
        "McInnisLabs", "McInnisWorks", "McInnisCraft", "McInnisBuilt",
        "McInnisGroup", "McInnisStudio", "McInnisCo", "McInnisDigital",
        "McInnisHoldings", "McInnisVentures", "McInnisPartners",
        "M34Labs", "M34Studio", "M34Works", "M34Forge", "M34Built",
        "M34Bridge", "M34Group", "M34Digital", "M34Holdings",
        "MaxLabs34", "Maxwell34", "MaxworkLabs", "MaxwellWorks",
        "MaxwellLabs", "MaxwellForge", "MaxwellGroup",
    ],
    # Geographic, Mississauga / GTA coded
    "geographic": [
        "PortCreditWorks", "PortCreditLabs", "PortCreditStudio", "PortCreditCo",
        "PortCreditGroup", "PortCreditDigital", "PortCreditPartners",
        "MississaugaForge", "Mississaugabay", "Mississauga34", "MississaugaWorks",
        "MississaugaLabs", "MississaugaCraft",
        "CreditValleyLabs", "CreditValley34", "CreditValleyWorks",
        "CreditValleyDigital", "CreditValleyGroup",
        "CreditRiverWorks", "CreditRiverLabs", "CreditRiverDigital",
        "LakeshoreCraft", "LakeshoreLabs", "LakeshoreWorks",
        "LorneParkLabs", "LorneParkWorks",
        "ClarksonForge", "ClarksonLabs",
        "CooksvilleWorks", "CooksvilleLabs",
        "StreetsvilleCraft", "StreetsvilleLabs",
    ],
    # Modern abstract, Stripe / Linear / Vercel adjacent
    "modern_abstract": [
        "Polden", "Kelven", "Norven", "Praven", "Solden", "Vorel",
        "Karven", "Lurent", "Sorben", "Mirvex", "Pelden", "Korven",
        "Talvex", "Vurent", "Norellis", "Solbrith", "Karpath", "Vorenta",
        "Lupath", "Trevant",
    ],
    # Compound -ant, -ive, -lex style
    "compound_modern": [
        "Caldwell", "Strident", "Verant", "Solvant", "Mirivant",
        "Karavant", "Stelvant", "Calvant", "Norvant", "Praxivant",
        "Verdivex", "Stelvex", "Calvex", "Marvex", "Lentivex",
        "Solvex", "Norvex", "Plendex", "Stenvex", "Velnex",
        "Karplex", "Calplex", "Norplex", "Stelplex", "Marplex",
    ],
}


def main():
    out_path = Path("/Users/janchinapoo/max/incorp/data/pool.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    lines = []
    for cat, names in POOL.items():
        unique = []
        for n in names:
            key = n.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(n)
        for n in sorted(unique):
            lines.append(f"{cat}\t{n}")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} unique names to {out_path}")
    by_cat = {}
    for line in lines:
        cat = line.split("\t")[0]
        by_cat[cat] = by_cat.get(cat, 0) + 1
    for cat, n in by_cat.items():
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
