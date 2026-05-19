import os
#!/usr/bin/env python3
"""Carte simple : contours communes + points BdV — circ 9502."""
import json, requests
import pandas as pd
import folium
_PROJ = os.path.dirname(os.path.abspath(__file__))

DATA = os.path.join(_PROJ, "data")
CODES = ['95026','95042','95056','95127','95218','95313','95353',
         '95392','95394','95430','95445','95450','95456','95480',
         '95504','95566','95572','95594','95652','95660','95678']

# ── 1. Contours communes ──────────────────────────────────────────────────────
print("Chargement contours communes...")
geojson_features = []
centroids = {}
for code in CODES:
    r = requests.get(
        f"https://geo.api.gouv.fr/communes/{code}",
        params={"fields": "nom,code,contour,centre"},
        timeout=10
    )
    if r.status_code != 200:
        print(f"  ✗ {code}")
        continue
    d = r.json()
    nom = d.get("nom", code)
    contour = d.get("contour")
    centre = d.get("centre", {}).get("coordinates")
    if contour:
        geojson_features.append({
            "type": "Feature",
            "properties": {"nom": nom, "code": code},
            "geometry": contour
        })
    if centre:
        centroids[code] = (centre[1], centre[0])  # (lat, lon)
    print(f"  ✓ {nom}")

geojson_circ = {"type": "FeatureCollection", "features": geojson_features}
print(f"  → {len(geojson_features)} communes chargées")

# ── 2. Données BdV ───────────────────────────────────────────────────────────
print("Chargement données BdV...")
df = pd.read_csv(f"{DATA}/bdv_9502_scenarios.csv")
df['code_commune'] = df['code_commune'].astype(str).str.zfill(5)
print(f"  → {len(df)} BdV")

# Jitter : place N BdV en cercle autour du centroïde
def jitter(code, n):
    if code not in centroids or n == 0:
        return []
    lat0, lon0 = centroids[code]
    import math
    r = 0.012 * math.sqrt(n)
    return [
        (lat0 + r * math.sin(2 * math.pi * i / n),
         lon0 + r * math.cos(2 * math.pi * i / n))
        for i in range(n)
    ]

# Construire les positions par commune
positions = {}  # (code_commune, num_bdv) → (lat, lon)
for code, grp in df.groupby('code_commune'):
    bdvs = grp['num_bdv'].tolist()
    pts = jitter(code, len(bdvs))
    for i, nb in enumerate(bdvs):
        positions[(code, str(nb))] = pts[i] if i < len(pts) else centroids.get(code, (49.07, 2.22))

# ── 3. Carte Folium ──────────────────────────────────────────────────────────
print("Construction de la carte...")
m = folium.Map(
    location=[49.078, 2.221],
    zoom_start=11,
    tiles="CartoDB positron"
)

# Contours communes
folium.GeoJson(
    geojson_circ,
    name="Communes",
    style_function=lambda f: {
        "fillColor": "#f0f0f0",
        "color": "#333333",
        "weight": 1.5,
        "fillOpacity": 0.15,
    },
    tooltip=folium.GeoJsonTooltip(fields=["nom"], aliases=["Commune :"])
).add_to(m)

# Points BdV
def bdv_color(row):
    left = row.get("nfp", 0)
    far  = row.get("rn",  0)
    ctr  = row.get("ens", 0)
    dom  = max([("gauche", left), ("rn", far), ("centre", ctr)], key=lambda x: x[1])[0]
    if dom == "gauche":
        t = min(1.0, left / 65.0)
        r = int(180 + 75 * t); g = int(20 * (1 - t)); b = int(20 * (1 - t))
        return f"#{r:02x}{g:02x}{b:02x}"
    elif dom == "rn":
        t = min(1.0, far / 50.0)
        return f"#{int(20*(1-t)):02x}{int(50*(1-t)):02x}{int(120+135*t):02x}"
    else:
        t = min(1.0, ctr / 40.0)
        return f"#{int(240*t+200*(1-t)):02x}{int(200*t+180*(1-t)):02x}{int(20*(1-t)):02x}"

layer_bdv = folium.FeatureGroup(name="Bureaux de vote", show=True)
for _, row in df.iterrows():
    key = (str(row['code_commune']).zfill(5), str(row['num_bdv']))
    if key not in positions:
        continue
    lat, lon = positions[key]
    color = bdv_color(row)
    popup_html = f"""
    <b>{row['nom_commune']} — BdV {row['num_bdv']}</b><br>
    Inscrits : {int(row['ins'])}<br>
    <hr>
    NFP : <b>{row['nfp']:.1f}%</b><br>
    RN : <b>{row['rn']:.1f}%</b><br>
    ENS : <b>{row['ens']:.1f}%</b>
    """
    folium.CircleMarker(
        location=[lat, lon],
        radius=6,
        color="#333",
        weight=0.8,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        popup=folium.Popup(popup_html, max_width=220),
        tooltip=f"{row['nom_commune']} BdV {row['num_bdv']}: NFP {row['nfp']:.1f}% / RN {row['rn']:.1f}%"
    ).add_to(layer_bdv)

layer_bdv.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

out = os.path.join(_PROJ, "carte_simple_9502.html")
m.save(out)
print(f"✓ Carte → {out}")
