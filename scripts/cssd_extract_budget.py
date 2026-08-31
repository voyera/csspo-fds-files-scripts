#!/usr/bin/env python3
"""
Extraction des prévisions budgétaires CSSD (PDF numériques, gabarit 2021-22+).

Cible la page « Comparatif par section » de chaque PDF, qui porte trois
colonnes d'exercices (Prévisions N, Révisions N-1, Résultats N-2) :
  - la ligne « Clientèle » (effectif de l'école) ;
  - la section « Activités et campagnes de financement » (Revenus / Dépenses).
La colonne « Résultats N-2 » fournit les REVENUS ET DÉPENSES RÉELS des
campagnes de financement — la seule mesure comparable au « argent amassé /
dépensé » du CSSPO (le grand livre FDS ne l'est pas).

PIÈGE CONNU : l'ordre de lecture de la couche texte mélange les colonnes.
Toute l'extraction est donc par coordonnées : les jetons d'une ligne sont
triés par x, et les colonnes sont identifiées par les années imprimées dans
les en-têtes de la page — jamais supposées.

Hors périmètre, avec statut explicite (jamais un zéro silencieux) :
  - PDF scannés (pas de couche texte) ;
  - gabarit « Commission scolaire » de 2019-20 / 2020-21.

Sortie : extracted/cssd_budget_raw.json
"""
import json
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "extracted" / "cssd_manifest.json").read_text())
OUT = ROOT / "extracted" / "cssd_budget_raw.json"

MODERN_YEARS = {"2021-2022", "2022-2023", "2023-2024", "2025-2026"}
YEAR_RE = re.compile(r"^20\d{2}-20\d{2}$")
# montant : « 671 939 », « (12 200) », « - » ; le « $ » est un jeton séparé
AMOUNT_RE = re.compile(r"^\(?-?[\d  ]+\)?$|^-$")


def parse_amount(tok: str):
    tok = tok.strip()
    if tok == "-":
        return 0
    neg = tok.startswith("(") and tok.endswith(")")
    digits = re.sub(r"[^\d]", "", tok)
    if not digits:
        return None
    v = int(digits)
    return -v if neg else v


def lines_of(page):
    """Regroupe les mots par ligne visuelle (tri x), clé = position verticale."""
    words = page.extract_words(keep_blank_chars=False)
    rows = {}
    for w in words:
        key = round(w["top"] / 3)  # tolérance verticale ~3 pt
        rows.setdefault(key, []).append(w)
    out = []
    for key in sorted(rows):
        ws = sorted(rows[key], key=lambda w: w["x0"])
        out.append((key * 3, ws))
    return out


def find_comparatif_page(pdf):
    for i, page in enumerate(pdf.pages[:6]):
        txt = page.extract_text() or ""
        if "Clientèle" in txt and "campagnes de financement" in txt:
            return i, page
    return None, None


def column_years(lines, before_top):
    """Années des en-têtes de colonnes : la ligne la plus basse au-dessus de
    « Clientèle » portant plusieurs jetons d'année (le titre de page peut
    contenir une année isolée — il est ainsi ignoré). Tri par x = ordre visuel."""
    toks = [(top, w["x0"], w["text"])
            for top, ws in lines if top < before_top
            for w in ws if YEAR_RE.match(w["text"])]
    if not toks:
        return []
    # bande verticale de ±15 pt autour du jeton le plus bas : les trois
    # en-têtes de colonnes, même si l'arrondi de ligne les sépare
    lowest = max(t for t, _, _ in toks)
    band = sorted((x, y) for t, x, y in toks if t >= lowest - 15)
    return [y for _, y in band]


def amounts_in(ws):
    """Montants d'une ligne, en ordre visuel. Les milliers sont des jetons
    séparés (« 8 000 » → « 8 », « 000 ») : on fusionne les jetons numériques
    adjacents dont l'écart horizontal est petit ; un grand écart = colonne
    suivante. Le « $ » clôt toujours le montant en cours."""
    vals = []
    buf = []
    prev_x1 = None

    def flush():
        nonlocal buf
        if buf:
            v = parse_amount("".join(buf))
            if v is not None:
                vals.append(v)
            buf = []

    for w in ws:
        t = w["text"]
        if t == "$":
            flush()
            prev_x1 = None
            continue
        if AMOUNT_RE.match(t):
            if buf and prev_x1 is not None and w["x0"] - prev_x1 > 12:
                flush()
            buf.append(t)
            prev_x1 = w["x1"]
        else:
            flush()
            prev_x1 = None
    flush()
    return vals


def extract_file(path: Path):
    with pdfplumber.open(path) as pdf:
        idx, page = find_comparatif_page(pdf)
        if page is None:
            return {"status": "page-comparatif-introuvable"}
        lines = lines_of(page)

        cli_top = None
        campagne_top = None
        for top, ws in lines:
            text = " ".join(w["text"] for w in ws)
            if cli_top is None and text.startswith("Clientèle") and "régulier" not in text:
                cli_top = top
                cli_vals = amounts_in(ws)
            if "campagnes de financement" in text:
                campagne_top = top
        if cli_top is None:
            return {"status": "ligne-clientele-introuvable", "page": idx + 1}

        years = column_years(lines, cli_top)
        if len(years) != 3:
            return {"status": f"en-têtes d'années inattendus: {years}", "page": idx + 1}

        rec = {"status": "ok", "page": idx + 1, "columnYears": years,
               "clientele": dict(zip(years, cli_vals)) if len(cli_vals) == len(years) else None}

        if campagne_top is not None:
            rev = dep = None
            for top, ws in lines:
                if top <= campagne_top or top > campagne_top + 40:
                    continue
                text = " ".join(w["text"] for w in ws)
                vals = amounts_in(ws)
                if text.startswith("Revenus") and rev is None and len(vals) == 3:
                    rev = vals
                elif text.startswith("Dépenses") and dep is None and len(vals) == 3:
                    dep = vals
            if rev and dep:
                rec["campagnes"] = {y: {"rev": r, "dep": d}
                                    for y, r, d in zip(years, rev, dep)}
            else:
                rec["campagnes"] = None
                rec["campagnesNote"] = "section trouvée mais lignes Revenus/Dépenses non appariées"
        else:
            rec["campagnes"] = None
            rec["campagnesNote"] = "section absente de la page comparatif"
        return rec


def main():
    out = {}
    problems = []
    for e in MANIFEST["entries"]:
        if e["family"] != "budget" or e["status"] != "present":
            continue
        year, code = e["year"], e["code"]
        out.setdefault(year, {})
        if year not in MODERN_YEARS:
            out[year][code] = {"status": "gabarit-ancien-hors-perimetre"}
            continue
        if not e.get("textLayer"):
            out[year][code] = {"status": "scanne-sans-couche-texte"}
            continue
        rec = extract_file(ROOT / e["file"])
        rec["file"] = e["file"]
        out[year][code] = rec
        if rec["status"] != "ok":
            problems.append(f"{year} {code}: {rec['status']}")
        elif rec.get("clientele") is None:
            problems.append(f"{year} {code}: clientèle non alignée sur les colonnes")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    ok = sum(1 for y in out.values() for r in y.values() if r.get("status") == "ok")
    skipped = sum(1 for y in out.values() for r in y.values() if r.get("status") != "ok")
    print(f"extrait: {ok} PDF ok, {skipped} hors périmètre/scannés (statuts explicites)")
    for p in problems:
        print("PROBLÈME:", p)
    if problems:
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
