#!/usr/bin/env python3
"""
Manifeste des sources CSSD (Centre de services scolaire des Draveurs).

Construit la grille attendue école × exercice × famille de documents et
enregistre, pour chaque case : le fichier trouvé (chemin + hash SHA-256),
le format détecté, ou la raison explicite de l'absence. L'extraction et le
site doivent distinguer « source absente » de « valeur zéro » — jamais
convertir l'un en l'autre.

Sortie : extracted/cssd_manifest.json
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSSD = ROOT / "Centre de services scolaire des Draveurs"
OUT = ROOT / "extracted" / "cssd_manifest.json"

FDS_DIR = CSSD / "Fonds à destination spéciale"
BUDGET_DIR = CSSD / "Prévision budgétaire établissements"

FDS_YEARS = ["2019-2020", "2020-2021", "2021-2022", "2022-2023", "2023-2024"]
BUDGET_YEARS = FDS_YEARS + ["2025-2026"]

# Identité des établissements : le code est la clé, le nom officiel vient de
# l'INTÉRIEUR des documents (les noms de fichiers contiennent des erreurs —
# ex. « 072 De l'Odyssée.png » en 2019-20 alors que la page titre du PDF dit
# ÉCOLE DU BOIS JOLI). Cas particuliers documentés dans "identity_notes".
SCHOOLS = {
    "050": "Massé",
    "051": "La Source",
    "053": "du Nouveau-Monde",
    "054": "de Touraine",
    "056": "le Tremplin",
    "059": "l'Oiseau Bleu",
    "063": "Sainte-Élisabeth",
    "064": "de la Colline",
    "065": "le Petit Prince",
    "066": "de l'Envolée",
    "067": "du Vallon",
    "068": "des Cépages",
    "069": "de l'Escalade",
    "070": "de l'Odyssée",
    "072": "du Bois-Joli",
    "073": "des Trois-Saisons",
    "075": "Carle",
    "076": "des Sentiers",          # PDF 2023-24 titré « École Lavigne » (renommage)
    "077": "l'Équipage",
    "079": "des Belles-Rives",
    "080": "de la Montée",
    "081": "de la Traversée",       # jusqu'en 2022-23; voir 097
    "083": "la Sablonnière",
    "085": "des Apprentis-Sages",
    "086": "de la Rose-des-Vents",
    "087": "de l'Orée-des-Bois",
    "088": "du Sommet",
    "089": "du Cheval-Blanc",
    "097": "de la Traversée",       # à partir de 2023-24 (ex-081; clientèle 425→254)
}

IDENTITY_NOTES = {
    "072": "Nom de fichier FDS 2019-20 erroné (« De l'Odyssée ») ; la page "
           "titre des prévisions budgétaires confirme ÉCOLE DU BOIS JOLI.",
    "076": "Nouvelle école apparue en 2023-24 ; PDF titré « École Lavigne », "
           "PNG FDS nommé « Des Sentiers » (renommage à vérifier).",
    "081": "Code utilisé jusqu'en 2022-23 pour l'école de la Traversée.",
    "097": "Reprend l'école de la Traversée à partir de 2023-24 "
           "(clientèle 425 → 254 : possible scission, à documenter).",
}

# Cases attendues absentes de l'archive, avec la raison connue.
EXPECTED_ABSENT = {
    ("076", "2019-2020"): "école inexistante avant 2023-24",
    ("076", "2020-2021"): "école inexistante avant 2023-24",
    ("076", "2021-2022"): "école inexistante avant 2023-24",
    ("076", "2022-2023"): "école inexistante avant 2023-24",
    ("097", "2019-2020"): "code inexistant avant 2023-24 (voir 081)",
    ("097", "2020-2021"): "code inexistant avant 2023-24 (voir 081)",
    ("097", "2021-2022"): "code inexistant avant 2023-24 (voir 081)",
    ("097", "2022-2023"): "code inexistant avant 2023-24 (voir 081)",
    ("081", "2023-2024"): "code remplacé par 097 à partir de 2023-24",
    ("081", "2025-2026"): "code remplacé par 097 à partir de 2023-24",
    ("085", "2019-2020"): "absent de la réponse d'accès (budget seulement)",
}

# Formats FDS par exercice (vérifiés visuellement sur échantillons).
FDS_FORMAT = {
    "2019-2020": "summary-4-lignes",       # appropriation imprimée positive, soustraite
    "2020-2021": "table-projets-ajouts",   # colonne « Ajouts »
    "2021-2022": "table-projets-revenus",  # négatifs entre parenthèses
    "2022-2023": "table-projets-revenus",
    "2023-2024": "table-projets-revenus",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def find_file(directory: Path, code: str, ext: str):
    matches = sorted(p for p in directory.iterdir()
                     if p.suffix.lower() == ext and p.name.startswith(code))
    return matches


def budget_has_text_layer(path: Path) -> bool:
    try:
        import pdfplumber
        import warnings
        warnings.filterwarnings("ignore")
        with pdfplumber.open(path) as pdf:
            return sum(len(p.chars) for p in pdf.pages[:2]) > 0
    except Exception:
        return False


def main():
    entries = []
    problems = []
    for family, base, years, ext in [
        ("fds", FDS_DIR, FDS_YEARS, ".png"),
        ("budget", BUDGET_DIR, BUDGET_YEARS, ".pdf"),
    ]:
        for year in years:
            ydir = base / year
            for code in SCHOOLS:
                matches = find_file(ydir, code, ext)
                key = (code, year)
                if len(matches) == 1:
                    f = matches[0]
                    entry = {
                        "family": family, "year": year, "code": code,
                        "school": SCHOOLS[code],
                        "file": str(f.relative_to(ROOT)),
                        "sha256": sha256(f),
                        "status": "present",
                    }
                    if family == "fds":
                        entry["format"] = FDS_FORMAT[year]
                    else:
                        entry["textLayer"] = budget_has_text_layer(f)
                    entries.append(entry)
                elif len(matches) == 0:
                    reason = EXPECTED_ABSENT.get(key)
                    entries.append({
                        "family": family, "year": year, "code": code,
                        "school": SCHOOLS[code],
                        "status": "absent",
                        "reason": reason or "ABSENCE NON EXPLIQUÉE",
                    })
                    if reason is None:
                        problems.append(f"{family} {year} {code}: absent sans raison connue")
                else:
                    problems.append(f"{family} {year} {code}: {len(matches)} fichiers")

            # fichiers non rattachés à un code connu
            for f in sorted(ydir.iterdir()):
                if f.suffix.lower() != ext:
                    continue
                m = re.match(r"^(\d{3})", f.name)
                if not m or m.group(1) not in SCHOOLS:
                    problems.append(f"{family} {year}: fichier inattendu {f.name}")

    out = {
        "network": "cssd",
        "schools": SCHOOLS,
        "identityNotes": IDENTITY_NOTES,
        "entries": entries,
        "problems": problems,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    present = sum(1 for e in entries if e["status"] == "present")
    absent = sum(1 for e in entries if e["status"] == "absent")
    print(f"manifest: {present} fichiers présents, {absent} cases absentes (expliquées)")
    for p in problems:
        print("PROBLÈME:", p)
    if problems:
        raise SystemExit(1)
    print("OK — aucune absence inexpliquée, aucun fichier orphelin")


if __name__ == "__main__":
    main()
