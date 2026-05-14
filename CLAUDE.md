# CLAUDE.md — Analyse électorale NFP

## 1. WHY
Outil d'analyse électorale partisane pour le NFP, destiné à préparer les législatives 2027.
Produit des cartes interactives et notes d'analyse par circonscription à partir des données officielles MI / data.gouv.fr.

## 2. WHAT
**Deux niveaux d'analyse, trois échelles géographiques :**
- National : 577 circos (`build_map.py`, `build_model.py`) — progression RN + modèle bascule
- Commune : circ 9502 et extensible (`build_commune_data.py`, `build_map_commune.py`, `build_model_commune.py`)
- Bureau de vote (BdV) : dep 95, focus circ 9502 (`build_bdv_data.py`, `build_map_bdv_9502.py`)

**Scrutins intégrés :** Leg 2024 T1+T2 | Euro 2024 | Leg 2022 T1+T2 | Pres 2022 T1+T2 | Muni 2026

**Livrables :** `carte_*.html` (Folium/Leaflet autonome) + `analyse_*.md` (auto-générée) + `data/*.csv`

**Cache :** `data/_cache_*` — ne jamais supprimer, évite les re-téléchargements

**Agents disponibles :** @data-fetcher | @data-parser | @data-validator | @electoral-analyst | @cartographer | @report-writer
**Règles d'interaction entre agents :** voir `.claude/contracts.md`

## 3. HOW
**Nommage :**
- Scripts : `build_<niveau>_<scope>.py`
- Cartes : `carte_<scope>.html` | Notes : `analyse_<scope>.md`
- Clé circo : 4 chiffres string `"9502"` (dep 2 chiffres + circo 2 chiffres)
- Code commune : 5 chiffres absolus string `"95127"` via `norm_commune()`
- **Clé BdV composite obligatoire :** `f"{code_commune}_{num_bdv}"` — `num_bdv` seul n'est PAS unique

**Blocs électoraux canoniques :**
```
left = {LFI, SOC, DVG, PCF, COM, ECO, VEC, RDG, UG, LEXG, EXG, GS, NUP, LUG, LSOC}
ctr  = {ENS, HOR, DVC, UDI, MDM, REM, LENS}
rgt  = {LR, DVD, DLF, LLR}
far  = {RN, REC, EXD, UXD, DSV, LRN, LREC, LEXD}
```

**Couleurs :** rouge = gauche | jaune = centre | bleu = droite/RN (jamais l'inverse)

**Seuil maintien T2 :** 19.14% des exprimés (ne pas recalculer sans validation humaine)

**Sources :**
- Données électorales : data.gouv.fr (resource IDs dans chaque `build_*.py`)
- Géométries communes : `geo.api.gouv.fr/communes/{code}?fields=contour,centre`
- Boundaries circos : `data/circonscriptions.geojson` (559 features, local)

**Ouvrir les cartes :** toujours `open carte_*.html` dans un vrai navigateur, jamais dans l'IDE

## 4. RÈGLES NON-NÉGOCIABLES
- **RN = extrême droite** — jamais "droite nationale", jamais "droite"
- **NFP = gauche unie** — jamais attribuer les scores NFP à LFI seul
- **Scénario C = risque désunion** — jamais une option neutre ou favorable
- **Données officielles uniquement** — aucun sondage, aucune projection externe
- **Jamais `num_bdv` seul comme clé** — toujours le composite `code_commune_num_bdv`
- **Jamais ignorer `norm_commune()`** sur les anciens codes XLSX relatifs
- **block_size XLSX burvot** : premier `Unnamed:N` dans `bloc_header[1:]`, pas le premier nommé
- **`data-validator` TOUJOURS invoqué** après `data-parser` avant tout autre agent
- **Cartes HTML autonomes** — ne jamais introduire de dépendances serveur

## 5. ARCHITECTURE
**Stack figé :** Python 3 + pandas + numpy + folium + requests (pas de BDD, pas de backend)

**Chiffres de référence circ 9502 (intangibles, validés vs MI cirlg via REU) :**
- Leg 2024 T1 : NFP 34.4% | RN 31.2% | ENS 25.3% | LR 6.3% | 80 BdV (78 781 inscrits)
- Leg 2024 T2 : NFP 59.5% | RN 40.5%
- Source circ : REU `data/reu_bv_circ_95.csv` (BdV-level) — jamais commune-level
- Cergy (95127) éclatée entre 9502 (11 BdV) et 9510 (24 BdV) — voir EDR-017

**Décisions figées :**
- Scénarios 2027 : matrice 2×2 + référence (voir EDR-020 + EDR-022)
  - Référence : T1 2024 (réel)
  - **Dynamique Philippe** (+12 ENS+LR, -2.5 NFP, -6 RN) × **Union** ou **Désunion**
  - **Effondrement centre** (-12 ENS+LR, +4 NFP, +7 RN) × **Union** ou **Désunion**
- Mécanique modèle v4 (cibles politiques par bloc + scaling uniforme) :
  - Pour chaque bloc b ∈ {centre+LR, NFP, RN} : `scaling_b = (mean_circo_b + cible_b) / mean_circo_b`
  - Projection BdV : `score_27_bdv_b = score_24_bdv_b × scaling_b` (préserve géographie)
  - Asymétrie ENS/LR : sursaut → LR garde 50%, ENS absorbe ; effondrement → partage proportionnel
  - Désunion : split NFP via `lfi_ratio = eu_lfi / (eu_lfi + eu_lug + eu_vec + eu_com)` au BdV
  - Paramètres : `SCENARIO_CIBLES` (dict par bloc), `LR_RETENTION_SURSAUT = 0.5`
  - Cibles calibrées sur les ratios historiques 2017→2024 (centre érodé : 64% RN, 34% NFP)
- Un script = une responsabilité (data download ≠ model ≠ map)
- Pas de tests automatisés — validation manuelle contre chiffres officiels via `data-validator`
