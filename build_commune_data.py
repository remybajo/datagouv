#!/usr/bin/env python3
"""
build_commune_data.py
Télécharge et consolide les résultats électoraux par commune
2ème circonscription du Val-d'Oise (dépt 95, code 9502)

Scrutins : Leg 2024 T1+T2 | Euro 2024 | Pres 2022 T1+T2 | Leg 2022 T1
"""
import io, os, warnings, requests
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

DATA = "/Users/remybajolet/Desktop/datagouv/data"
API  = "https://www.data.gouv.fr/api/1"
DEP  = "95"

# ─── Resource IDs data.gouv.fr ────────────────────────────────────────────────
RESOURCES = {
    'leg24t1': ('6682d0c255dcda5df20b1d90', 'bd32fcd3-53df-47ac-bf1d-8d8003fe23a1', 'csv'),
    'leg24t2': ('668b4092826ddcf70e9e62cd', '5a8088fd-8168-402a-9f40-c48daab88cd1', 'csv'),
    'eu24':    ('666b1337471f4fe2f19f2573', '6a782ef9-8ad6-4e66-832d-338b1041a42d', 'csv'),
    'pr22t1':  ('62581fdf02e05e365ea227a1', '6d9b33e5-667d-4c3e-9a0b-5fdf5baac708', 'xlsx'),
    'pr22t2':  ('626a86215fb310e32b48b137', '06d9816c-1b87-498d-985e-f312acee4f51', 'xlsx'),
    'leg22t1': ('62a8c3f92b3b572a67d307f4', '3cf49bf4-c171-4328-b002-fea995cb85d8', 'xlsx'),
}

# ─── Blocs électoraux ─────────────────────────────────────────────────────────
LEG_BLOCS = {
    'left': {'LFI','FI','SOC','DVG','PCF','COM','ECO','VEC','RDG','UG',
             'LEXG','EXG','GS','NUP','DXG','LUG','FG','LDVG','LSOC'},
    'ctr':  {'ENS','HOR','DVC','UDI','MDM','REM','LREM'},
    'rgt':  {'LR','DVD','DLF','DVR'},
    'far':  {'RN','REC','EXD','UXD','DSV'},
}

# Européennes 2024 — détail pour Scénario C (désunion gauche)
EURO_MAP = {
    'eu_lfi':  {'LFI'},
    'eu_ps':   {'LUG'},        # Glucksmann – Réveiller l'Europe
    'eu_vec':  {'LVEC'},       # Europe Écologie
    'eu_com':  {'LCOM'},       # Gauche unie (PCF)
    'eu_lxeg': {'LEXG','LDVG'},
    'eu_ctr':  {'LENS'},       # Besoin d'Europe
    'eu_lr':   {'LLR'},
    'eu_rn':   {'LRN'},
    'eu_rec':  {'LREC','LEXD'},
}

# Présidentielle 2022 — identification par nom
PRES22_T1_MAP = {
    'pr_left':   ['ARTHAUD','HIDALGO','JADOT','MÉLENCHON','MELENCHON','POUTOU','ROUSSEL','TAUBIRA'],
    'pr_macron': ['MACRON'],
    'pr_pec':    ['PÉCRESSE','PECRESSE'],
    'pr_lepen':  ['LE PEN'],
    'pr_zem':    ['ZEMMOUR'],
    'pr_other':  ['DUPONT-AIGNAN','DUPONT','LASSALLE','ASSELINEAU'],
}
PRES22_T2_MAP = {
    'pr2_macron': ['MACRON'],
    'pr2_lepen':  ['LE PEN'],
}

# ─── Utilitaires ──────────────────────────────────────────────────────────────
def sf(v):
    if pd.isna(v): return 0.0
    try: return float(str(v).replace(',','.').replace('\xa0','').replace(' ',''))
    except: return 0.0

def get_url(ds_id, rid):
    ds = requests.get(f"{API}/datasets/{ds_id}/", timeout=30).json()
    return next(r['url'] for r in ds['resources'] if r['id'] == rid)

