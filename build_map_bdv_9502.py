#!/usr/bin/env python3
"""
build_map_bdv_9502.py
Carte interactive par bureau de vote — 2ème Circo Val-d'Oise (Ayda Hadizadeh)

Couleurs : rouge = gauche | jaune = centre | bleu = droite/RN
Couches  : T1 2024 réel | Scénario A1 (+4pts RN) | Scénario A2 (+8pts RN) | Scénario C (désunion)
Popups   : top 3 formations + estimations par scénario

Output : carte_bdv_9502.html  +  analyse_9502_bdv.md
"""
import os, math, json, warnings, requests
import pandas as pd
import numpy as np
import folium
from folium.plugins import FeatureGroupSubGroup
warnings.filterwarnings('ignore')

DATA   = "/Users/remybajolet/Desktop/datagouv/data"
CIRC   = "2"
DEP    = "95"
SEUIL  = 19.14   # % exprimés pour se maintenir au 2nd tour

# ─── Palettes ─────────────────────────────────────────────────────────────────
def color_gauche(pct):
    t = min(1.0, pct / 65.0)
    r = int(180 + 75 * t)
    g = int(20 * (1 - t))
    b = int(20 * (1 - t))
    return f"#{r:02x}{g:02x}{b:02x}"

def color_centre(pct):
    t = min(1.0, pct / 40.0)
    r = int(240 * t + 200 * (1 - t))
    g = int(200 * t + 180 * (1 - t))
    b = int(20 * (1 - t))
    return f"#{r:02x}{g:02x}{b:02x}"

def color_droite(pct):
    t = min(1.0, pct / 50.0)
    r = int(20 * (1 - t))
    g = int(50 * (1 - t))
    b = int(120 + 135 * t)
    return f"#{r:02x}{g:02x}{b:02x}"

def dominant_color(left, ctr, rgt, far, rnx=None):
    """Couleur selon la formation dominante."""
    rn = rnx if rnx is not None else far
    scores = {'gauche': left, 'centre': ctr, 'droite': rgt, 'far': rn}
    dom = max(scores, key=scores.get)
    if dom == 'gauche': return color_gauche(left)
    if dom == 'centre': return color_centre(ctr)
    return color_droite(max(rgt, rn))


# ─── Chargement des données BdV ───────────────────────────────────────────────
def load_bdv():
    """Charge et fusionne les BdV de circ 2 pour tous les scrutins."""
    dfs = {}
    for label in ['leg17t1', 'leg22t1', 'leg22t2', 'leg24t1', 'leg24t2',
                  'eu24', 'pr17t1', 'pr22t1', 'pr22t2']:
        path = os.path.join(DATA, f'bdv_{label}.csv')
        df = pd.read_csv(path, dtype={'code_commune': str, 'num_bdv': str})
        # code_circ peut être "2", "2.0", "02" selon écriture pandas — normaliser
        df['code_circ'] = (df['code_circ'].astype(str).str.strip()
                                          .str.replace(r'\.0$', '', regex=True)
                                          .str.lstrip('0'))
        df['code_commune'] = df['code_commune'].astype(str).str.strip().str.zfill(5)
        df['num_bdv'] = df['num_bdv'].astype(str).str.strip().str.lstrip('0')
        dfs[label] = df[df['code_circ'] == CIRC].copy()
    return dfs


def parse_eu24_bdv_detail(communes_circ2):
    """
    Re-parse le fichier eu24 BdV pour obtenir LFI, PS+G (LUG), EELV (LVEC), PCF (LCOM)
    par bureau de vote de la circ 2.
    """
    LFI_MAP = {
        'eu_lfi': {'LFI'},
        'eu_lug': {'LUG'},
        'eu_vec': {'LVEC'},
        'eu_com': {'LCOM'},
    }
    cache = os.path.join(DATA, '_cache_bdv_eu24.csv')
    chunks = []
    for chunk in pd.read_csv(cache, sep=';', chunksize=10000, low_memory=False):
        chunk.columns = chunk.columns.str.strip()
        if 'Code département' not in chunk.columns: continue
        filt = chunk[chunk['Code département'].astype(str).str.strip() == DEP]
        filt = filt[filt['Code commune'].astype(str).str.strip().isin(communes_circ2)]
        if len(filt) > 0:
            chunks.append(filt)
    if not chunks:
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    cols = list(df.columns)
    nuance_cols = [(c, c.split()[-1]) for c in cols
                   if 'nuance' in c.lower() and c.split()[-1].isdigit()]

    def sf(v):
        if pd.isna(v): return 0.0
        try: return float(str(v).replace(',','.').replace('\xa0','').replace(' ',''))
        except: return 0.0

    records = []
    for _, row in df.iterrows():
        code_com = str(row['Code commune']).strip().zfill(5)
        bdv_num  = str(row['Code BV']).strip()
        ins  = sf(row.get('Inscrits', 0))
        vot  = sf(row.get('Votants', 0))
        exp  = sf(row.get('Exprimés', 0))
        scores = {k: 0.0 for k in LFI_MAP}
        for nc, num in nuance_cols:
            nuance = str(row[nc]).strip().upper()
            if nuance in ('NAN', 'NONE', ''): continue
            vc = next((c for c in cols if c.strip() == f'Voix {num}'), None)
            if vc is None: continue
            voix = sf(row[vc])
            for bl, ns in LFI_MAP.items():
                if nuance in ns:
                    scores[bl] += voix; break
        rec = {'code_commune': code_com, 'num_bdv': bdv_num,
               'eu_ins': int(ins), 'eu_exp': int(exp)}
        for bl, v in scores.items():
            rec[bl] = round(100 * v / exp, 2) if exp > 0 else 0.0
        records.append(rec)
    return pd.DataFrame(records)


