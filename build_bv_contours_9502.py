#!/usr/bin/env python3
"""
build_bv_contours_9502.py
Filtre le GeoJSON France entière des contours BdV (source data.gouv.fr / repo datagouv/bureau-vote)
pour ne garder que la 2e circonscription du Val-d'Oise (code 9502).

Source : https://www.data.gouv.fr/fr/datasets/contours-des-bureaux-de-vote/
Cache  : data/_cache_bv_contours_france.geojson (~676 Mo, ne jamais supprimer)
Output : data/bv_contours_9502.geojson (filtré, ~21 communes × N BdV)

Utilise jq en streaming → mémoire constante même sur 676 Mo.
"""
import os, subprocess, json, sys

DATA = "/Users/remybajolet/Desktop/datagouv/data"
CACHE = os.path.join(DATA, "_cache_bv_contours_france.geojson")
OUT   = os.path.join(DATA, "bv_contours_9502.geojson")
CIRC  = "9502"


def main():
    if not os.path.exists(CACHE):
        print(f"✗ Cache absent : {CACHE}")
        print("  Lancer d'abord le téléchargement avec :")
        print('  curl -L "https://object.files.data.gouv.fr/data-pipeline-open/reu/contours-france-entiere-latest-v2.geojson" \\')
        print(f'       -o {CACHE}')
        sys.exit(1)

    size_mb = os.path.getsize(CACHE) / (1024*1024)
    print(f"  Cache : {size_mb:.0f} Mo")
    print(f"  Filtrage circonscription {CIRC} via jq streaming…")

    # jq streaming : extrait toutes les features dont codeCirconscription == "9502"
    jq_filter = (
        '{type: "FeatureCollection", '
        'features: [.features[] | select(.properties.codeCirconscription == "' + CIRC + '")]}'
    )

    result = subprocess.run(
        ["jq", "-c", jq_filter, CACHE],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        print(f"✗ jq error: {result.stderr[:500]}")
        sys.exit(1)

    geo = json.loads(result.stdout)
    n_features = len(geo['features'])
    print(f"  → {n_features} BdV trouvés dans la circ {CIRC}")

    # Inspection rapide
    communes = sorted(set(f['properties']['codeCommune'] for f in geo['features']))
    print(f"  Communes couvertes : {len(communes)}")
    for c in communes:
        bdvs = [f for f in geo['features'] if f['properties']['codeCommune'] == c]
        nom = bdvs[0]['properties']['nomCommune'] if bdvs else ''
        print(f"    {c} {nom:30s} {len(bdvs):3d} BdV")

    with open(OUT, 'w') as f:
        json.dump(geo, f)
    print(f"\n✓ {OUT} ({os.path.getsize(OUT)//1024} Ko)")


if __name__ == '__main__':
    main()
