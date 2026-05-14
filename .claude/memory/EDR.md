# EDR.md — Registre des décisions structurantes
## Projet : Analyse électorale NFP

> Règle absolue : on ne SUPPRIME JAMAIS une entrée.
> Si une décision change → nouvelle entrée qui remplace, ancienne marquée "Dépréciée par EDR-XXX".
> Différence avec INSIGHTS.md : une décision = un choix conscient. Un apprentissage = un pattern découvert.

---

ID : EDR-001
Date : 2026-05-10
Titre : Stack Python pandas folium requests

Contexte
Le projet nécessite de traiter des fichiers CSV/XLSX de plusieurs centaines de Mo, de calculer
des scores agrégés par blocs électoraux, et de produire des visualisations géographiques
interactives. La solution doit être utilisable par une personne seule sans infrastructure serveur.

Problème
Quel langage et quelles bibliothèques utiliser pour couvrir les trois besoins : ETL électorale,
modélisation analytique et cartographie interactive ?

Décision
Python 3 + pandas (ETL/analyse) + numpy (calcul) + folium (cartes) + requests (téléchargement).
Pas de base de données, pas de framework web.

Alternatives rejetées
- R/ggplot2 : rejeté parce que l'écosystème de cartes interactives web est moins mature qu'en Python
- JavaScript/D3.js : rejeté parce que le traitement de données volumineuses (XLSX, CSV 250 Mo) est
  inconfortable sans un backend Python de toute façon
- QGIS : rejeté parce que non automatisable en script, pas reproductible
- GeoPandas + Plotly : rejeté parce que Folium produit des HTML autonomes Leaflet sans serveur,
  ce qui correspond mieux au besoin de portabilité

Conséquences
(+) Pipeline entièrement scriptable, reproductible, versable dans un repo
(+) HTML autonomes = partageables par email/clé USB sans serveur
(-) Pas de tests automatisés possibles facilement (pas de framework de test intégré)
(-) Les cartes ne fonctionnent pas dans les IDE — navigateur obligatoire

---

ID : EDR-002
Date : 2026-05-10
Titre : Données MI data.gouv.fr exclusivement

Contexte
Des analyses électorales peuvent utiliser plusieurs types de sources : données officielles MI,
sondages, projections de médias, données de terrain. Le choix de la source conditionne la
crédibilité des outputs et la cohérence méthodologique.

Problème
Quelles sources de données accepter dans le projet ?

Décision
Uniquement les données officielles du Ministère de l'Intérieur publiées sur data.gouv.fr.
Aucun sondage, aucune projection externe, aucune donnée tierce.

Alternatives rejetées
- Sondages nationaux : rejetés parce qu'ils ne donnent pas de granularité circo/commune/BdV,
  et leur méthodologie est extérieure à notre contrôle
- Données de terrain (porte-à-porte, pétitions) : rejetées parce que non standardisées
  et non comparables d'une circo à l'autre
- Projections médias (Le Monde, Politico) : rejetées parce qu'elles introduisent des hypothèses
  non auditables dans la chaîne analytique

Conséquences
(+) Reproductibilité parfaite : les résultats peuvent être vérifiés par n'importe qui
(+) Crédibilité : aucune contestation possible sur les données brutes
(-) Pas de signal avancé sur les tendances 2027 (on travaille toujours sur des données passées)
(-) Les données les plus récentes sont celles de 2024 — latence de 3 ans pour 2027

---

ID : EDR-003
Date : 2026-05-10
Titre : Livrables HTML autonomes, pas d'application

Contexte
Les cartes doivent être accessibles à des équipes de campagne qui n'ont pas nécessairement
de compétences techniques. La question de l'hébergement et de la maintenance d'une application
web se pose dès que l'on choisit un format de distribution.

Problème
Comment distribuer les cartes interactives sans imposer une infrastructure serveur ?

Décision
Les cartes sont des fichiers `.html` autonomes (Folium/Leaflet), partageables par email,
clé USB ou Wetransfer. Aucun serveur, aucune authentification, aucun déploiement.

Alternatives rejetées
- Application web déployée (Flask/Streamlit) : rejetée parce qu'elle nécessite un hébergement
  maintenu, une URL, et une disponibilité serveur permanente
- PDF/PNG statiques : rejetés parce qu'ils ne permettent pas le zoom, les tooltips et les couches
- Notebook Jupyter : rejeté parce qu'il nécessite un environnement Python installé chez le destinataire

