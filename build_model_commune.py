#!/usr/bin/env python3
"""
build_model_commune.py
Analyse prédictive — 2ème circ Val-d'Oise (9502) — 3 scénarios pour 2027
"""
import os, warnings
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')
DATA = "/Users/remybajolet/Desktop/datagouv/data"

# ─── Valeurs de référence cirlg officielles (non corrigées par notre CSV) ────
# Source : leg2024_t1_cirlg.csv + leg2024_t2_cirlg.csv
REF = {
    'inscrits':        78_781,
    'participation_t1': 66.88,
    'participation_t2': 65.98,
    'l24t1_nfp':       33.47,  # HADIZADEH UG
    'l24t1_rn':        30.21,  # REMY
    'l24t1_ens':       25.35,  # VUILLETET
    'l24t1_lr':         6.25,  # PAIN
    'l24t1_rec':        1.03,  # CHANZY
    'l24t1_div':        2.80,  # IVANAJ + OUBAIROUK
    'l24t2_nfp':       59.51,
    'l24t2_rn':        40.49,
    # Européennes 2024 (% exprimés)
    'eu24_rn':         28.93,
    'eu24_lfi':        15.49,  # LFI – Union Populaire
    'eu24_ps':         12.99,  # Glucksmann – Réveiller l'Europe
    'eu24_eelv':        5.08,  # Europe Écologie
    'eu24_pcf':         2.01,  # Gauche Unie
    'eu24_ens':        13.89,  # Besoin d'Europe
    'eu24_lr':          7.04,  # Bellamy
    'eu24_rec':         5.43,  # Maréchal/Reconquête
    # Pres 2022 T1
    'pr22t1_melenchon': 26.46,
    'pr22t1_macron':    27.60,
    'pr22t1_lepen':     19.78,
    'pr22t1_zemmour':    7.54,
    'pr22t1_pecresse':   4.00,  # approx
    # Pres 2022 T2
    'pr22t2_macron':    None,   # non disponible dans notre base
    # Leg 2022 T1 (cirlg)
    'l22t1_nup':        27.10,  # GEOFFROY-MARTIN NUP
    'l22t1_ens':        28.79,  # ENS
    'l22t1_far':        24.93,  # RN
}

# ─── Chargement des données communes ─────────────────────────────────────────
df = pd.read_csv(os.path.join(DATA, 'communes_9502.csv'), index_col='code_commune')
print(f"Base : {len(df)} communes, {len(df.columns)} colonnes\n")

# Correction : pour Cergy (95127), les inscrits dans notre CSV incluent plusieurs circs.
# On applique un ratio de correction basé sur les inscrits totaux officiels.
# Inscrits officiels circ : 78 781 / inscrits dans notre CSV
total_inscrits_csv  = df['inscrits'].sum()
CORR_FACTOR = REF['inscrits'] / total_inscrits_csv
print(f"Ratio correction inscrits : {REF['inscrits']:,} / {total_inscrits_csv:,} = {CORR_FACTOR:.3f}")
print("(Cergy déborde sur d'autres circs — les scores % restent valides, le poids de Cergy est surestimé)\n")

# ─── 1. DIAGNOSTIC HISTORIQUE PAR COMMUNE ────────────────────────────────────
print("=" * 70)
print("1. DIAGNOSTIC HISTORIQUE")
print("=" * 70)

# Progression RN 2022 → 2024
df['rn_delta'] = (df['l24t1_far'] - df['l22t1_far']).round(1)
# Niveau gauche 2024 vs 2022
df['left_delta'] = (df['l24t1_left'] - df['l22t1_left']).round(1)
# Détail européennes : part gauche totale
df['eu24_left_total'] = (
    df.get('eu24_eu_lfi', 0).fillna(0) + df.get('eu24_eu_ps', 0).fillna(0) +
    df.get('eu24_eu_vec', 0).fillna(0) + df.get('eu24_eu_com', 0).fillna(0) +
    df.get('eu24_eu_lxeg', 0).fillna(0)
).round(2)

