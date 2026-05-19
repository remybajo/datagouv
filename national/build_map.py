import os
#!/usr/bin/env python3
"""
Carte interactive : dynamiques électorales de l'extrême droite en France
- Législatives T1 : 2017 (FN), 2022 (RN), 2024 (RN+REC)
- Municipales 2026 : communes gagnées par le RN
"""

import json
import pandas as pd
import numpy as np
import folium
from folium.plugins import MarkerCluster
import warnings
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings('ignore')

DATA = os.path.join(_PROJ, "data")

# ─── Color scales ─────────────────────────────────────────────────────────────

def pct_to_color(pct):
    """Red gradient for absolute score."""
    if pct is None or pct == 0:
        return '#f7f7f7'
    steps = [(10, '#fee5d9'), (20, '#fcae91'), (30, '#fb6b50'),
             (40, '#ef3b2c'), (50, '#cb181d'), (100, '#67000d')]
    for threshold, color in steps:
        if pct < threshold:
            return color
    return '#67000d'


def delta_to_color(delta):
    """Diverging blue-red for progression."""
    if delta is None:
        return '#f7f7f7'
    if delta < -10: return '#2166ac'
    if delta < -5:  return '#4393c3'
    if delta < 0:   return '#92c5de'
    if delta < 5:   return '#f7f7f7'
    if delta < 10:  return '#f4a582'
    if delta < 15:  return '#d6604d'
    return '#b2182b'


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def make_circo_key(dept, circo):
    dept_str = str(dept).strip().zfill(2)
    circo_str = str(int(float(str(circo).strip()))).zfill(2)
    return dept_str + circo_str


# ─── 2017 : FN ───────────────────────────────────────────────────────────────

def load_2017():
    xl = pd.ExcelFile(f"{DATA}/leg2017_t1.xlsx")
    df = xl.parse('Circo. leg. T1', header=None)
    BASE, BLOCK, NUANCE_OFF, VOIX_OFF = 18, 9, 4, 5
    max_cands = (df.shape[1] - BASE) // BLOCK
    FAR_RIGHT = {'FN', 'FN '}

    records = []
    for _, row in df.iloc[3:].iterrows():
        dept, circo = row.iloc[0], row.iloc[2]
        if pd.isna(dept) or pd.isna(circo):
            continue
        exprim = row.iloc[15]
        if pd.isna(exprim) or float(exprim) == 0:
            continue

        fn_votes = sum(
            float(row.iloc[BASE + k * BLOCK + VOIX_OFF])
            for k in range(max_cands)
            if str(row.iloc[BASE + k * BLOCK + NUANCE_OFF]).strip() in FAR_RIGHT
            and not pd.isna(row.iloc[BASE + k * BLOCK + VOIX_OFF])
        )
        key = make_circo_key(dept, circo)
        records.append({'key': key, 'rn_pct_2017': round(100 * fn_votes / float(exprim), 2)})

    return pd.DataFrame(records).set_index('key')


# ─── 2022 : RN ───────────────────────────────────────────────────────────────

def load_2022():
    df = pd.read_excel(f"{DATA}/leg2022_t1_cirlg.xlsx", header=None)
    BASE, BLOCK, NUANCE_OFF, VOIX_OFF = 19, 9, 4, 5
    max_cands = (df.shape[1] - BASE) // BLOCK
    FAR_RIGHT = {'RN', 'FN'}

    records = []
    for _, row in df.iloc[1:].iterrows():
        dept, circo = row.iloc[0], row.iloc[2]
        if pd.isna(dept) or pd.isna(circo):
            continue
        exprim = row.iloc[16]
        if pd.isna(exprim) or float(exprim) == 0:
            continue

        rn_votes = sum(
            float(row.iloc[BASE + k * BLOCK + VOIX_OFF])
            for k in range(max_cands)
            if str(row.iloc[BASE + k * BLOCK + NUANCE_OFF]).strip() in FAR_RIGHT
            and not pd.isna(row.iloc[BASE + k * BLOCK + VOIX_OFF])
        )
        key = make_circo_key(dept, circo)
        records.append({'key': key, 'rn_pct_2022': round(100 * rn_votes / float(exprim), 2)})

    return pd.DataFrame(records).set_index('key')


