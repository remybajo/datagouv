# INSIGHTS.md — Registre des apprentissages
## Projet : Analyse électorale NFP

> Ce fichier capture ce que le projet a DÉCOUVERT en avançant.
> Chaque entrée est actionnable : si on ne peut pas l'appliquer concrètement, elle ne mérite pas d'être ici.
> Différence avec CLAUDE.md : CLAUDE.md dit QUOI faire. INSIGHTS.md dit POURQUOI on l'a appris.

---

## Domaine : Parsing & données

---

ID : INS-001
Date : 2026-05-12
Titre : num_bdv seul n'est pas unique

Découverte
`num_bdv` (1, 2, 3…) est réutilisé dans chaque commune. Sur les 105 BdV
de la circ 9502, on ne compte que 35 valeurs uniques de `num_bdv`. Utiliser
ce champ seul comme clé produit des collisions silencieuses qui écrasent des
entrées dans les dictionnaires Python.

Source
Diagnostic : `grep -c "L.circleMarker" carte_bdv_9502.html` retournait 0
alors que le script confirmait "105 marqueurs ajoutés". Tracé de la taille
de `positions` dict : 35 entrées au lieu de 105.

Impact
Toute opération de jointure, fusion ou positionnement utilisant `num_bdv`
seul est incorrecte sur des données multi-communes.

Action
Toujours construire la clé composite `f"{code_commune}_{num_bdv}"` avant
toute opération de lookup. Jamais `num_bdv` seul comme index ou clé de dict.

---

ID : INS-002
Date : 2026-05-12
Titre : block_size XLSX via premier Unnamed

Découverte
Dans le parseur d'anciens XLSX burvot (leg22, pres22), le `block_size` doit
être détecté en cherchant le PREMIER `Unnamed:N` dans `bloc_header[1:]`.
L'approche naïve (premier colonne nommée après le début) retournait
position 1 (colonne "Sexe"), donnant `block_size=1` et des scores tous à 0.

Source
Vérification manuelle des fichiers : leg22 → block_size attendu 8, pres22 → 7.
Scores todos à 0.0 dans les CSV produits, détecté lors de la validation circ 9502.

Impact
Un `block_size` incorrect rend le parsing XLSX entier silencieusement faux :
pas d'erreur, juste des scores à zéro pour tous les candidats.

Action
Détecter avec :
```python
first_unnamed = next(
    (i for i, c in enumerate(bloc_header) if i > 0 and str(c).startswith('Unnamed')),
    None
)
block_size = first_unnamed if first_unnamed else (7 if pres else 8)
```

---

ID : INS-003
Date : 2026-05-12
Titre : String vs int : perte silencieuse lookups

Découverte
`code_commune` est stocké comme entier (95026) dans certains DataFrames
pandas, mais le dict `centroids` utilise des clés string ('95026').
Le lookup `centroids[95026]` retourne toujours `None` → `positions` dict
vide → zéro marqueurs sur la carte. Aucune erreur levée.

Source
Carte vide après correction du bug INS-001. Ajout de `print(type(key))`
dans `jitter_positions()` : `int` au lieu de `str`.

Impact
Toutes les opérations de lookup commune × centroïde silencieusement
échouent si le type n'est pas homogène.

Action
Toujours normaliser à l'entrée des fonctions de lookup :
```python
key_str = str(commune_code).zfill(5)
if key_str not in centroids: return {}
```
Convention : les codes communes sont TOUJOURS des strings 5 chiffres
dans tout dictionnaire ou index.

---

ID : INS-004
Date : 2026-05-12
Titre : Leg 2024 BdV sans colonne circo

Découverte
Le fichier CSV BdV des Législatives 2024 (nouveau format MI) ne contient
pas de colonne "Code de la circonscription", contrairement au format XLSX
de 2022. La circo ne peut pas être lue directement.

Source
`col_circ = None` retourné par le détecteur de colonnes sur le fichier
leg24t1 BdV. Comparaison des headers : 2022 XLSX a la colonne, 2024 CSV
ne l'a pas.

Impact
Toute analyse BdV cross-scrutin nécessitant la circo doit dériver
l'information depuis une source tierce.

