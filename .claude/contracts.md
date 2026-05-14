# Contrats d'interaction — Agents électoraux NFP

## Pipeline standard

```
data-fetcher
    ↓
data-parser ──────────────────→ data-validator (AUTOMATIQUE)
    ↓                                   ↓
electoral-analyst              VALIDE / ALERTE / BLOQUANT
    ↓                                   ↓
  ┌─────────────────┐          Si BLOQUANT : stopper ici
  ↓                 ↓
cartographer    report-writer
```

**Règle fondamentale :** `data-validator` est TOUJOURS invoqué automatiquement après `data-parser`. `cartographer` et `report-writer` ne peuvent démarrer que si `data-validator` retourne VALIDE ou ALERTE (jamais BLOQUANT).

---

## Parallélisme autorisé

| Agents | Peuvent tourner en parallèle ? | Condition |
|---|---|---|
| `cartographer` + `data-validator` | ✓ OUI | Après `electoral-analyst` |
| `cartographer` + `report-writer` | ✓ OUI | Si validation VALIDE |
| `data-fetcher` × plusieurs scrutins | ✓ OUI | Chaque scrutin indépendant |
| `data-parser` × plusieurs circos | ✓ OUI | Pas de dépendances croisées |
| `electoral-analyst` + `data-fetcher` | ✓ OUI | Circos différentes |
| `data-parser` + `electoral-analyst` | ✗ NON | Parser doit finir en premier |
| `data-fetcher` + `data-parser` (même fichier) | ✗ NON | Fetch doit finir en premier |

---

## Autorité par domaine

| Domaine | Agent responsable | Droit de blocage |
|---|---|---|
| Acquisition données | `data-fetcher` | Peut refuser de télécharger (source invalide) |
| Parsing et normalisation | `data-parser` | Autorité sur les formats de sortie CSV |
| Cadrage politique / scénarios | `electoral-analyst` | Autorité sur les paramètres A1/A2/C et seuil |
| Intégrité des données | `data-validator` | **Droit de blocage absolu** sur cartographer et report-writer |
| Visualisation | `cartographer` | Autorité sur couleurs et format HTML |
| Rédaction | `report-writer` | Autorité sur la structure des notes `.md` |

---

## Validation humaine obligatoire

Ces décisions ne peuvent PAS être prises par un agent seul :

1. **Changement de définition des blocs électoraux** (ex: ajouter une nuance à `left`)
2. **Changement du seuil de maintien au T2** (actuellement 19.14%)
3. **Changement des paramètres de scénarios** (A1=+4pts, A2=+8pts)
4. **Première analyse d'une nouvelle circonscription** (valider les chiffres de référence)
5. **Modification du cadrage politique** (terminologie RN, NFP, scénario C)

---

## Règles de transmission entre agents

### data-fetcher → data-parser
- Transmettre : liste des fichiers cache créés + format (CSV/XLSX)
- Ne pas transmettre : interprétation des données

### data-parser → data-validator (automatique)
- Transmettre : chemin exact du CSV produit
- data-validator répond avec son rapport structuré avant que le pipeline continue

### data-parser / electoral-analyst → cartographer
- Prérequis : verdict data-validator = VALIDE ou ALERTE
- Transmettre : chemin CSV + circo cible + nombre de BdV attendus

### data-parser / electoral-analyst → report-writer
- Prérequis **strict** : verdict data-validator = VALIDE (pas ALERTE, pas BLOQUANT)
- Transmettre : chiffres clés de référence pour vérification croisée dans la note

### electoral-analyst → report-writer
- Transmettre : résumé des risques par scénario (texte) + CSV enrichi

---

## Escalades vers l'utilisateur

| Situation | Agent qui escalade | Action requise |
|---|---|---|
| Resource ID 404 | `data-fetcher` | Trouver le nouvel ID sur data.gouv.fr |
| block_size ≠ 7 ou 8 | `data-parser` | Vérifier manuellement le format XLSX |
| Validation BLOQUANT | `data-validator` | Inspecter les données brutes, corriger le parser |
| Chiffres circ 9502 dérivent >1pt | `data-validator` | Vérifier la source et reparser |
| Carte vide après navigateur | `cartographer` | Déboguer JS et clés composites |
| Seuil 19.14% à recalculer | `electoral-analyst` | Décision humaine obligatoire |
| Victoire RN en scénario de base | `report-writer` | Alerte stratégique — revue humaine |
