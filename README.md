# Analyse électorale NFP — Législatives 2027

Outil d'analyse électorale partisan (Nouveau Front Populaire) pour préparer les
législatives 2027. Produit des **cartes interactives par bureau de vote** et des
**notes d'analyse** à partir des données officielles du Ministère de l'Intérieur
(data.gouv.fr).

Circonscription pilote : **2ème du Val-d'Oise (9502)** — Ayda Hadizadeh (NFP).

🔗 Carte en ligne : https://remybajo.github.io/datagouv/carte_bdv_9502.html

---

## Structure du projet

```
config_circos.py        ← configuration centralisée (1 bloc par circonscription)
CLAUDE.md               ← contexte projet, règles, décisions

build_bdv_data.py       ← télécharge + parse les résultats par bureau de vote
build_bv_contours.py    ← extrait les contours BdV du REU pour la circo active
build_map_bdv.py        ← génère la carte interactive BdV + scénarios 2027

build_commune_data.py   ← variante échelle commune
build_map_commune.py    ← carte échelle commune
build_model_commune.py  ← modèle commune
build_map_simple_9502.py← carte simple (contours + points)

national/               ← ancien chantier France entière (577 circos)
  build_map.py
  build_model.py
  carte_electorale.html
  carte_predictive.html

data/                   ← données (CSV/GeoJSON). data/_cache_* = gros fichiers
                          téléchargés, gitignorés, régénérables.
.claude/                ← config agents, contrats, mémoire (EDR + INSIGHTS)
carte_bdv_9502.html     ← livrable principal (carte interactive)
```

## Installation

```bash
pip install -r requirements.txt
```

## Lancer le pipeline (circ 9502)

```bash
python3 build_bdv_data.py        # télécharge + parse les BdV (long la 1re fois)
python3 build_bv_contours.py     # extrait les contours BdV du REU
python3 build_map_bdv.py         # génère carte_bdv_9502.html
```

Ouvrir ensuite `carte_bdv_9502.html` dans un navigateur.

## Ajouter une nouvelle circonscription

Tout est centralisé dans **`config_circos.py`** :

1. Copier le gabarit commenté dans le dict `CIRCOS`
2. Renseigner les champs (identité, carte, seuil T2, cibles scénarios,
   typologie BdV, références MI)
3. Mettre `CIRCO_ACTIVE = "<nouveau code>"`
4. Lancer `build_bv_contours.py` puis `build_map_bdv.py`

Pour une circo d'un **autre département** : changer aussi `DEP` dans
`build_bdv_data.py` et générer `data/reu_bv_circ_<dep>.csv` depuis le REU.

## Modèle de scénarios 2027

Matrice 2×2 + référence (voir `CLAUDE.md` et `.claude/memory/EDR.md`) :

|  | Union NFP | Désunion (LFI / PS+G) |
|---|---|---|
| **Dynamique Philippe** | sursaut centre-droit | + gauche divisée |
| **Effondrement centre** | NFP en profite | scénario à risque |

- **Dynamique Philippe** : le centre+LR remonte de +6 pts
- **Effondrement** : le centre+LR perd -12 pts, redistribués BdV par BdV selon
  le type sociologique (urbain populaire / mixte / bourgeois / périurbain / rural)

Mécanique détaillée : `.claude/memory/EDR.md` (EDR-020 à EDR-024).

## Sources

Données officielles du Ministère de l'Intérieur via data.gouv.fr :
Législatives 2017/2022/2024, Présidentielles 2017/2022, Européennes 2024.
Contours des bureaux de vote : REU (datagouv/bureau-vote).

## Note

Le projet utilise des chemins **dynamiques** (relatifs aux scripts) : le dossier
peut être déplacé n'importe où sans rien casser.