Action
Construire `circ_map` (code_commune_5dig → numéro circo) depuis le fichier
`_cache_bdv_leg22t1.xlsx` au démarrage, puis appliquer sur leg24. Ce fichier
XLSX 2022 a la colonne circo et couvre toutes les communes.

---

ID : INS-005
Date : 2026-05-12
Titre : Euro 2024 BdV : 254 MB, lecture chunks

Découverte
Le fichier BdV des Européennes 2024 fait 254 Mo (France entière). Charger
avec `pd.read_csv()` standard monopolise ~2 Go RAM et prend plusieurs minutes.
Pour dep 95, seules ~3 500 lignes sur ~67 000 sont pertinentes.

Source
Tentative de chargement naïf : timeout + swap mémoire observable.
Filtrage sur `Code département == '95'` pendant le chargement réduit la
mémoire d'un facteur 20.

Impact
Tous les fichiers BdV France entière (> 100 Mo) doivent être traités en
mode streaming. Ne jamais charger en mémoire puis filtrer.

Action
Toujours utiliser la lecture par chunks avec filtrage immédiat :
```python
for chunk in pd.read_csv(path, sep=';', chunksize=10_000, low_memory=False):
    filt = chunk[chunk[dep_col].astype(str).str.strip() == DEP]
    if len(filt) > 0:
        chunks.append(filt)
```

---

ID : INS-006
Date : 2026-05-12
Titre : Cartes Folium : navigateur, pas IDE

Découverte
Les cartes `.html` Folium/Leaflet sont silencieusement vides dans le
prévisualisateur HTML de l'IDE (VS Code, Claude Code IDE). Le JavaScript
de Leaflet n'est pas exécuté. La carte apparaît blanche — même avec 420
`L.circleMarker` corrects dans le fichier.

Source
Rapport utilisateur "carte vide" après vérification `grep -c "L.circleMarker"`
confirmant 420 marqueurs présents. Test dans Chrome → carte visible.

Impact
On ne peut PAS valider visuellement une carte Folium dans l'IDE. Chaque
validation visuelle requiert un vrai navigateur.

Action
Systématiquement exécuter `open carte_*.html` après génération.
Ajouter la vérification programmatique en amont :
```bash
grep -c "L.circleMarker" carte_*.html  # doit = N_BdV × N_couches
```

---

ID : INS-007
Date : 2026-05-12
Titre : Euro 2024 nuances : préfixe "L" obligatoire

Découverte
Dans les fichiers Européennes 2024, toutes les nuances portent un préfixe
"L" : `LFI` (pas `FI`), `LUG` (pas `UG`), `LRN` (pas `RN`), `LREC`,
`LVEC`, `LCOM`, `LENS`, `LLR`. Les nuances des Législatives n'ont pas ce
préfixe. Mélanger les deux ensembles de nuances ne lève aucune erreur mais
ne classe rien.

Source
Scores `eu_left = 0.0` sur toutes les communes après premier test. Inspection
manuelle des valeurs de nuance dans le CSV brut : `"LFI"` là où le code bloc
cherchait `"FI"`.

Impact
Les définitions de blocs sont format-spécifiques. Un seul set de nuances
ne peut pas couvrir à la fois les leg et les euro.

Action
Maintenir des ensembles de nuances séparés par scrutin :
`LEG_BLOCS` (sans L) vs `EURO_BLOCS` (avec L). Ne jamais fusionner.
Référence dans CLAUDE.md section 3.

---

ID : INS-008
Date : 2026-05-10
Titre : XLSX anciens : codes communes relatifs

Découverte
Dans les anciens fichiers XLSX burvot (leg22, pres22), la colonne "Code
commune" contient des entiers RELATIFS au département (ex: `2` pour la
commune 95002, `127` pour 95127). Ce ne sont pas des codes INSEE absolus.
Pandas lit ces valeurs comme des flottants (`2.0`, `127.0`).

Source
Jointures communes → aucun match. Inspection des valeurs brutes : `2.0`,
`56.0`, `127.0` au lieu de `95002`, `95056`, `95127`.

Impact
Toute jointure sur code commune entre fichiers XLSX anciens et CSV modernes
échoue silencieusement si la normalisation n'est pas appliquée.

