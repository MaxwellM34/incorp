#!/usr/bin/env python3
"""Round 5 candidate pool: ~700 varied names across all styles to ensure ~200+
cleared after WHOIS filter. Dedupes against rounds 1-4 pools."""
from pathlib import Path

NAMES = [
    # Block A: tech_invented_long, more variety in stems
    "Avenarith", "Brevidor", "Crelvanth", "Drevarist", "Endorica",
    "Ferenova", "Grendalor", "Holvarith", "Iverando", "Jorvenor",
    "Krelantha", "Lervadom", "Mariverth", "Nordendros", "Orvelantha",
    "Pelvarith", "Quintaroth", "Renvardel", "Stradivor", "Trevandos",
    "Ulvenarith", "Vendarith", "Welvarith", "Xenardel", "Yvenarist",
    "Zelandros", "Avenarith2", "Brevidos", "Crelvarith", "Drevandel",
    "Brendanos", "Calantha", "Carendrik", "Daravost", "Eronvel",
    "Forenvar", "Gavandrik", "Helvanora", "Indrelta", "Jovenrik",
    "Karenvor", "Lavendrik", "Maredor", "Nendrarik", "Olvendrum",
    "Pelvarum", "Quivendor", "Resvanrik", "Sondervic", "Talverin",
    "Uvendrik", "Vorenrik", "Welvarum", "Yandrik", "Zerendrik",

    # Block B: -aron / -aris / -onia / -elta
    "Vendaron", "Calderon", "Marderon", "Solderon", "Olverdon",
    "Steldron", "Norvelron", "Karvelron", "Plenadron", "Lumadron",
    "Trendvaris", "Karelvaris", "Plenovaris", "Calovaris", "Marovaris",
    "Solovaris", "Olvovaris", "Stelovaris", "Norvovaris", "Lumovaris",
    "Verbonia", "Calbonia", "Marbonia", "Solbonia", "Olvbonia",
    "Stelbonia", "Norvbonia", "Karvbonia", "Plenbonia", "Lumbonia",
    "Trevelta", "Krevelta", "Brevelta", "Drevelta", "Erelta",
    "Felvelta", "Gelvelta", "Helvelta", "Ivelta", "Jelvelta",

    # Block C: stripe-y short to mid (2-3 syl)
    "Provet", "Sondex", "Caldex", "Marvex", "Olvex", "Stelvex",
    "Norvex", "Karvex", "Plenvex", "Lumvex", "Vetrix", "Calmex",
    "Marmex", "Solmex", "Olvmex", "Stelmex", "Norvmex", "Karvmex",
    "Plenmex", "Lummex",
    "Veresca", "Caleska", "Mareska", "Soleska", "Olveska", "Steleska",
    "Norveska", "Karveska", "Pleneska", "Lumeska",
    "Maresta", "Solesta", "Olvesta", "Stelesta", "Norvesta",

    # Block D: distinctive short invented
    "Pravin", "Solvik", "Marvik", "Olvik", "Karvik", "Plenvik",
    "Lumvik", "Calvik", "Stelvik", "Norvik2",
    "Verdek", "Caldek", "Mardek", "Soldek", "Olvdek", "Steldek",
    "Norvdek", "Karvdek", "Plendek", "Lumdek",
    "Brento", "Crento", "Dremto", "Ferto", "Gerto", "Hento", "Iverto",
    "Jorto", "Kalvto", "Lurmento",

    # Block E: -axis / -ova / -ient / -ord
    "Verbaxis", "Calbaxis", "Marbaxis", "Solbaxis", "Olvbaxis",
    "Stelbaxis", "Norvbaxis", "Karvbaxis", "Plenbaxis", "Lumbaxis",
    "Verdova", "Caldova", "Mardova", "Soldova", "Olvdova",
    "Steldova", "Norvdova", "Karvdova", "Plendova", "Lumdova",
    "Verdord", "Caldord", "Mardord", "Soldord", "Olvdord",
    "Steldord", "Norvdord", "Karvdord", "Plendord", "Lumdord",

    # Block F: holdfast / steadwell / quietwright kind of two-word pro
    "Quietfield", "Quietridge", "Quietport", "Quietstone", "Quietwell",
    "Steadfield", "Steadridge", "Steadport", "Steadstone", "Steadwell2",
    "Truefield", "Trueridge", "Trueport", "Truestone", "Truewell",
    "Boldfield", "Boldridge", "Boldport", "Boldstone", "Boldwell",
    "Northfield2", "Northridge2", "Northport", "Northstone", "Northwell",
    "Stillfield", "Stillridge", "Stillport", "Stillstone", "Stillwell",

    # Block G: -ridge / -path / -wright variations
    "Calridge", "Marridge", "Solridge", "Olvridge", "Stelridge2",
    "Calpath", "Marpath2", "Solpath", "Olvpath", "Stelpath2",
    "Calwright", "Marwright", "Solwright", "Olvwright", "Stelwright",

    # Block H: distinct fresh stems
    "Avronell", "Brovenell", "Crovedell", "Drovendel", "Eronvell",
    "Frovendel", "Grovendel", "Hrovendell", "Irovendel", "Jrovendel",
    "Krovendel", "Lrovendel", "Mrovendel", "Nrovendel", "Orovendel",
    "Provendel", "Qrovendel", "Rrovendel", "Srovendel", "Trovendel",
    "Urovendel", "Vrovendel", "Wrovendel", "Yrovendel", "Zrovendel",

    # Block I: - ier / -ial / -tor enterprise
    "Calatier", "Maratier", "Solatier", "Olvatier", "Stelatier",
    "Norvatier", "Karvatier", "Plenatier", "Lumatier", "Vendatier",
    "Calatial", "Maratial", "Solatial", "Olvatial", "Stelatial",
    "Norvatial", "Karvatial", "Plenatial", "Lumatial", "Vendatial",
    "Caltor", "Martor", "Soltor", "Olvtor", "Steltor",
    "Norvtor", "Karvtor", "Plentor", "Lumtor", "Vendtor",

    # Block J: -ity / -ence / -ance ideas
    "Calivity", "Marivity", "Solivity", "Olvivity", "Stelivity",
    "Norvivity", "Karvivity", "Plenivity", "Lumivity", "Vendivity",
    "Calanence", "Maranence", "Solanence", "Olvanence", "Stelanence",
    "Norvanence", "Karvanence", "Plenanence", "Lumanence", "Vendanence",

    # Block K: pure invented variations
    "Vendaris", "Calaris", "Maris", "Solaris2", "Olvaris", "Stelaris2",
    "Norvaris", "Karvaris", "Plenaris2", "Lumaris2",
    "Vendoria", "Caloria", "Maroria", "Soloria", "Olvoria", "Steloria",
    "Norvoria", "Karvoria", "Plenoria", "Lumoria",

    # Block L: distinct one-off words
    "Tarvora", "Pelmaron", "Quivora", "Renvora", "Stradox",
    "Tovaron", "Vrendar", "Yvenor", "Zelendar", "Aremvor",
    "Bridvor", "Calmaron", "Domvora", "Ervaron", "Felvaron",
    "Gravaron", "Holvor", "Indrar", "Jovaron", "Kalvor",
    "Lavron", "Marvor", "Norvor", "Olvor", "Pelvor",
    "Quivor", "Renvor", "Solvor", "Tarvor", "Uvron",
    "Vendvor", "Welvor", "Yvenvor", "Zerivor",
]


def main():
    out = Path("/Users/janchinapoo/max/incorp/data/pool_v5.txt")
    seen = set()
    for prev in ["pool.txt", "pool_v2.txt", "pool_v3.txt", "pool_v4.txt"]:
        p = Path(f"/Users/janchinapoo/max/incorp/data/{prev}")
        if p.exists():
            for line in p.read_text().splitlines():
                if "\t" in line:
                    seen.add(line.split("\t", 1)[1].lower())
    lines = []
    dropped = 0
    for n in NAMES:
        # strip trailing "2" sentinel I used to avoid dupes against my own list
        clean = n.rstrip("2")
        if not clean.lower() in seen and len(clean) >= 4:
            seen.add(clean.lower())
            lines.append(f"tech_general\t{clean}")
        else:
            dropped += 1
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} unique new names to {out}")
    print(f"  dropped {dropped} duplicates")


if __name__ == "__main__":
    main()