# ─── Construction du tableau principal par BdV ────────────────────────────────
def build_bdv_table(dfs, eu_detail):
    """Fusionne tous les scrutins sur une ligne par BdV."""
    base = dfs['leg24t1'][['code_commune','nom_commune','num_bdv',
                            'inscrits','votants','exprimes','participation',
                            'left','ctr','rgt','far']].copy()
    base.columns = ['code_commune','nom_commune','num_bdv',
                    'ins','vot','exp','part',
                    'l24t1_left','l24t1_ctr','l24t1_rgt','l24t1_far']
    base['key'] = base['code_commune'].astype(str) + '_' + base['num_bdv'].astype(str)

    # leg24t2
    t2 = dfs['leg24t2'][['code_commune','num_bdv','left','far']].copy()
    t2.columns = ['cc','nb','l24t2_left','l24t2_far']
    t2['key'] = t2['cc'].astype(str) + '_' + t2['nb'].astype(str)
    base = base.merge(t2[['key','l24t2_left','l24t2_far']], on='key', how='left')

    # leg22t1 (centre, droite, gauche, RN au BdV — pour modèle d'érosion dynamique)
    l22 = dfs['leg22t1'][['code_commune','num_bdv','left','ctr','rgt','far']].copy()
    l22.columns = ['cc','nb','l22t1_left','l22t1_ctr','l22t1_rgt','l22t1_far']
    l22['key'] = l22['cc'].astype(str) + '_' + l22['nb'].astype(str)
    base = base.merge(l22[['key','l22t1_left','l22t1_ctr','l22t1_rgt','l22t1_far']],
                      on='key', how='left')

    # pr22t1
    pr = dfs['pr22t1'][['code_commune','num_bdv','pr_left','pr_macron','pr_lepen','pr_pec','pr_zem','pr_other']].copy()
    pr = pr.rename(columns={'code_commune':'cc','num_bdv':'nb'})
    pr['key'] = pr['cc'].astype(str) + '_' + pr['nb'].astype(str)
    base = base.merge(pr[['key','pr_left','pr_macron','pr_lepen','pr_pec','pr_zem','pr_other']],
                      on='key', how='left')

    # Historique : Leg 2017 T1 (blocs canoniques anciens)
    if 'leg17t1' in dfs:
        l17 = dfs['leg17t1'][['code_commune','num_bdv','left','ctr','rgt','far']].copy()
        l17.columns = ['cc','nb','l17t1_left','l17t1_ctr','l17t1_rgt','l17t1_far']
        l17['key'] = l17['cc'].astype(str) + '_' + l17['nb'].astype(str)
        base = base.merge(l17[['key','l17t1_left','l17t1_ctr','l17t1_rgt','l17t1_far']],
                          on='key', how='left')

    # Historique : Pres 2017 T1
    if 'pr17t1' in dfs:
        p17 = dfs['pr17t1'][['code_commune','num_bdv','pr_left','pr_macron','pr_pec','pr_lepen']].copy()
        p17 = p17.rename(columns={'code_commune':'cc','num_bdv':'nb',
                                  'pr_left':'p17_left','pr_macron':'p17_macron',
                                  'pr_pec':'p17_fillon','pr_lepen':'p17_lepen'})
        p17['key'] = p17['cc'].astype(str) + '_' + p17['nb'].astype(str)
        base = base.merge(p17[['key','p17_left','p17_macron','p17_fillon','p17_lepen']],
                          on='key', how='left')

    # Historique : Pres 2022 T2 (Macron vs Le Pen)
    if 'pr22t2' in dfs:
        p22t2 = dfs['pr22t2'][['code_commune','num_bdv','pr2_macron','pr2_lepen']].copy()
        p22t2.columns = ['cc','nb','p22t2_macron','p22t2_lepen']
        p22t2['key'] = p22t2['cc'].astype(str) + '_' + p22t2['nb'].astype(str)
        base = base.merge(p22t2[['key','p22t2_macron','p22t2_lepen']], on='key', how='left')

    # Historique : Euro 2024 — agrégats par bloc canonique
    eu_totals = dfs['eu24'][['code_commune','num_bdv','eu_left','eu_ctr','eu_lr','eu_rn']].copy()
    eu_totals.columns = ['cc','nb','eu_left_t','eu_ctr_t','eu_lr_t','eu_rn_t']
    eu_totals['key'] = eu_totals['cc'].astype(str) + '_' + eu_totals['nb'].astype(str)
    base = base.merge(eu_totals[['key','eu_left_t','eu_ctr_t','eu_lr_t','eu_rn_t']],
                      on='key', how='left')

    # eu24 detail (LFI split — pour la désunion)
    if not eu_detail.empty:
        eu_detail = eu_detail.copy()
        eu_detail['key'] = eu_detail['code_commune'].astype(str) + '_' + eu_detail['num_bdv'].astype(str)
        base = base.merge(eu_detail[['key','eu_lfi','eu_lug','eu_vec','eu_com']],
                          on='key', how='left')
    else:
        base['eu_lfi'] = base['eu_lug'] = base['eu_vec'] = base['eu_com'] = np.nan

    # NFP split ratio par BdV (proxy euro24 → LFI vs PS+G)
    base['eu_total_left'] = (base['eu_lfi'].fillna(0) + base['eu_lug'].fillna(0) +
                              base['eu_vec'].fillna(0) + base['eu_com'].fillna(0))
    base['lfi_ratio'] = np.where(base['eu_total_left'] > 0,
                                  base['eu_lfi'].fillna(0) / base['eu_total_left'],
                                  0.435)  # fallback circ-level
    base['psg_ratio'] = 1 - base['lfi_ratio']

    # NFP absolu
    base['nfp']  = base['l24t1_left']
    base['ens']  = base['l24t1_ctr']
    base['lr']   = base['l24t1_rgt']
    base['rn']   = base['l24t1_far']
    base['lfi']  = base['nfp'] * base['lfi_ratio']
    base['psg']  = base['nfp'] * base['psg_ratio']

    # Progression RN 2022→2024
    base['delta_rn'] = base['rn'] - base['l22t1_far'].fillna(base['rn'])

    return base.fillna(0)


# ─── Scénarios — Modèle d'érosion dynamique du centre/droite ─────────────────
#
# Hypothèse : le moteur de la recomposition n'est pas "RN +X pts" mais
# l'évolution du bloc centre+LR (ENS+LR), qui se redistribue selon les
# profils LOCAUX observés 2022→2024 par BdV (pas un ratio uniforme).
#
# Mécanique :
#   1. Calculer Δ_22_24 par bloc pour chaque BdV (centre+LR, RN, NFP)
#   2. Multiplier ×K pour calibrer la moyenne circo à la cible scénario
#      - Effondrement : cible Δcentre+LR = -12 pts → K = +12 / mean_observed
#      - Sursaut Philippe : cible Δcentre+LR = +12 pts → K = -12 / mean_observed
#      (mean_observed ≈ -5.35 pts pour la 9502 → K ≈ ±2.24)
#   3. Projection : pct_27 = pct_24 + Δ_22_24 × K  (bornée [0, ceiling])
#
# Avantage : chaque BdV évolue selon SON propre profil de transfert
# (un BdV où le centre est allé vers le RN continue ainsi ; un BdV
# où le centre est allé vers le NFP fait pareil).

# ─── Paramètres scénarios (modèle v4) ────────────────────────────────────────
# Cibles politiques par bloc et par scénario (Δ en pts sur la moy. circo).
# Calibrées sur les ratios historiques observés 2017→2024 sur la 9502
# (centre+LR perdu : 64% vers RN, 34% vers NFP, 2% vers abst).
#
# Refonte v4 (mai 2026) : abandonne le multiplier×Δ_locale (v3) qui produisait
# des résultats absurdes pour NFP/RN dans les BdV au profil atypique
# (ex : NFP qui baisse en effondrement). Nouveau modèle : scaling uniforme
# proportionnel par bloc, chaque BdV évolue selon sa proportion 2024.
SCENARIO_CIBLES = {
    'sursaut': {
        'centre_lr': +12.0,   # ENS+LR remonte fort (sursaut républicain)
        'nfp':       -2.5,    # NFP perd un peu (vote utile centre)
        'rn':        -6.0,    # RN baisse modérément (socle préservé)
    },
    'effondrement': {
        'centre_lr': -12.0,   # Centre+LR s'effondre
        'nfp':       +4.0,    # NFP gagne 34% de l'érosion centre (ratio historique)
        'rn':        +7.0,    # RN gagne 64% de l'érosion centre (ratio historique)
    },
}

CEILING_RN  = 60.0         # plafond physique
CEILING_NFP = 80.0
CEILING_CTR = 60.0
CEILING_LR  = 30.0

# Asymétrie ENS/LR (Option C) :
# En SURSAUT Philippe, Édouard Philippe (marque Horizons) absorbe une partie
# de l'électorat LR résiduel. LR ne profite pas du sursaut : il continue à
# baisser. Paramètre : fraction de LR conservée en sursaut.
LR_RETENTION_SURSAUT = 0.5  # LR conserve 50% de son score 2024, le reste va à ENS


def compute_scenario_params(bdv_table, direction):
    """
    Calcule les scalings uniformes par bloc pour un scénario (modèle v4).
    direction : 'sursaut' ou 'effondrement'

    Pour chaque bloc (centre+LR, NFP, RN) :
        scaling_b = (mean_circo_b + cible_b) / mean_circo_b

    Chaque BdV verra son score scalé du même facteur pour ce bloc :
        score_27_bdv_b = score_24_bdv_b × scaling_b

    Le scaling uniforme préserve les profils géographiques (un BdV à 50% NFP
    reste relativement plus à gauche qu'un BdV à 25%), sans amplification
    artificielle des dynamiques locales 22→24 (qui produisaient des résultats
    incohérents en v3 pour les BdV atypiques).

    Renvoie un dict : {'centre_lr', 'nfp', 'rn'} → scaling factor
    Et conserve une clé 'K' = 0 pour rétrocompatibilité (utilisé par v3, plus
    nécessaire mais évite de casser les autres appels).
    """
    cibles = SCENARIO_CIBLES[direction]

    means = {
        'centre_lr': (bdv_table['ens'] + bdv_table['lr']).mean(),
        'nfp':       bdv_table['nfp'].mean(),
        'rn':        bdv_table['rn'].mean(),
    }

    scalings = {}
    for bloc in ('centre_lr', 'nfp', 'rn'):
        m = means[bloc]
        scalings[bloc] = (m + cibles[bloc]) / m if m > 0.1 else 1.0

    return scalings


