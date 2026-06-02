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

## Notes

- Codes d'établissement : voir le mappage code → nom dans
  `scripts/build_data.py` du dépôt du site.
- L'exercice **2025-26** est *provisoire* (rapport produit en début d'année) :
  surtout du budget, peu de transactions réelles.
- Documents publics obtenus par accès à l'information ; archive citoyenne
  indépendante, sans affiliation avec le CSSPO.
