import os
#!/usr/bin/env python3
"""
Modèle prédictif : bascule à gauche sous scénario "gauche unie + effondrement centre/droite"
Sources : Législatives 2017/2022/2024, Présidentielle 2022, Européennes 2024, Municipales 2026
"""

import json, warnings
import pandas as pd
import numpy as np
import folium
from folium.plugins import MarkerCluster
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

warnings.filterwarnings('ignore')
DATA = os.path.join(_PROJ, "data")

# ─── Bloc definitions ─────────────────────────────────────────────────────────

LEG_BLOCS = {
    'LEFT':      {'LFI','FI','SOC','DVG','PCF','COM','ECO','VEC','RDG','UG','LEXG','EXG','GS'},
    'CENTRE':    {'ENS','HOR','DVC','UDI'},
    'RIGHT':     {'LR','DVD'},
    'FAR_RIGHT': {'RN','REC','EXD','UXD','DSV'},
}

EURO_BLOCS = {
    'LEFT':      {'LFI','LEXG','LECO','LDVG','LUG','LCOM','LVEC'},
    'CENTRE':    {'LENS'},
    'RIGHT':     {'LLR'},
    'FAR_RIGHT': {'LRN','LREC','LEXD'},
}

PRES_2022_BLOCS = {
    'LEFT':      {'ARTHAUD','HIDALGO','JADOT','MÉLENCHON','POUTOU','ROUSSEL','TAUBIRA'},
    'CENTRE':    {'MACRON'},
    'RIGHT':     {'PÉCRESSE'},
    'FAR_RIGHT': {'LE PEN','ZEMMOUR','DUPONT-AIGNAN'},
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_key(dept, circo):
    d = str(dept).strip()
    c = str(int(float(str(circo).strip()))).zfill(2) if str(dept).strip().isdigit() else str(circo).strip()[-2:]
    return d.zfill(2) + c

def circo_key_from_code(dept_str, circo_code_str):
    if str(dept_str).isdigit():
        try:
            circo_num = int(float(circo_code_str)) - int(float(dept_str)) * 100
            return make_key(dept_str, circo_num)
        except Exception:
            return None
    else:
        return str(circo_code_str)  # e.g. '2A01'

def safe_float(v):
    if pd.isna(v): return 0.0
    try: return float(str(v).replace(',', '.').replace('\xa0', '').replace(' ', ''))
    except Exception: return 0.0


# ─── Wide-format parser (Legislatives & Presidential 2022) ───────────────────

def parse_wide_xlsx(path, data_start_row, dept_col, circo_col, exprim_col,
                    base_cols, block_size, nuance_offset, voix_offset,
                    bloc_map, key_fn=None):
    """Generic parser for Ministry-of-Interior wide XLSX format."""
    df = pd.read_excel(path, header=None)
    max_cands = (df.shape[1] - base_cols) // block_size
    records = []
    for _, row in df.iloc[data_start_row:].iterrows():
        dept = row.iloc[dept_col]
        circo = row.iloc[circo_col]
        if pd.isna(dept) or pd.isna(circo): continue
        exprim = safe_float(row.iloc[exprim_col])
        if exprim == 0: continue

        scores = {b: 0.0 for b in bloc_map}
        for k in range(max_cands):
            nuance = str(row.iloc[base_cols + k * block_size + nuance_offset]).strip().upper()
            voix   = safe_float(row.iloc[base_cols + k * block_size + voix_offset])
            for bloc, nuances in bloc_map.items():
                if nuance in nuances:
                    scores[bloc] += voix
                    break

        key = key_fn(dept, circo) if key_fn else make_key(dept, circo)
        rec = {'key': key, 'exprim': exprim}
        for bloc, v in scores.items():
            rec[f'{bloc.lower()}_votes'] = v
            rec[f'{bloc.lower()}_pct']   = round(100 * v / exprim, 2)
        records.append(rec)
    return pd.DataFrame(records).set_index('key')


def parse_wide_xlsx_pres(path):
    """Presidential 2022 T1 – candidates identified by surname."""
    df = pd.read_excel(path, header=None)
    BASE, BLOCK, NOM_OFF, VOIX_OFF = 19, 6, 2, 4
    max_cands = (df.shape[1] - BASE) // BLOCK
    records = []
    for _, row in df.iloc[1:].iterrows():
        dept, circo = row.iloc[0], row.iloc[2]
        if pd.isna(dept) or pd.isna(circo): continue
        exprim = safe_float(row.iloc[16])
        if exprim == 0: continue

        scores = {b: 0.0 for b in PRES_2022_BLOCS}
        for k in range(max_cands):
            nom   = str(row.iloc[BASE + k * BLOCK + NOM_OFF]).strip().upper()
            voix  = safe_float(row.iloc[BASE + k * BLOCK + VOIX_OFF])
            for bloc, noms in PRES_2022_BLOCS.items():
                if any(n in nom for n in noms):
                    scores[bloc] += voix
                    break

        key = make_key(dept, circo)
        rec = {'key': key, 'exprim_pres22': exprim}
        for bloc, v in scores.items():
            rec[f'{bloc.lower()}_pres22'] = round(100 * v / exprim, 2)
        records.append(rec)
    return pd.DataFrame(records).set_index('key')


# ─── CSV wide-format parser (Leg 2024, Euro 2024) ───────────────────────────

def parse_wide_csv(path, bloc_map, prefix, sep=';'):
    df = pd.read_csv(path, sep=sep, low_memory=False)
    nuance_cols = [c for c in df.columns if 'Nuance' in c]
    voix_map = {}
    for nc in nuance_cols:
        # Voix col: same suffix number
        num = ''.join(filter(str.isdigit, nc.split()[-1])) if nc.split()[-1].isdigit() else ''.join(filter(str.isdigit, nc))
        candidates = [f'Voix {num}', f'Voix{num}']
        for vc in candidates:
            if vc in df.columns:
                voix_map[nc] = vc
                break

    records = []
    for _, row in df.iterrows():
        dept_raw  = str(row.get('Code département', row.get('Code du département', ''))).strip()
        circo_raw = str(row.get('Code circonscription législative', row.get('Code de la circonscription', ''))).strip()
        exprim    = safe_float(row.get('Exprimés', row.get('Exprimés', 0)))
        if exprim == 0: continue

        key = circo_key_from_code(dept_raw, circo_raw)
        if key is None: continue

        scores = {b: 0.0 for b in bloc_map}
        for nc, vc in voix_map.items():
            nuance = str(row.get(nc, '')).strip().upper()
            voix   = safe_float(row.get(vc, 0))
            for bloc, nuances in bloc_map.items():
                if nuance in nuances:
                    scores[bloc] += voix
                    break

        rec = {'key': key, f'exprim_{prefix}': exprim}
        for bloc, v in scores.items():
            rec[f'{bloc.lower()}_{prefix}'] = round(100 * v / exprim, 2) if exprim > 0 else 0.0
        records.append(rec)
    return pd.DataFrame(records).set_index('key')


# ─── T2 2024 winner per circonscription ─────────────────────────────────────

def get_t2_winners():
    df = pd.read_csv(f"{DATA}/leg2024_t2_cirlg.csv", sep=';', low_memory=False)
    T2_LEFT      = {'LFI','FI','SOC','DVG','ECO','VEC','UG','RDG','LEXG','EXG'}
    T2_CENTRE    = {'ENS','HOR','DVC','UDI'}
    T2_RIGHT     = {'LR','DVD'}
    T2_FAR_RIGHT = {'RN','REC','EXD','UXD','DSV'}

    def get_bloc(nuance):
        n = str(nuance).strip().upper()
        if n in T2_LEFT:      return 'LEFT'
        if n in T2_CENTRE:    return 'CENTRE'
        if n in T2_RIGHT:     return 'RIGHT'
        if n in T2_FAR_RIGHT: return 'FAR_RIGHT'
        return 'OTHER'

    records = []
    # Get nuance + voix for each candidate (up to 3 at T2)
    nuance_cols = [c for c in df.columns if c.startswith('Nuance candidat')]
    voix_map = {}
    for nc in nuance_cols:
        num = nc.replace('Nuance candidat ', '').strip()
        vc = f'Voix {num}'
        if vc in df.columns:
            voix_map[nc] = vc

    for _, row in df.iterrows():
        dept_raw  = str(row.get('Code département', '')).strip()
        circo_raw = str(row.get('Code circonscription législative', '')).strip()
        key = circo_key_from_code(dept_raw, circo_raw)
        if key is None: continue

        # Find winner: look for 'élu' in Elu N columns
        winner_bloc = 'UNKNOWN'
        for nc in list(voix_map.keys()):
            num = nc.replace('Nuance candidat ', '').strip()
            elu_col = f'Elu {num}'
            elu_val = str(row.get(elu_col, '')).strip().lower()
            if 'lu' in elu_val:  # catches 'élu', 'elu'
                winner_bloc = get_bloc(row.get(nc, ''))
                break

        records.append({'key': key, 'winner_t2_24': winner_bloc})

    return pd.DataFrame(records).set_index('key')


# ─── Load 2017 (FN only, already computed) ───────────────────────────────────

def load_2017_rn():
    xl = pd.ExcelFile(f"{DATA}/leg2017_t1.xlsx")
    df = xl.parse('Circo. leg. T1', header=None)
    BASE, BLOCK, NUANCE_OFF, VOIX_OFF = 18, 9, 4, 5
    max_cands = (df.shape[1] - BASE) // BLOCK

    LEG17_BLOCS = {
        'LEFT':      {'FG','FI','COM','SOC','DVG','ECO','VEC','RDG','LEXG','EXG','LREM_PROCHE','PRG','DVG'},
        'CENTRE':    {'MDM','REM','UDI','LREM','UDI'},
        'RIGHT':     {'LR','DVD','DVC'},
        'FAR_RIGHT': {'FN','DLF','DSV'},
    }
    # Simpler approach for 2017: map nuances directly
    LEG17_MAP = {
        # left
        'FI':'LEFT','COM':'LEFT','SOC':'LEFT','DVG':'LEFT','ECO':'LEFT','VEC':'LEFT',
        'RDG':'LEFT','LEXG':'LEFT','EXG':'LEFT','PRG':'LEFT','FG':'LEFT',
        # centre (LREM + MDM + etc.)
        'REM':'CENTRE','MDM':'CENTRE','UDI':'CENTRE','LREM':'CENTRE',
        'ENS':'CENTRE','HOR':'CENTRE','DVC':'CENTRE',
        # right
        'LR':'RIGHT','DVD':'RIGHT',
        # far right
        'FN':'FAR_RIGHT','DLF':'FAR_RIGHT','DSV':'FAR_RIGHT',
    }

    records = []
    for _, row in df.iloc[3:].iterrows():
        dept, circo = row.iloc[0], row.iloc[2]
        if pd.isna(dept) or pd.isna(circo): continue
        exprim = safe_float(row.iloc[15])
        if exprim == 0: continue

        scores = {'LEFT':0.,'CENTRE':0.,'RIGHT':0.,'FAR_RIGHT':0.,'OTHER':0.}
        for k in range(max_cands):
            nuance = str(row.iloc[BASE + k * BLOCK + NUANCE_OFF]).strip().upper()
            voix   = safe_float(row.iloc[BASE + k * BLOCK + VOIX_OFF])
            bloc   = LEG17_MAP.get(nuance, 'OTHER')
            scores[bloc] += voix

        key = make_key(dept, circo)
        records.append({
            'key': key,
            'left_leg17':      round(100*scores['LEFT']/exprim, 2),
            'centre_leg17':    round(100*scores['CENTRE']/exprim, 2),
            'right_leg17':     round(100*scores['RIGHT']/exprim, 2),
            'far_right_leg17': round(100*scores['FAR_RIGHT']/exprim, 2),
        })
    return pd.DataFrame(records).set_index('key')


# ─── Main ─────────────────────────────────────────────────────────────────────

def build_prediction():
    print("Loading electoral data...")

    # Leg 2024 T1 – tous blocs
    df_l24 = parse_wide_csv(f"{DATA}/leg2024_t1_cirlg.csv", LEG_BLOCS, 'leg24')
    print(f"  Leg 2024 T1 : {len(df_l24)} circos")

    # Leg 2022 T1
    df_l22 = parse_wide_xlsx(
        f"{DATA}/leg2022_t1_cirlg.xlsx",
        data_start_row=1, dept_col=0, circo_col=2, exprim_col=16,
        base_cols=19, block_size=9, nuance_offset=4, voix_offset=5,
        bloc_map=LEG_BLOCS
    )
    print(f"  Leg 2022 T1 : {len(df_l22)} circos")

    # Leg 2017 T1
    df_l17 = load_2017_rn()
    print(f"  Leg 2017 T1 : {len(df_l17)} circos")

    # Pres 2022 T1
    df_p22 = parse_wide_xlsx_pres(f"{DATA}/pres2022_t1_cirlg.xlsx")
    print(f"  Pres 2022 T1 : {len(df_p22)} circos")

    # Euro 2024
    df_e24 = parse_wide_csv(f"{DATA}/euro2024_cirlg.csv", EURO_BLOCS, 'euro24')
    print(f"  Euro 2024    : {len(df_e24)} circos")

    # T2 2024 winners
    df_t2 = get_t2_winners()
    print(f"  Leg 2024 T2  : {len(df_t2)} circos au T2")

    # Merge all
    master = df_l24[['left_leg24','centre_leg24','right_leg24','far_right_leg24']].copy()
    master = master.join(df_l22[['left_pct','centre_pct','right_pct','far_right_pct']]
                         .rename(columns=lambda c: c.replace('_pct', '_leg22')), how='left')
    master = master.join(df_l17[['left_leg17','centre_leg17','right_leg17','far_right_leg17']], how='left')
    master = master.join(df_p22[['left_pres22','centre_pres22','right_pres22','far_right_pres22']], how='left')
    master = master.join(df_e24[['left_euro24','centre_euro24','right_euro24','far_right_euro24']], how='left')
    master = master.join(df_t2[['winner_t2_24']], how='left')
    master['winner_t2_24'] = master['winner_t2_24'].fillna('T1_WIN')

    # ── Scenario parameters ──────────────────────────────────────────────────
    # "Gauche unie + effondrement centre/droite"
    # Centre (ENS/HOR) : garde 10%, perd 90% → 60% gauche, 20% RN, 20% abstention
    # Droite (LR/DVD)  : garde 10%, perd 90% → 30% gauche, 40% RN, 30% abstention
    CENTRE_TO_LEFT  = 0.60
    CENTRE_TO_RN    = 0.15
    RIGHT_TO_LEFT   = 0.28
    RIGHT_TO_RN     = 0.38

    master['proj_left'] = (
        master['left_leg24']
        + master['centre_leg24'] * CENTRE_TO_LEFT
        + master['right_leg24']  * RIGHT_TO_LEFT
    ).round(1)

    master['proj_rn'] = (
        master['far_right_leg24']
        + master['centre_leg24'] * CENTRE_TO_RN
        + master['right_leg24']  * RIGHT_TO_RN
    ).round(1)

    master['margin_left'] = (master['proj_left'] - master['proj_rn']).round(1)

    def classify(row):
        m = row['margin_left']
        w = row['winner_t2_24']
        if m > 15:   return 'bastion_gauche'
        if m > 7:    return 'bascule_probable'
        if m > 1:    return 'bascule_possible'
        if m > -5:   return 'rn_resistant'
        return 'bastion_rn'

    master['scenario'] = master.apply(classify, axis=1)

    # Stats
    print("\n" + "─"*55)
    print("SCÉNARIO : GAUCHE UNIE + EFFONDREMENT CENTRE/DROITE")
    print("─"*55)
    vc = master['scenario'].value_counts()
    labels = {
        'bastion_gauche':   '🔵 Bastion gauche (marge >15 pts)',
        'bascule_probable': '💙 Bascule probable (7-15 pts)',
        'bascule_possible': '🩵 Bascule possible (1-7 pts)',
        'rn_resistant':     '🟠 RN résistant (-5 à +1 pts)',
        'bastion_rn':       '🔴 Bastion RN (marge <-5 pts)',
    }
    for k, label in labels.items():
        n = vc.get(k, 0)
        print(f"  {label} : {n} circos")
    print(f"\n  Proj. gauche moy. : {master['proj_left'].mean():.1f}%")
    print(f"  Proj. RN moy.     : {master['proj_rn'].mean():.1f}%")
    n_left_wins = (master['margin_left'] > 0).sum()
    print(f"  Circos où gauche gagne : {n_left_wins} / {len(master)}")

    # Focus sur les bascules potentielles hors territoires déjà gauche
    bascules = master[
        (master['scenario'].isin(['bascule_probable','bascule_possible'])) &
        (master['winner_t2_24'].isin(['FAR_RIGHT','CENTRE','RIGHT','T1_WIN','UNKNOWN']))
    ]
    print(f"\n  Territoires à basculer (non-gauche → gauche) : {len(bascules)} circos")

    return master


# ─── Map builder ─────────────────────────────────────────────────────────────

SCENARIO_COLORS = {
    'bastion_gauche':   '#1a4ea8',
    'bascule_probable': '#5b94d8',
    'bascule_possible': '#a8c8f0',
    'rn_resistant':     '#f4a55c',
    'bastion_rn':       '#c0392b',
}

WINNER_COLORS = {
    'LEFT':      '#1a4ea8',
    'CENTRE':    '#e8b400',
    'RIGHT':     '#2d7a4f',
    'FAR_RIGHT': '#c0392b',
    'OTHER':     '#888888',
    'T1_WIN':    '#cccccc',
    'UNKNOWN':   '#cccccc',
}

def pct_to_red(pct):
    if pct < 10: return '#fee5d9'
    if pct < 20: return '#fcae91'
    if pct < 30: return '#fb6b50'
    if pct < 40: return '#ef3b2c'
    if pct < 50: return '#cb181d'
    return '#67000d'


def build_map(master):
    with open(f"{DATA}/circonscriptions.geojson") as f:
        geo = json.load(f)
    dept_centroids = pd.read_csv(f"{DATA}/dept_centroids.csv")
    dept_centroids['codeDepartement'] = dept_centroids['codeDepartement'].astype(str).str.zfill(2)

    # Enrich GeoJSON
    for feature in geo['features']:
        props = feature['properties']
        key   = props.get('codeCirconscription', '')
        dept  = props.get('codeDepartement', '').zfill(2)

        if key in master.index:
            row = master.loc[key]
            props.update({
                'proj_left':       float(row['proj_left']),
                'proj_rn':         float(row['proj_rn']),
                'margin_left':     float(row['margin_left']),
                'scenario':        str(row['scenario']),
                'winner_t2_24':    str(row['winner_t2_24']),
                'left_leg24':      float(row['left_leg24']),
                'centre_leg24':    float(row['centre_leg24']),
                'right_leg24':     float(row['right_leg24']),
                'far_right_leg24': float(row['far_right_leg24']),
                'left_leg17':      float(row.get('left_leg17', 0) or 0),
                'far_right_leg17': float(row.get('far_right_leg17', 0) or 0),
                'left_pres22':     float(row.get('left_pres22', 0) or 0),
                'far_right_pres22':float(row.get('far_right_pres22', 0) or 0),
                'left_euro24':     float(row.get('left_euro24', 0) or 0),
                'far_right_euro24':float(row.get('far_right_euro24', 0) or 0),
            })
        else:
            props.update({k: 0 for k in [
                'proj_left','proj_rn','margin_left',
                'left_leg24','centre_leg24','right_leg24','far_right_leg24',
                'left_leg17','far_right_leg17','left_pres22','far_right_pres22',
                'left_euro24','far_right_euro24'
            ]})
            props['scenario'] = 'unknown'
            props['winner_t2_24'] = 'UNKNOWN'

    # ── MAP ──
    m = folium.Map(location=[46.5, 2.5], zoom_start=6,
                   tiles='CartoDB positron', prefer_canvas=True)

    # ── LAYER 1: Scénario prédictif ──────────────────────────────────────────
    fg_pred = folium.FeatureGroup(name='🔮 Prédiction : bascule à gauche', show=True)
    for feature in geo['features']:
        p = feature['properties']
        sc = p.get('scenario', 'unknown')
        color = SCENARIO_COLORS.get(sc, '#cccccc')

        margin = p.get('margin_left', 0)
        winner = p.get('winner_t2_24', '?')
        winner_labels = {'LEFT':'Gauche','CENTRE':'Centre','RIGHT':'Droite',
                         'FAR_RIGHT':'Extr. droite','T1_WIN':'Élu T1','UNKNOWN':'?','OTHER':'Autre'}
        scenario_labels = {
            'bastion_gauche':'Bastion gauche ✅',
            'bascule_probable':'Bascule probable 💙',
            'bascule_possible':'Bascule possible 🩵',
            'rn_resistant':'RN résistant 🟠',
            'bastion_rn':'Bastion RN 🔴',
        }

        tooltip_html = f"""
        <div style="font-family:Arial;font-size:12px;min-width:230px">
          <b>{p.get('nomDepartement','')} – {p.get('nomCirconscription','')}</b><br>
          <i>Élu en 2024 : {winner_labels.get(winner,'?')}</i><br>
          <hr style="margin:3px 0">
          <b style="color:{'#1a4ea8' if margin>0 else '#c0392b'}">
            {scenario_labels.get(sc, sc)}
          </b><br>
          Proj. Gauche : <b>{p.get('proj_left',0):.1f}%</b> &nbsp;|&nbsp;
          Proj. RN : <b>{p.get('proj_rn',0):.1f}%</b><br>
          Marge : <b>{margin:+.1f} pts</b><br>
          <hr style="margin:3px 0">
          <small>
          T1 L2024 – G:{p.get('left_leg24',0):.1f}% C:{p.get('centre_leg24',0):.1f}%
          D:{p.get('right_leg24',0):.1f}% RN:{p.get('far_right_leg24',0):.1f}%<br>
          Pres22 G:{p.get('left_pres22',0):.1f}% RN:{p.get('far_right_pres22',0):.1f}%<br>
          Euro24 G:{p.get('left_euro24',0):.1f}% RN:{p.get('far_right_euro24',0):.1f}%
          </small>
        </div>
        """

        folium.GeoJson(
            feature,
            style_function=lambda f, c=color, sc=sc: {
                'fillColor': c,
                'color': '#444' if sc in ('bascule_probable','bascule_possible') else '#666',
                'weight': 1.0 if sc in ('bascule_probable','bascule_possible') else 0.5,
                'fillOpacity': 0.85
            },
            tooltip=folium.Tooltip(tooltip_html, sticky=True)
        ).add_to(fg_pred)
    fg_pred.add_to(m)

    # ── LAYER 2: Résultats 2024 T2 (situation actuelle) ──────────────────────
    fg_t2 = folium.FeatureGroup(name='📍 Situation actuelle (T2 2024)', show=False)
    for feature in geo['features']:
        p = feature['properties']
        winner = p.get('winner_t2_24', 'UNKNOWN')
        color  = WINNER_COLORS.get(winner, '#cccccc')
        folium.GeoJson(
            feature,
            style_function=lambda f, c=color: {
                'fillColor': c, 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.75
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement','nomCirconscription','winner_t2_24','far_right_leg24','left_leg24'],
                aliases=['Département','Circonscription','Élu T2 2024','RN T1 2024 (%)','Gauche T1 2024 (%)']
            )
        ).add_to(fg_t2)
    fg_t2.add_to(m)

    # ── LAYER 3: Score gauche T1 2024 ────────────────────────────────────────
    fg_left24 = folium.FeatureGroup(name='🗳️ Score Gauche T1 2024', show=False)
    for feature in geo['features']:
        pct = feature['properties'].get('left_leg24', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, p=pct: {
                'fillColor': _blue_scale(p), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.82
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement','nomCirconscription','left_leg24','centre_leg24','right_leg24','far_right_leg24'],
                aliases=['Département','Circonscription','Gauche (%)','Centre (%)','Droite (%)','RN (%)']
            )
        ).add_to(fg_left24)
    fg_left24.add_to(m)

    # ── LAYER 4: Score RN T1 2024 ────────────────────────────────────────────
    fg_rn24 = folium.FeatureGroup(name='🗳️ Score RN T1 2024', show=False)
    for feature in geo['features']:
        pct = feature['properties'].get('far_right_leg24', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, p=pct: {
                'fillColor': pct_to_red(p), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.82
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement','nomCirconscription','far_right_leg24','left_leg24','centre_leg24'],
                aliases=['Département','Circonscription','RN T1 2024 (%)','Gauche T1 2024 (%)','Centre T1 2024 (%)']
            )
        ).add_to(fg_rn24)
    fg_rn24.add_to(m)

    # ── LAYER 5: Score gauche Euro 2024 ──────────────────────────────────────
    fg_euro = folium.FeatureGroup(name='🇪🇺 Score Gauche Européennes 2024', show=False)
    for feature in geo['features']:
        pct = feature['properties'].get('left_euro24', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, p=pct: {
                'fillColor': _blue_scale(p), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.82
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement','nomCirconscription','left_euro24','far_right_euro24'],
                aliases=['Département','Circonscription','Gauche Euro24 (%)','RN Euro24 (%)']
            )
        ).add_to(fg_euro)
    fg_euro.add_to(m)

    # ── LEGEND ───────────────────────────────────────────────────────────────
    legend_html = """
    <div style="
        position:fixed; bottom:30px; left:30px; z-index:1000;
        background:white; padding:14px 18px; border-radius:10px;
        box-shadow:0 2px 12px rgba(0,0,0,.25);
        font-family:Arial,sans-serif; font-size:12px; min-width:220px
    ">
    <b style="font-size:13px">🔮 Prédiction – Bascule à gauche</b><br>
    <i style="color:#888;font-size:10px">Gauche unie + effondrement centre/droite</i><br><br>

    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#1a4ea8;width:18px;height:12px;display:inline-block"></span>
      <b>Bastion gauche</b> (&gt;15 pts)
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#5b94d8;width:18px;height:12px;display:inline-block"></span>
      Bascule <b>probable</b> (7-15 pts)
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#a8c8f0;width:18px;height:12px;display:inline-block;border:1px solid #ccc"></span>
      Bascule <b>possible</b> (1-7 pts)
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#f4a55c;width:18px;height:12px;display:inline-block"></span>
      RN <b>résistant</b> (-5 à 0 pts)
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#c0392b;width:18px;height:12px;display:inline-block"></span>
      <b>Bastion RN</b> (&lt;-5 pts)
    </div>
    <br>
    <b style="font-size:12px">Situation actuelle (T2 2024)</b><br>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#1a4ea8;width:14px;height:14px;display:inline-block;border-radius:2px"></span> Gauche
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#e8b400;width:14px;height:14px;display:inline-block;border-radius:2px"></span> Centre (Macron)
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#2d7a4f;width:14px;height:14px;display:inline-block;border-radius:2px"></span> Droite (LR)
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:4px 0">
      <span style="background:#c0392b;width:14px;height:14px;display:inline-block;border-radius:2px"></span> Extrême droite (RN)
    </div>
    <br>
    <i style="color:#aaa;font-size:10px">
    Hypothèses scénario :<br>
    Centre→Gauche : 60% | Centre→RN : 15%<br>
    Droite→Gauche : 28% | Droite→RN : 38%<br>
    Sources : Min. Intérieur / data.gouv.fr<br>
    Leg. 2017/2022/2024 · Pres. 2022 · Euro 2024
    </i>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # ── TITLE ────────────────────────────────────────────────────────────────
    title_html = """
    <div style="
        position:fixed; top:12px; left:50%; transform:translateX(-50%);
        z-index:1000; background:white; padding:10px 24px; border-radius:10px;
        box-shadow:0 2px 12px rgba(0,0,0,.25); font-family:Arial,sans-serif; text-align:center
    ">
    <b style="font-size:16px">Carte prédictive – Bascule à gauche</b><br>
    <span style="font-size:11px;color:#555">
      Scénario : gauche unie · effondrement centre/droite · par circonscription
    </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    folium.LayerControl(collapsed=False, position='topright').add_to(m)

    out = os.path.join(_PROJ, "carte_predictive.html")
    m.save(out)
    print(f"\n✓ Carte prédictive : {out}")
    return out


def _blue_scale(pct):
    if pct < 10: return '#f7fbff'
    if pct < 20: return '#c6dbef'
    if pct < 30: return '#6baed6'
    if pct < 40: return '#2171b5'
    if pct < 50: return '#08519c'
    return '#08306b'


if __name__ == '__main__':
    master = build_prediction()
    build_map(master)
    master.to_csv(os.path.join(_PROJ, "data/master_electoral.csv"))
    print("✓ Données exportées : data/master_electoral.csv")