# Alias rétrocompatibilité (compute_scenario_multiplier renvoyait (K, scaling))
def compute_scenario_multiplier(bdv_table, direction):
    return 0.0  # v3 K plus utilisé


def apply_scenario_dynamique(row, scalings, _legacy=None):
    """
    Projette un BdV en 2027 (modèle v4) :
    Pour chaque bloc (centre+LR, NFP, RN), application d'un scaling uniforme :
        score_27_bdv_b = score_24_bdv_b × scaling_b

    Le scaling est calibré sur les cibles politiques circo (SCENARIO_CIBLES) :
    - Sursaut Philippe  : centre+LR +12 pts, NFP -2.5 pts, RN -6 pts
    - Effondrement      : centre+LR -12 pts, NFP +4 pts (récup 34% du centre),
                          RN +7 pts (récup 64% du centre)

    Asymétrie ENS/LR (Option C, conservée) :
    - SURSAUT : LR conserve 50% (LR_RETENTION_SURSAUT) ; ENS récupère le reste
                de la cible centre+LR (Philippe absorbe LR).
    - EFFONDREMENT : ENS et LR baissent proportionnellement à leur poids 2024.

    Retourne (nfp_27, ens_27, lr_27, rn_27).

    Le 3e paramètre `_legacy` existe pour rétrocompatibilité avec l'ancienne
    signature `apply_scenario_dynamique(row, K, scaling)` — ignoré.

    Si scalings est None ou {} → renvoie T1 2024 inchangé (référence).
    """
    if not scalings:
        return row['nfp'], row['ens'], row['lr'], row['rn']

    sc_centre = scalings['centre_lr']
    sc_nfp    = scalings['nfp']
    sc_rn     = scalings['rn']

    # Bloc ENS+LR : scaling uniforme + asymétrie ENS/LR
    centre_lr_24 = row['ens'] + row['lr']
    centre_lr_27 = centre_lr_24 * sc_centre

    if sc_centre > 1.0:
        # SURSAUT Philippe : LR résiduel, ENS absorbe
        lr = row['lr'] * LR_RETENTION_SURSAUT
        ens = max(0.0, centre_lr_27 - lr)
    elif sc_centre < 1.0:
        # EFFONDREMENT : partage proportionnel selon poids 2024
        if centre_lr_24 < 0.01:
            ens, lr = row['ens'], row['lr']
        else:
            ens = centre_lr_27 * (row['ens'] / centre_lr_24)
            lr  = centre_lr_27 * (row['lr']  / centre_lr_24)
    else:
        ens, lr = row['ens'], row['lr']

    # NFP et RN : scaling uniforme proportionnel
    nfp = row['nfp'] * sc_nfp
    rn  = row['rn']  * sc_rn

    # Bornes physiques
    ens = max(0.0, min(CEILING_CTR, ens))
    lr  = max(0.0, min(CEILING_LR,  lr))
    rn  = max(0.0, min(CEILING_RN,  rn))
    nfp = max(0.0, min(CEILING_NFP, nfp))
    return nfp, ens, lr, rn


def apply_desunion(nfp_pct, lfi_ratio, psg_ratio):
    """Split d'un score NFP en (LFI seul, PS+G seul) selon ratio Euro 2024 BdV."""
    return nfp_pct * lfi_ratio, nfp_pct * psg_ratio


def top3(parties_dict):
    """Retourne les 3 formations avec les plus hauts scores."""
    return sorted(parties_dict.items(), key=lambda x: -x[1])[:3]


# ─── Géographie : centroides communes ─────────────────────────────────────────
def get_commune_centroids(commune_codes):
    """Récupère les contours et calcule le centroïde de chaque commune."""
    centroids = {}
    for code in commune_codes:
        url = f"https://geo.api.gouv.fr/communes/{code}?format=geojson&geometry=contour"
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            gj = r.json()
            coords_raw = gj['geometry']['coordinates']
            # Gérer Polygon vs MultiPolygon
            if gj['geometry']['type'] == 'MultiPolygon':
                pts = [p for ring in coords_raw for p in ring[0]]
            else:
                pts = coords_raw[0]
            lons = [p[0] for p in pts]
            lats = [p[1] for p in pts]
            centroids[code] = (np.mean(lats), np.mean(lons))
        except Exception as e:
            print(f"    {code} erreur centroïde: {e}")
    return centroids


def jitter_positions(commune_code, bdv_list, centroids):
    """
    Répartit N BdV autour du centroïde de la commune.
    Retourne {f"{commune_code}_{bdv}": (lat, lon)}.
    """
    key_str = str(commune_code)
    if key_str not in centroids:
        return {}
    lat0, lon0 = centroids[key_str]
    n = len(bdv_list)
    positions = {}
    if n == 1:
        positions[f"{commune_code}_{bdv_list[0]}"] = (lat0, lon0)
        return positions
    radius = 0.003 * math.sqrt(n)
    for i, bdv in enumerate(bdv_list):
        angle = 2 * math.pi * i / n
        dlat = radius * math.cos(angle)
        dlon = radius * math.sin(angle) / math.cos(math.radians(lat0))
        positions[f"{commune_code}_{bdv}"] = (lat0 + dlat, lon0 + dlon)
    return positions


# ─── HTML popup ───────────────────────────────────────────────────────────────
PARTY_FR = {
    'NFP':  'NFP',
    'LFI':  'LFI',
    'PSG':  'PS+G',
    'ENS':  'Ensemble',
    'LR':   'LR',
    'RN':   'RN',
}
PARTY_COLOR = {
    'NFP': '#c0392b', 'LFI': '#8e1010', 'PSG': '#e74c3c',
    'ENS': '#e67e22', 'LR':  '#2980b9', 'RN':  '#1a5276',
}

def make_popup(row):
    """Génère le HTML de popup pour un BdV."""
    def bar(name, pct):
        color = PARTY_COLOR.get(name, '#888')
        width = min(100, pct * 2)
        sous_seuil = pct < SEUIL and name in ('LFI', 'PSG', 'NFP', 'ENS')
        mark = ' <span style="color:red">⚠</span>' if sous_seuil else ''
        return (f'<div style="margin:2px 0">'
                f'<span style="display:inline-block;width:65px;font-size:11px">'
                f'{PARTY_FR.get(name, name)}</span>'
                f'<span style="display:inline-block;width:{width:.0f}px;height:9px;'
                f'background:{color};vertical-align:middle"></span>'
                f' <b>{pct:.1f}%</b>{mark}</div>')

    nom  = str(row['nom_commune'])
    bdv  = str(row['num_bdv'])
    ins  = int(row['ins'])
    part = float(row['part'])

    nfp_a1, ens_a1, lr_a1, rn_a1 = apply_scenario_a(row, 4)
    nfp_a2, ens_a2, lr_a2, rn_a2 = apply_scenario_a(row, 8)
    lfi_c, psg_c, ens_c, lr_c, rn_c = apply_scenario_c(row)

    def section(title, parties):
        t3 = top3(parties)
        inner = ''.join(bar(n, v) for n, v in t3)
        return (f'<div style="background:#f8f9fa;margin:3px 0;padding:4px 6px;'
                f'border-radius:3px"><b style="font-size:11px">{title}</b><br>'
                + inner + '</div>')

    html = (
        f'<div style="font-family:Arial,sans-serif;min-width:230px;font-size:12px;padding:4px">'
        f'<b>{nom} &mdash; BdV {bdv}</b><br>'
        f'<span style="color:#666;font-size:11px">Inscrits&nbsp;: {ins:,} &nbsp;|&nbsp; Part.&nbsp;: {part:.1f}%</span>'
        f'<hr style="margin:4px 0;border:0;border-top:1px solid #ddd">'
        + section('T1 2024 (réel)',
                  {'NFP': float(row['nfp']), 'ENS': float(row['ens']),
                   'LR': float(row['lr']),   'RN':  float(row['rn'])})
        + section('Scénario A1 +4pts RN',
                  {'NFP': nfp_a1, 'ENS': ens_a1, 'LR': lr_a1, 'RN': rn_a1})
        + section('Scénario A2 +8pts RN',
                  {'NFP': nfp_a2, 'ENS': ens_a2, 'LR': lr_a2, 'RN': rn_a2})
        + section('Scénario C désunion',
                  {'LFI': lfi_c, 'PSG': psg_c, 'ENS': ens_c, 'LR': lr_c, 'RN': rn_c})
        + f'<div style="font-size:9px;color:#aaa;margin-top:3px">'
          f'Seuil T2 : {SEUIL}% | ⚠ = sous le seuil</div></div>'
    )
    return folium.Popup(html, max_width=310)


