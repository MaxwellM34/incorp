#!/usr/bin/env python3
"""Round 4 candidate pool: ~400 invented tech-company names.
Larger candidate set so ~100+ pass WHOIS. Bias toward long unique stems
since short names are heavily squatted."""
from pathlib import Path

# Mix of stems and suffixes that produce distinct, pronounceable names.
# Generated with deliberate variation so we don't end up with 50 names
# all starting with Cal/Mar/Sol.
NAMES = [
    # Group 1: -ova / -ica / -ria / -elia endings (firm-coded)
    "Calenova", "Maredonia", "Olviantra", "Solendros", "Norvavera",
    "Plenavara", "Lumarista", "Vendarist", "Calovera", "Stelorica",
    "Marioca", "Olvarista", "Solverica", "Cendoria", "Marendra",
    "Plenarica", "Stelarica", "Norvarica", "Karvarica", "Lumarica",
    "Olvenova", "Stelinova", "Marinova", "Solinova", "Calinova",
    "Plenova", "Olvanova", "Norvanova", "Calostra", "Marostra",
    "Solostra", "Olvostra", "Stelostra", "Norvostra", "Karvostra",

    # Group 2: -aris / -ant / -ient endings (consultant-coded)
    "Veritarian", "Solveriant", "Marveriant", "Calveriant",
    "Olveriant", "Stelveriant", "Norveriant", "Karveriant",
    "Plenveriant", "Lumveriant", "Vendveriant", "Calorant",
    "Marorant", "Solorant", "Olvorant", "Stelorant", "Norvorant",
    "Karvorant", "Plenorant", "Lumorant",

    # Group 3: distinct fresh stems (no Cal/Mar/Sol/Olv prefixes)
    "Trevarra", "Quorindra", "Plymara", "Braxonova", "Strydora",
    "Krentelis", "Dornalba", "Fernivex", "Glexandra", "Zordwell",
    "Yvorant", "Mernovic", "Peltarion", "Sindalor", "Vornelta",
    "Trevidor", "Quorelis", "Plymara", "Braxenor", "Strydor",
    "Krendar", "Dornova", "Fernoria", "Glexar", "Zordara",
    "Yvora", "Mernovis", "Pelvarist", "Sindara", "Vornara",

    # Group 4: Single-stem distinctive
    "Brendar", "Crelvant", "Dremara", "Edwarra", "Florant",
    "Garondra", "Holvant", "Ivermel", "Jorvant", "Kraviant",
    "Lerovant", "Marivok", "Norindra", "Orvelta", "Prendarith",
    "Quintaval", "Renvarith", "Stridmar", "Travidor", "Ulvarist",
    "Vendaroth", "Wenivok", "Xenarith", "Yvenova", "Zelvarith",

    # Group 5: -etric / -atic / -ician scientific tone
    "Calometric", "Marometric", "Solometric", "Olvometric",
    "Stelometric", "Norvometric", "Karvometric", "Plenometric",
    "Lumometric", "Vendometric", "Calatic", "Maratic", "Solatic",
    "Olvatic", "Stelatic", "Norvatic", "Karvatic", "Plenatic",
    "Lumatic", "Vendatic",

    # Group 6: Latin -us / -os / -is endings
    "Marivos", "Solavos", "Olvavos", "Stelavos", "Norvavos",
    "Karvavos", "Plenavos", "Lumavos", "Vendavos", "Calavos",
    "Mariros", "Solaros", "Olvaros", "Stelaros", "Norvaros",
    "Karvaros", "Plenaros", "Lumaros", "Vendaros", "Calaros",

    # Group 7: Two-element compounds, tech-modern
    "Verbase", "Calbase", "Marbase", "Solbase", "Olvbase",
    "Vergrid", "Calgrid", "Margrid", "Solgrid", "Olvgrid",
    "Vercore", "Calcore", "Marcore", "Solcore", "Olvcore",
    "Verlight", "Callight", "Marlight", "Sollight", "Olvlight",
    "Verprime", "Calprime", "Marprime", "Solprime", "Olvprime",

    # Group 8: -lex / -nex / -dex tech-y
    "Calonex", "Maronex", "Solonex", "Olvonex", "Stelonex",
    "Norvonex", "Karvonex", "Plenonex", "Lumonex", "Vendonex",
    "Calodex", "Marodex", "Solodex", "Olvodex", "Stelodex",
    "Norvodex", "Karvodex", "Plenodex", "Lumodex", "Vendodex",

    # Group 9: Distinctive multi-syllable
    "Tarendor", "Vorindel", "Stradonia", "Orvarist", "Pelmedora",
    "Caltheria", "Solantheria", "Marantheria", "Olvantheria",
    "Stelantheria", "Norvantheria", "Karvantheria", "Plenantheria",
    "Lumantheria", "Vendantheria",
    "Caldroma", "Mardroma", "Soldroma", "Olvdroma", "Steldroma",
    "Norvdroma", "Karvdroma", "Plendroma", "Lumdroma", "Venddroma",

    # Group 10: -tide / -wave / -river / -peak (modern soft)
    "Calatide", "Maratide", "Solatide", "Olvatide", "Stelatide",
    "Norvatide", "Karvatide", "Plenatide", "Lumatide", "Vendatide",
    "Calwave", "Marwave", "Solwave", "Olvwave", "Stelwave",
    "Norvwave", "Karvwave", "Plenwave", "Lumwave", "Vendwave",

    # Group 11: -river / -peak / -summit
    "Calsummit", "Marsummit", "Solsummit", "Olvsummit", "Stelsummit",
    "Calpeak", "Marpeak", "Solpeak", "Olvpeak", "Stelpeak",
    "Calriver", "Marriver", "Solriver", "Olvriver", "Stelriver",

    # Group 12: Distinct stems, single category
    "Quintavor", "Pelmarist", "Strendaroth", "Volnareth",
    "Drelmara", "Trevarith", "Marendoth", "Stradorial",
    "Olverith", "Stelverith", "Norverith", "Karverith",
    "Plenverith", "Lumverith", "Vendverith", "Calverith",
    "Caltheon", "Maritheon", "Solitheon", "Olvitheon",
    "Stelitheon", "Norvitheon", "Karvitheon", "Plenitheon",
]


def main():
    out = Path("/Users/janchinapoo/max/incorp/data/pool_v4.txt")
    seen = set()
    for prev in ["pool.txt", "pool_v2.txt", "pool_v3.txt"]:
        p = Path(f"/Users/janchinapoo/max/incorp/data/{prev}")
        if p.exists():
            for line in p.read_text().splitlines():
                if "\t" in line:
                    seen.add(line.split("\t", 1)[1].lower())
    lines = []
    dropped = 0
    for n in NAMES:
        k = n.lower()
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        lines.append(f"tech_general\t{n}")
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} unique new names to {out}")
    print(f"  dropped {dropped} duplicates of prior pools")


if __name__ == "__main__":
    main()