# Typage des communes
def typer_commune(row):
    left24   = row.get('l24t1_left', np.nan)
    far24    = row.get('l24t1_far',  np.nan)
    left22   = row.get('l22t1_left', np.nan)
    rn_delta = row.get('rn_delta',   np.nan)

    if pd.isna(left24): return 'données insuffisantes'
    if left24 > 45:     return 'bastion_gauche'
    if far24  > 40:     return 'bastion_rn'
    if not pd.isna(rn_delta) and rn_delta > 8: return 'rn_ascendant'
    if not pd.isna(left22) and abs(left24 - left22) > 8: return 'bascule'
    if left24 > 30 and far24 < 35: return 'penchant_gauche'
    return 'competitive'

df['type_commune'] = df.apply(typer_commune, axis=1)

print("\nTypologie des communes :")
print(df.groupby('type_commune')[['nom_commune']].count().rename(columns={'nom_commune':'nb'}))
print()

diag_cols = ['nom_commune','inscrits','l24t1_left','l24t1_far','l24t1_ctr',
             'l22t1_left','l22t1_far','rn_delta','eu24_eu_rn','eu24_left_total','type_commune']
diag = df[diag_cols].copy()
diag.columns = ['Commune','Inscrits','Left24T1','RN24T1','Ctr24T1',
                'Left22T1','RN22T1','ΔRNTX','RN_EU24','Left_EU24','Type']
print(diag.sort_values('Left24T1', ascending=False).to_string())

# ─── 2. PARAMÈTRES DE MODÉLISATION ───────────────────────────────────────────
print("\n" + "=" * 70)
print("2. PARAMÈTRES DE MODÉLISATION")
print("=" * 70)

# Progression RN observée (base cirlg officielle)
rn_17  = 12.49   # leg 2017
rn_22  = 24.93   # leg 2022 T1
rn_24  = 30.21   # leg 2024 T1
rn_eu24 = 28.93  # euro 2024

progression_annuelle_rn = (rn_24 - rn_17) / 7   # +2.68 pts/an
progression_22_24       = rn_24 - rn_22           # +5.28 pts sur 2 ans
progression_eu_leg24    = rn_24 - rn_eu24         # +1.28 pts (euro→leg)

print(f"\nProgression RN observée :")
print(f"  2017→2024 : +{rn_24-rn_17:.1f} pts sur 7 ans = +{progression_annuelle_rn:.2f} pts/an")
print(f"  2022→2024 : +{progression_22_24:.1f} pts")
print(f"  Euro→Leg2024 : +{progression_eu_leg24:.1f} pts (mobilisation supplémentaire)")

# Décomposition de la gauche (euro 2024 → proxy poids LFI/PS/EELV au sein du NFP)
nfp_total_eu24 = REF['eu24_lfi'] + REF['eu24_ps'] + REF['eu24_eelv'] + REF['eu24_pcf']
LFI_SHARE  = REF['eu24_lfi']  / nfp_total_eu24
PS_SHARE   = REF['eu24_ps']   / nfp_total_eu24
EELV_SHARE = REF['eu24_eelv'] / nfp_total_eu24
PCF_SHARE  = REF['eu24_pcf']  / nfp_total_eu24

print(f"\nDécomposition interne NFP (proxy euros 2024, circ 9502) :")
print(f"  LFI  : {LFI_SHARE*100:.1f}% du NFP")
print(f"  PS/PP: {PS_SHARE*100:.1f}% du NFP")
print(f"  EELV : {EELV_SHARE*100:.1f}% du NFP")
print(f"  PCF  : {PCF_SHARE*100:.1f}% du NFP")

# Seuil de maintien au 2nd tour : 12.5% des inscrits
SEUIL_MAINTIEN_INS = 12.5   # % inscrits
# Avec participation T1 de 66.9% et 97.65% exprimes/votants :
part_t1   = REF['participation_t1'] / 100
exp_ratio = 0.9765
SEUIL_MAINTIEN_EXP = SEUIL_MAINTIEN_INS / (part_t1 * exp_ratio * 100)  # % exprimés
print(f"\nSeuil de maintien 2nd tour :")
print(f"  12.5% inscrits = {SEUIL_MAINTIEN_EXP*100:.1f}% des exprimés (avec participation {REF['participation_t1']}%)")
print(f"  En voix absolues : {int(REF['inscrits'] * 0.125):,} voix")