Conséquences
(+) Zéro coût d'infrastructure, zéro maintenance
(+) Distribution immédiate par n'importe quel canal
(-) Taille des fichiers parfois > 30 Mo (cartes nationales)
(-) Pas de mise à jour dynamique : chaque nouvelle analyse = nouveau fichier

---

ID : EDR-004
Date : 2026-05-10
Titre : Deux échelles d'analyse simultanées

Contexte
Les données MI sont disponibles à deux niveaux : commune (agrégé) et bureau de vote (granulaire).
L'analyse commune donne une vue stratégique, l'analyse BdV permet d'identifier des micro-poches
et de cibler la mobilisation.

Problème
À quelle granularité faut-il analyser ? Commune seul, BdV seul, ou les deux ?

Décision
Les deux échelles sont maintenues en parallèle : commune pour la modélisation et les scénarios
(scripts `build_commune_*.py`), BdV pour la cartographie terrain (scripts `build_bdv_*.py`).

Alternatives rejetées
- Commune uniquement : rejeté parce qu'on perd l'information de dispersion intra-communale
  (ex : Cergy a 35 BdV avec des scores NFP de 67% à 30% selon le quartier)
- BdV uniquement : rejeté parce que les données de Pres 2022 T2 ne sont pas disponibles au BdV
  pour toutes les circos, et la commune donne une vision plus stable pour la modélisation

Conséquences
(+) Vue stratégique (commune) et vue tactique (BdV) combinées
(+) Possibilité de croiser les deux pour valider les chiffres
(-) Doublement du volume de code et de données à maintenir
(-) Le niveau BdV est disponible uniquement pour dep 95 dans l'état actuel

---

ID : EDR-005
Date : 2026-05-10
Titre : Un script, une responsabilité

