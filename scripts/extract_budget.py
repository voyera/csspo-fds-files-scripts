#!/usr/bin/env python3
"""
Extract the *descriptive* proposed FDS budget (Annexe D) from each school's
"Préparation budgétaire" PDF — the real line items the direction wrote, e.g.
"Campagne de financement dîner Pizza", "Embellissement de la cour d'école".

These are far richer than the standardized account report (which lumps the
whole plan into "520 - Services spécialisés"). One file per school per year.

Output: data/proposed_budget.json
  { "<year>": { "<code>": {"revenus": [{label, amount}], "depenses": [...]} } }
"""
import json
import re
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "OneDrive_1_2025-10-08" / "251006-Budgets et FDS"
OUT = REPO / "extracted" / "proposed_budget.json"

FOLDERS = {
    "19-20-Budget": "19-20",
    "20-21-Budget": "20-21",
    "22-23-Budget": "22-23",
    "23-24-Budget": "23-24",
    "24-25-Budget": "24-25",
}
KNOWN = {f"{i:03d}" for i in range(1, 38)}
NUM_RE = re.compile(r"^\(?\d[\d ]*\$?\)?$")  # 25 000  | 25 000 $ | (2 528 $)
NUMERICISH = re.compile(r"^[\d ().,$%-]+$")


def to_amount(tok):
    neg = "(" in tok
    digits = re.sub(r"[^\d]", "", tok)
    if not digits:
        return None
    val = float(digits)
    return -val if neg else val


def merge_fragments(words, gap=10):
    out = []
    for w in sorted(words, key=lambda x: x["x0"]):
        if (out and NUMERICISH.match(out[-1]["text"]) and NUMERICISH.match(w["text"])
                and "%" not in out[-1]["text"] and "%" not in w["text"]
                and w["x0"] - out[-1]["x1"] < gap):
            out[-1] = {"text": out[-1]["text"] + " " + w["text"],
                       "x0": out[-1]["x0"], "x1": w["x1"]}
        else:
            out.append({"text": w["text"], "x0": w["x0"], "x1": w["x1"]})
    return out


def lines_of(page, tol=3):
    rows = {}
    for w in page.extract_words():
        rows.setdefault(round(w["top"] / tol), []).append(w)
    out = []
    for k in sorted(rows):
        out.append(merge_fragments(rows[k]))
    return out


def amount_indices(cells):
    """Indices of cells that are real dollar amounts (a number followed by '$',
    or a token already carrying '$'). Excludes bare digits inside labels
    like 'Bloc 1' / 'Bloc 2'."""
    idx = []
    for i, c in enumerate(cells):
        if not NUM_RE.match(c["text"]):
            continue
        has_dollar = "$" in c["text"]
        next_dollar = i + 1 < len(cells) and cells[i + 1]["text"].startswith("$")
        if has_dollar or next_dollar:
            idx.append(i)
    return idx


def amounts_in(cells):
    return [(cells[i]["text"], (cells[i]["x0"] + cells[i]["x1"]) / 2) for i in amount_indices(cells)]


def parse_section(lines, start_idx, stop_label, current_x, prior_x):
    """Collect item lines until a line whose text starts with stop_label."""
    items = []
    for cells in lines[start_idx + 1:]:
        text = " ".join(c["text"] for c in cells).strip()
        if text.upper().startswith(stop_label):
            break
        amt_idx = amount_indices(cells)
        if not amt_idx:
            continue  # sub-header or label-only line with no figure
        amts = [(cells[i]["text"], (cells[i]["x0"] + cells[i]["x1"]) / 2) for i in amt_idx]
        cur = min(amts, key=lambda a: abs(a[1] - current_x))
        if abs(cur[1] - current_x) > abs(cur[1] - prior_x):
            continue  # value only in prior-year column → not budgeted this year
        val = to_amount(cur[0])
        if not val:
            continue
        skip = set(amt_idx)
        label = " ".join(c["text"] for j, c in enumerate(cells)
                          if j not in skip and c["text"] != "$").strip(" :")
        if label:
            items.append({"label": label, "amount": round(val, 2)})
    return items


def find_header_cols(lines):
    """Locate current-year vs prior-year column x using the TOTAL - REVENUS row."""
    for cells in lines:
        text = " ".join(c["text"] for c in cells).upper()
        if "TOTAL" in text and "REVENUS" in text:
            amts = amounts_in(cells)
            if len(amts) >= 2:
                xs = sorted(a[1] for a in amts)
                return xs[0], xs[-1]  # current (left), prior (right)
    return None


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = (page.extract_text() or "").upper()
            if "ANNEXE D" not in txt or "TOTAL - REVENUS" not in txt:
                continue
            lines = lines_of(page)
            cols = find_header_cols(lines)
            if not cols:
                return None
            cur_x, prior_x = cols
            rev_i = dep_i = None
            for i, cells in enumerate(lines):
                t = " ".join(c["text"] for c in cells).strip().upper()
                if t == "REVENUS":
                    rev_i = i
                elif t in ("DÉPENSES", "DEPENSES"):
                    dep_i = i
            if rev_i is None or dep_i is None:
                return None
            revenus = parse_section(lines, rev_i, "TOTAL", cur_x, prior_x)
            depenses = parse_section(lines, dep_i, "TOTAL", cur_x, prior_x)
            return {"revenus": revenus, "depenses": depenses}
    return None


def code_of(filename):
    m = re.match(r"(\d{3})", filename)
    return m.group(1) if m else None


def main():
    result = {}
    for folder, year in FOLDERS.items():
        d = BASE / folder
        if not d.exists():
            continue
        seen = {}
        for pdf in sorted(d.glob("*.pdf")):
            code = code_of(pdf.name)
            if code not in KNOWN:
                continue
            # prefer exact NNN.pdf; otherwise first file for that code
            if code in seen and seen[code].name == f"{code}.pdf":
                continue
            seen[code] = pdf
        year_out = {}
        for code, pdf in sorted(seen.items()):
            try:
                parsed = parse_pdf(pdf)
            except Exception as e:  # noqa
                parsed = None
                print(f"  ! {year}/{code}: {e}")
            if parsed and (parsed["revenus"] or parsed["depenses"]):
                year_out[code] = parsed
        result[year] = year_out
        print(f"{year}: {len(year_out)}/{len(seen)} écoles avec Annexe D détaillée")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