# ─── 3. SCÉNARIO A — DYNAMIQUE EXTRÊME DROITE RENFORCÉE ──────────────────────
print("\n" + "=" * 70)
print("3. SCÉNARIO A — RN RENFORCÉ")
print("=" * 70)

# Hypothèses :
# A1 : progression modérée (+4 pts vs 2024, continuation de la tendance)
# A2 : progression forte  (+8 pts vs 2024, accélération)
# A3 : progression maximale (+12 pts, intégration quasi-totale Reconquête + DVD)

# Report Reconquête→RN : CHANZY a fait 1.03% en 2024
# On estime 70-80% de report → +0.7-0.8 pts pour le RN
REC_REPORT = 1.03 * 0.75  # estimation médiane

# Base RN cirlg : 30.21 + 1.03 (REC potential report) = 31.24% de plafond bas
rn_base_potential = rn_24 + REC_REPORT

for scenario_name, delta_rn in [('A1 (+4pts)', 4.0), ('A2 (+8pts)', 8.0), ('A3 (+12pts)', 12.0)]:
    rn_proj  = rn_24 + delta_rn
    # La gauche reste stable ou se comprime légèrement (abstention différentielle)
    nfp_proj = REF['l24t1_nfp'] - delta_rn * 0.15   # hypothèse : chaque pt RN prend 0.15 pt à la gauche
    ens_proj = REF['l24t1_ens'] - delta_rn * 0.3    # le centre souffre davantage
    lr_proj  = REF['l24t1_lr']  - delta_rn * 0.05

    total_proj = rn_proj + nfp_proj + ens_proj + lr_proj + REF['l24t1_div']
    # Normaliser
    factor = 100 / total_proj
    rn_n, nfp_n, ens_n, lr_n = rn_proj*factor, nfp_proj*factor, ens_proj*factor, lr_proj*factor

    print(f"\n  [{scenario_name}] RN {rn_n:.1f}% | NFP {nfp_n:.1f}% | ENS {ens_n:.1f}% | LR {lr_n:.1f}%")

    # Qualification au 2nd tour (seuil 12.5% inscrits = ~19.2% exprimés)
    print(f"    T1 qualifiés : ", end='')
    qualifies = []
    for label, score in [('NFP', nfp_n), ('RN', rn_n), ('ENS', ens_n), ('LR', lr_n)]:
        if score >= SEUIL_MAINTIEN_EXP * 100:
            qualifies.append(f"{label} ({score:.1f}%)")
    print(', '.join(qualifies) if qualifies else 'aucun')

    # Simulation T2 selon configurations
    if rn_n > nfp_n and len(qualifies) >= 2:
        # RN en tête au T1
        if ens_n >= SEUIL_MAINTIEN_EXP * 100:
            # Triangulaire possible
            # Report ENS+LR vers NFP (barrage) : hypothèse 60-70%
            nfp_t2 = nfp_n + (ens_n + lr_n) * 0.65
            rn_t2  = rn_n + (ens_n + lr_n) * 0.20
            print(f"    T2 (triangulaire avec retrait partiel ENS→barrage) : NFP {nfp_t2:.1f}% vs RN {rn_t2:.1f}%")
            if nfp_t2 > rn_t2:
                print(f"    → NFP gagne avec {nfp_t2:.1f}% (marge +{nfp_t2-rn_t2:.1f} pts)")
            else:
                print(f"    → RN GAGNE avec {rn_t2:.1f}% (marge +{rn_t2-nfp_t2:.1f} pts) ⚠")
        else:
            # Duel RN vs NFP, ENS se désiste
            nfp_t2 = nfp_n + (ens_n + lr_n) * 0.65
            rn_t2  = rn_n + (ens_n + lr_n) * 0.15
            print(f"    T2 (duel après désistement ENS) : NFP {nfp_t2:.1f}% vs RN {rn_t2:.1f}%")
            if nfp_t2 > rn_t2:
                print(f"    → NFP gagne avec {nfp_t2:.1f}% (marge +{nfp_t2-rn_t2:.1f} pts)")
            else:
                print(f"    → RN GAGNE ⚠  {rn_t2:.1f}% vs NFP {nfp_t2:.1f}%")

