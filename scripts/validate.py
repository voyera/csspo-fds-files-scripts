#!/usr/bin/env python3
"""Sanity-check extracted FDS data against known 24-25 figures."""
import json
from pathlib import Path

data = json.loads((Path(__file__).resolve().parent.parent / "extracted" / "fds_raw.json").read_text())

# (code, expected budget, depense, revenu, disponibilite) from the 24-25 PDF summary rows
EXPECT = [
    ("001", 46706.00, 53140.90, 72106.83, 34371.93),
    ("004", 198529.00, 36783.88, 24954.31, 28788.43),
    ("006", 289834.00, 118110.95, 93920.01, 89643.06),
    ("012", 193532.00, 112220.44, 80336.10, 110147.66),
    ("037", 18500.00, 31046.43, 50688.82, 19642.39),
]

y = data["24-25"]
ok = True
for code, b, d, r, disp in EXPECT:
    s = y[code]["summary"]
    got = (s.get("budget"), s.get("depense"), s.get("revenu"), s.get("disponibilite"))
    exp = (b, d, r, disp)
    match = all(g is not None and abs(g - e) < 0.5 for g, e in zip(got, exp))
    ok = ok and match
    print(f"{code} {'OK ' if match else 'BAD'} got={got} exp={exp}")

# Cross-check: revenu column summed from accounts should match summary revenu
print("\n-- account-sum vs summary (revenu / depense) for 24-25 --")
for code in ["001", "006", "012"]:
    accts = y[code]["accounts"]
    rev = sum(a["revenu"] for a in accts.values())
    dep = sum(a["depense"] for a in accts.values())
    s = y[code]["summary"]
    print(f"{code} rev acct={rev:.2f} summary={s['revenu']:.2f} | dep acct={dep:.2f} summary={s['depense']:.2f}")

print("\nALL OK" if ok else "\nMISMATCH")
