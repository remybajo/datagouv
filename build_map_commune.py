#!/usr/bin/env python3
"""
build_map_commune.py
Carte électorale interactive — 2ème circ Val-d'Oise (9502)
Couches : résultats 2024, progression RN, scénarios A/B/C 2027
"""
import json, os, requests, warnings
import pandas as pd
import numpy as np
import folium
from folium import GeoJson, GeoJsonTooltip, GeoJsonPopup
from folium.plugins import GroupedLayerControl

warnings.filterwarnings('ignore')
DATA    = "/Users/remybajolet/Desktop/datagouv/data"
OUT     = "/Users/remybajolet/Desktop/datagouv/carte_commune_9502.html"
GEO_API = "https://geo.api.gouv.fr"

# ─── Chargement des projections ───────────────────────────────────────────────
df = pd.read_csv(os.path.join(DATA, 'projections_9502.csv'), index_col='code_commune')
df.index = df.index.astype(str)

# Recalcul scénario C révisé (PS+EELV+PCF vs LFI)
eu_left = 15.49 + 12.99 + 5.08 + 2.01
PS_BLOC  = (12.99 + 5.08 + 2.01) / eu_left   # 56.5%
LFI_SHR  = 15.49 / eu_left                    # 43.5%
SEUIL_EXP = 12.5 / (0.6688 * 0.9765 * 100)   # ~19.14% exprimés
SEUIL_VAL  = SEUIL_EXP * 100

df['sc_ps_bloc']    = (df['l24t1_left'] * PS_BLOC).round(2)
df['sc_lfi_only']   = (df['l24t1_left'] * LFI_SHR).round(2)
df['gap_ps_seuil']  = (SEUIL_VAL - df['sc_ps_bloc']).round(2)

communes = df.index.tolist()
print(f"Communes à cartographier : {len(communes)}")

# ─── Récupération des contours GeoJSON depuis geo.api.gouv.fr ─────────────────
print("Téléchargement des contours communaux...")
features = []
for code in communes:
    url = f"{GEO_API}/communes/{code}?format=geojson&geometry=contour&fields=nom,population,surface"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        gj = r.json()
        # Enrichir les properties avec nos données
        row = df.loc[code]
        gj['properties'].update({
            'code_commune':   code,
            'nom_commune':    row.get('nom_commune', code),
            'inscrits':       int(row.get('inscrits', 0)),
            # Résultats 2024
            'left_24':        round(float(row.get('l24t1_left', 0)), 1),
            'rn_24':          round(float(row.get('l24t1_far', 0)), 1),
            'ctr_24':         round(float(row.get('l24t1_ctr', 0)), 1),
            'rgt_24':         round(float(row.get('l24t1_rgt', 0)), 1),
            'part_24':        round(float(row.get('l24t1_participation', 0) or 0), 1),
            't2_left_24':     round(float(row.get('l24t2_left', 0) or 0), 1),
            # Leg 2022
            'left_22':        round(float(row.get('l22t1_left', 0) or 0), 1),
            'rn_22':          round(float(row.get('l22t1_far', 0) or 0), 1),
            # Progression RN
            'rn_delta':       round(float(row.get('rn_delta', 0) or 0), 1),
            # Euro 2024
            'eu_rn':          round(float(row.get('eu24_eu_rn', 0) or 0), 1),
            'eu_lfi':         round(float(row.get('eu24_eu_lfi', 0) or 0), 1),
            'eu_ps':          round(float(row.get('eu24_eu_ps', 0) or 0), 1),
            # Scénario A (A1/A2)
            'a1_win':         str(row.get('proj_a1_win', '?')),
            'a1_nfp':         round(float(row.get('proj_a1_nfp', 0)), 1),
            'a1_rn':          round(float(row.get('proj_a1_rn', 0)), 1),
            'a2_win':         str(row.get('proj_a2_win', '?')),
            'a2_nfp':         round(float(row.get('proj_a2_nfp', 0)), 1),
            'a2_rn':          round(float(row.get('proj_a2_rn', 0)), 1),
            # Scénario C révisé
            'c_ps_bloc':      round(float(row.get('sc_ps_bloc', 0)), 1),
            'c_lfi':          round(float(row.get('sc_lfi_only', 0)), 1),
            'c_gap_seuil':    round(float(row.get('gap_ps_seuil', 0)), 2),
            'c_ps_qualifie':  'OUI ✓' if float(row.get('sc_ps_bloc', 0)) >= SEUIL_VAL else 'NON ✗',
            # Type
            'type':           str(row.get('type_commune', '?')),
        })
        features.append(gj)
        print(f"  {code} — {row.get('nom_commune', '')} OK")
    except Exception as e:
        print(f"  {code} ERREUR : {e}")