# Analyse par commune : combien basculent dans chaque scénario ?
print(f"\n  Communes RN > NFP au T1 selon scénario :")
for scenario_name, delta_rn in [('A1 +4pts', 4.0), ('A2 +8pts', 8.0), ('A3 +12pts', 12.0)]:
    df[f'rn_a{scenario_name[-2]}'] = (df['l24t1_far'] + delta_rn).clip(upper=75)
    df[f'nfp_a{scenario_name[-2]}'] = (df['l24t1_left'] * 0.97).clip(lower=10)
    bascule = ((df[f'rn_a{scenario_name[-2]}'] > df[f'nfp_a{scenario_name[-2]}'])).sum()
    print(f"    {scenario_name} : {bascule}/21 communes avec RN > NFP")

# ─── 4. SCÉNARIO B — RECOMPOSITION CENTRE-DROIT ──────────────────────────────
print("\n" + "=" * 70)
print("4. SCÉNARIO B — DROITE RECOMPOSÉE (Wauquiez/Retailleau type)")
print("=" * 70)

# Potentiel maximal de la droite recomposée :
# ENS 25.35% + LR 6.25% + REC 1.03% + une fraction RN modérée
# Si 20% des électeurs RN se reportent sur la droite recomposée :
ens_lr_base = REF['l24t1_ens'] + REF['l24t1_lr'] + REF['l24t1_rec']
print(f"\n  Base droite recomposée (ENS+LR+REC) : {ens_lr_base:.1f}%")

for scenario_name, rn_transfer, label in [
    ('B1 — Droite unie (ENS+LR+REC, 0% RN)',   0.00, '25-28%'),
    ('B2 — Droite élargie (+10% RN modéré)',      0.10, '28-32%'),
    ('B3 — Droite forte (+20% RN modéré)',        0.20, '32-35%'),
]:
    cdr_score  = ens_lr_base + rn_transfer * REF['l24t1_rn']
    rn_residual = REF['l24t1_rn'] * (1 - rn_transfer)
    nfp_score  = REF['l24t1_nfp']   # inchangé

    print(f"\n  [{scenario_name}]")
    print(f"    CDR {cdr_score:.1f}% | NFP {nfp_score:.1f}% | RN résiduel {rn_residual:.1f}%")

    qualifies = []
    for lbl, score in [('NFP', nfp_score), ('CDR', cdr_score), ('RN', rn_residual)]:
        if score >= SEUIL_MAINTIEN_EXP * 100:
            qualifies.append(f"{lbl} ({score:.1f}%)")

    print(f"    T1 qualifiés : {', '.join(qualifies)}")

    # Configs T2 :
    all_scores = sorted([('NFP', nfp_score), ('CDR', cdr_score), ('RN', rn_residual)],
                         key=lambda x: -x[1])
    print(f"    Classement T1 : {all_scores[0][0]} ({all_scores[0][1]:.1f}%) > "
          f"{all_scores[1][0]} ({all_scores[1][1]:.1f}%) > "
          f"{all_scores[2][0]} ({all_scores[2][1]:.1f}%)")

    if cdr_score >= SEUIL_MAINTIEN_EXP * 100 and rn_residual >= SEUIL_MAINTIEN_EXP * 100:
        print(f"    → TRIANGULAIRE CDR / RN / NFP")
        # T2 triangulaire : les reports sont complexes
        # NFP: ne peut compter que sur ses propres votes (pas de report CDR → gauche)
        # CDR: peut compter sur report partiel RN si RN se désiste (30-40%)
        # RN: reporte peu
        if nfp_score > cdr_score:
            nfp_t2 = nfp_score + cdr_score * 0.25  # petit report CDR→NFP
            cdr_t2 = cdr_score + nfp_score * 0.05
            rn_t2  = rn_residual + cdr_score * 0.35 + nfp_score * 0.05
        else:
            nfp_t2 = nfp_score + cdr_score * 0.20
            cdr_t2 = cdr_score + nfp_score * 0.03
            rn_t2  = rn_residual + cdr_score * 0.40 + nfp_score * 0.05
        winner = max([('NFP', nfp_t2), ('CDR', cdr_t2), ('RN', rn_t2)], key=lambda x: x[1])
        print(f"    T2 estimé : {winner[0]} gagne avec ~{winner[1]:.1f}%  "
              f"(NFP~{nfp_t2:.1f}%, CDR~{cdr_t2:.1f}%, RN~{rn_t2:.1f}%)")
    else:
        # Duel
        if rn_residual < SEUIL_MAINTIEN_EXP * 100:
            nfp_t2 = nfp_score + cdr_score * 0.30  # une fraction CDR barrage
            cdr_t2 = cdr_score + rn_residual * 0.50 + nfp_score * 0.05
            print(f"    T2 duel CDR/NFP : CDR {cdr_t2:.1f}% vs NFP {nfp_t2:.1f}%")
            if cdr_t2 > nfp_t2:
                print(f"    → CDR GAGNE ⚠  (dép. sortante NFP défaite)")
            else:
                print(f"    → NFP gagne")
        else:
            print(f"    → Duel NFP/RN avec CDR qualifié — report à analyser")