Contexte
Au démarrage, une seule logique monolithique `build_map.py` couvrait le téléchargement,
l'ETL, la modélisation et la carte. À mesure que les besoins se sont complexifiés
(BdV, scénarios, notes d'analyse), le fichier unique devenait ingérable.

Problème
Comment organiser le code pour que chaque partie puisse évoluer indépendamment ?

Décision
Séparation stricte : `build_*_data.py` (ETL), `build_model_*.py` (analyse/scénarios),
`build_map_*.py` (cartographie). Chaque script peut être relancé indépendamment.

Alternatives rejetées
- Script unique par circo : rejeté parce que la logique d'ETL est partagée entre toutes les circos
- Module Python importable : rejeté parce qu'il introduirait une gestion de dépendances
  (requirements, setup.py) non justifiée pour un usage solo

Conséquences
(+) Chaque étape peut être rejouée sans recalculer les autres
(+) Débogage plus facile : les erreurs sont isolées dans leur domaine
(-) Pas de workflow orchestré : l'ordre d'exécution (data → model → map) est implicite, pas enforced

---

ID : EDR-006
Date : 2026-05-10
Titre : Cache local évite re-téléchargements

Contexte
Les fichiers MI sur data.gouv.fr font de 2 à 254 Mo. Les re-télécharger à chaque relance
du script prend plusieurs minutes et dépend de la connexion. Des coupures réseau peuvent
corrompre des téléchargements partiels.

Problème
Comment éviter de re-télécharger des fichiers qui ne changent pas (résultats définitifs) ?

Décision
Tous les fichiers téléchargés sont sauvegardés dans `data/_cache_{label}.{ext}`.
Le script vérifie l'existence du fichier avant tout téléchargement. Le cache n'est jamais écrasé.

Alternatives rejetées
- Re-téléchargement systématique : rejeté pour raisons de performance et de fiabilité réseau
- Cache avec TTL (expiration automatique) : rejeté parce que les résultats électoraux définitifs
  ne changent jamais — un TTL serait purement du bruit

Conséquences
(+) Développement itératif rapide : les scripts relancent en secondes après le premier run
(-) Si un fichier source est mis à jour par le MI (correction), le cache doit être manuellement supprimé
(-) L'espace disque augmente avec chaque nouvelle élection intégrée (~2 Go au total)

---

ID : EDR-007
Date : 2026-05-10
Titre : Blocs électoraux canoniques fixes

Contexte
Les nuances MI changent légèrement d'une élection à l'autre (ex : UG en 2024, NUP en 2022,
NFP non officiel). Pour comparer les scrutins entre eux, il faut regrouper les nuances
en blocs stables qui traversent les élections.

Problème
Comment agréger des nuances hétérogènes entre scrutins en catégories comparables dans le temps ?

Décision
Quatre blocs canoniques, définis une fois pour toutes :
- `left`  : LFI, SOC, DVG, PCF, COM, ECO, VEC, RDG, UG, LEXG, EXG, GS, NUP, LUG, LSOC
- `ctr`   : ENS, HOR, DVC, UDI, MDM, REM, LENS
- `rgt`   : LR, DVD, DLF, LLR
- `far`   : RN, REC, EXD, UXD, DSV, LRN, LREC, LEXD
Les ensembles sont format-spécifiques (Euro24 a le préfixe "L"). Tout changement requiert
une validation humaine et crée un nouvel EDR.

Alternatives rejetées
- Blocs par élection (sans comparabilité) : rejeté parce que l'analyse multi-scrutin
  est centrale au projet
- 5 blocs avec extrême-gauche séparée (NPA, LO) : rejeté parce que les scores sont
  marginaux (<1%) et ne justifient pas un bloc supplémentaire

Conséquences
(+) Comparaison directe Leg 2017 / 2022 / 2024 / Euro 2024 / Pres 2022
(-) Des nuances mineures non listées sont perdues (~0.5-1% des votes)
(-) Si une nouvelle formation majeure émerge (ex : fusion RN/Reconquête officielle),
  il faut mettre à jour les blocs et re-générer tous les CSV

---

ID : EDR-008
Date : 2026-05-12
Titre : Rouge gauche, bleu droite, jaune centre

Contexte
La convention internationale de couleurs (rouge=gauche, bleu=droite) est cohérente avec
la tradition politique française (rouge = mouvement ouvrier/socialiste). Un premier prototype
de carte utilisait une échelle de rouge différente pour la progresssion RN.

Problème
Quelle convention de couleur adopter pour que les cartes soient lisibles intuitivement
par une équipe de campagne NFP ?

Décision
Rouge → gauche (NFP) | Jaune → centre (ENS) | Bleu → droite/RN
Intensité proportionnelle au score. Cette convention est fixe et s'applique à toutes les cartes.

Alternatives rejetées
- Vert=gauche (couleur EELV) : rejeté parce qu'il exclut LFI et les autres composantes du NFP
- Rouge=RN (convention de certains médias) : rejeté parce qu'il est politiquement contre-intuitif
  pour une équipe NFP et inverse la tradition gauche/rouge française
- Carte monochromatique par intensité : rejeté parce qu'elle ne permet pas de comparer
  trois blocs sur la même couche

Conséquences
(+) Convention mémorisable en 3 secondes par n'importe quel membre de l'équipe
(+) Cohérente avec les codes visuels du NFP (rouge/rose)
(-) Le bleu pour le RN peut créer une confusion avec les couleurs historiques de la droite
  républicaine (LR = bleu aussi) — accepté car le contexte circo-level est toujours NFP vs RN

---

ID : EDR-009
Date : 2026-05-10
Titre : Trois scénarios A1 A2 C standardisés
⚠ DÉPRÉCIÉ par EDR-020 (matrice 2×2 Sursaut/Effondrement × Union/Désunion)

Contexte
Une analyse prospective 2027 peut modéliser un nombre infini de scénarios. Pour rester
actionnable, il faut en sélectionner un nombre limité qui couvrent les risques principaux
identifiés par l'équipe : montée de l'extrême droite et désunion de la gauche.

Problème
Quels scénarios modéliser, avec quels paramètres ?

Décision
Trois scénarios standardisés, les mêmes pour toutes les circos :
- A1 : RN +4pts (progression modérée, continuation de la tendance 2022→2024)
- A2 : RN +8pts (progression forte, accélération)
- C  : Désunion gauche — LFI seul vs PS+G seul, ratio basé sur Euro 2024
Un scénario A3 (+12pts) et des scénarios B (recomposition droite) existent dans le modèle
mais ne sont pas publiés dans les livrables actuels.

Alternatives rejetées
- Scénario unique "pire cas" : rejeté parce qu'il ne permet pas de graduer le risque
  et donc de prioriser les BdV cibles
- Scénarios basés sur des sondages : rejeté (voir EDR-002)
- Paramétrage circo-par-circo : rejeté parce qu'il empêche la comparaison entre circos

Conséquences
(+) Comparabilité entre toutes les circos analysées
(+) Le scénario C identifie précisément les BdV où la désunion est fatale
(-) Les paramètres (+4pts, +8pts) sont des hypothèses rondes, pas des projections statistiques
(-) Le scénario B (recomposition centre-droite) est documenté mais non livré — dette technique

---

ID : EDR-010
Date : 2026-05-10
Titre : Seuil T2 : 12.5% inscrits = 19.14% exprimés

Contexte
La loi électorale française fixe le seuil de maintien au second tour des législatives à
12.5% des électeurs inscrits. Pour comparer ce seuil aux scores en % des exprimés
(format des données MI), il faut le convertir via les paramètres de participation.

Problème
Quel seuil d'alerte utiliser pour identifier les BdV où un candidat risque de ne pas
se maintenir au 2nd tour ?

Décision
Seuil = 12.5% inscrits ÷ (participation T1 × ratio exprimés/votants)
= 12.5% ÷ (66.88% × 97.65%) ≈ 19.14% des exprimés
Ce seuil est spécifique à la circ 9502 (participation 2024 T1 = 66.88%).
Il est fixé en constante `SEUIL = 19.14` dans le code.

Alternatives rejetées
- Utiliser 12.5% des inscrits directement : rejeté parce que les données MI donnent
  les scores en % des exprimés, pas des inscrits — conversion nécessaire
- Recalculer dynamiquement selon chaque BdV : rejeté parce que le seuil légal est
  fixé à l'échelle de la circo entière, pas BdV par BdV

Conséquences
(+) Alerte ⚠ visible dans les popups pour tout candidat sous le seuil
(-) Si la participation 2027 diffère significativement de 2024, le seuil réel changera
  (ex: participation 60% → seuil = 21.3% des exprimés)
(-) Le seuil est hard-codé : une participation très différente en 2027 nécessitera une mise à jour

---

ID : EDR-011
Date : 2026-05-12
Titre : Désunion gauche via ratio Euro 2024

Contexte
Le scénario C (désunion gauche) nécessite de scinder le score NFP entre LFI et PS+G
au niveau bureau de vote. Il n'existe pas de source officielle MI donnant cette répartition
directement pour les Législatives.

Problème
Comment estimer la part LFI vs PS+G au niveau BdV pour le scénario C ?

Décision
Utiliser les résultats des Européennes 2024 comme proxy :
`lfi_ratio = eu_lfi / (eu_lfi + eu_lug + eu_vec + eu_com)`
Ce ratio est calculé au niveau BdV depuis le fichier `_cache_bdv_eu24.csv`
(nuances LFI, LUG=Glucksmann, LVEC=EELV, LCOM=PCF).

Alternatives rejetées
- Ratio national fixe (LFI≈47%, PS≈53%) appliqué uniformément : rejeté parce qu'il efface
  les disparités locales importantes (ex: BdV Cergy très LFI vs BdV péri-urbains plus PS)
- Données de primaires ou d'adhérents : indisponibles à l'échelle BdV
- Pas de scénario C (ne pas modéliser la désunion) : rejeté parce que c'est un risque
  stratégique majeur que l'analyse doit couvrir

Conséquences
(+) Scénario C disponible au niveau BdV avec dispersion géographique réelle
(-) Le proxy Euro→Leg est une approximation : la participation aux Européennes diffère
  (plus faible, électorat différent)
(-) Si LFI ou PS change radicalement de position entre 2024 et 2027, le ratio sera périmé

---

ID : EDR-012
Date : 2026-05-10
Titre : Circ 9502 comme circo pilote

Contexte
Le projet a vocation à couvrir la France entière. Il faut une circo de référence pour
développer et valider tous les scripts avant de les déployer à grande échelle.

Problème
Quelle circonscription choisir comme terrain d'expérimentation et de validation ?

Décision
La 2ème circonscription du Val-d'Oise (9502), celle d'Ayda Hadizadeh (NFP/UG), est la
circo pilote. Toutes les fonctionnalités sont développées et validées d'abord sur cette circo.

Alternatives rejetées
- Circo nationale emblématique (ex : 1ère de Paris) : rejetée parce que la circo d'Ayda
  est la demande client directe et que les scripts doivent correspondre aux besoins réels
- Circo générée aléatoirement : rejeté parce que la validation nécessite des chiffres
  de référence connus (NFP 39.2%, RN 28.2%)

Conséquences
(+) Validation sur une circo réelle avec des données de référence connues
(+) Adéquation directe entre les outputs et les besoins de l'équipe d'Ayda
(-) Si des spécificités de la 9502 (Cergy, multi-circo Cergy) sont traitées en dur,
  l'extension à d'autres circos nécessitera des adaptations

---

ID : EDR-013
Date : 2026-05-12
Titre : BdV restreint au département 95

Contexte
Les fichiers BdV France entière (Leg 2024, Euro 2024) font entre 100 et 254 Mo.
Les données BdV pour toute la France représenteraient plusieurs Go de cache et
nécessiteraient une architecture différente pour le traitement.

Problème
Quelle est la portée géographique du téléchargement et du traitement des données BdV ?

Décision
Les scripts BdV (`build_bdv_data.py`) filtrent sur `dep=95` pendant le chargement
et ne conservent que les BdV du Val-d'Oise. Le cache contient les fichiers France entière,
mais le traitement est limité au département.

Alternatives rejetées
- Téléchargement département par département : pas d'API MI par département pour les BdV
- France entière sans filtre : rejeté pour des raisons de mémoire RAM (>10 Go) et de temps
  de traitement (plusieurs heures)
- Extraction une circo à la fois : rejeté parce que les fichiers BdV n'ont pas de colonne
  circo fiable en 2024 (voir EDR sur leg24 sans colonne circo)

Conséquences
(+) Traitement rapide : ~3 500 lignes dep 95 vs ~67 000 France entière
(-) Extension à d'autres départements nécessite de modifier la constante `DEP = "95"`
  et de re-télécharger ou de travailler depuis le cache France entière existant

---

ID : EDR-014
Date : 2026-05-10
Titre : Pas de tests auto, validation manuelle MI

Contexte
Un framework de tests automatisés (pytest, etc.) nécessite de maintenir des fixtures,
des données de test et une suite de tests parallèlement au code de production.
Pour un projet solo mono-utilisateur, ce coût peut être disproportionné.

Problème
Comment garantir la correction des données produites sans framework de test automatisé ?

Décision
Validation manuelle systématique contre les chiffres officiels MI pour la circ 9502 :
NFP 39.2%, RN 28.2%, ENS 23.9%, 105 BdV (Leg 2024 T1). L'agent `data-validator`
formalise cette validation à chaque run de `data-parser`.

Alternatives rejetées
- pytest + fixtures de données : rejeté parce que les données MI ne peuvent pas être
  versionnées dans un repo (taille) et que les fixtures deviendraient le vrai risque
- Validation uniquement par l'agent IA : rejeté parce que l'agent peut se tromper — les
  chiffres officiels MI sont la seule référence impartiale

Conséquences
(+) Validation ancré sur la réalité électorale officielle, pas sur des mocks
(-) Si les chiffres de référence circ 9502 changent (correction MI), le seuil de validation
  doit être mis à jour manuellement dans `data-validator.md`

---

ID : EDR-015
Date : 2026-05-10
Titre : RN = extrême droite, jamais droite

Contexte
Le cadrage terminologique des formations politiques dans les livrables conditionne la lecture
politique des analyses. Dans certains médias ou contextes, le RN est qualifié de "droite
nationale" ou simplement de "droite". Ce projet est partisan : les livrables sont destinés
à une équipe NFP.

Problème
Quelle terminologie adopter pour désigner les formations d'extrême droite dans tous les outputs ?

Décision
RN et REC (Reconquête) sont systématiquement qualifiés d'"extrême droite" dans tous les textes
générés (notes d'analyse, tooltips, popups). Jamais "droite", "droite nationale" ou "droite
populaire". Le NFP est qualifié de "gauche unie", jamais attribué à LFI seul.

Alternatives rejetées
- Terminologie neutre ("droite radicale", "droite populiste") : rejetée parce que ce projet
  est un outil partisan NFP — la neutralité serait une posture incohérente
- Terminologie différenciée par contexte : rejetée parce qu'elle introduit des incohérences
  entre les différents outputs du projet

Conséquences
(+) Cohérence totale entre tous les livrables sur le cadrage politique
(-) Les livrables ne peuvent pas être utilisés tels quels dans un contexte journalistique
  ou académique qui requiert une terminologie neutre

---

ID : EDR-016
Date : 2026-05-12
Titre : Agents IA dans scope projet, pas global

Contexte
Le système de 6 agents défini pour le projet (data-fetcher, data-parser, data-validator,
electoral-analyst, cartographer, report-writer) peut être placé soit dans `.claude/agents/`
(scope projet, partageable via git) soit dans `~/.claude/agents/` (scope global, toutes sessions).

Problème
Où placer les fichiers d'agents pour qu'ils soient à la fois disponibles et
maintenables dans le contexte du projet ?

Décision
Les agents sont définis dans `.claude/agents/` (scope projet). Ils sont versionnables
avec le reste du code et ne polluent pas les autres projets. Les contrats d'interaction
sont dans `.claude/contracts.md`.

Alternatives rejetées
- Scope global `~/.claude/agents/` : rejeté parce que ces agents sont spécifiques au contexte
  électoral NFP et n'ont pas de sens dans d'autres projets
- Pas d'agents : rejeté parce que les domaines (parsing, analyse, cartographie, validation)
  ont des règles suffisamment distinctes pour justifier une séparation

Conséquences
(+) Les agents évoluent avec le projet, versionnés dans le même repo
(+) Partageables avec d'autres membres de l'équipe qui clonent le repo
(-) Les agents doivent être rechargés (restart Claude Code) si modifiés manuellement
  (les modifications via `/agents` prennent effet immédiatement)

---

ID : EDR-017
Date : 2026-05-12
Titre : Paramètres scénarios A1/A2 arbitraires
⚠ À RETRAVAILLER — décision provisoire

Contexte
Les scénarios A1 (+4pts RN) et A2 (+8pts RN) ont été définis lors de la première itération
du modèle. La progression observée 2022→2024 est de +5.28pts sur la circ 9502, et de +2.68pts/an
sur 7 ans (2017→2024). Des valeurs rondes ont été choisies pour faciliter la communication.

Problème
Quels deltas de progression RN choisir pour les scénarios A1 et A2 ?

Décision
A1 = +4pts, A2 = +8pts. Valeurs rondes encadrant la progression observée 2022→2024 (+5.28pts).
Décision provisoire — à recalibrer sur des bases empiriques solides avant usage en campagne.

Alternatives rejetées
- Aucune — les paramètres ont été fixés sans évaluation formelle des alternatives

Conséquences
(+) Valeurs simples à communiquer à une équipe de campagne non technicienne
(-) Pas d'ancrage statistique rigoureux : A1 est en dessous de la progression réelle 2022→2024,
  A2 la double sans justification empirique claire
(-) À remplacer par des paramètres basés sur des modèles de régression ou des données
  de sondage agrégé quand disponibles

---

ID : EDR-018
Date : 2026-05-12
Titre : Scénarios B et A3 : dette technique
⚠ DETTE TECHNIQUE — non livré, non supprimé

Contexte
Le script `build_model_commune.py` contient un scénario A3 (RN +12pts) et trois sous-scénarios
B (recomposition centre-droite : B1 ENS+LR+REC, B2 avec 10% RN modéré, B3 avec 20% RN modéré).
Ces scénarios ont été développés lors de la modélisation initiale mais n'ont jamais été intégrés
dans les livrables (cartes, notes d'analyse).

Problème
Que faire des scénarios calculés mais non publiés dans les livrables ?

Décision
Les scénarios B et A3 restent dans le code de modélisation (`build_model_commune.py`)
mais ne sont pas exposés dans les cartes ni les notes d'analyse. Dette technique assumée :
ils seront intégrés si le besoin se confirme, supprimés si la complexité devient un frein.

Alternatives rejetées
- Supprimer du code : rejeté parce que la logique est déjà écrite et pourrait servir
- Publier tous les scénarios : rejeté parce que trop de scénarios nuit à la lisibilité
  des livrables pour une équipe de campagne

Conséquences
(-) Divergence entre le modèle (riche) et les livrables (A1/A2/C seulement)
(-) Risque de confusion si quelqu'un lit le code source et ne comprend pas pourquoi
  B1/B2/B3 existent sans être affichés
(-) Action à planifier : décider explicitement d'intégrer ou de supprimer avant 2027

---

ID : EDR-019
Date : 2026-05-12
Titre : Report ENS→NFP 65% : estimation provisoire
⚠ À AMÉLIORER — hypothèse non calibrée

Contexte
Le modèle de T2 simule les reports de voix entre les formations qualifiées. La valeur clé
est le taux de report ENS (Ensemble/Macron) vers NFP en cas de duel NFP/RN, qui détermine
si le "front républicain" est suffisant pour faire gagner le NFP.

Problème
Quel taux de report ENS→NFP utiliser dans les simulations de second tour ?

Décision
65% des voix ENS se reportent sur NFP, 15-20% sur RN, le reste s'abstient.
Estimation basée sur l'observation qualitative du T2 2024 national, sans calibration
empirique sur la circ 9502 spécifiquement.

Alternatives rejetées
- 50% (report symétrique) : sous-évalue le front républicain observé en 2024
- 80% (report maximal) : surévalue, correspond au pic 2022 pas à une tendance stable
- Paramètre variable par commune selon socio-démographie : rejeté pour complexité,
  faute de données de report par commune disponibles au niveau MI

Conséquences
(+) Donne une estimation de T2 utilisable en première approximation
(-) Non calibré sur les données réelles circ 9502 T2 2024 (qui montrent NFP 59.5%,
  ce qui implique un report effectif calculable mais non encore formalisé)
(-) Action : calibrer rétrospectivement depuis le T2 2024 réel pour vérifier la cohérence,
  puis ajuster si l'écart est > 5pts

---

ID : EDR-020
Date : 2026-05-14
Titre : Refonte des scénarios — matrice 2×2 (Sursaut Philippe / Effondrement × Union / Désunion)
⚠ DÉPRÉCIE EDR-009 (scénarios A1/A2/C par delta RN uniforme)

Contexte
Les scénarios initiaux (EDR-009) reposaient sur des hypothèses uniformes "RN +X pts en moyenne
circo, redistribution proportionnelle depuis NFP/ENS/LR". Cette modélisation présentait deux
limites politiques majeures :
1. Elle décrivait le phénomène par son effet (RN qui monte) au lieu de son cause (effritement du
   centre/droite qui se redistribue) — non défendable en analyse stratégique
2. Elle imposait une homogénéité géographique fictive : appliquer +4 pts RN à un BdV urbain
   populaire (où RN était à 15% en 2022) et à un BdV périurbain (où RN était à 35%) revient
   à ignorer les profils locaux opposés

L'analyse des données 2017→2024 montre que le vrai moteur est l'érosion du bloc ENS+LR :
sur la circ 9502, ENS+LR est passé de 59.9% (2017) à 31.6% (2024), soit -28 pts en 7 ans.
Ces voix se sont redistribuées de façon hétérogène par BdV :
- BdV périurbains (Mériel, Seugy, Parmain) : centre→RN à 100%+ (RN gagne plus que centre perd)
- BdV urbains populaires (Cergy 21-22, St-Ouen 4-8) : centre→NFP, RN stagne ou baisse

Problème
Comment modéliser les scénarios 2027 de manière à (a) refléter la dynamique politique réelle
(érosion du centre comme moteur), (b) respecter l'hétérogénéité par BdV, (c) rester
interprétable par une équipe de campagne ?

Décision
Adopter une matrice 2×2 de scénarios + une référence T1 2024 :

  Référence : T1 2024 (réel)

  Axe 1 — Centre+LR :
    Sursaut Philippe   : ENS+LR cible 43.6% (= 31.6% + 12 pts)
    Effondrement       : ENS+LR cible 19.6% (= 31.6% - 12 pts)

  Axe 2 — Gauche :
    Union    : NFP en bloc (comme 2024)
    Désunion : LFI seul vs PS+G seul, split par BdV via ratio Euro 2024

  → 4 scénarios prospectifs : {Sursaut, Effondrement} × {Union, Désunion}

Mécanique de projection (modèle v3, par BdV) :

  1. ENS+LR : trajectoire UNIFORME PROPORTIONNELLE
     scaling = (centre_lr_circo ± 12) / centre_lr_circo
             = 1.383 (sursaut) ou 0.617 (effondrement) pour la 9502
     centre_lr_27_bdv = (ens_24_bdv + lr_24_bdv) × scaling

  2. Asymétrie ENS/LR (Option C) :
     - SURSAUT (scaling > 1) : LR conserve 50% de son score 2024 (LR_RETENTION_SURSAUT),
       Édouard Philippe (= ENS post-2027) absorbe le reste
       → ENS_27 = centre_lr_27 - (LR_24 × 0.5)
       → LR_27  = LR_24 × 0.5
     - EFFONDREMENT (scaling < 1) : partage proportionnel selon poids 2024
       → ENS_27 = centre_lr_27 × (ENS_24 / (ENS_24 + LR_24))
       → LR_27  = centre_lr_27 × (LR_24 / (ENS_24 + LR_24))

  3. NFP et RN : DYNAMIQUE LOCALE amplifiée par K
     K = cible / mean(Δ_centre_22_24_par_BdV) ≈ ±2.24 pour la 9502
     nfp_27 = nfp_24 + (nfp_24 - nfp_22) × K
     rn_27  = rn_24  + (rn_24  - rn_22)  × K
     → Conserve le profil local : un BdV où le NFP a gagné 22→24 continue à
       gagner en effondrement et à perdre en sursaut

  4. Désunion (axe 2, indépendant) :
     LFI_27 = NFP_27 × lfi_ratio_bdv     (split via Euro 2024)
     PSG_27 = NFP_27 × (1 - lfi_ratio_bdv)
     Alerte : bordure rouge si PSG_27 < 19.14% (seuil T2)

  5. Bornes physiques : ENS ∈ [0, 60], LR ∈ [0, 30], RN ∈ [0, 60], NFP ∈ [0, 80]

Paramètres :
  SCENARIO_CIBLE_PTS    = 12.0  (Δ centre+LR en moy. circo)
  LR_RETENTION_SURSAUT  = 0.5   (LR conserve 50% en sursaut Philippe)

Alternatives rejetées
- Modèle v1 (delta RN uniforme +4/+8) : non défendable politiquement (EDR-009 déprécié)
- Modèle v2 (multiplier×Δ_locale sur les 4 blocs) : dans les BdV où le centre a augmenté
  22→24 (Presles), un "effondrement" amplifiait paradoxalement la hausse — incohérent
- Asymétrie ENS/LR option A (LR figé à son score 2024) : trop rigide, ne capte pas le
  glissement progressif
- Asymétrie ENS/LR option B (partage proportionnel sur les deux scénarios) : produit un LR
  qui remonte mécaniquement en sursaut (11% au lieu de 6%), contraire à la dynamique
  d'absorption Philippe→LR observée

Conséquences
(+) Modèle plus défendable : raconte une histoire politique (érosion du centre, qui absorbe
   quoi selon le profil du BdV)
(+) Respecte les profils locaux : les BdV urbains populaires et périurbains ne sont pas
   traités identiquement
(+) LR cohérent : reste résiduel dans tous les scénarios, plafonne à ~6.2% en T1, descend
   à 3.1% en sursaut Philippe (absorbé), 3.9% en effondrement (proportionnel)
(+) Calibrage automatique : K et scaling sont recalculés depuis la dynamique observée
   de la circo, pas codés en dur
(-) Plus complexe à expliquer qu'un "delta uniforme"
(-) Hypothèses fortes sur LR_RETENTION_SURSAUT (50%) — à valider sur d'autres circos
(-) Suppose que la dynamique 2022→2024 est représentative pour projeter 2024→2027
   (3 ans, hypothèse de continuité du régime électoral)

---

ID : EDR-021
Date : 2026-05-14
Titre : Source contours BdV — REU France entière + filtre circ 9502

Contexte
La carte BdV affichait initialement des CircleMarker positionnés par jitter autour du
centroïde communal. Cette représentation ne reflète pas la géographie réelle des BdV.
Le dépôt github.com/datagouv/bureau-vote (publié 2025) expose un GeoJSON France entière
(676 Mo) avec les contours estimés par diagrammes de Voronoï depuis le REU (Répertoire
Électoral Unique).

Problème
Comment intégrer ces contours BdV sans alourdir le repo de 676 Mo ni multiplier les
téléchargements ?

Décision
1. Télécharger une fois `data/_cache_bv_contours_france.geojson` (676 Mo) — jamais resupprimé
2. Filtrer par codeCirconscription="9502" avec jq streaming → `data/bv_contours_9502.geojson`
   (~667 Ko, 80 BdV)
3. Charger ce fichier filtré dans build_map_bdv_9502.py pour afficher les polygones
4. CircleMarker reste comme fallback si un BdV n'a pas de contour REU

Source officielle : https://www.data.gouv.fr/fr/datasets/contours-des-bureaux-de-vote/
URL directe GeoJSON : https://object.files.data.gouv.fr/data-pipeline-open/reu/contours-france-entiere-latest-v2.geojson

Alternatives rejetées
- PMTiles (282 Mo) : nécessite un plugin Leaflet supplémentaire, sortie HTML non autonome
- Contours communaux uniquement (sans BdV) : ne montre pas la granularité fine
- CircleMarker uniquement : précis géographiquement mais sans surface — visuellement plus pauvre

Conséquences
(+) Vraie représentation géographique des BdV (zones de Voronoï)
(+) Permet une lecture territoriale fine (quartiers urbains vs ruraux)
(+) Source officielle Etalab/INSEE — pas d'interprétation tierce
(-) Cache de 676 Mo à conserver (ne pas le supprimer du `data/_cache_`)
(-) Le REU est de 2022 → les redécoupages post-2022 ne sont pas reflétés