Action
Appliquer `norm_commune()` sur toutes les valeurs issues de fichiers XLSX
anciens avant toute jointure ou lookup :
```python
def norm_commune(raw, dep='95'):
    s = str(raw).strip().split('.')[0]
    if len(s) >= 5: return s.zfill(5)
    try: return dep + str(int(s)).zfill(3)
    except: return s
```

---

## Domaine : Analyse électorale

---

ID : INS-009
Date : 2026-05-12
Titre : Euro 2024 = seul proxy désunion BdV

Découverte
Il n'existe pas de source officielle donnant la répartition interne du vote
gauche (LFI vs PS+G) au niveau bureau de vote pour les Législatives. Les
Européennes 2024 sont le seul scrutin MI disponible à ce niveau de
granularité avec des listes distinctes LFI / Glucksmann. Le ratio
`lfi_ratio = eu_lfi / (eu_lfi + eu_lug + eu_vec + eu_com)` est donc la
meilleure approximation disponible pour le scénario C.

Source
Recherche de sources BdV : absence de données de primaires, de sondages
locaux, ou d'autres scrutins avec listes gauche séparées. Euro 2024 =
seule donnée disponible avec listes distinctes à ce niveau.

Impact
Le scénario C (désunion) repose entièrement sur une approximation Euro →
Leg. La fiabilité du scénario est bornée par la corrélation Euro/Leg, qui
est forte mais non parfaite (participation différente, dynamique nationale).

Action
Toujours signaler dans les notes d'analyse que le scénario C est une
estimation basée sur les Européennes 2024, pas une donnée directe.
Si une primaire ou un autre scrutin avec listes gauche séparées devient
disponible, mettre à jour `lfi_ratio`.

---

ID : INS-010
Date : 2026-05-12
Titre : Cergy commune chevauche plusieurs circos

Découverte
La commune de Cergy (95127) est découpée entre plusieurs circonscriptions.
Les données à l'échelle commune agrègent l'intégralité des inscrits de Cergy
(~38 000), alors que la circ 9502 ne couvre qu'une partie (~25 000). Les
scores en % restent valides (identiques par BdV), mais le poids électoral
de Cergy est surestimé au niveau commune-level.

Source
Comparaison : `inscrits.sum()` du CSV communes circ 9502 > inscrits officiels
MI (78 781). Ratio de correction = 78 781 / total_csv ≈ 0.93. Commentaire
dans `build_model_commune.py` ligne 57.

Impact
Les calculs pondérés par inscrits au niveau commune (ex: score moyen pondéré
de la circo) surestiment le poids de Cergy si on ne corrige pas.

Action
Au niveau commune : appliquer `CORR_FACTOR` sur les inscrits de Cergy avant
toute pondération. Au niveau BdV : pas de correction nécessaire, chaque BdV
est correctement assigné à sa circo via `circ_map`.

---

ID : INS-011
Date : 2026-05-14
Titre : Bug commune-level circ_map → 24 BdV fantômes en circ 9502

Pattern observé
Le `circ_map` construit dans `build_bdv_data.py` était au niveau commune (`code_commune → code_circ`),
en utilisant `groupby(commune).first()`. Pour les communes éclatées entre plusieurs circonscriptions
(notamment Cergy 95127, partagée entre 9502 et 9510), tous les BdV de la commune se voyaient
assigner la même circ — celle du premier BdV rencontré dans la table.

Symptômes
- Notre dataset circ 9502 contenait 105 BdV (vs 80 dans le REU officiel)
- Les chiffres agrégés étaient contaminés : NFP 39.2% (faux) vs 34.4% (réel MI cirlg)
- Le bug existait depuis l'origine du pipeline mais n'a été détecté qu'avec l'intégration
  des contours REU (qui ont révélé le mismatch BdV/circ)

Solution
Construire `circ_map` au niveau BdV (clé composite `code_commune_num_bdv`) depuis le REU,
qui est la source officielle Etalab/INSEE. Fallback commune-level conservé pour scrutins
hors-95.

Leçon
- Toute donnée d'attribution circo-BdV doit venir du REU, pas d'un agrégat commune
- Détecter les communes éclatées : grep `groupby(commune).first()` est suspect partout
  où on assigne un attribut BdV-level