# ─── 5. SCÉNARIO C — DÉSUNION DE LA GAUCHE ───────────────────────────────────
print("\n" + "=" * 70)
print("5. SCÉNARIO C — DÉSUNION DE LA GAUCHE")
print("=" * 70)

# Répartition des voix NFP entre candidats LFI et PS/PP
# Proxy : européennes 2024 (parts internes au bloc gauche)

nfp_2024 = REF['l24t1_nfp']   # 33.47%
lfi_candidate  = round(nfp_2024 * LFI_SHARE, 2)
ps_candidate   = round(nfp_2024 * PS_SHARE,  2)
eelv_block     = round(nfp_2024 * (EELV_SHARE + PCF_SHARE), 2)

print(f"\n  Hypothèse de départ : NFP 2024 = {nfp_2024}% réparti selon euros 2024")
print(f"  Candidat LFI        : {lfi_candidate:.1f}%  ({LFI_SHARE*100:.0f}% du NFP)")
print(f"  Candidat PS/PP      : {ps_candidate:.1f}%  ({PS_SHARE*100:.0f}% du NFP)")
print(f"  Bloc EELV+PCF       : {eelv_block:.1f}%  (ne présentent pas de candidat séparé → report sur l'un ou l'autre)")
print(f"\n  Seuil de maintien : {SEUIL_MAINTIEN_EXP*100:.1f}% exprimés ({SEUIL_MAINTIEN_INS}% inscrits)")

# Cas 1 : LFI + PS séparés, EELV/PCF sans candidat (s'abstiennent ou reportent)
print(f"\n  --- C1 : LFI + PS séparés, EELV sans candidat ---")
print(f"    LFI {lfi_candidate:.1f}% → {'QUALIFIÉ ✓' if lfi_candidate >= SEUIL_MAINTIEN_EXP*100 else f'NON qualifié ✗ (manque {SEUIL_MAINTIEN_EXP*100-lfi_candidate:.1f} pts)'}")
print(f"    PS  {ps_candidate:.1f}% → {'QUALIFIÉ ✓' if ps_candidate >= SEUIL_MAINTIEN_EXP*100 else f'NON qualifié ✗ (manque {SEUIL_MAINTIEN_EXP*100-ps_candidate:.1f} pts)'}")

# Si EELV+PCF se reportent sur LFI ou PS (+ 5-6% du NFP)
lfi_with_eelv = lfi_candidate + eelv_block * 0.3   # EELV va plutôt vers PS
ps_with_eelv  = ps_candidate  + eelv_block * 0.7
print(f"  --- C2 : EELV+PCF se reportent PS>LFI (70/30) ---")
print(f"    LFI ~{lfi_with_eelv:.1f}% → {'QUALIFIÉ ✓' if lfi_with_eelv >= SEUIL_MAINTIEN_EXP*100 else f'NON qualifié ✗ (manque {SEUIL_MAINTIEN_EXP*100-lfi_with_eelv:.1f} pts)'}")
print(f"    PS  ~{ps_with_eelv:.1f}%  → {'QUALIFIÉ ✓' if ps_with_eelv >= SEUIL_MAINTIEN_EXP*100 else f'NON qualifié ✗ (manque {SEUIL_MAINTIEN_EXP*100-ps_with_eelv:.1f} pts)'}")