def download(url, fmt, label):
    cache = os.path.join(DATA, f"_cache_{label}.{'csv' if fmt=='csv' else 'xlsx'}")
    if os.path.exists(cache):
        print(f"  [cache] {label}")
        return pd.read_csv(cache, sep=';', low_memory=False) if fmt == 'csv' \
               else pd.read_excel(cache, header=0)
    print(f"  ↓ {label} ({url[-55:]})... ", end='', flush=True)
    for attempt in range(3):
        try:
            with requests.get(url, timeout=300, stream=True) as r:
                r.raise_for_status()
                chunks = []
                for chunk in r.iter_content(chunk_size=65536):
                    chunks.append(chunk)
                content = b''.join(chunks)
            break
        except Exception as e:
            if attempt == 2: raise
            print(f"retry {attempt+1}... ", end='', flush=True)
    print(f"{len(content)//1024:,} KB")
    with open(cache, 'wb') as f: f.write(content)
    return pd.read_csv(io.StringIO(content.decode('utf-8', errors='replace')), sep=';', low_memory=False) \
           if fmt == 'csv' else pd.read_excel(io.BytesIO(content), header=0)


# ─── Parser 1 : Nouveau format CSV (Leg 2024, Euro 2024) ─────────────────────
def parse_modern_csv(df, bloc_map, dep=DEP, commune_whitelist=None):
    """
    Nouveau format MI : CSV séparé par ; avec colonnes nommées.
    Retourne un DataFrame avec une ligne par commune et les scores par bloc.
    """
    df.columns = df.columns.str.strip()
    cols = list(df.columns)

    # Colonnes structurelles
    col_dep  = next(c for c in cols if 'département' in c.lower() and 'code' in c.lower() and 'libellé' not in c.lower())
    col_com  = next(c for c in cols if 'commune' in c.lower() and 'code' in c.lower() and 'libellé' not in c.lower())
    col_nom  = next(c for c in cols if 'commune' in c.lower() and ('libellé' in c.lower() or 'lib' in c.lower()))
    col_ins  = next((c for c in cols if c.strip().lower() == 'inscrits'), None)
    col_vot  = next((c for c in cols if c.strip().lower() == 'votants'), None)
    # "Exprimés" seul (pas "% Exprimés/inscrits")
    col_exp  = next((c for c in cols if c.strip().lower() == 'exprimés'), None)
    if col_exp is None:
        col_exp = next((c for c in cols if 'exprimés' in c.lower() and '%' not in c and '/' not in c), None)
    col_circ = next((c for c in cols if 'circonscription' in c.lower() and 'code' in c.lower()), None)

    # Filtres
    mask = df[col_dep].astype(str).str.strip() == dep
    df_f = df[mask].copy()
    if commune_whitelist is not None:
        df_f = df_f[df_f[col_com].astype(str).str.strip().isin(commune_whitelist)]
    elif col_circ:
        df_f = df_f[df_f[col_circ].astype(str).str.strip().isin(['9502', '2'])]
    print(f"    → {len(df_f)} communes")

    # Colonnes candidat/liste : trouver les paires (Nuance N, Voix N)
    nuance_cols = [(c, c.split()[-1]) for c in cols if 'nuance' in c.lower() and c.split()[-1].isdigit()]

    records = []
    for _, row in df_f.iterrows():
        code_com = str(row[col_com]).strip()
        nom_com  = str(row[col_nom]).strip()
        inscrits = sf(row[col_ins]) if col_ins else 0
        votants  = sf(row[col_vot]) if col_vot else 0
        exprimes = sf(row[col_exp]) if col_exp else 0
        if exprimes == 0: continue

        scores = {b: 0.0 for b in bloc_map}
        for nc, num in nuance_cols:
            nuance = str(row[nc]).strip().upper()
            if nuance in ('NAN', 'NONE', ''): continue
            vc = next((c for c in cols if c.strip() == f'Voix {num}'), None)
            if vc is None: continue
            voix = sf(row[vc])
            for bloc, nuances_set in bloc_map.items():
                if nuance in nuances_set:
                    scores[bloc] += voix; break

        rec = {
            'code_commune': code_com,
            'nom_commune':  nom_com,
            'inscrits':     int(inscrits),
            'exprimes':     int(exprimes),
            'participation': round(100 * votants / inscrits, 1) if inscrits > 0 else None,
        }
        for b, v in scores.items():
            rec[b] = round(100 * v / exprimes, 2) if exprimes > 0 else 0.0
        records.append(rec)

    out = pd.DataFrame(records)
    return out.set_index('code_commune') if len(out) else out


