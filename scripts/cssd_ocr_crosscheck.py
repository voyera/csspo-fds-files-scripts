#!/usr/bin/env python3
"""
Contre-vérification indépendante de l'extraction FDS CSSD par OCR (tesseract).

Deuxième lecture indépendante des captures PNG : pour chaque école-exercice,
tous les montants de l'extraction (extracted/cssd_fds_raw.json) doivent
apparaître dans le texte OCR de l'image, et tous les montants « significatifs »
vus par l'OCR doivent exister dans l'extraction. Tout désaccord est listé pour
arbitrage manuel (ré-inspection de l'image) — l'OCR n'est jamais réputé avoir
raison, il sert de détecteur de divergence.

Usage : python3 scripts/cssd_ocr_crosscheck.py [année ...]
"""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = json.loads((ROOT / "extracted" / "cssd_fds_raw.json").read_text())
MANIFEST = json.loads((ROOT / "extracted" / "cssd_manifest.json").read_text())

FILES = {(e["year"], e["code"]): ROOT / e["file"]
         for e in MANIFEST["entries"]
         if e["family"] == "fds" and e["status"] == "present"}

# Désaccords OCR déjà arbitrés à la main (ré-inspection de l'image), avec la
# raison consignée. L'OCR n'a jamais raison d'office : chaque entrée documente
# pourquoi l'extraction est maintenue.
ADJ_PATH = ROOT / "extracted" / "cssd_ocr_adjudications.json"
ADJUDICATED = json.loads(ADJ_PATH.read_text()) if ADJ_PATH.exists() else {}

# jetons numériques : « 12 345 » (milliers séparés par espace fine/insécable)
# ou séquence de chiffres collés (l'OCR perd parfois le séparateur)
NUM = re.compile(r"(?<![\d,.])(\d{1,3}(?:[   ]\d{3})+|\d{1,6})(?![\d,.])")

SEP = re.compile(r"[   ]")


def ocr_numbers(png: Path) -> Counter:
    # tesseract lit mal les captures à taille native (séparateurs de milliers
    # en espace fine sur fond gris) ; un agrandissement 4× règle l'essentiel.
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        img = Image.open(png).convert("L")
        img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)
        img.save(tmp.name)
        out = subprocess.run(
            ["tesseract", tmp.name, "stdout", "-l", "fra", "--psm", "6"],
            capture_output=True, text=True, check=True).stdout
    nums = Counter()
    for m in NUM.finditer(out):
        nums[int(SEP.sub("", m.group(1)))] += 1
    return nums


def expected_numbers(rec) -> Counter:
    nums = Counter()
    for p in rec.get("projects", []) + [rec["totals"]]:
        for col in ("open", "add", "approp", "close"):
            v = p[col]
            if v:  # les zéros sont imprimés « - », pas 0
                nums[v] += 1
    return nums


# Le rendu 2019-20 (sérif gras, ancien gabarit) est illisible pour tesseract
# quel que soit le prétraitement (agrandissement, binarisation, psm) : les
# montants en gras de la colonne de droite sont simplement omis. Pour cet
# exercice, la contre-vérification indépendante est assurée autrement :
# identité comptable interne + continuité des soldes avec les captures
# 2020-21 (documents indépendants), toutes deux vérifiées par
# cssd_validate_fds.py. L'OCR n'est donc exécuté que sur les formats tableau.
OCR_UNSUPPORTED_FORMATS = {"summary-4-lignes"}


def main():
    years = sys.argv[1:] or sorted(RAW.keys())
    disagreements = 0
    checked = 0
    skipped = 0
    for year in years:
        for code, rec in sorted(RAW.get(year, {}).items()):
            if rec.get("format") in OCR_UNSUPPORTED_FORMATS:
                skipped += 1
                continue
            png = FILES.get((year, code))
            if png is None:
                print(f"{year} {code}: PNG introuvable dans le manifeste")
                disagreements += 1
                continue
            seen = ocr_numbers(png)
            expect = expected_numbers(rec)
            checked += 1

            adj_missing = Counter()
            adj_extra = Counter()
            for a in ADJUDICATED.get(year, {}).get(code, []):
                (adj_missing if a["kind"] == "missing" else adj_extra)[a["value"]] += a["count"]

            missing = expect - seen - adj_missing
            for v, n in sorted(missing.items()):
                print(f"{year} {code}: attendu {v} $ ({n}×) absent de l'OCR — à arbitrer")
                disagreements += n
            # montants significatifs vus par l'OCR mais absents de l'extraction
            # (seuil : ≥ 100 $ pour ignorer numéros de groupe, années, bruit)
            extra = Counter({v: n for v, n in (seen - expect - adj_extra).items() if v >= 100})
            # retirer le bruit connu : années scolaires imprimées dans les libellés
            for noise in (2019, 2020, 2021, 2022, 2023, 2024, 901, 902):
                extra.pop(noise, None)
            for v, n in sorted(extra.items()):
                print(f"{year} {code}: OCR voit {v} ({n}×) absent de l'extraction — à arbitrer")
                disagreements += n

    print(f"\n{checked} images contre-vérifiées, {disagreements} désaccords à arbitrer"
          + (f" ({skipped} au format résumé 2019-20, hors OCR — voir note)" if skipped else ""))
    sys.exit(1 if disagreements else 0)


if __name__ == "__main__":
    main()