# ─── Contours communes GeoJSON ────────────────────────────────────────────────
def get_commune_contours(commune_codes):
    """Récupère les contours GeoJSON de chaque commune."""
    features = []
    for code in commune_codes:
        url = f"https://geo.api.gouv.fr/communes/{code}?format=geojson&geometry=contour"
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            gj = r.json()
            gj['properties']['code'] = code
            features.append(gj)
        except Exception as e:
            print(f"    contour {code} erreur: {e}")
    return {'type': 'FeatureCollection', 'features': features}


# ─── Tooltip simple (pas de popup jQuery) ─────────────────────────────────────
def make_tooltip_t1(row):
    nom = str(row['nom_commune'])
    bdv = str(row['num_bdv'])
    nfp = float(row['nfp']); ens = float(row['ens'])
    lr = float(row['lr']); rn = float(row['rn'])
    return (f"{nom} BdV {bdv} | "
            f"NFP {nfp:.1f}% ENS {ens:.1f}% RN {rn:.1f}% LR {lr:.1f}%")


def make_tooltip_a(row, delta, label):
    nom = str(row['nom_commune'])
    bdv = str(row['num_bdv'])
    nfp, ens, lr, rn = apply_scenario_a(row, delta)
    return (f"{nom} BdV {bdv} | {label} | "
            f"NFP {nfp:.1f}% ENS {ens:.1f}% RN {rn:.1f}%")


def make_tooltip_c(row):
    nom = str(row['nom_commune'])
    bdv = str(row['num_bdv'])
    lfi, psg, ens, lr, rn = apply_scenario_c(row)
    tag = " [PSG sous seuil]" if psg < SEUIL else ""
    return (f"{nom} BdV {bdv} | Sc. C | "
            f"LFI {lfi:.1f}% PSG {psg:.1f}% RN {rn:.1f}%{tag}")


# ─── Agrégats historiques circo (4 scrutins demandés) ─────────────────────────
def compute_circo_history(bdv_table):
    """
    Calcule les agrégats circo pondérés par les exprimés pour 4 scrutins historiques :
    Présidentielles 2017 T1, Législatives 2017 T1, Présidentielles 2022 T1, Européennes 2024.
    Renvoie une liste de dicts {label, year, blocs:[(name, pct, color), ...]}.
    """
    exp = bdv_table['exp']
    exp_total = exp.sum()

    def w(col):
        """Moyenne pondérée par les exprimés ; renvoie None si colonne absente/vide."""
        if col not in bdv_table.columns:
            return None
        s = bdv_table[col].fillna(0)
        if s.sum() == 0:
            return None
        return float((s * exp).sum() / exp_total)

    history = []

    # Présidentielle 2017 T1
    p17_left   = w('p17_left')
    p17_macron = w('p17_macron')
    p17_fillon = w('p17_fillon')
    p17_lepen  = w('p17_lepen')
    if p17_lepen is not None:
        history.append({
            'label': 'Présidentielle 2017 T1',
            'blocs': [
                ('Gauche',         p17_left,   '#c0392b'),
                ('Macron',         p17_macron, '#e67e22'),
                ('Fillon (LR)',    p17_fillon, '#2980b9'),
                ('Le Pen (FN)',    p17_lepen,  '#1a5276'),
            ],
        })

    # Législatives 2017 T1
    l17_left = w('l17t1_left')
    l17_ctr  = w('l17t1_ctr')
    l17_rgt  = w('l17t1_rgt')
    l17_far  = w('l17t1_far')
    if l17_far is not None:
        history.append({
            'label': 'Législatives 2017 T1',
            'blocs': [
                ('Gauche',     l17_left, '#c0392b'),
                ('REM/Macron', l17_ctr,  '#e67e22'),
                ('LR/Droite',  l17_rgt,  '#2980b9'),
                ('FN',         l17_far,  '#1a5276'),
            ],
        })

    # Présidentielle 2022 T1
    p22_left   = w('pr_left')
    p22_macron = w('pr_macron')
    p22_pec    = w('pr_pec')
    p22_lepen  = w('pr_lepen')
    p22_zem    = w('pr_zem')
    if p22_lepen is not None:
        history.append({
            'label': 'Présidentielle 2022 T1',
            'blocs': [
                ('Gauche',          p22_left,   '#c0392b'),
                ('Macron',          p22_macron, '#e67e22'),
                ('Pécresse (LR)',   p22_pec,    '#2980b9'),
                ('Le Pen (RN)',     p22_lepen,  '#1a5276'),
                ('Zemmour (REC)',   p22_zem,    '#7b241c'),
            ],
        })

    # Européennes 2024
    eu_left = w('eu_left_t')
    eu_ctr  = w('eu_ctr_t')
    eu_lr   = w('eu_lr_t')
    eu_rn   = w('eu_rn_t')
    if eu_rn is not None:
        history.append({
            'label': 'Européennes 2024',
            'blocs': [
                ('Gauche unie',     eu_left, '#c0392b'),
                ('Besoin d\'Europe',eu_ctr,  '#e67e22'),
                ('LR',              eu_lr,   '#2980b9'),
                ('RN+REC',          eu_rn,   '#1a5276'),
            ],
        })

    return history


def render_history_panel(history):
    """Rend le panneau d'historique électoral circo (fixe, indépendant du scénario)."""
    if not history:
        return ''

    def mini_bar(label, pct, color):
        if pct is None:
            return ''
        width = min(120, pct * 2.5)
        return (f'<div style="margin:1px 0;display:flex;align-items:center;gap:5px;font-size:10px;line-height:1.3">'
                f'<span style="display:inline-block;width:105px">{label}</span>'
                f'<span style="display:inline-block;width:{width:.0f}px;height:8px;'
                f'background:{color};border-radius:2px"></span>'
                f'<span><b>{pct:.1f}%</b></span></div>')

    sections = []
    for elec in history:
        bars = ''.join(mini_bar(name, pct, color) for name, pct, color in elec['blocs'])
        sections.append(
            f'<div style="margin-top:5px">'
            f'<div style="font-weight:600;font-size:10.5px;margin-bottom:1px;color:#444">{elec["label"]}</div>'
            + bars + '</div>'
        )

    return (
        '<div id="history-panel" style="'
        'position:fixed;bottom:295px;left:30px;z-index:9998;'
        'background:white;padding:8px 12px;border-radius:8px;'
        'box-shadow:0 2px 8px rgba(0,0,0,.18);font-family:Arial,sans-serif;'
        'width:290px;max-height:200px;overflow-y:auto;'
        'border:1px solid #ddd">'
        '<div style="font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.5px;'
        'margin-bottom:4px;position:sticky;top:0;background:white;padding-bottom:2px">'
        'Historique circo 9502</div>'
        + ''.join(sections) + '</div>'
    )


