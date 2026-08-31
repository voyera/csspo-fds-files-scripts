#!/usr/bin/env python3
"""
Validation de l'extraction FDS CSSD (extracted/cssd_fds_raw.json).

Trois familles de contrôles :
  1. Identité comptable par ligne et par totaux :
       solde_fin = solde_début + ajouts − appropriations
     Les rapports sont en dollars entiers (cents cachés), donc tolérance de
     ± TOL_LINE $ par ligne. L'affirmation publique est « rapproché des totaux
     imprimés en dollars entiers », jamais « au cent près ».
  2. Somme des lignes = ligne des totaux imprimée (par colonne, ± TOL_SUM).
  3. Continuité inter-exercices : solde_fin(N) = solde_début(N+1) par école
     (± TOL_LINE), sauf discontinuités documentées dans KNOWN_BREAKS.

Sortie non nulle si un contrôle échoue.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = json.loads((ROOT / "extracted" / "cssd_fds_raw.json").read_text())

TOL_LINE = 3   # arrondi de cents cachés par ligne
TOL_SUM = 5    # accumulation d'arrondis sur la ligne des totaux

YEARS = ["2019-2020", "2020-2021", "2021-2022", "2022-2023", "2023-2024"]

# Discontinuités attendues entre exercices : (code, année_N, année_N+1) -> raison
KNOWN_BREAKS = {
    ("081", "2022-2023", "2023-2024"): "code 081 remplacé par 097 (Traversée)",
    ("065", "2020-2021", "2021-2022"):
        "restatement dans la source : solde fin 2020-21 imprimé 3 284 $ mais "
        "solde début 2021-22 imprimé 970 $ (écart 2 314 $, vérifié par "
        "recadrage sur les deux captures)",
}


def check(errors, cond, msg):
    if not cond:
        errors.append(msg)


def main():
    errors = []
    warnings = []

    for year, schools in sorted(RAW.items()):
        for code, rec in sorted(schools.items()):
            where = f"{year} {code}"
            t = rec["totals"]

            # 1. identité par ligne (sauf anomalie de source documentée sur la ligne)
            for p in rec.get("projects", []):
                delta = p["open"] + p["add"] - p["approp"] - p["close"]
                if p.get("sourceAnomaly"):
                    warnings.append(f"{where} « {p['label']} »: anomalie de source "
                                    f"documentée (delta {delta:+d} $) — {p['sourceAnomaly']}")
                    continue
                check(errors, abs(delta) <= TOL_LINE,
                      f"{where} « {p['label']} »: identité ligne échouée (delta {delta:+d} $)")

            # identité sur les totaux imprimés
            delta = t["open"] + t["add"] - t["approp"] - t["close"]
            check(errors, abs(delta) <= TOL_SUM,
                  f"{where}: identité des totaux échouée (delta {delta:+d} $)")

            # 2. somme des lignes = totaux imprimés
            if rec.get("incompleteLines"):
                warnings.append(f"{where}: lignes incomplètes documentées — {rec.get('note', '')}")
            elif rec.get("projects"):
                for col in ("open", "add", "approp", "close"):
                    s = sum(p[col] for p in rec["projects"])
                    check(errors, abs(s - t[col]) <= TOL_SUM,
                          f"{where}: somme des lignes ({col}) {s} ≠ total imprimé {t[col]}")
            elif rec["format"] != "summary-4-lignes":
                errors.append(f"{where}: aucune ligne projet mais format {rec['format']}")

    # 3. continuité inter-exercices
    for i, year in enumerate(YEARS[:-1]):
        nxt = YEARS[i + 1]
        if year not in RAW or nxt not in RAW:
            continue
        for code, rec in sorted(RAW[year].items()):
            if code not in RAW[nxt]:
                if (code, year, nxt) not in KNOWN_BREAKS:
                    warnings.append(f"{code}: présent en {year}, absent en {nxt}")
                continue
            close_n = rec["totals"]["close"]
            open_n1 = RAW[nxt][code]["totals"]["open"]
            if abs(close_n - open_n1) > TOL_LINE:
                key = (code, year, nxt)
                if key in KNOWN_BREAKS:
                    warnings.append(f"{code} {year}→{nxt}: rupture connue "
                                    f"({KNOWN_BREAKS[key]}): {close_n} → {open_n1}")
                else:
                    errors.append(f"{code} {year}→{nxt}: continuité échouée "
                                  f"(solde fin {close_n} ≠ solde début {open_n1})")

    n_sy = sum(len(v) for v in RAW.values())
    n_lines = sum(len(r.get("projects", [])) for v in RAW.values() for r in v.values())
    print(f"contrôlé : {n_sy} école-exercices, {n_lines} lignes projet")
    for w in warnings:
        print("AVERTISSEMENT:", w)
    if errors:
        for e in errors:
            print("ERREUR:", e)
        sys.exit(1)
    print("ALL OK — identités, totaux imprimés et continuité inter-exercices")


if __name__ == "__main__":
    main()