# ─── 2024 : RN + REC + EXD ───────────────────────────────────────────────────

def load_2024():
    df = pd.read_csv(f"{DATA}/leg2024_t1_cirlg.csv", sep=';', low_memory=False)
    FAR_RIGHT = {'RN', 'REC', 'UXD', 'EXD', 'LUXD'}

    nuance_cols = [c for c in df.columns if c.startswith('Nuance candidat')]
    voix_map = {
        nc: f"Voix {nc.replace('Nuance candidat ', '').strip()}"
        for nc in nuance_cols
        if f"Voix {nc.replace('Nuance candidat ', '').strip()}" in df.columns
    }

    records = []
    for _, row in df.iterrows():
        dept = str(row['Code département']).strip()
        circo_code = str(row['Code circonscription législative']).strip()
        if pd.isna(row.get('Exprimés', None)):
            continue
        exprim_raw = str(row.get('Exprimés', '0')).replace('\xa0', '').replace(' ', '')
        try:
            exprim = float(exprim_raw)
        except Exception:
            continue
        if exprim == 0:
            continue

        if dept.isdigit():
            try:
                circo_num = int(float(circo_code)) - int(float(dept)) * 100
                key = make_circo_key(dept, circo_num)
            except Exception:
                continue
        else:
            key = circo_code  # e.g. '2A01', 'ZZ01'

        rn_votes = 0.0
        for nc, vc in voix_map.items():
            nuance = str(row.get(nc, '')).strip()
            if nuance in FAR_RIGHT:
                v = row.get(vc, 0)
                if not pd.isna(v):
                    try:
                        rn_votes += float(str(v).replace(',', '.').replace('\xa0', '').replace(' ', ''))
                    except Exception:
                        pass

        records.append({'key': key, 'rn_pct_2024': round(100 * rn_votes / exprim, 2)})

    return pd.DataFrame(records).set_index('key')


# ─── Muni 2026 ───────────────────────────────────────────────────────────────

def load_muni2026():
    df = pd.read_csv(f"{DATA}/muni2026_elus.csv", sep=';', low_memory=False)
    FAR_RIGHT = {'LRN', 'LEXD', 'LUXD'}

    # Winning nuance per commune = one with most elected
    grp = df.groupby(['CODDPT', 'CODCOM', 'CODE_NUANCE_DE_LISTE']).size().reset_index(name='n_elus')
    idx = grp.groupby(['CODDPT', 'CODCOM'])['n_elus'].idxmax()
    winners = grp.loc[idx].copy()
    winners['far_right'] = winners['CODE_NUANCE_DE_LISTE'].isin(FAR_RIGHT)

    fr_communes = winners[winners['far_right']].copy()
    fr_by_dept = fr_communes.groupby('CODDPT').size().reset_index(name='n_fr_communes')
    all_by_dept = winners.groupby('CODDPT').size().reset_index(name='n_total_communes')

    dept_stats = fr_by_dept.merge(all_by_dept, on='CODDPT', how='left')
    dept_stats['pct_fr'] = (100 * dept_stats['n_fr_communes'] / dept_stats['n_total_communes']).round(1)
    dept_stats['CODDPT'] = dept_stats['CODDPT'].astype(str).str.zfill(2)

    return dept_stats


# ─── Main ─────────────────────────────────────────────────────────────────────