commune_geojson = {'type': 'FeatureCollection', 'features': features}
print(f"\n{len(features)} communes récupérées\n")

# Aussi récupérer le contour de la circ 9502
with open(os.path.join(DATA, 'circonscriptions.geojson')) as f:
    circ_gj = json.load(f)
circ_9502 = next(f for f in circ_gj['features']
                 if f['properties'].get('codeCirconscription') == '9502')

# ─── Palettes de couleurs ──────────────────────────────────────────────────────
def color_left_rn(left, rn):
    """Couleur selon qui est en tête."""
    if   left > 45:                   return '#1a53ff'   # bleu foncé — bastion gauche
    elif left > 35:                   return '#4d79ff'   # bleu moyen
    elif left > 25 and left > rn:     return '#80a0ff'   # bleu clair
    elif rn > 45:                     return '#cc0000'   # rouge foncé — bastion RN
    elif rn > 35:                     return '#e63300'   # orange-rouge
    elif rn > left:                   return '#ff6633'   # orange — RN en tête
    else:                             return '#aaaaaa'   # gris — équilibré

def color_rn_delta(delta):
    """Couleur progression RN."""
    if pd.isna(delta) or delta == 0: return '#eeeeee'
    if delta >= 10:  return '#7f0000'
    if delta >= 8:   return '#cc0000'
    if delta >= 6:   return '#ff4444'
    if delta >= 4:   return '#ff8888'
    return '#ffbbbb'

def color_scenario_a(win, nfp, rn):
    """Couleur scénario A — qui gagne ?"""
    if win == 'NFP':
        margin = nfp - rn
        if margin > 15: return '#1a53ff'
        if margin > 8:  return '#4d79ff'
        return '#99aaff'
    else:
        margin = rn - nfp
        if margin > 15: return '#cc0000'
        if margin > 8:  return '#e63300'
        return '#ff9966'

def color_scenario_c(ps_qualifie, gap):
    """Couleur scénario C — PS+G qualifié ou non ?"""
    if ps_qualifie == 'OUI ✓': return '#1a53ff'
    if gap < 3:  return '#ffcc00'   # très proche
    if gap < 6:  return '#ff8800'
    return '#cc0000'

# ─── Construction de la carte ──────────────────────────────────────────────────
print("Construction de la carte...")

m = folium.Map(
    location=[49.06, 2.20],
    zoom_start=11,
    tiles='CartoDB positron',
    prefer_canvas=True,
)

# ── Contour de la circ en arrière-plan ────────────────────────────────────────
folium.GeoJson(
    circ_9502,
    style_function=lambda x: {
        'fillColor': 'transparent', 'color': '#333333',
        'weight': 3, 'dashArray': '6 3',
    },
    name='Contour 2ème circ',
    show=True,
).add_to(m)

# ── Couche 1 : Résultats Leg 2024 T1 ─────────────────────────────────────────
def tooltip_2024(props):
    return f"""
    <b>{props['nom_commune']}</b> — {props['inscrits']:,} inscrits<br>
    <b>Leg 2024 T1</b><br>
    NFP : <b>{props['left_24']}%</b> | RN : <b>{props['rn_24']}%</b> | ENS : {props['ctr_24']}% | LR : {props['rgt_24']}%<br>
    Participation : {props['part_24']}%<br>
    T2 : NFP {props['t2_left_24']}%<br>
    <i>2022 : NFP {props['left_22']}% | RN {props['rn_22']}%</i>
    """