# ─── Couleurs scénarios pour polygones BdV ────────────────────────────────────
def compute_circo_aggregates(bdv_table, params):
    """
    Calcule les agrégats circo (pondérés par les exprimés) pour chaque scénario.
    Retourne un dict {scen_code: {'nfp': X, 'ens': Y, 'lr': Z, 'rn': W, 'lfi': L, 'psg': P, 'psg_under': N}}
    """
    out = {}
    exp_total = bdv_table['exp'].sum()

    # T1 réel
    nfp_t1 = (bdv_table['nfp'] * bdv_table['exp']).sum() / exp_total
    ens_t1 = (bdv_table['ens'] * bdv_table['exp']).sum() / exp_total
    lr_t1  = (bdv_table['lr']  * bdv_table['exp']).sum() / exp_total
    rn_t1  = (bdv_table['rn']  * bdv_table['exp']).sum() / exp_total
    out['t1'] = {'nfp': nfp_t1, 'ens': ens_t1, 'lr': lr_t1, 'rn': rn_t1,
                 'lfi': None, 'psg': None, 'psg_under': None}

    # 4 scénarios prospectifs
    for scen, key in [('sur_union','sur'), ('sur_desunion','sur'),
                       ('eff_union','eff'), ('eff_desunion','eff')]:
        scalings = params[key]
        proj = bdv_table.apply(lambda r: apply_scenario_dynamique(r, scalings),
                               axis=1, result_type='expand')
        proj.columns = ['nfp','ens','lr','rn']

        nfp = (proj['nfp'] * bdv_table['exp']).sum() / exp_total
        ens = (proj['ens'] * bdv_table['exp']).sum() / exp_total
        lr  = (proj['lr']  * bdv_table['exp']).sum() / exp_total
        rn  = (proj['rn']  * bdv_table['exp']).sum() / exp_total

        rec = {'nfp': nfp, 'ens': ens, 'lr': lr, 'rn': rn,
               'lfi': None, 'psg': None, 'psg_under': None}

        if scen.endswith('desunion'):
            lfi_bdv = proj['nfp'] * bdv_table['lfi_ratio']
            psg_bdv = proj['nfp'] * bdv_table['psg_ratio']
            rec['lfi']       = (lfi_bdv * bdv_table['exp']).sum() / exp_total
            rec['psg']       = (psg_bdv * bdv_table['exp']).sum() / exp_total
            rec['psg_under'] = int((psg_bdv < SEUIL).sum())

        out[scen] = rec

    return out


def render_aggregate_panel(aggregates, n_bdv):
    """
    Construit le HTML d'un panneau d'agrégats circo (5 vues, une par scénario).
    Une seule visible à la fois — toggle JS via overlayadd.
    """
    scen_titles = {
        't1':           "T1 2024 (réel)",
        'sur_union':    "Dynamique Philippe + Union NFP",
        'sur_desunion': "Dynamique Philippe + Désunion",
        'eff_union':    "Effondrement centre + Union NFP",
        'eff_desunion': "Effondrement centre + Désunion",
    }

    def bar(label, pct, alert=False):
        color = {'NFP':'#c0392b','LFI':'#8e1010','PSG':'#e74c3c',
                 'ENS':'#e67e22','LR':'#2980b9','RN':'#1a5276'}.get(label, '#888')
        width = min(220, pct * 4.5)
        mark = ' <span style="color:#c00">⚠</span>' if alert else ''
        return (f'<div style="margin:3px 0;display:flex;align-items:center;gap:6px">'
                f'<span style="display:inline-block;width:38px;font-size:12px;font-weight:600">{label}</span>'
                f'<span style="display:inline-block;width:{width:.0f}px;height:12px;'
                f'background:{color};border-radius:2px"></span>'
                f'<span style="font-size:12px"><b>{pct:.1f}%</b>{mark}</span></div>')

    panels = []
    for scen, title in scen_titles.items():
        agg = aggregates[scen]
        display = 'block' if scen == 't1' else 'none'
        body_rows = []
        if scen.endswith('desunion'):
            body_rows.append(bar('LFI', agg['lfi'], alert=(agg['lfi'] < SEUIL)))
            body_rows.append(bar('PSG', agg['psg'], alert=(agg['psg'] < SEUIL)))
            body_rows.append(bar('ENS', agg['ens']))
            body_rows.append(bar('LR',  agg['lr']))
            body_rows.append(bar('RN',  agg['rn']))
            footer = (f'<div style="font-size:10px;color:#888;margin-top:4px">'
                      f'<b>{agg["psg_under"]} BdV / {n_bdv}</b> avec PSG sous seuil ({SEUIL}%)</div>')
        else:
            body_rows.append(bar('NFP', agg['nfp']))
            body_rows.append(bar('ENS', agg['ens']))
            body_rows.append(bar('LR',  agg['lr']))
            body_rows.append(bar('RN',  agg['rn']))
            footer = (f'<div style="font-size:10px;color:#888;margin-top:4px">'
                      f'Centre+LR = {agg["ens"]+agg["lr"]:.1f}%</div>')

        panels.append(
            f'<div id="agg_{scen}" class="agg-panel" style="display:{display}">'
            f'<div style="font-weight:600;font-size:13px;margin-bottom:6px">{title}</div>'
            + ''.join(body_rows) + footer + '</div>'
        )

    return (
        '<div id="aggregate-panel" style="'
        'position:fixed;top:260px;right:14px;z-index:9998;'
        'background:white;padding:12px 16px;border-radius:8px;'
        'box-shadow:0 2px 12px rgba(0,0,0,.2);font-family:Arial,sans-serif;'
        'min-width:280px;border:1px solid #ddd">'
        '<div style="font-size:10px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">'
        'Agrégats circo 9502 — moyenne pondérée</div>'
        + ''.join(panels) + '</div>'
    )


def compute_scenario_color(row, scen_code, params):
    """
    Retourne la couleur du parti dominant pour le scénario donné.
    scen_code : 't1' | 'sur_union' | 'sur_desunion' | 'eff_union' | 'eff_desunion'
    params : dict {'eff': (K_eff, sc_eff), 'sur': (K_sur, sc_sur)}
    """
    if scen_code == 't1':
        return dominant_color(float(row['nfp']), float(row['ens']),
                              float(row['lr']),  float(row['rn']))
    scalings = params['eff'] if scen_code.startswith('eff') else params['sur']
    nfp, ens, lr, rn = apply_scenario_dynamique(row, scalings)
    # ATTENTION : 'desunion'.endswith('union') == True en Python.
    # Toujours tester endswith('desunion') ou == '_desunion' explicitement.
    if scen_code.endswith('desunion'):
        lfi, psg = apply_desunion(nfp, row['lfi_ratio'], row['psg_ratio'])
        return dominant_color(max(lfi, psg), ens, lr, rn)
    return dominant_color(nfp, ens, lr, rn)


def _party_bar(label, pct, alert=False):
    """Petite barre de score colorée."""
    color = {'NFP':'#c0392b','LFI':'#8e1010','PSG':'#e74c3c',
             'ENS':'#e67e22','LR':'#2980b9','RN':'#1a5276'}.get(label, '#888')
    width = min(100, pct * 2)
    mark = ' <span style="color:#c00">⚠</span>' if alert else ''
    return (f'<div style="margin:2px 0">'
            f'<span style="display:inline-block;width:45px;font-size:11px">{label}</span>'
            f'<span style="display:inline-block;width:{width:.0f}px;height:8px;'
            f'background:{color};vertical-align:middle"></span>'
            f' <b>{pct:.1f}%</b>{mark}</div>')


