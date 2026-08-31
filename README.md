# CSSPO — Demande d'accès à l'information : budgets & fonds à destination spéciale

Archive des **documents officiels** obtenus par demande d'accès à l'information
auprès du **Centre de services scolaire des Portages-de-l'Outaouais (CSSPO)**,
région de Gatineau, en **octobre 2025**, ainsi que des **scripts Python** qui en
extraient les données.

La demande portait sur les **budgets des écoles primaires** — en particulier le
**fonds à destination spéciale (FDS)**, alimenté par les levées de fonds et les
dons des familles. Ces données alimentent le site de transparence
**[Le Dossier FDS](https://csspo-fds.vercel.app/)** (code :
`github.com/voyera/csspo-fds`).

---

## Contenu de l'archive

```
OneDrive_1_2025-10-08/
├── 25_10-08 réponse.pdf            # Lettre-réponse du CSSPO à la demande
├── Avis de recours en révison.pdf  # Avis des droits de recours (révision)
├── 2021-2022/                      # Préparation budgétaire 2021-22 (format groupé)
└── 251006-Budgets et FDS/
    ├── Fonds à destination spéciale/   # ★ Rapports « État des catégories » (Dofin)
    │   └── 19-20.pdf … 25-26.pdf       #   un PDF par exercice, toutes les écoles
    ├── 19-20-Budget/ … 24-25-Budget/   # Préparation budgétaire, un PDF par école
    │   └── 001.pdf … 037.pdf           #   (le nom commence par le code d'établissement)
    └── …
```

### Deux familles de documents

1. **Rapports « État des catégories » (FDS)** — `Fonds à destination spéciale/*.pdf`
   Un rapport comptable par exercice (2019-20 → 2025-26). Pour chaque école et
   chaque compte : **budget, engagement, dépense, revenu, disponibilité**. C'est
   la source des montants *réels* (ce qui est passé au compte).

2. **Préparation budgétaire par école** — `NN-NN-Budget/NNN.pdf`
   Le budget *proposé* par la direction, avec ses annexes. L'**Annexe D — Fonds
   à destination spéciale** contient les **lignes descriptives** du budget
   proposé (ex. « Campagne de financement dîner Pizza », « Embellissement de la
   cour d'école »). Le nom de fichier commence par le code d'établissement
   (`034` = de la Forêt, etc.).

---

## Scripts d'extraction

Écrits en Python avec [`pdfplumber`](https://github.com/jsvine/pdfplumber)
(extraction par coordonnées, robuste aux espaces de séparation des milliers).

| Script | Rôle | Sortie |
|---|---|---|
| `scripts/extract_fds.py` | Parse les rapports « État des catégories » | `extracted/fds_raw.json` |
| `scripts/extract_budget.py` | Parse l'Annexe D des préparations budgétaires | `extracted/proposed_budget.json` |
| `scripts/validate.py` | Vérifie l'extraction FDS contre des totaux connus de 24-25 | (affiche `ALL OK`) |

### Installation & exécution

```bash
python3 -m pip install --user pdfplumber

python3 scripts/extract_fds.py       # → extracted/fds_raw.json
python3 scripts/extract_budget.py    # → extracted/proposed_budget.json
python3 scripts/validate.py          # doit afficher « ALL OK »
```

Les chemins sont relatifs à ce dépôt : les scripts lisent dans
`OneDrive_1_2025-10-08/` et écrivent dans `extracted/`. Les fichiers JSON
extraits sont versionnés pour pouvoir être utilisés directement.

### Fiabilité

L'extraction FDS est **validée au cent près** contre les totaux imprimés des
rapports originaux (`validate.py`). Les montants des préparations budgétaires
ne comptent comme « postes proposés » que les lignes portant réellement un
montant en dollars (les chiffres internes aux libellés, comme « Bloc 1 », sont
ignorés).

---

## Centre de services scolaire des Draveurs (CSSD)

Deuxième réponse d'accès à l'information, dans
`Centre de services scolaire des Draveurs/` : ~28 écoles primaires
(codes 050–097), **FDS en captures PNG** (2019-20 → 2023-24, une image par
école) et **prévisions budgétaires en PDF** (2019-20 → 2023-24 + 2025-26).
Sémantique différente du CSSPO : les rapports FDS montrent le *grand livre du
fonds* (solde début, ajouts/revenus = transferts vers le fonds, appropriation
= sortie du fonds quand la dépense est engagée, solde fin) — PAS le
revenu/dépense des campagnes de financement (ceux-ci sont dans les colonnes
« Résultats N-2 » des PDF budgétaires).

| Script | Rôle | Sortie |
|---|---|---|
| `scripts/cssd_manifest.py` | Grille école×exercice, hash, format, absences expliquées | `extracted/cssd_manifest.json` |
| _(extraction vision, en session)_ | Lecture des 136 captures FDS → JSON grand-livre | `extracted/cssd_fds_raw.json` |
| `scripts/cssd_validate_fds.py` | Identités comptables, totaux imprimés, continuité inter-exercices | `ALL OK` |
| `scripts/cssd_ocr_crosscheck.py` | Contre-lecture indépendante (tesseract 4×), désaccords arbitrés | `0 désaccords` |
| `scripts/cssd_extract_budget.py` | PDF numériques 2021-22+ : Clientèle (effectif) + campagnes de financement, 3 colonnes datées par les en-têtes (extraction par coordonnées) | `extracted/cssd_budget_raw.json` |

Les colonnes « Résultats N-2 » des PDF numériques donnent les revenus et
dépenses **réels** des campagnes de financement pour 2019-20, 2021-22 et
2023-24 (2020-21 : seulement les 15 écoles au PDF 2022-23 numérique).

### Fiabilité (CSSD)

Montants en **dollars entiers** dans la source : l'affirmation est « rapproché
des totaux imprimés » (tolérance d'arrondi ±3 $ par ligne), jamais « au cent
près ». Chaque valeur est validée par (1) l'identité
`solde fin = début + ajouts − appropriation`, (2) la ligne des totaux
imprimée, (3) la continuité des soldes entre exercices, et (4) une
contre-lecture OCR indépendante pour les formats tableau (le gabarit résumé
2019-20 est illisible par tesseract ; il est couvert par 1-3). Tous les
désaccords OCR sont arbitrés à la main par recadrage et consignés dans
`extracted/cssd_ocr_adjudications.json`. Anomalies **de la source** relevées
et documentées dans le JSON : lignes masquées (051 et 072 en 2022-23),
incohérence de ±180 $ (070 en 2021-22), solde début vierge (073 en 2019-20),
restatement 065 entre 2020-21 et 2021-22, remplacement du code 081 par 097
(Traversée) en 2023-24.

---

## Notes

- Codes d'établissement : voir le mappage code → nom dans
  `scripts/build_data.py` du dépôt du site.
- L'exercice **2025-26** est *provisoire* (rapport produit en début d'année) :
  surtout du budget, peu de transactions réelles.
- Documents publics obtenus par accès à l'information ; archive citoyenne
  indépendante, sans affiliation avec le CSSPO.