À refaire si
- Ajout d'un nouveau département où des communes sont éclatées entre circos (Paris, Lyon,
  Marseille, et toutes les grandes communes urbaines)
- Refactor du `circ_map` : utiliser systématiquement REU comme source primaire

---

ID : INS-012
Date : 2026-05-14
Titre : Modèle scénario v3 — séparer trajectoire imposée et dynamique locale

Pattern observé
Modèle v1 (delta RN uniforme) : imposait une homogénéité géographique fictive — produisait
des résultats absurdes dans les BdV à profil opposé (urbains populaires vs périurbains).

Modèle v2 (multiplier ×Δ_locale sur les 4 blocs) : capturait bien la dynamique locale mais
amplifiait paradoxalement les CAS ATYPIQUES — dans les BdV où le centre avait *monté* entre
2022 et 2024 (Presles), un "scénario effondrement" produisait... une hausse encore plus forte
du centre. Incohérent.

Solution v3 : séparer deux moteurs
- Bloc qu'on veut FORCER dans une direction (ENS+LR ici) → trajectoire imposée par scaling
  uniforme proportionnel. Calibré sur la moyenne circo, applique le même facteur partout.
- Blocs qu'on veut laisser RÉAGIR aux dynamiques locales (NFP, RN) → multiplier ×K de la
  dynamique observée. Capture les profils urbain/périurbain.

Asymétrie politique additionnelle (Option C, ENS/LR) : modélise une logique réelle
"Édouard Philippe = nouvelle marque qui absorbe LR" — LR ne profite pas du sursaut, il est
cannibalisé. Implémenté via `LR_RETENTION_SURSAUT = 0.5`.

Leçon générale pour la modélisation prospective
- Identifier ce qu'on impose (la "thèse" du scénario) vs ce qu'on laisse réagir (les profils)
- Un multiplier global × dynamique locale = bonne idée mais doit s'appliquer aux blocs où
  la dynamique locale fait sens (transfer de votes)
- Pour les blocs où on veut imposer une direction, scaling proportionnel uniforme
- Toujours tester sur des BdV atypiques (ex: Presles avait centre+LR en hausse 22→24)
  avant de déclarer le modèle stable

À refaire si
- Ajout d'un nouveau scénario où on veut imposer une trajectoire (ex: poussée NFP forcée)
  → même mécanique scaling sur NFP
- Si on observe à nouveau des projections incohérentes : chercher d'abord les BdV où la
  dynamique locale 22→24 est inverse de la cible scénario

---

ID : INS-013
Date : 2026-05-14
Titre : Piège Python — 'desunion'.endswith('union') == True

Pattern observé
Avec les scénarios codés `sur_union`, `sur_desunion`, `eff_union`, `eff_desunion`, le check
`scen_code.endswith('union')` matchait à la fois `*_union` ET `*_desunion`. Conséquence :
les scénarios désunion affichaient à tort le NFP en bloc au lieu du split LFI/PS+G.

Symptômes
- Tooltips BdV en Effondrement+Désunion ou Philippe+Désunion : afficheur NFP au lieu de LFI/PSG
- Couleur du polygone calculée sur NFP au lieu de max(LFI, PSG)
- Le panneau d'agrégats fonctionnait correctement (utilise `endswith('desunion')`)
- L'incohérence n'apparaissait que sur les tooltips et la couleur dominante

Solution
Toujours tester `endswith('desunion')` (le plus spécifique) et inverser la logique
plutôt que `endswith('union')`. Commentaires ajoutés en bord de code.

Leçon générale
- Quand on encode des variantes hiérarchiques (ex: `union` / `desunion`), le préfixe
  négatif (`des-`) crée des collisions avec endswith
- Préférer des codes orthogonaux non-emboîtés : `*_uni`, `*_split` aurait évité le bug
- Pour les checks de suffixe avec risque de collision, toujours tester le suffixe le plus
  long en premier
- Vérification systématique : compter les occurrences de chaque label dans le HTML généré
  (`grep -c '>LFI<'` etc.) avant de déclarer une feature stable

À refaire si
- On introduit d'autres scénarios avec des noms emboîtés
- Si on observe des incohérences entre panneau agrégats et tooltips/couleurs : suspecter
  un mismatch dans la logique de check de scénario