layer1 = folium.FeatureGroup(name='📊 Leg 2024 T1 — résultats', show=True)
for feat in features:
    p = feat['properties']
    color = color_left_rn(p['left_24'], p['rn_24'])
    folium.GeoJson(
        feat,
        style_function=lambda x, c=color: {
            'fillColor': c, 'color': '#333', 'weight': 1,
            'fillOpacity': 0.75,
        },
        tooltip=folium.Tooltip(tooltip_2024(p), sticky=True),
        popup=folium.Popup(f"""
        <div style='font-family:sans-serif;min-width:220px'>
        <b style='font-size:14px'>{p['nom_commune']}</b><br>
        {p['inscrits']:,} inscrits — participation {p['part_24']}%<br><hr>
        <table>
        <tr><td>NFP (Hadizadeh)</td><td><b>{p['left_24']}%</b></td></tr>
        <tr><td>RN (Rémy)</td><td><b>{p['rn_24']}%</b></td></tr>
        <tr><td>ENS (Vuilletet)</td><td>{p['ctr_24']}%</td></tr>
        <tr><td>LR (Pain)</td><td>{p['rgt_24']}%</td></tr>
        </table><hr>
        <b>T2 :</b> NFP {p['t2_left_24']}% vs RN {round(100-p['t2_left_24'],1)}%<br>
        <i>Type : {p['type']}</i>
        </div>""", max_width=280),
    ).add_to(layer1)
layer1.add_to(m)

# ── Couche 2 : Progression RN 2022→2024 ──────────────────────────────────────
layer2 = folium.FeatureGroup(name='📈 Progression RN 2022→2024', show=False)
for feat in features:
    p = feat['properties']
    color = color_rn_delta(p['rn_delta'])
    folium.GeoJson(
        feat,
        style_function=lambda x, c=color: {
            'fillColor': c, 'color': '#555', 'weight': 1, 'fillOpacity': 0.80,
        },
        tooltip=folium.Tooltip(
            f"<b>{p['nom_commune']}</b><br>"
            f"RN 2022 : {p['rn_22']}% → 2024 : {p['rn_24']}%<br>"
            f"Δ = <b>+{p['rn_delta']} pts</b><br>"
            f"Euros 2024 RN : {p['eu_rn']}%",
            sticky=True,
        ),
    ).add_to(layer2)
layer2.add_to(m)

# ── Couche 3a : Scénario A1 (+4 pts RN) ──────────────────────────────────────
layer3a = folium.FeatureGroup(name='🔴 Scénario A1 — RN +4 pts (2027)', show=False)
for feat in features:
    p = feat['properties']
    color = color_scenario_a(p['a1_win'], p['a1_nfp'], p['a1_rn'])
    folium.GeoJson(
        feat,
        style_function=lambda x, c=color: {
            'fillColor': c, 'color': '#444', 'weight': 1, 'fillOpacity': 0.80,
        },
        tooltip=folium.Tooltip(
            f"<b>{p['nom_commune']}</b> — Scénario A1<br>"
            f"NFP proj. : {p['a1_nfp']}% | RN proj. : {p['a1_rn']}%<br>"
            f"T1 → <b>{p['a1_win']} en tête</b>",
            sticky=True,
        ),
    ).add_to(layer3a)
layer3a.add_to(m)

# ── Couche 3b : Scénario A2 (+8 pts RN) ──────────────────────────────────────
layer3b = folium.FeatureGroup(name='🔴 Scénario A2 — RN +8 pts (2027)', show=False)
for feat in features:
    p = feat['properties']
    color = color_scenario_a(p['a2_win'], p['a2_nfp'], p['a2_rn'])
    folium.GeoJson(
        feat,
        style_function=lambda x, c=color: {
            'fillColor': c, 'color': '#444', 'weight': 1, 'fillOpacity': 0.80,
        },
        tooltip=folium.Tooltip(
            f"<b>{p['nom_commune']}</b> — Scénario A2<br>"
            f"NFP proj. : {p['a2_nfp']}% | RN proj. : {p['a2_rn']}%<br>"
            f"T1 → <b>{p['a2_win']} en tête</b>",
            sticky=True,
        ),
    ).add_to(layer3b)
layer3b.add_to(m)