def make_bdv_tooltip_for_scenario(row, scen_code, params):
    """
    Tooltip pour un BdV, filtré au scénario actif uniquement (UX épurée).
    scen_code : 't1' | 'sur_union' | 'sur_desunion' | 'eff_union' | 'eff_desunion'
    """
    nom = str(row['nom_commune'])
    bdv = str(row['num_bdv'])
    ins = int(row['ins'])
    part = float(row['part'])

    header = (f"<b>{nom} — BdV {bdv}</b><br>"
              f"<span style='color:#666;font-size:11px'>Inscrits {ins:,} | Part. {part:.1f}%</span>"
              f"<hr style='margin:4px 0'>")

    if scen_code == 't1':
        title = "T1 2024 (réel)"
        bars = (_party_bar('NFP', row['nfp']) + _party_bar('ENS', row['ens'])
              + _party_bar('LR',  row['lr'])  + _party_bar('RN',  row['rn']))
    else:
        scalings = params['eff'] if scen_code.startswith('eff') else params['sur']
        nfp, ens, lr, rn = apply_scenario_dynamique(row, scalings)
        scen_label = {
            'sur_union':    'Dynamique Philippe + Union NFP',
            'sur_desunion': 'Dynamique Philippe + Désunion',
            'eff_union':    'Effondrement centre + Union NFP',
            'eff_desunion': 'Effondrement centre + Désunion',
        }[scen_code]
        title = scen_label
        # ATTENTION : 'desunion'.endswith('union') == True. Tester endswith('desunion').
        if scen_code.endswith('desunion'):
            lfi, psg = apply_desunion(nfp, row['lfi_ratio'], row['psg_ratio'])
            bars = (_party_bar('LFI', lfi, alert=(lfi < SEUIL))
                  + _party_bar('PSG', psg, alert=(psg < SEUIL))
                  + _party_bar('ENS', ens) + _party_bar('LR', lr)
                  + _party_bar('RN',  rn))
        else:
            bars = (_party_bar('NFP', nfp) + _party_bar('ENS', ens)
                  + _party_bar('LR',  lr)  + _party_bar('RN',  rn))

    # Section Historique (toujours affichée, indépendante du scénario)
    def _val(key, default=None):
        v = row.get(key, default)
        try:
            v = float(v)
            return v if not (v != v) else default  # NaN check
        except (TypeError, ValueError):
            return default

    def _fmt(v):
        return f"{v:.1f}%" if v is not None else "—"

    # Trajectoire RN/extrême droite
    rn_traj = [
        ('Leg 17', _val('l17t1_far')),
        ('Prés 17', _val('p17_lepen')),
        ('Leg 22', _val('l22t1_far')),
        ('Prés 22', _val('pr_lepen')),
        ('Prés 22 T2', _val('p22t2_lepen')),
        ('Euro 24', _val('eu_rn_t')),
        ('Leg 24', float(row['rn'])),
    ]
    rn_html = ''.join(
        f"<span style='display:inline-block;margin-right:6px;font-size:10px'>"
        f"<span style='color:#666'>{lbl}</span> "
        f"<b style='color:#1a5276'>{_fmt(v)}</b></span>"
        for lbl, v in rn_traj if v is not None
    )

    # Trajectoire NFP/gauche
    nfp_traj = [
        ('Leg 17', _val('l17t1_left')),
        ('Prés 17', _val('p17_left')),
        ('Leg 22', _val('l22t1_left')),
        ('Prés 22', _val('pr_left')),
        ('Euro 24', _val('eu_left_t')),
        ('Leg 24', float(row['nfp'])),
    ]
    nfp_html = ''.join(
        f"<span style='display:inline-block;margin-right:6px;font-size:10px'>"
        f"<span style='color:#666'>{lbl}</span> "
        f"<b style='color:#c0392b'>{_fmt(v)}</b></span>"
        for lbl, v in nfp_traj if v is not None
    )

    # Trajectoire Centre (ENS + LR ou équivalents Macron/Fillon en présidentielle)
    ens_traj = [
        ('Leg 17', _val('l17t1_ctr')),
        ('Prés 17 Macron', _val('p17_macron')),
        ('Prés 17 Fillon', _val('p17_fillon')),
        ('Leg 22', _val('l22t1_ctr')),
        ('Prés 22 Macron', _val('pr_macron')),
        ('Euro 24', _val('eu_ctr_t')),
        ('Leg 24', float(row['ens'])),
    ]
    ens_html = ''.join(
        f"<span style='display:inline-block;margin-right:6px;font-size:10px'>"
        f"<span style='color:#666'>{lbl}</span> "
        f"<b style='color:#e67e22'>{_fmt(v)}</b></span>"
        for lbl, v in ens_traj if v is not None
    )

    historique = (
        "<hr style='margin:5px 0;border:0;border-top:1px dashed #ddd'>"
        "<div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:3px'>"
        "Historique BdV</div>"
        f"<div style='margin:2px 0'><b style='color:#1a5276;font-size:10px'>RN / Le Pen</b><br>{rn_html}</div>"
        f"<div style='margin:2px 0'><b style='color:#c0392b;font-size:10px'>Gauche / NFP</b><br>{nfp_html}</div>"
        f"<div style='margin:2px 0'><b style='color:#e67e22;font-size:10px'>Centre / Macron</b><br>{ens_html}</div>"
    )

    return (header + f"<b style='font-size:11px'>{title}</b>" + bars + historique
            + f"<div style='font-size:9px;color:#999;margin-top:3px'>Seuil T2 : {SEUIL}%</div>")


# ─── Carte principale ──────────────────────────────────────────────────────────
def build_map(bdv_table, centroids, contours_communes_gj, contours_bv_gj):
    m = folium.Map(location=[49.06, 2.20], zoom_start=12,
                   tiles='CartoDB positron')

    # Contours communes en arrière-plan (pas dans le layer control)
    fg_comm = folium.FeatureGroup(name='_communes', show=True, control=False)
    folium.GeoJson(
        contours_communes_gj,
        style_function=lambda x: {
            'fillColor': '#ffffff', 'color': '#222',
            'weight': 2, 'fillOpacity': 0,
        },
        tooltip=folium.GeoJsonTooltip(fields=['nom'], aliases=['Commune']),
    ).add_to(fg_comm)
    fg_comm.add_to(m)

    # Index BdV par id_bv (clé composite code_commune_num_bdv)
    bdv_table = bdv_table.copy()
    bdv_table['_id_bv'] = (bdv_table['code_commune'].astype(str) + '_'
                           + bdv_table['num_bdv'].astype(int).astype(str))
    bdv_by_id = {row['_id_bv']: row for _, row in bdv_table.iterrows()}

    # Positions (fallback CircleMarker pour BdV sans contour)
    commune_groups = (bdv_table
                      .assign(cc=bdv_table['code_commune'].astype(str),
                              nb=bdv_table['num_bdv'].astype(int).astype(str))
                      .groupby('cc')['nb'].apply(list).to_dict())
    positions = {}
    for com, bdvs in commune_groups.items():
        positions.update(jitter_positions(com, bdvs, centroids))

    # Calibrer les paramètres scénarios depuis la dynamique observée (modèle v3)
    scalings_eff = compute_scenario_params(bdv_table, 'effondrement')
    scalings_sur = compute_scenario_params(bdv_table, 'sursaut')
    params = {'eff': scalings_eff, 'sur': scalings_sur}
    print(f"    Paramètres scénarios (v4 — scaling uniforme par bloc) :")
    print(f"      Effondrement : centre+LR ×{scalings_eff['centre_lr']:.3f} | "
          f"NFP ×{scalings_eff['nfp']:.3f} | RN ×{scalings_eff['rn']:.3f}")
    print(f"      Sursaut      : centre+LR ×{scalings_sur['centre_lr']:.3f} | "
          f"NFP ×{scalings_sur['nfp']:.3f} | RN ×{scalings_sur['rn']:.3f}")

    # 5 couches : référence + 4 scénarios prospectifs
    layers = {
        'T1 2024 (réel)':                       (folium.FeatureGroup(name='T1 2024 (réel)',                       show=True),  't1'),
        'Dynamique Philippe + Union NFP':       (folium.FeatureGroup(name='Dynamique Philippe + Union NFP',       show=False), 'sur_union'),
        'Dynamique Philippe + Désunion gauche': (folium.FeatureGroup(name='Dynamique Philippe + Désunion gauche', show=False), 'sur_desunion'),
        'Effondrement centre + Union NFP':      (folium.FeatureGroup(name='Effondrement centre + Union NFP',      show=False), 'eff_union'),
        'Effondrement centre + Désunion gauche': (folium.FeatureGroup(name='Effondrement centre + Désunion gauche', show=False), 'eff_desunion'),
    }

    # Identifier les BdV avec contour
    ids_with_contour = set()
    for feat in contours_bv_gj['features']:
        ids_with_contour.add(feat['properties']['id_bv'])

    n_poly = 0
    n_circle = 0

    def _psg_under_seuil(row, scen_code):
        """Pour scénarios désunion : retourne True si PS+G est sous le seuil 19.14%."""
        if not scen_code.endswith('desunion'):
            return False
        scalings = params['eff'] if scen_code.startswith('eff') else params['sur']
        nfp_proj, _, _, _ = apply_scenario_dynamique(row, scalings)
        _, psg = apply_desunion(nfp_proj, row['lfi_ratio'], row['psg_ratio'])
        return psg < SEUIL

    # Pour chaque scénario : ajouter les polygones (1 par BdV avec contour)
    for label, (layer, scen) in layers.items():
        for feat in contours_bv_gj['features']:
            id_bv = feat['properties']['id_bv']
            if id_bv not in bdv_by_id:
                continue
            row = bdv_by_id[id_bv]
            color = compute_scenario_color(row, scen, params)

            # Bordure uniforme blanche sur tous les polygones (effet "tuile")
            # Info "PSG sous seuil" est dans le tooltip + panneau agrégats
            folium.GeoJson(
                feat,
                style_function=lambda x, c=color: {
                    'fillColor': c, 'color': '#ffffff',
                    'weight': 1.2, 'fillOpacity': 0.82,
                },
                tooltip=folium.Tooltip(make_bdv_tooltip_for_scenario(row, scen, params), sticky=True),
            ).add_to(layer)
            if scen == 't1':
                n_poly += 1

        # Fallback CircleMarker pour les BdV sans contour
        for _, row in bdv_table.iterrows():
            id_bv = row['_id_bv']
            if id_bv in ids_with_contour:
                continue
            pos_key = f"{row['code_commune']}_{int(row['num_bdv'])}"
            if pos_key not in positions:
                continue
            lat, lon = positions[pos_key]
            radius = max(5, min(14, math.sqrt(float(row['ins'])) / 9))
            color = compute_scenario_color(row, scen, params)
            folium.CircleMarker(
                [lat, lon], radius=radius,
                color='#ffffff', weight=1.2,
                fill=True, fill_color=color, fill_opacity=0.88,
                tooltip=folium.Tooltip(make_bdv_tooltip_for_scenario(row, scen, params), sticky=True),
            ).add_to(layer)
            if scen == 't1':
                n_circle += 1

    print(f"    {n_poly} polygones BdV + {n_circle} cercles (BdV sans contour)")

    for layer, _ in layers.values():
        layer.add_to(m)

    # Panneau d'agrégats circo (5 vues, une par scénario, switch via JS)
    aggregates = compute_circo_aggregates(bdv_table, params)
    m.get_root().html.add_child(folium.Element(render_aggregate_panel(aggregates, len(bdv_table))))

    # Panneau historique électoral circo (toujours visible)
    history = compute_circo_history(bdv_table)
    m.get_root().html.add_child(folium.Element(render_history_panel(history)))

    # Légende + titre
    legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:9999;
            background:white;padding:12px 14px;border-radius:8px;
            border:1px solid #ccc;font-family:Arial,sans-serif;font-size:12px;
            box-shadow:2px 2px 6px rgba(0,0,0,.2)">
  <b>Bloc dominant</b><br>
  <span style="background:#c0392b;width:12px;height:12px;
               display:inline-block;border-radius:50%;margin-right:4px"></span>Gauche (NFP)<br>
  <span style="background:#f39c12;width:12px;height:12px;
               display:inline-block;border-radius:50%;margin-right:4px"></span>Centre (ENS)<br>
  <span style="background:#1a5276;width:12px;height:12px;
               display:inline-block;border-radius:50%;margin-right:4px"></span>Extr. droite (RN)<br>
  <span style="background:#2980b9;width:12px;height:12px;
               display:inline-block;border-radius:50%;margin-right:4px"></span>Droite (LR)<br>
  <hr style="margin:4px 0">
  <b>Scénarios 2027</b><br>
  <span style="font-size:10px;color:#555">
  • <b>Dynamique Philippe</b> : sursaut centre-droit (+12 pts)<br>
  • <b>Effondrement centre</b> : chute centre+LR (-12 pts)<br>
  • <b>+ Désunion</b> : LFI seul vs PS+G<br>
  Multiplier ×K appliqué aux Δ22→24 par BdV
  </span>
  <hr style="margin:4px 0">
  <span style="font-size:10px;color:#888">Taille = inscrits<br>
  PS+G sous seuil 19.14% (désunion) : voir panneau agrégats</span>