# Impact par commune (en appliquant les mêmes ratios)
print(f"\n  Communes où le candidat PS/PP atteint le seuil :")
df['sc_lfi'] = (df['l24t1_left'] * LFI_SHARE).round(2)
df['sc_ps']  = (df['l24t1_left'] * (PS_SHARE + EELV_SHARE * 0.7)).round(2)
df['sc_rn']  = df['l24t1_far']

threshold_com = df['l24t1_participation'] * 0.9765 * SEUIL_MAINTIEN_INS / 100 if 'l24t1_participation' in df.columns else SEUIL_MAINTIEN_EXP * 100

ps_qualifies  = df[df['sc_ps']  >= SEUIL_MAINTIEN_EXP * 100]
lfi_qualifies = df[df['sc_lfi'] >= SEUIL_MAINTIEN_EXP * 100]
print(f"    PS/PP qualifié dans {len(ps_qualifies)}/21 communes")
print(f"    LFI qualifié dans   {len(lfi_qualifies)}/21 communes")
if len(ps_qualifies): print(f"    Communes PS qualifié : {ps_qualifies['nom_commune'].tolist()}")
if len(lfi_qualifies): print(f"    Communes LFI qualifié : {lfi_qualifies['nom_commune'].tolist()}")

# Configurations possibles au T2
print(f"\n  Configurations T2 scénario C :")
print(f"  Config. C-α (aucun gauche qualifié) : RN vs ENS/CDR — PERTE assurée pour la gauche ⚠")
print(f"  Config. C-β (seul PS qualifié) : PS vs RN — report LFI/EELV nécessaire")
ps_alone_t2 = ps_with_eelv + lfi_candidate * 0.70  # 70% de l'électorat LFI voterait PS au T2
ens_report  = REF['l24t1_ens'] * 0.25  # fraction ENS voterait PS (barrage)
ps_t2_total = ps_alone_t2 + ens_report
rn_t2_sc    = REF['l24t1_rn'] + REF['l24t1_ens'] * 0.15 + REF['l24t1_lr'] * 0.30
print(f"    PS au T2 (avec report LFI 70% + ENS barrage 25%) : ~{ps_t2_total:.1f}%")
print(f"    RN au T2 (+ reports droite) : ~{rn_t2_sc:.1f}%")
if ps_t2_total > rn_t2_sc:
    print(f"    → PS gagne avec {ps_t2_total:.1f}% (mais sous conditions de report fragiles)")
else:
    print(f"    → RN GAGNE ⚠  {rn_t2_sc:.1f}% vs PS {ps_t2_total:.1f}%")

# ─── 6. TABLEAU DE BORD PAR COMMUNE ──────────────────────────────────────────
print("\n" + "=" * 70)
print("6. TABLEAU DE BORD PAR COMMUNE — PROJECTIONS 2027")
print("=" * 70)

# Projections par commune
DELTA_A1, DELTA_A2 = 4.0, 8.0

df['proj_a1_rn']  = (df['l24t1_far'] + DELTA_A1).round(1)
df['proj_a1_nfp'] = (df['l24t1_left'] - DELTA_A1 * 0.15).round(1)
df['proj_a1_win'] = np.where(df['proj_a1_rn'] > df['proj_a1_nfp'], 'RN', 'NFP')

df['proj_a2_rn']  = (df['l24t1_far'] + DELTA_A2).round(1)
df['proj_a2_nfp'] = (df['l24t1_left'] - DELTA_A2 * 0.15).round(1)
df['proj_a2_win'] = np.where(df['proj_a2_rn'] > df['proj_a2_nfp'], 'RN', 'NFP')

df['proj_b2_cdr'] = (REF['l24t1_ens'] + REF['l24t1_lr'] + REF['l24t1_rec'] +
                     df['l24t1_far'] * 0.10).round(1)