# ─── Parser 2 : Ancien format XLSX large (Pres 2022, Leg 2022) ───────────────
def parse_old_xlsx(df, bloc_map_type, dep=DEP, commune_whitelist=None):
    """
    Ancien format MI (wide XLSX) : colonnes fixes + blocs candidats répétés.
    - bloc_map_type = 'leg' : identification par nuance (col Nuance dans chaque bloc)
    - bloc_map_type = 'pres_t1' : identification par nom de famille
    - bloc_map_type = 'pres_t2' : identification par nom (2 candidats)
    Retourne un DataFrame avec une ligne par commune et scores par bloc.
    """
    cols = list(df.columns)

    # Auto-détection de la structure : trouver le début des blocs candidats
    # Les colonnes header sont nommées, les blocs suivants sont "Unnamed: N"
    named = [i for i, c in enumerate(cols) if not str(c).startswith('Unnamed')]
    # Trouver l'index de "N°Panneau" (ou similaire) qui marque le début des candidats
    try:
        base_idx = next(i for i, c in enumerate(cols) if 'panneau' in str(c).lower() or 'n°' in str(c).lower())
    except StopIteration:
        # Fallback : chercher "Exprimés" et ajouter ~3 cols
        exp_idx = next((i for i, c in enumerate(cols) if 'exprimés' in str(c).lower()), 16)
        base_idx = exp_idx + 3

    # Détecter la taille du bloc candidat en cherchant les colonnes "Unnamed"
    # dont le nom précédent nommé révèle la structure
    # On repère "Voix" dans les colonnes nommées pour identifier le bon offset
    bloc_header = cols[base_idx:]
    # Chercher la colonne Voix dans le 1er bloc (nommée)
    try:
        voix_off = next(i for i, c in enumerate(bloc_header) if str(c).lower().strip() == 'voix')
    except StopIteration:
        voix_off = 4  # fallback

    # Chercher la colonne Nuance (pour leg) ou Nom (pour pres)
    if bloc_map_type.startswith('pres'):
        try:
            nom_off = next(i for i, c in enumerate(bloc_header) if str(c).lower().strip() == 'nom')
        except StopIteration:
            nom_off = 2
    else:
        try:
            nua_off = next(i for i, c in enumerate(bloc_header) if str(c).lower().strip() == 'nuance')
        except StopIteration:
            nua_off = 4

    # Taille d'un bloc : distance entre base_idx et la prochaine colonne "Unnamed: (base_idx+X)"
    # qui corresponde à un nouveau N°Panneau
    remaining = cols[base_idx:]
    # Compter les colonnes nommées dans le 1er bloc
    # Un bloc finit quand on rencontre une colonne nommée après des Unnamed
    # OU quand on compte les colonnes nommées du header
    bloc_header_named = [str(c) for c in remaining if not str(c).startswith('Unnamed')]
    block_size = len(bloc_header_named)  # nb de colonnes nommées = taille 1er bloc
    if block_size == 0:
        block_size = 7  # fallback

    max_cands = (len(df.columns) - base_idx) // block_size

    # Détecter colonnes structurelles
    col_dep_i = next((i for i, c in enumerate(cols[:10]) if 'département' in str(c).lower() and 'code' in str(c).lower()), 0)
    col_com_i = next((i for i, c in enumerate(cols[:10]) if 'commune' in str(c).lower() and 'code' in str(c).lower()), 2)
    col_nom_i = next((i for i, c in enumerate(cols[:10]) if 'commune' in str(c).lower() and ('libellé' in str(c).lower() or 'lib' in str(c).lower())), 3)
    col_ins_i = next((i for i, c in enumerate(cols) if str(c).strip().lower() == 'inscrits'), 5)
    col_exp_i = next((i for i, c in enumerate(cols) if 'exprimés' in str(c).lower() and '%' not in str(c)), 16)
    col_vot_i = next((i for i, c in enumerate(cols) if str(c).strip().lower() == 'votants'), 8)

    # Convertir la whitelist en codes relatifs (ancien format : dept=95, com=26 pour 95026)
    rel_whitelist = None
    if commune_whitelist is not None:
        rel_whitelist = set()
        for full_code in commune_whitelist:
            s = str(full_code).strip()
            if s.startswith(dep):
                rel_whitelist.add(str(int(s[len(dep):])))  # '95026' → '26'
            rel_whitelist.add(s)  # garder aussi le code complet par sécurité

    print(f"    Structure: base_idx={base_idx}, block_size={block_size}, max_cands={max_cands}")
    print(f"    Colonnes clés: dept[{col_dep_i}]={cols[col_dep_i]}, com[{col_com_i}]={cols[col_com_i]}, exp[{col_exp_i}]={cols[col_exp_i]}")

    # Choisir le bon map selon type
    if bloc_map_type == 'pres_t1':
        bloc_map = PRES22_T1_MAP
        id_off   = nom_off
        by_name  = True
    elif bloc_map_type == 'pres_t2':
        bloc_map = PRES22_T2_MAP
        id_off   = nom_off
        by_name  = True
    else:  # leg
        bloc_map = LEG_BLOCS
        id_off   = nua_off
        by_name  = False

    records = []
    for _, row in df.iterrows():
        dept_val = str(row.iloc[col_dep_i]).strip()
        # Normaliser le code département
        if dept_val.isdigit():
            dept_val = dept_val.zfill(2)
        if dept_val != dep: continue

        code_com_raw = str(row.iloc[col_com_i]).strip().rstrip('.0')
        # Reconstruire le code INSEE complet : dept + commune_relatif (zero-padded à 3)
        try:
            code_com = f"{int(dept_val):02d}{int(code_com_raw):03d}"
        except Exception:
            code_com = code_com_raw
        nom_com  = str(row.iloc[col_nom_i]).strip() if col_nom_i < len(cols) else ''
        inscrits = sf(row.iloc[col_ins_i])
        votants  = sf(row.iloc[col_vot_i])
        exprimes = sf(row.iloc[col_exp_i])
        if exprimes == 0: continue

        if rel_whitelist is not None and code_com_raw not in rel_whitelist and code_com not in rel_whitelist:
            continue

        scores = {b: 0.0 for b in bloc_map}
        for k in range(max_cands):
            base = base_idx + k * block_size
            if base + max(id_off, voix_off) >= len(cols): break
            identifier = str(row.iloc[base + id_off]).strip().upper()
            voix = sf(row.iloc[base + voix_off])
            if identifier in ('NAN','NONE',''): continue

            if by_name:
                for bloc, names in bloc_map.items():
                    if any(n in identifier for n in names):
                        scores[bloc] += voix; break
            else:
                for bloc, nuances_set in bloc_map.items():
                    if identifier in nuances_set:
                        scores[bloc] += voix; break

        rec = {
            'code_commune': code_com,
            'nom_commune':  nom_com,
            'inscrits':     int(inscrits),
            'exprimes':     int(exprimes),
            'participation': round(100 * votants / inscrits, 1) if inscrits > 0 else None,
        }
        for b, v in scores.items():
            rec[b] = round(100 * v / exprimes, 2) if exprimes > 0 else 0.0
        records.append(rec)

    out = pd.DataFrame(records)
    if len(out): out = out.set_index('code_commune')
    print(f"    → {len(out)} communes")
    return out


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA, exist_ok=True)
    results = {}

    # Récupérer toutes les URLs en une passe
    print("\n[1/7] Résolution des URLs data.gouv.fr...")
    urls = {}
    for key, (ds_id, rid, fmt) in RESOURCES.items():
        ds = requests.get(f"{API}/datasets/{ds_id}/", timeout=30).json()
        urls[key] = (next(r['url'] for r in ds['resources'] if r['id'] == rid), fmt)
        print(f"  {key}: OK")

    # ── Leg 2024 T1 — identifier les communes de la 2ème circ ───────────────
    print("\n[2/7] Législatives 2024 T1 par communes...")
    url, fmt = urls['leg24t1']
    df_raw = download(url, fmt, 'leg24t1')

    # Identifier la liste des communes de la 2ème circ par la présence de HADIZADEH
    # (candidate UG dans la 2ème circ Val-d'Oise 2024)
    # Le fichier commune n'a pas de colonne circonscription — on filtre par candidate.
    df_dep95 = df_raw[df_raw['Code département'].astype(str).str.strip() == DEP].copy()
    nom_cols = [c for c in df_dep95.columns if 'nom candidat' in c.lower()]
    mask_circ = df_dep95[nom_cols].apply(
        lambda row: row.astype(str).str.upper().str.contains('HADIZADEH').any(), axis=1
    )
    commune_list = df_dep95.loc[mask_circ, 'Code commune'].astype(str).str.strip().tolist()
    commune_names = df_dep95.loc[mask_circ, 'Libellé commune'].tolist()
    print(f"  Communes circ 9502 identifiées : {len(commune_list)}")
    for code, nom in zip(commune_list, commune_names):
        print(f"    {code} — {nom}")

    leg24t1 = parse_modern_csv(df_raw, LEG_BLOCS, commune_whitelist=commune_list)
    results['leg24t1'] = leg24t1

    # ── Leg 2024 T2 ──────────────────────────────────────────────────────────
    print("\n[3/7] Législatives 2024 T2 par communes...")
    url, fmt = urls['leg24t2']
    df_raw = download(url, fmt, 'leg24t2')
    results['leg24t2'] = parse_modern_csv(df_raw, {'left': LEG_BLOCS['left'], 'far': LEG_BLOCS['far']},
                                           commune_whitelist=commune_list)

    # ── Euro 2024 ─────────────────────────────────────────────────────────────
    print("\n[4/7] Européennes 2024 par communes...")
    url, fmt = urls['eu24']
    df_raw = download(url, fmt, 'eu24')
    results['eu24'] = parse_modern_csv(df_raw, EURO_MAP, commune_whitelist=commune_list)

    # ── Pres 2022 T1 ─────────────────────────────────────────────────────────
    print("\n[5/7] Présidentielle 2022 T1 par communes...")
    url, fmt = urls['pr22t1']
    df_raw = download(url, fmt, 'pr22t1')
    results['pr22t1'] = parse_old_xlsx(df_raw, 'pres_t1', commune_whitelist=commune_list)

    # ── Pres 2022 T2 ─────────────────────────────────────────────────────────
    print("\n[6/7] Présidentielle 2022 T2 par communes...")
    url, fmt = urls['pr22t2']
    df_raw = download(url, fmt, 'pr22t2')
    results['pr22t2'] = parse_old_xlsx(df_raw, 'pres_t2', commune_whitelist=commune_list)

    # ── Leg 2022 T1 ──────────────────────────────────────────────────────────
    print("\n[7/7] Législatives 2022 T1 par communes...")
    url, fmt = urls['leg22t1']
    df_raw = download(url, fmt, 'leg22t1')
    results['leg22t1'] = parse_old_xlsx(df_raw, 'leg', commune_whitelist=commune_list)

    # ── Consolidation ─────────────────────────────────────────────────────────
    print("\n=== Consolidation ===")

    # Dédupliquer les index de chaque résultat (garder le premier)
    for k in results:
        if isinstance(results[k].index, pd.Index) and results[k].index.duplicated().any():
            n_dup = results[k].index.duplicated().sum()
            print(f"  Déduplication {k}: {n_dup} doublons supprimés")
            results[k] = results[k][~results[k].index.duplicated(keep='first')]

    base = results['leg24t1'][['nom_commune','inscrits']].copy()

    def add_cols(src_df, prefix, cols_to_add):
        if len(src_df) == 0:
            for c in cols_to_add: base[f'{prefix}_{c}'] = np.nan
            return
        for c in cols_to_add:
            if c in src_df.columns:
                # Alignement sur l'index de base (reindex)
                base[f'{prefix}_{c}'] = src_df[c].reindex(base.index)
            else:
                base[f'{prefix}_{c}'] = np.nan

    # Leg 2024 T1
    add_cols(results['leg24t1'], 'l24t1', ['left','ctr','rgt','far','participation','exprimes'])
    # Leg 2024 T2
    add_cols(results['leg24t2'], 'l24t2', ['left','far','participation'])
    # Euro 2024
    add_cols(results['eu24'], 'eu24', ['eu_lfi','eu_ps','eu_vec','eu_com','eu_lxeg',
                                        'eu_ctr','eu_lr','eu_rn','eu_rec','participation'])
    # Pres 2022 T1
    add_cols(results['pr22t1'], 'pr22t1', ['pr_left','pr_macron','pr_lepen','pr_zem','pr_pec','pr_other','participation'])
    # Pres 2022 T2
    add_cols(results['pr22t2'], 'pr22t2', ['pr2_macron','pr2_lepen','participation'])
    # Leg 2022 T1 (avec NUP corrigé)
    add_cols(results['leg22t1'], 'l22t1', ['left','ctr','rgt','far','participation'])

    # Colonnes dérivées utiles
    base['eu24_left_total'] = (
        base.get('eu24_eu_lfi',0).fillna(0) +
        base.get('eu24_eu_ps',0).fillna(0)  +
        base.get('eu24_eu_vec',0).fillna(0) +
        base.get('eu24_eu_com',0).fillna(0) +
        base.get('eu24_eu_lxeg',0).fillna(0)
    ).round(2)
    base['eu24_far_total'] = (
        base.get('eu24_eu_rn',0).fillna(0) +
        base.get('eu24_eu_rec',0).fillna(0)
    ).round(2)
    base['rn_delta_22_24'] = (base['l24t1_far'] - base['l22t1_far']).round(2)

    # Sauvegarde
    out_path = os.path.join(DATA, 'communes_9502.csv')
    base.to_csv(out_path)
    print(f"\n✓ Sauvegardé : {out_path}")
    print(f"  {len(base)} communes × {len(base.columns)} colonnes\n")
    print(base[['nom_commune','inscrits','l24t1_left','l24t1_far','l22t1_left','l22t1_far',
                'pr22t1_pr_left','eu24_left_total','eu24_eu_rn']].to_string())

    # Vérification : totaux circ doivent coller avec les fichiers cirlg
    print("\n=== Vérification vs données cirlg connues ===")
    total_exp = base['l24t1_exprimes'].sum()
    weighted = lambda c: (base[c] * base['l24t1_exprimes']).sum() / total_exp if total_exp > 0 else 0
    print(f"Leg2024 T1 agrégé circ — left: {weighted('l24t1_left'):.1f}% (attendu ~34.4%)")
    print(f"Leg2024 T1 agrégé circ — far:  {weighted('l24t1_far'):.1f}% (attendu ~31.2%)")
    print(f"Leg2024 T1 agrégé circ — ctr:  {weighted('l24t1_ctr'):.1f}% (attendu ~25.4%)")

if __name__ == '__main__':
    main()