# ── Couche 4 : Scénario C — désunion gauche ───────────────────────────────────
layer4 = folium.FeatureGroup(name='🟡 Scénario C — désunion gauche (LFI vs PS+G)', show=False)
for feat in features:
    p = feat['properties']
    color = color_scenario_c(p['c_ps_qualifie'], p['c_gap_seuil'])
    label_ps  = f"PS+G {p['c_ps_bloc']}% → {p['c_ps_qualifie']}"
    label_lfi = f"LFI {p['c_lfi']}% → NON ✗ (manque {max(0, SEUIL_VAL - p['c_lfi']):.1f} pts)"
    folium.GeoJson(
        feat,
        style_function=lambda x, c=color: {
            'fillColor': c, 'color': '#555', 'weight': 1, 'fillOpacity': 0.80,
        },
        tooltip=folium.Tooltip(
            f"<b>{p['nom_commune']}</b> — Scénario C (désunion)<br>"
            f"{label_ps}<br>{label_lfi}<br>"
            f"<i>Bleu = PS qualifié | Jaune = PS presque | Rouge = PS exclu</i>",
            sticky=True,
        ),
    ).add_to(layer4)
layer4.add_to(m)

# ── Légende ───────────────────────────────────────────────────────────────────
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:9999;
     background:white;padding:15px;border-radius:8px;
     box-shadow:0 2px 8px rgba(0,0,0,0.3);font-family:sans-serif;font-size:12px;max-width:260px">
<b style="font-size:13px">2ème circ. Val-d'Oise</b><br>
<i style="color:#666">Analyse prédictive 2027</i><hr style="margin:6px 0">

<b>Couche 1 — Résultats 2024</b><br>
<span style="background:#1a53ff;padding:2px 8px;color:white">■</span> Bastion gauche (>45%)<br>
<span style="background:#4d79ff;padding:2px 8px;color:white">■</span> Penchant gauche (35-45%)<br>
<span style="background:#ff6633;padding:2px 8px;color:white">■</span> RN en tête<br>
<span style="background:#cc0000;padding:2px 8px;color:white">■</span> Bastion RN (>45%)<br><br>

<b>Couche 2 — Progression RN</b><br>
<span style="background:#ff8888;padding:2px 8px">■</span> +4–6 pts<br>
<span style="background:#e63300;padding:2px 8px;color:white">■</span> +8–10 pts<br>
<span style="background:#7f0000;padding:2px 8px;color:white">■</span> >+10 pts<br><br>

<b>Couches 3 — Scénario A</b><br>
<span style="background:#1a53ff;padding:2px 8px;color:white">■</span> NFP en tête (fort)<br>
<span style="background:#99aaff;padding:2px 8px">■</span> NFP en tête (fragile)<br>
<span style="background:#ff9966;padding:2px 8px">■</span> RN en tête (fragile)<br>
<span style="background:#cc0000;padding:2px 8px;color:white">■</span> RN en tête (fort)<br><br>

<b>Couche 4 — Scénario C</b><br>
<span style="background:#1a53ff;padding:2px 8px;color:white">■</span> PS+G qualifié au T2<br>
<span style="background:#ffcc00;padding:2px 8px">■</span> PS+G très proche<br>
<span style="background:#cc0000;padding:2px 8px;color:white">■</span> PS+G exclu du T2<br><br>
<i>Seuil T2 : 12,5% inscrits (≈ 19,1% exprimés)</i>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Titre ─────────────────────────────────────────────────────────────────────
title_html = """
<div style="position:fixed;top:15px;left:50%;transform:translateX(-50%);z-index:9999;
     background:white;padding:10px 20px;border-radius:6px;
     box-shadow:0 2px 8px rgba(0,0,0,0.25);font-family:sans-serif;text-align:center">
<b style="font-size:15px">2ème circonscription du Val-d'Oise</b><br>
<span style="font-size:12px;color:#555">Analyse prédictive législatives 2027 — Hadizadeh (NFP) sortante</span>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

# Contrôle des couches
folium.LayerControl(collapsed=False, position='topright').add_to(m)

# ─── Sauvegarde ───────────────────────────────────────────────────────────────
m.save(OUT)
print(f"\n✓ Carte sauvegardée : {OUT}")
print("  Ouvrir dans un navigateur pour naviguer entre les couches.")
