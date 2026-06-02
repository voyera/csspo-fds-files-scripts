#!/usr/bin/env python3
"""
Extract Fonds a destination speciale (FDS) ledgers from the CSSPO Dofin
"Etat des categories" PDFs (one per fiscal year) into a single JSON file.

Each PDF lists, per school (code NNN + "CFDS"), a set of account lines with
five numeric columns: Budget | Engagement | Depense | Revenu | Disponibilite
(plus a trailing % on some rows). We use pdfplumber word coordinates to assign
each number to the right column, then aggregate per school.
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parent.parent
FDS_DIR = REPO / "OneDrive_1_2025-10-08" / "251006-Budgets et FDS" / "Fonds à destination spéciale"
OUT = REPO / "extracted" / "fds_raw.json"

PCT_RE = re.compile(r"^(\d+%|\*+%)$")  # 223% or ***%
COLUMNS = ["budget", "engagement", "depense", "revenu", "disponibilite"]
HEADER_LABELS = {
    "Budget": "budget",
    "Engagement": "engagement",
    "Dépense": "depense",
    "Revenu": "revenu",
    "Disponibilité": "disponibilite",
}

ACCOUNT_RE = re.compile(r"^(\d{3})-\d-(\d{5})-(\d{3})$")
SCHOOL_RE = re.compile(r"^(\d{3})CFDS$")
NUM_RE = re.compile(r"^\d[\d  ]*,\d{2}-?$")  # 1 234,56 or 1 234,56-


def to_float(tok):
    neg = tok.endswith("-")
    tok = tok.rstrip("-").replace(" ", "").replace(" ", "").replace(",", ".")
    val = float(tok)
    return -val if neg else val


NUMERICISH = re.compile(r"^[\d.,%-]+$")


def merge_fragments(words, gap=10):
    """Stitch number fragments split on thousand-separator spaces.

    '71' + '453,83' (gap ~5px) -> '71 453,83'. Column gaps are >100px so
    distinct columns never merge. Only numeric-ish tokens are stitched."""
    out = []
    for w in sorted(words, key=lambda x: x["x0"]):
        if (out and NUMERICISH.match(out[-1]["text"]) and NUMERICISH.match(w["text"])
                and "%" not in out[-1]["text"] and "%" not in w["text"]
                and w["x0"] - out[-1]["x1"] < gap):
            out[-1] = {"text": out[-1]["text"] + " " + w["text"],
                       "x0": out[-1]["x0"], "x1": w["x1"], "top": out[-1]["top"]}
        else:
            out.append({"text": w["text"], "x0": w["x0"], "x1": w["x1"], "top": w["top"]})
    return out


def group_lines(words, tol=3):
    """Group words into visual lines by their vertical position."""
    lines = []
    for w in sorted(words, key=lambda x: (round(x["top"]), x["x0"])):
        if lines and abs(w["top"] - lines[-1]["top"]) <= tol:
            lines[-1]["words"].append(w)
        else:
            lines.append({"top": w["top"], "words": [w]})
    for ln in lines:
        ln["words"] = merge_fragments(ln["words"])
    return lines


def find_column_centers(lines):
    """Locate the x-center of each numeric column from the header row."""
    for ln in lines:
        labels = {w["text"]: (w["x0"] + w["x1"]) / 2 for w in ln["words"]}
        if "Budget" in labels and "Disponibilité" in labels:
            return {HEADER_LABELS[k]: labels[k] for k in HEADER_LABELS if k in labels}
    return None


def assign_columns(num_words, centers):
    """Map numeric tokens to columns by nearest header center (use right edge)."""
    out = {}
    for w in num_words:
        # numbers are right-aligned; the right edge tracks the column best
        edge = w["x1"]
        col = min(centers, key=lambda c: abs(centers[c] - edge))
        out[col] = to_float(w["text"])
    return out


def parse_pdf(path):
    schools = {}
    centers = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            lines = group_lines(words)
            pc = find_column_centers(lines)
            if pc:
                centers = pc
            current = None
            for ln in lines:
                texts = [w["text"] for w in ln["words"]]
                joined = " ".join(texts)
                # school header
                for t in texts:
                    m = SCHOOL_RE.match(t)
                    if m:
                        current = m.group(1)
                        schools.setdefault(current, {
                            "accounts": {}, "budget_revenu": 0.0, "summary": None})
                if current is None or centers is None:
                    continue
                # account line: first token matches NNN-d-NNNNN-NNN
                m = ACCOUNT_RE.match(texts[0]) if texts else None
                if m:
                    suffix = m.group(3)
                    nums = [w for w in ln["words"] if NUM_RE.match(w["text"])]
                    cols = assign_columns(nums, centers)
                    acc = schools[current]["accounts"].setdefault(
                        suffix, {c: 0.0 for c in COLUMNS})
                    for c, v in cols.items():
                        acc[c] += v
                    continue
                # budget de revenu line
                if "Budget" in joined and "revenu:" in joined:
                    nums = [w for w in ln["words"] if NUM_RE.match(w["text"])]
                    if nums:
                        schools[current]["budget_revenu"] = to_float(nums[-1]["text"])
                    continue
                # summary row: only numbers / percent tokens, >=3 numerics
                non_blank = [t for t in texts if t.strip()]
                nums = [w for w in ln["words"] if NUM_RE.match(w["text"])]
                if non_blank and len(nums) >= 3 and all(
                        NUM_RE.match(t) or PCT_RE.match(t) for t in non_blank):
                    cols = assign_columns(nums, centers)
                    schools[current]["summary"] = cols
                    continue
    return schools


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = {}
    for pdf in sorted(FDS_DIR.glob("*.pdf")):
        year = pdf.stem  # e.g. "24-25"
        schools = parse_pdf(pdf)
        result[year] = schools
        print(f"{year}: {len(schools)} schools", file=sys.stderr)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