def build_map():
    print("Loading data...")
    df17 = load_2017()
    print(f"  2017: {len(df17)} circos | FN moy. {df17['rn_pct_2017'].mean():.1f}%")
    df22 = load_2022()
    print(f"  2022: {len(df22)} circos | RN moy. {df22['rn_pct_2022'].mean():.1f}%")
    df24 = load_2024()
    print(f"  2024: {len(df24)} circos | RN moy. {df24['rn_pct_2024'].mean():.1f}%")
    muni_stats = load_muni2026()
    print(f"  Muni 2026: {muni_stats['n_fr_communes'].sum()} communes RN, {len(muni_stats)} depts touchés")

    dept_centroids = pd.read_csv(f"{DATA}/dept_centroids.csv")
    dept_centroids['codeDepartement'] = dept_centroids['codeDepartement'].astype(str).str.zfill(2)

    # Load GeoJSON and enrich
    with open(f"{DATA}/circonscriptions.geojson") as f:
        geo = json.load(f)

    for feature in geo['features']:
        props = feature['properties']
        key = props.get('codeCirconscription', '')
        dept_code = props.get('codeDepartement', '').zfill(2)

        p17 = float(df17.loc[key, 'rn_pct_2017']) if key in df17.index else 0.0
        p22 = float(df22.loc[key, 'rn_pct_2022']) if key in df22.index else 0.0
        p24 = float(df24.loc[key, 'rn_pct_2024']) if key in df24.index else 0.0

        props['rn_2017'] = p17
        props['rn_2022'] = p22
        props['rn_2024'] = p24
        props['delta_17_24'] = round(p24 - p17, 1)
        props['delta_22_24'] = round(p24 - p22, 1)

        muni_row = muni_stats[muni_stats['CODDPT'] == dept_code]
        props['muni_rn_communes'] = int(muni_row['n_fr_communes'].values[0]) if len(muni_row) else 0
        props['muni_pct_rn'] = float(muni_row['pct_fr'].values[0]) if len(muni_row) else 0.0

    print("Building map...")
    m = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles='CartoDB positron', prefer_canvas=True)

    # ── Tooltip builder ──
    def make_tooltip(fields, aliases):
        return folium.GeoJsonTooltip(fields=fields, aliases=aliases, localize=True,
                                     style="font-size:13px; font-family:Arial")

    def make_popup(feature_props):
        p = feature_props
        html = f"""
        <div style="font-family:Arial; min-width:220px">
          <b>{p.get('nomDepartement','')} – {p.get('nomCirconscription','')}</b><br>
          <hr style="margin:4px 0">
          <table style="font-size:12px; width:100%">
            <tr><td>FN T1 2017</td><td align="right"><b>{p.get('rn_2017',0):.1f}%</b></td></tr>
            <tr><td>RN T1 2022</td><td align="right"><b>{p.get('rn_2022',0):.1f}%</b></td></tr>
            <tr><td>RN T1 2024</td><td align="right"><b>{p.get('rn_2024',0):.1f}%</b></td></tr>
            <tr style="color:#b2182b"><td>↑ Progression 2017→2024</td>
              <td align="right"><b>+{p.get('delta_17_24',0):.1f} pts</b></td></tr>
            <tr style="color:#666"><td>↑ Progression 2022→2024</td>
              <td align="right"><b>{p.get('delta_22_24',0):+.1f} pts</b></td></tr>
          </table>
          <hr style="margin:4px 0">
          <i style="font-size:11px">Muni 2026 (dépt.) : {p.get('muni_rn_communes',0)} commune(s) RN</i>
        </div>
        """
        return folium.Popup(html, max_width=300)

    # ── Layer 1 : Score RN 2024 ──
    fg_2024 = folium.FeatureGroup(name='🗳️ Score RN – T1 Législatives 2024', show=True)
    for feature in geo['features']:
        props = feature['properties']
        pct = props.get('rn_2024', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, p=pct: {
                'fillColor': pct_to_color(p), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.82
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement', 'nomCirconscription', 'rn_2017', 'rn_2022', 'rn_2024', 'delta_17_24'],
                aliases=['Département', 'Circonscription', 'FN 2017 (%)', 'RN 2022 (%)', 'RN 2024 (%)', 'Évol. 2017→24 (pts)']
            ),
            popup=make_popup(props)
        ).add_to(fg_2024)
    fg_2024.add_to(m)

    # ── Layer 2 : Score RN 2022 ──
    fg_2022 = folium.FeatureGroup(name='🗳️ Score RN – T1 Législatives 2022', show=False)
    for feature in geo['features']:
        pct = feature['properties'].get('rn_2022', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, p=pct: {
                'fillColor': pct_to_color(p), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.82
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement', 'nomCirconscription', 'rn_2022'],
                aliases=['Département', 'Circonscription', 'RN 2022 (%)']
            )
        ).add_to(fg_2022)
    fg_2022.add_to(m)

    # ── Layer 3 : Score FN 2017 ──
    fg_2017 = folium.FeatureGroup(name='🗳️ Score FN – T1 Législatives 2017', show=False)
    for feature in geo['features']:
        pct = feature['properties'].get('rn_2017', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, p=pct: {
                'fillColor': pct_to_color(p), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.82
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement', 'nomCirconscription', 'rn_2017'],
                aliases=['Département', 'Circonscription', 'FN 2017 (%)']
            )
        ).add_to(fg_2017)
    fg_2017.add_to(m)

    # ── Layer 4 : Progression 2017→2024 ──
    fg_delta = folium.FeatureGroup(name='📈 Progression RN 2017→2024', show=False)
    for feature in geo['features']:
        delta = feature['properties'].get('delta_17_24', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, d=delta: {
                'fillColor': delta_to_color(d), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.85
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement', 'nomCirconscription', 'rn_2017', 'rn_2024', 'delta_17_24'],
                aliases=['Département', 'Circonscription', 'FN 2017 (%)', 'RN 2024 (%)', 'Progression (pts)']
            )
        ).add_to(fg_delta)
    fg_delta.add_to(m)

    # ── Layer 5 : Progression 2022→2024 ──
    fg_delta22 = folium.FeatureGroup(name='📈 Progression RN 2022→2024', show=False)
    for feature in geo['features']:
        delta = feature['properties'].get('delta_22_24', 0)
        folium.GeoJson(
            feature,
            style_function=lambda f, d=delta: {
                'fillColor': delta_to_color(d), 'color': '#666', 'weight': 0.5, 'fillOpacity': 0.85
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nomDepartement', 'nomCirconscription', 'rn_2022', 'rn_2024', 'delta_22_24'],
                aliases=['Département', 'Circonscription', 'RN 2022 (%)', 'RN 2024 (%)', 'Progression (pts)']
            )
        ).add_to(fg_delta22)
    fg_delta22.add_to(m)

    # ── Layer 6 : Muni 2026 – communes RN par département ──
    fg_muni = folium.FeatureGroup(name='🏛️ Municipales 2026 : communes RN', show=True)
    muni_with_coords = muni_stats.merge(dept_centroids, left_on='CODDPT', right_on='codeDepartement', how='left')
    muni_with_coords = muni_with_coords.dropna(subset=['centroid_lat', 'centroid_lon'])

    for _, row in muni_with_coords.iterrows():
        n = int(row['n_fr_communes'])
        pct = float(row['pct_fr'])
        dept = row.get('nomDepartement', row['CODDPT'])
        radius = min(5 + n * 2, 30)
        folium.CircleMarker(
            location=[row['centroid_lat'], row['centroid_lon']],
            radius=radius,
            color='#7b0d1e',
            fill=True,
            fill_color='#c41230',
            fill_opacity=0.75,
            weight=2,
            tooltip=folium.Tooltip(
                f"<b>{dept}</b><br>{n} commune(s) gagnée(s) par RN/ExtrD<br>{pct:.1f}% des communes du dept."
            )
        ).add_to(fg_muni)

    fg_muni.add_to(m)

    # ── Legend ──
    legend = """
    <div id="map-legend" style="
        position: fixed; bottom: 30px; left: 30px; z-index: 1000;
        background: white; padding: 14px 18px; border-radius: 10px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.25);
        font-family: Arial, sans-serif; font-size: 12px; min-width: 200px;
    ">
    <b style="font-size:13px">Score RN / Extrême droite</b><br>
    <span style="color:#888;font-size:10px">T1 législatives (par circonscription)</span><br><br>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#fee5d9;width:18px;height:12px;display:inline-block;border:1px solid #ccc"></span> &lt; 10%
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#fcae91;width:18px;height:12px;display:inline-block;border:1px solid #ccc"></span> 10 – 20%
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#fb6b50;width:18px;height:12px;display:inline-block;border:1px solid #ccc"></span> 20 – 30%
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#ef3b2c;width:18px;height:12px;display:inline-block"></span> 30 – 40%
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#cb181d;width:18px;height:12px;display:inline-block"></span> 40 – 50%
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#67000d;width:18px;height:12px;display:inline-block"></span> &gt; 50%
    </div>
    <br>
    <b style="font-size:13px">Progression</b><br>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#2166ac;width:18px;height:12px;display:inline-block"></span> Recul &gt; 10 pts
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#92c5de;width:18px;height:12px;display:inline-block"></span> Légère baisse
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#f7f7f7;width:18px;height:12px;display:inline-block;border:1px solid #ddd"></span> Stable
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#f4a582;width:18px;height:12px;display:inline-block"></span> +5 à +10 pts
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#d6604d;width:18px;height:12px;display:inline-block"></span> +10 à +15 pts
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#b2182b;width:18px;height:12px;display:inline-block"></span> &gt; +15 pts
    </div>
    <br>
    <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
      <span style="background:#c41230;width:14px;height:14px;display:inline-block;border-radius:50%;border:2px solid #7b0d1e"></span>
      Communes RN muni. 2026
    </div>
    <br>
    <span style="color:#999;font-size:10px">Sources : Ministère de l'Intérieur<br>data.gouv.fr · Législatives 2017, 2022, 2024<br>Municipales 2026</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))

    # ── Title ──
    title = """
    <div style="
        position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: white; padding: 10px 22px; border-radius: 10px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.25); font-family: Arial, sans-serif; text-align:center;
    ">
        <b style="font-size:16px; color:#1a1a1a">Dynamiques de l'extrême droite en France</b><br>
        <span style="font-size:11px; color:#666">
          Législatives T1 2017 · 2022 · 2024 &nbsp;|&nbsp; Municipales 2026 &nbsp;|&nbsp; Par circonscription
        </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title))

    folium.LayerControl(collapsed=False, position='topright').add_to(m)

    out = os.path.join(_PROJ, "carte_electorale.html")
    m.save(out)

    # Print summary stats
    merged_stats = df17.join(df22, how='outer').join(df24, how='outer')
    merged_stats['delta'] = merged_stats['rn_pct_2024'] - merged_stats['rn_pct_2017']
    print(f"\n{'─'*50}")
    print("RÉSUMÉ NATIONAL (T1 législatives, métropole)")
    print(f"{'─'*50}")
    print(f"  FN T1 2017  : {df17['rn_pct_2017'].mean():.1f}% moy. | max {df17['rn_pct_2017'].max():.1f}%")
    print(f"  RN T1 2022  : {df22['rn_pct_2022'].mean():.1f}% moy. | max {df22['rn_pct_2022'].max():.1f}%")
    print(f"  RN T1 2024  : {df24['rn_pct_2024'].mean():.1f}% moy. | max {df24['rn_pct_2024'].max():.1f}%")
    print(f"  Progression 2017→2024 : +{merged_stats['delta'].mean():.1f} pts moy.")
    n_above40 = (df24['rn_pct_2024'] >= 40).sum()
    print(f"  Circos avec RN ≥ 40% en 2024 : {n_above40}")
    print(f"\n  Muni 2026 : {muni_stats['n_fr_communes'].sum()} communes gagnées par RN/ExtrD")
    print(f"  Depts touchés : {len(muni_stats)}")
    print(f"\n✓ Carte : {out}")


if __name__ == '__main__':
    build_map()