df['proj_c_ps']   = (df['l24t1_left'] * (PS_SHARE + EELV_SHARE * 0.7)).round(1)
df['proj_c_lfi']  = (df['l24t1_left'] * LFI_SHARE).round(1)
df['proj_c_gap_maintien'] = (SEUIL_MAINTIEN_EXP * 100 - df['proj_c_ps']).round(1)

board_cols = ['nom_commune','inscrits','l24t1_left','l24t1_far',
              'proj_a1_win','proj_a1_nfp','proj_a1_rn',
              'proj_a2_win','proj_a2_nfp','proj_a2_rn',
              'proj_c_ps','proj_c_lfi','proj_c_gap_maintien','type_commune']
board = df[board_cols].copy()
board.columns = ['Commune','Inscrits','Left24','RN24',
                 'Win_A1','NFP_A1','RN_A1',
                 'Win_A2','NFP_A2','RN_A2',
                 'PS_C','LFI_C','GAP_seuil_PS','Type']

print("\n" + board.sort_values('Left24', ascending=False).to_string())

# ─── 7. SYNTHÈSE ET PROBABILITÉS ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("7. SYNTHÈSE — PROBABILITÉS ET RECOMMANDATIONS")
print("=" * 70)

print("""
RÉSULTATS 2024 (référence) :
  T1 : NFP 33.5% | RN 30.2% | ENS 25.4% | LR 6.3% | REC 1.0% — participation 66.9%
  T2 : NFP 59.5% vs RN 40.5% — écart +19 pts (barrage massif)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCÉNARIO A — RN RENFORCÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  A1 (+4 pts RN = 34%) : NFP GAGNE si barrage ENS > 60%. FRAGILE.
     → Probabilité réélection : ~65-70%
  A2 (+8 pts RN = 38%) : T2 très serré. NFP gagne seulement si barrage fort.
     → Probabilité réélection : ~45-55%
  A3 (+12 pts RN = 42%) : RN premier au T1 avec une avance solide.
     → Probabilité réélection : ~25-35%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCÉNARIO B — DROITE RECOMPOSÉE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  B1 (ENS+LR unis, 0% RN) : CDR ~32.6% qualifié. T2 triangulaire probable.
     → Si NFP premier : NFP gagne. Si CDR premier : risque de duel CDR/RN.
     → Probabilité réélection NFP : ~55-65%
  B2 (+10% RN) : CDR ~35.6% — peut passer premier. T2 CDR/RN possible.
     → Probabilité réélection NFP : ~35-45% (défaite si NFP pas au T2)
  B3 (+20% RN) : CDR ~38.6% — duel CDR/RN, NFP exclu du T2.
     → Probabilité réélection NFP : ~0% ⚠  (NFP hors T2)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCÉNARIO C — DÉSUNION GAUCHE (LFI + PS séparés)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Sans EELV : LFI ~13.4%, PS ~11.2% — AUCUN ne passe le seuil de 19.2%
  Avec EELV reporté PS : PS ~14.6%, LFI ~13.4% — TOUJOURS sous le seuil ⚠
  → T2 RN / ENS sans représentation gauche = PERTE CERTAINE
  → Seule condition de survie : un seul candidat gauche se maintient
    (ex. LFI ou PS retire avant le seuil officiel, accord avant T1)
  Probabilité réélection si désunion : ~5-10% (dépend du contexte national)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOP 10 COMMUNES PRIORITAIRES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

# Critère : communes où l'écart NFP-RN est le plus faible (à consolider/reconquérir)
df['ecart_nfp_rn'] = (df['l24t1_left'] - df['l24t1_far']).round(1)
top10_risk = df.nsmallest(10, 'ecart_nfp_rn')[['nom_commune','inscrits','l24t1_left','l24t1_far','ecart_nfp_rn','type_commune']]
top10_risk.columns = ['Commune','Inscrits','NFP24','RN24','Écart','Type']
print("  Communes les plus fragiles (écart NFP-RN le plus faible) :")
print(top10_risk.to_string())

# ─── EXPORT ──────────────────────────────────────────────────────────────────
out_path = os.path.join(DATA, 'projections_9502.csv')
df.to_csv(out_path)
print(f"\n\n✓ Projections sauvegardées : {out_path}")
print(f"  {len(df)} communes × {len(df.columns)} colonnes")