</div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    title_html = """
<div style="position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9999;
     background:white;padding:8px 18px;border-radius:8px;
     box-shadow:0 2px 8px rgba(0,0,0,.25);font-family:Arial,sans-serif;text-align:center">
<b style="font-size:14px">2e circ. Val-d'Oise — Bureaux de vote</b><br>
<span style="font-size:11px;color:#555">Ayda Hadizadeh (NFP) | Scénarios 2027</span>
</div>"""
    m.get_root().html.add_child(folium.Element(title_html))

    folium.LayerControl(collapsed=False, position='topright').add_to(m)

    # JS : (1) exclusion mutuelle, (2) bascule click-anywhere, (3) sync panneau agrégats
    map_var = m.get_name()
    layer_vars = [layer.get_name() for layer, _ in layers.values()]
    scen_codes = ['t1', 'sur_union', 'sur_desunion', 'eff_union', 'eff_desunion']

    exclusive_js = f"""
<script>
window.addEventListener('load', function() {{
    var scenarioLayers = [{', '.join(layer_vars)}];
    var scenCodes = {json.dumps(scen_codes)};
    var map = {map_var};

    function switchScenario(idx) {{
        // Active la couche idx, désactive les autres
        scenarioLayers.forEach(function(layer, i) {{
            if (i === idx) {{
                if (!map.hasLayer(layer)) map.addLayer(layer);
            }} else {{
                if (map.hasLayer(layer)) map.removeLayer(layer);
            }}
        }});
        // Sync panneau agrégats
        document.querySelectorAll('.agg-panel').forEach(function(p) {{ p.style.display = 'none'; }});
        var active = document.getElementById('agg_' + scenCodes[idx]);
        if (active) active.style.display = 'block';
        // Sync radio buttons custom
        document.querySelectorAll('.scen-radio').forEach(function(r, i) {{
            r.classList.toggle('active', i === idx);
        }});
        // Sync les checkboxes natives du LayerControl
        var inputs = document.querySelectorAll('.leaflet-control-layers-overlays input');
        inputs.forEach(function(inp, i) {{ inp.checked = (i === idx); }});
    }}

    // Synchronisation depuis le LayerControl natif (si user clique dedans)
    map.on('overlayadd', function(e) {{
        var idx = scenarioLayers.indexOf(e.layer);
        if (idx >= 0) switchScenario(idx);
    }});

    // Initial : T1 actif
    switchScenario(0);

    // Exposer pour les boutons custom
    window._switchScenario = switchScenario;
}});
</script>
"""
    m.get_root().html.add_child(folium.Element(exclusive_js))

    # Panneau de sélection rapide (radio buttons custom)
    scen_labels = ['T1 2024 (réel)',
                   'Dynamique Philippe + Union', 'Dynamique Philippe + Désunion',
                   'Effondrement centre + Union', 'Effondrement centre + Désunion']
    radio_html = (
        '<div id="scen-selector" style="'
        'position:fixed;top:14px;right:14px;z-index:9999;'
        'background:white;padding:8px;border-radius:8px;'
        'box-shadow:0 2px 12px rgba(0,0,0,.2);font-family:Arial,sans-serif;'
        'min-width:280px;border:1px solid #ddd">'
        '<div style="font-size:10px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;padding:0 4px">'
        'Scénario actif</div>'
        + ''.join(
            f'<div class="scen-radio" onclick="window._switchScenario({i})" '
            f'data-idx="{i}" style="'
            f'padding:6px 10px;margin:2px 0;border-radius:4px;cursor:pointer;'
            f'font-size:12px;transition:background .15s;display:flex;align-items:center;gap:8px">'
            f'<span class="radio-dot" style="display:inline-block;width:12px;height:12px;'
            f'border-radius:50%;border:2px solid #888;flex-shrink:0"></span>'
            f'<span>{label}</span></div>'
            for i, label in enumerate(scen_labels)
        )
        + '</div>'
        '<style>'
        '.scen-radio:hover { background: #f5f5f5; }'
        '.scen-radio.active { background: #1a5276; color: white; }'
        '.scen-radio.active .radio-dot { background: white; border-color: white; box-shadow: inset 0 0 0 2px #1a5276; }'
        # Masquer le LayerControl natif (on le garde fonctionnel mais hors écran)
        '.leaflet-control-layers { display: none !important; }'
        '</style>'
    )
    m.get_root().html.add_child(folium.Element(radio_html))

    return m


# ─── Note d'analyse ───────────────────────────────────────────────────────────
def generate_note(bdv_table):
    """Génère une note d'analyse markdown."""
    n = len(bdv_table)
    ins_total = bdv_table['ins'].sum()
    part_moy  = bdv_table['part'].mean()

    # T1 2024 agrégé
    exp_total = bdv_table['exp'].sum()
    nfp_voix  = (bdv_table['nfp'] * bdv_table['exp'] / 100).sum()
    rn_voix   = (bdv_table['rn']  * bdv_table['exp'] / 100).sum()
    ens_voix  = (bdv_table['ens'] * bdv_table['exp'] / 100).sum()
    nfp_pct   = 100 * nfp_voix / exp_total
    rn_pct    = 100 * rn_voix  / exp_total
    ens_pct   = 100 * ens_voix / exp_total

    # BdV à risque (RN dominant en T1)
    rn_dom   = bdv_table[bdv_table['rn'] > bdv_table['nfp']]
    # BdV RN dominant en A2
    bdv_table['rn_a2'] = bdv_table.apply(lambda r: apply_scenario_a(r, 8)[3], axis=1)
    bdv_table['nfp_a2'] = bdv_table.apply(lambda r: apply_scenario_a(r, 8)[0], axis=1)
    rn_dom_a2 = bdv_table[bdv_table['rn_a2'] > bdv_table['nfp_a2']]

    # BdV PSG sous seuil en scénario C
    bdv_table['psg'] = bdv_table['nfp'] * bdv_table['psg_ratio']
    psg_sous_seuil = bdv_table[bdv_table['psg'] < SEUIL]

    # Top 5 BdV les plus favorables RN
    top_rn = (bdv_table.nlargest(5, 'rn')[['nom_commune','num_bdv','rn','nfp','ens','ins']]
              .to_string(index=False))
    # Top 5 BdV les plus favorables NFP
    top_nfp = (bdv_table.nlargest(5, 'nfp')[['nom_commune','num_bdv','nfp','rn','ens','ins']]
               .to_string(index=False))

    # Résultats T2 2024 par commune (mean)
    t2_cols = ['l24t2_left','l24t2_far']
    t2_data = bdv_table[bdv_table['l24t2_left'] > 0].groupby('nom_commune')[t2_cols].mean().round(1)

    note = f"""# Note d'analyse — 2ème Circonscription du Val-d'Oise
### Circo d'Ayda Hadizadeh (NFP/UG) | Analyse BdV — {n} bureaux de vote

---

## 1. Résultats de référence — Législatives 2024 T1

| Indicateur | Valeur |
|---|---|
| Bureaux de vote | {n} |
| Inscrits (circ 2) | {ins_total:,} |
| Participation moyenne | {part_moy:.1f}% |
| **NFP (gauche)** | **{nfp_pct:.1f}%** |
| **ENS (centre)** | **{ens_pct:.1f}%** |
| **RN (extrême droite)** | **{rn_pct:.1f}%** |

En 2024 T1, le NFP est **premier dans {(bdv_table['nfp']>bdv_table['rn']).sum()} BdV / {n}** ;
le RN est premier dans **{(bdv_table['rn']>bdv_table['nfp']).sum()} BdV**.

---

## 2. Cartographie du risque RN par scénario

### 2.1 Scénario A1 — RN +4 pts
- BdV où le RN passerait premier : **{(bdv_table['rn_a2'] - 4 > bdv_table['nfp_a2'] + 4).sum()}**
  *(hypothèse conservative — uniquement les BdV à moins de 4 pts d'écart)*

### 2.2 Scénario A2 — RN +8 pts
- BdV où le RN serait premier en T1 : **{len(rn_dom_a2)} / {n}**
- Communes concernées : {', '.join(rn_dom_a2['nom_commune'].unique()[:8])}

### 2.3 Scénario C — Désunion gauche (LFI seul / PS+G seul)
- BdV où **PS+G passerait sous le seuil de {SEUIL}%** : **{len(psg_sous_seuil)} / {n}**
- Communes à risque : {', '.join(psg_sous_seuil['nom_commune'].unique()[:8]) if len(psg_sous_seuil) else 'aucune (PS+G tient partout)'}
- NFP interne : LFI ≈ {bdv_table['lfi_ratio'].mean()*100:.0f}% · PS+G ≈ {bdv_table['psg_ratio'].mean()*100:.0f}%

---

## 3. Bureaux de vote stratégiques

### Top 5 BdV les plus favorables au RN (T1 2024)
```
{top_rn}
```

### Top 5 BdV les plus favorables au NFP (T1 2024)
```
{top_nfp}
```

---

## 4. Résultats T2 2024 (NFP vs RN) par commune

{t2_data.to_string()}

NFP élu au T2 grâce à un report massif : **{bdv_table[bdv_table['l24t2_left']>50]['nom_commune'].nunique()} communes**
sur {bdv_table['nom_commune'].nunique()} ont voté >50% NFP au T2.

---

## 5. Synthèse — Risques pour 2027

| Scénario | Qualification NFP | Qualification RN | T2 projeté |
|---|---|---|---|
| **Base (2024 reconduit)** | ✓ ~39% | ✓ ~28% | NFP gagne 55-58% |
| **A1 (+4pts RN)** | ✓ ~36% | ✓ ~32% | NFP gagne ~52-54% |
| **A2 (+8pts RN)** | ✓ ~34% | ✓ ~36% — RN 1er | NFP gagne si report ≥ 52% |
| **C désunion** | LFI ~17%, PSG ~22% | ✓ ~28% | PSG qualifié → gagne T2 |

**Verdict :** La circ 2 reste favorable au NFP dans tous les scénarios sauf
une désunion gauche **avec** une poussée RN simultanée (+6pts). Le risque principal
est la démobilisation des quartiers populaires de Cergy (35 BdV, fort potentiel électoral).

---

*Analyse générée automatiquement — données MI/data.gouv.fr — mai 2026*
"""
    return note


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Chargement des données BdV circ 2...")
    dfs = load_bdv()
    communes_c2 = set(dfs['leg24t1']['code_commune'].astype(str).str.strip())
    print(f"  {len(communes_c2)} communes, {len(dfs['leg24t1'])} BdV")

    print("Parsing euro 2024 BdV (LFI/PS split)...")
    eu_detail = parse_eu24_bdv_detail(communes_c2)
    print(f"  {len(eu_detail)} BdV avec détail euro")

    print("Construction du tableau principal...")
    bdv_table = build_bdv_table(dfs, eu_detail)
    out_table = os.path.join(DATA, 'bdv_9502_scenarios.csv')
    bdv_table.to_csv(out_table, index=False)
    print(f"  ✓ {len(bdv_table)} BdV → {out_table}")

    print("Récupération des centroïdes communes...")
    centroids = get_commune_centroids(sorted(communes_c2))
    print(f"  {len(centroids)} centroïdes récupérés")

    print("Récupération des contours communes...")
    contours_communes_gj = get_commune_contours(sorted(communes_c2))
    print(f"  {len(contours_communes_gj['features'])} contours communes")

    print("Chargement des contours BdV (REU)...")
    bv_path = os.path.join(DATA, 'bv_contours_9502.geojson')
    if not os.path.exists(bv_path):
        print(f"  ✗ {bv_path} absent — lancer build_bv_contours_9502.py")
        contours_bv_gj = {'type': 'FeatureCollection', 'features': []}
    else:
        with open(bv_path) as f:
            contours_bv_gj = json.load(f)
        print(f"  {len(contours_bv_gj['features'])} contours BdV")

    print("Construction de la carte...")
    m = build_map(bdv_table, centroids, contours_communes_gj, contours_bv_gj)
    map_path = "/Users/remybajolet/Desktop/datagouv/carte_bdv_9502.html"
    m.save(map_path)
    print(f"  ✓ Carte → {map_path}")

    # Note d'analyse : désactivée tant que generate_note() n'est pas refactorisée
    # vers les nouveaux scénarios (Philippe/Effondrement × Union/Désunion).
    # Le rôle revient à l'agent report-writer (voir contracts.md).

    print("\n✓ Terminé.")


if __name__ == '__main__':
    main()
