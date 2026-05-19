#!/usr/bin/env python3
"""
build_bdv_data.py
Résultats par bureau de vote pour toutes les circonscriptions du Val-d'Oise (dep 95)
Elections : Leg 2024 T1+T2 | Euro 2024 | Pres 2022 T1+T2 | Leg 2022 T1+T2

Outputs :
  data/bdv_{label}.csv        — un fichier par scrutin (lignes = BdV dep 95)
  data/bdv_circ_summary.csv   — résumé participation + blocs par circ × scrutin
"""
import io, os, warnings, requests
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEP  = "95"

# ─── URLs sources bureau de vote ──────────────────────────────────────────────
BDV_SOURCES = {
    'leg17t1': {
        'url': ('https://static.data.gouv.fr/resources/'
                'elections-legislatives-des-11-et-18-juin-2017-resultats-par-bureaux-de-vote-du-1er-tour/'
                '20170613-100441/Leg_2017_Resultats_BVT_T1_c.txt'),
        'fmt': 'txt_2017', 'type': 'leg_txt_2017',
    },
    'pr17t1': {
        'url': ('https://static.data.gouv.fr/resources/'
                'election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-1er-tour-par-bureaux-de-vote/'
                '20170427-100955/PR17_BVot_T1_FE.txt'),
        'fmt': 'txt_2017', 'type': 'pres_t1_txt_2017',
    },
    'leg24t1': {
        'url': ('https://static.data.gouv.fr/resources/'
                'elections-legislatives-des-30-juin-et-7-juillet-2024-resultats-definitifs-du-1er-tour/'
                '20240710-171445/resultats-definitifs-par-bureau-de-vote.csv'),
        'fmt': 'csv', 'type': 'leg_csv',
    },
    'leg24t2': {
        'url': ('https://static.data.gouv.fr/resources/'
                'elections-legislatives-des-30-juin-et-7-juillet-2024-resultats-definitifs-du-2nd-tour/'
                '20240710-170658/resultats-definitifs-par-bureau-de-vote.csv'),
        'fmt': 'csv', 'type': 'leg_csv',
    },
    'eu24': {
        'url': ('https://static.data.gouv.fr/resources/'
                'resultats-des-elections-europeennes-du-9-juin-2024/'
                '20240613-154804/resultats-definitifs-par-bureau-de-vote.csv'),
        'fmt': 'csv', 'type': 'eu_csv',
    },
    'leg22t1': {
        'url': ('https://static.data.gouv.fr/resources/'
                'elections-legislatives-des-12-et-19-juin-2022-resultats-definitifs-du-premier-tour/'
                '20220614-192433/resultats-par-niveau-burvot-t1-france-entiere.xlsx'),
        'fmt': 'xlsx', 'type': 'leg_xlsx',
    },
    'leg22t2': {
        'url': ('https://static.data.gouv.fr/resources/'
                'elections-legislatives-des-12-et-19-juin-2022-resultats-definitifs-du-second-tour/'
                '20220621-175223/resultats-par-niveau-burvot-t2-france-entiere.xlsx'),
        'fmt': 'xlsx', 'type': 'leg_xlsx',
    },
    'pr22t1': {
        'url': ('https://static.data.gouv.fr/resources/'
                'election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/'
                '20220414-152612/resultats-par-niveau-burvot-t1-france-entiere.xlsx'),
        'fmt': 'xlsx', 'type': 'pres_t1_xlsx',
    },
    'pr22t2': {
        'url': ('https://static.data.gouv.fr/resources/'
                'election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/'
                '20220428-142301/resultats-par-niveau-burvot-t2-france-entiere.xlsx'),
        'fmt': 'xlsx', 'type': 'pres_t2_xlsx',
    },
}

# ─── Blocs ────────────────────────────────────────────────────────────────────
LEG_BLOCS = {
    'left': {'LFI','FI','SOC','DVG','PCF','COM','ECO','VEC','RDG','UG',
             'LEXG','EXG','GS','NUP','DXG','LUG','FG','LDVG','LSOC'},
    'ctr':  {'ENS','HOR','DVC','UDI','MDM','REM','LREM'},
    'rgt':  {'LR','DVD','DLF','DVR'},
    'far':  {'RN','REC','EXD','UXD','DSV'},
}
EU_BLOCS = {
    'eu_left': {'LFI','LUG','LVEC','LCOM','LEXG','LDVG'},
    'eu_ctr':  {'LENS'},
    'eu_lr':   {'LLR'},
    'eu_rn':   {'LRN','LREC','LEXD'},
}
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

# Pres 2017 T1 — 11 candidats fixes, mêmes blocs canoniques que Pres 2022 T1
# pour comparabilité directe des dynamiques 2017→2022→2024.
# Pas de ZEMMOUR en 2017 (REC n'existait pas) → bloc pr_zem reste vide.
PRES17_T1_MAP = {
    'pr_left':   ['ARTHAUD','POUTOU','MÉLENCHON','MELENCHON','HAMON'],
    'pr_macron': ['MACRON'],
    'pr_pec':    ['FILLON'],   # LR 2017 = équivalent Pécresse 2022
    'pr_lepen':  ['LE PEN'],
    'pr_zem':    [],
    'pr_other':  ['DUPONT-AIGNAN','DUPONT','LASSALLE','ASSELINEAU','CHEMINADE'],
}

# Leg 2017 — anciennes nuances MI (avant la grande refonte de 2022)
LEG17_BLOCS = {
    'left': {'FI','SOC','DVG','PCF','COM','ECO','VEC','RDG','FG','UDC','LREM_PROCHE'},
    'ctr':  {'REM','MDM','UDI','LREM','DVC'},
    'rgt':  {'LR','DVD'},
    'far':  {'FN','DLF','DSV','EXD'},
}

# ─── Utilitaires ─────────────────────────────────────────────────────────────
def sf(v):
    if pd.isna(v): return 0.0
    try: return float(str(v).replace(',','.').replace('\xa0','').replace(' ',''))
    except: return 0.0


def norm_commune(raw, dep=DEP):
    """Normalise un code commune en 5 chiffres (ex: 2 → '95002', '95002' → '95002')."""
    s = str(raw).strip().split('.')[0]
    if len(s) >= 5:
        return s.zfill(5)
    try:
        return dep + str(int(s)).zfill(3)
    except:
        return s


def _find_dep_col(cols):
    for c in cols:
        cl = c.lower()
        if ('département' in cl or 'departement' in cl) and 'code' in cl and 'libellé' not in cl:
            return c
    return cols[0]


def download_file(url, label, fmt):
    """Téléchargement streaming avec cache _cache_bdv_{label}."""
    ext = {'csv': 'csv', 'xlsx': 'xlsx', 'txt_2017': 'txt'}.get(fmt, 'csv')
    cache = os.path.join(DATA, f"_cache_bdv_{label}.{ext}")

    if os.path.exists(cache):
        print(f"  [cache] bdv_{label}")
        if fmt == 'csv':
            return _read_csv_filtered(cache)
        elif fmt == 'txt_2017':
            return _read_txt2017_filtered(cache)
        else:
            return pd.read_excel(cache, header=0)

    print(f"  ↓ bdv_{label} ({url[-60:]})... ", end='', flush=True)
    for attempt in range(3):
        try:
            with requests.get(url, timeout=600, stream=True) as r:
                r.raise_for_status()
                chunks_raw = []
                total = 0
                for chunk in r.iter_content(chunk_size=131072):
                    chunks_raw.append(chunk)
                    total += len(chunk)
                content = b''.join(chunks_raw)
            break
        except Exception as e:
            if attempt == 2: raise
            print(f"retry {attempt+1}... ", end='', flush=True)
    print(f"{total//1024:,} KB")
    with open(cache, 'wb') as f:
        f.write(content)

    if fmt == 'csv':
        return _read_csv_filtered(cache)
    elif fmt == 'txt_2017':
        return _read_txt2017_filtered(cache)
    else:
        return pd.read_excel(io.BytesIO(content), header=0)


def _read_csv_filtered(path):
    """Lit un CSV par chunks en filtrant immédiatement sur dep=95."""
    chunks = []
    for chunk in pd.read_csv(path, sep=';', chunksize=10000, low_memory=False):
        chunk.columns = chunk.columns.str.strip()
        dep_col = _find_dep_col(list(chunk.columns))
        filt = chunk[chunk[dep_col].astype(str).str.strip() == DEP]
        if len(filt) > 0:
            chunks.append(filt)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def _read_txt2017_filtered(path):
    """
    Lit un TXT MI 2017 (latin-1, séparateur ';', long-flat format),
    filtre sur dep=95.
    Renvoie un dict : {'header': [...], 'rows': [[str,...], ...]}
    car le nombre de colonnes varie par ligne (candidats variables en Leg).
    """
    rows = []
    with open(path, 'r', encoding='latin-1') as f:
        header = next(f).rstrip('\r\n').split(';')
        for line in f:
            line = line.rstrip('\r\n')
            if not line:
                continue
            parts = line.split(';')
            if not parts:
                continue
            # Code département en position 0
            if parts[0].strip() == DEP:
                rows.append(parts)
    return {'header': header, 'rows': rows}


# ─── Parser 1 : Nouveau format CSV (Leg 2024, Euro 2024) ─────────────────────
def parse_modern_csv_bdv(df, elec_type, circ_map):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = df.columns.str.strip()
    cols = list(df.columns)

    col_dep  = _find_dep_col(cols)
    col_com  = next((c for c in cols if 'commune' in c.lower() and 'code' in c.lower()
                     and 'libellé' not in c.lower()), None)
    col_nom  = next((c for c in cols if 'commune' in c.lower()
                     and ('libellé' in c.lower() or 'lib' in c.lower())), None)
    col_circ = next((c for c in cols if 'circonscription' in c.lower() and 'code' in c.lower()), None)
    col_bdv  = next((c for c in cols if c.strip().upper() == 'CODE BV'), None)
    if col_bdv is None:
        col_bdv = next((c for c in cols if 'bv' in c.lower()), None)

    col_ins = next((c for c in cols if c.strip().lower() == 'inscrits'), None)
    col_vot = next((c for c in cols if c.strip().lower() == 'votants'), None)
    col_exp = next((c for c in cols if c.strip().lower() == 'exprimés'), None)
    if col_exp is None:
        col_exp = next((c for c in cols if 'exprimés' in c.lower()
                        and '%' not in c and '/' not in c), None)

    print(f"    dep={col_dep}, com={col_com}, bdv={col_bdv}, circ={col_circ}, "
          f"ins={col_ins}, exp={col_exp}")

    if elec_type == 'leg_csv':
        BLOCS = LEG_BLOCS
        nuance_cols = [(c, c.split()[-1]) for c in cols
                       if 'nuance' in c.lower() and c.split()[-1].isdigit()]
    else:  # eu_csv
        BLOCS = EU_BLOCS
        # "Nuance liste N"
        nuance_cols = [(c, c.split()[-1]) for c in cols
                       if 'nuance' in c.lower() and c.split()[-1].isdigit()]

    records = []
    for _, row in df.iterrows():
        raw_com   = str(row[col_com]).strip() if col_com else ''
        code_com  = norm_commune(raw_com)
        nom_com   = str(row[col_nom]).strip() if col_nom else ''
        bdv_num   = str(row[col_bdv]).strip() if col_bdv else ''
        # circ: REU map au niveau BdV (key composite), fallback commune si REU absent
        try:
            bdv_int = int(str(bdv_num).strip().lstrip('0') or '0')
        except Exception:
            bdv_int = 0
        key_bdv = f"{code_com}_{bdv_int}"
        if col_circ:
            circ_code = str(row[col_circ]).strip()
        elif key_bdv in circ_map:
            circ_code = circ_map[key_bdv]
        else:
            # Fallback commune-level (legacy circ_map) — peut être inexact pour communes éclatées
            circ_code = circ_map.get(code_com, '')
        inscrits  = sf(row[col_ins]) if col_ins else 0
        votants   = sf(row[col_vot]) if col_vot else 0
        exprimes  = sf(row[col_exp]) if col_exp else 0
        if exprimes == 0 and inscrits == 0:
            continue

        scores = {b: 0.0 for b in BLOCS}
        for nc, num in nuance_cols:
            nuance = str(row[nc]).strip().upper()
            if nuance in ('NAN', 'NONE', ''): continue
            vc = next((c for c in cols if c.strip() == f'Voix {num}'), None)
            if vc is None: continue
            voix = sf(row[vc])
            for bloc, ns in BLOCS.items():
                if nuance in ns:
                    scores[bloc] += voix; break

        rec = {
            'code_commune': code_com,
            'nom_commune':  nom_com,
            'num_bdv':      bdv_num,
            'code_circ':    circ_code,
            'inscrits':     int(inscrits),
            'votants':      int(votants),
            'exprimes':     int(exprimes),
            'participation': round(100 * votants / inscrits, 2) if inscrits > 0 else 0.0,
        }
        for b, v in scores.items():
            rec[b] = round(100 * v / exprimes, 2) if exprimes > 0 else 0.0
        records.append(rec)

    return pd.DataFrame(records)


# ─── Parser 2 : Ancien format XLSX burvot (Leg 2022, Pres 2022) ──────────────
def parse_old_xlsx_bdv(df, elec_type, circ_map, dep=DEP):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = df.columns.str.strip()
    cols = list(df.columns)

    print(f"    ncols={len(cols)}, premières: {cols[:8]}")

    # Filtre département
    col_dep = _find_dep_col(cols)
    df = df[df[col_dep].astype(str).str.strip() == dep].copy()
    print(f"    → {len(df)} BdV pour dep {dep}")
    if df.empty:
        return pd.DataFrame()

    col_com  = next((c for c in cols if 'commune' in c.lower() and 'code' in c.lower()
                     and 'libellé' not in c.lower()), None)
    col_nom  = next((c for c in cols if 'commune' in c.lower()
                     and ('libellé' in c.lower() or 'lib' in c.lower())), None)
    col_circ = next((c for c in cols if 'circonscription' in c.lower() and 'code' in c.lower()), None)
    # bureau de vote : "Code du b.vote" ou "bureau"
    col_bdv = next((c for c in cols if 'b.vote' in c.lower() or 'b.v' in c.lower()
                    or 'bureau' in c.lower()), None)
    col_ins  = next((c for c in cols if c.strip().lower() == 'inscrits'), None)
    col_vot  = next((c for c in cols if c.strip().lower() == 'votants'), None)
    col_exp  = next((c for c in cols if c.strip().lower() == 'exprimés'), None)
    if col_exp is None:
        col_exp = next((c for c in cols if 'exprimés' in c.lower()
                        and '%' not in c and '/' not in c), None)

    print(f"    com={col_com}, bdv={col_bdv}, circ={col_circ}, "
          f"ins={col_ins}, exp={col_exp}")

    # Début des blocs candidats (N°Panneau)
    try:
        base_idx = next(i for i, c in enumerate(cols)
                        if 'panneau' in str(c).lower())
    except StopIteration:
        exp_idx = next((i for i, c in enumerate(cols) if 'exprimés' in str(c).lower()), 16)
        base_idx = exp_idx + 3

    bloc_header = cols[base_idx:]

    # CORRECTION : trouver le premier Unnamed dans bloc_header à partir de la position 1
    first_unnamed = next((i for i, c in enumerate(bloc_header) if i > 0 and str(c).startswith('Unnamed')), None)
    if first_unnamed:
        block_size = first_unnamed
    else:
        # Toutes les colonnes sont nommées (fichier non-wide) : estimer
        block_size = 7 if elec_type.startswith('pres') else 8

    # Offsets dans le bloc
    voix_off   = next((i for i, c in enumerate(bloc_header) if str(c).lower().strip() == 'voix'), 4)
    nuance_off = next((i for i, c in enumerate(bloc_header) if 'nuance' in str(c).lower()), None)
    nom_off    = next((i for i, c in enumerate(bloc_header) if str(c).lower().strip() == 'nom'), 2)

    n_cand = max(1, (len(cols) - base_idx) // block_size)
    id_mode = 'nuance' if (nuance_off is not None and elec_type.startswith('leg')) else 'nom'
    BLOCS = LEG_BLOCS if elec_type.startswith('leg') else \
            (PRES22_T1_MAP if elec_type == 'pres_t1_xlsx' else PRES22_T2_MAP)

    print(f"    base_idx={base_idx}, block_size={block_size}, voix_off={voix_off}, "
          f"id_mode={id_mode}, nuance_off={nuance_off}, nom_off={nom_off}, n_cand={n_cand}")

    records = []
    for _, row in df.iterrows():
        vals = list(row)
        raw_com   = str(vals[cols.index(col_com)]).strip() if col_com else ''
        code_com  = norm_commune(raw_com, dep)
        nom_com   = str(vals[cols.index(col_nom)]).strip() if col_nom else ''
        bdv_num   = str(vals[cols.index(col_bdv)]).strip() if col_bdv else ''
        try:
            bdv_int = int(str(bdv_num).strip().lstrip('0') or '0')
        except Exception:
            bdv_int = 0
        key_bdv = f"{code_com}_{bdv_int}"
        if col_circ:
            circ_code = str(vals[cols.index(col_circ)]).strip()
        elif key_bdv in circ_map:
            circ_code = circ_map[key_bdv]
        else:
            circ_code = circ_map.get(code_com, '')
        inscrits  = sf(vals[cols.index(col_ins)]) if col_ins else 0
        votants   = sf(vals[cols.index(col_vot)]) if col_vot else 0
        exprimes  = sf(vals[cols.index(col_exp)]) if col_exp else 0
        if exprimes == 0 and inscrits == 0:
            continue

        scores = {b: 0.0 for b in BLOCS}

        for k in range(n_cand):
            start = base_idx + k * block_size
            end   = start + block_size
            if end > len(vals): break
            block_vals = vals[start:end]

            # Identifier le candidat
            if id_mode == 'nuance' and nuance_off < len(block_vals):
                candidate_key = str(block_vals[nuance_off]).strip().upper()
            elif nom_off < len(block_vals):
                candidate_key = str(block_vals[nom_off]).strip().upper()
            else:
                continue
            if candidate_key in ('NAN', 'NONE', '', 'NAT'): continue

            # Voix
            if voix_off < len(block_vals):
                voix = sf(block_vals[voix_off])
            else:
                continue

            # Affectation au bloc
            for bloc, keys_set in BLOCS.items():
                if id_mode == 'nuance':
                    if candidate_key in keys_set:
                        scores[bloc] += voix; break
                else:
                    if any(k_name in candidate_key for k_name in keys_set):
                        scores[bloc] += voix; break

        rec = {
            'code_commune': code_com,
            'nom_commune':  nom_com,
            'num_bdv':      bdv_num,
            'code_circ':    circ_code,
            'inscrits':     int(inscrits),
            'votants':      int(votants),
            'exprimes':     int(exprimes),
            'participation': round(100 * votants / inscrits, 2) if inscrits > 0 else 0.0,
        }
        for b, v in scores.items():
            rec[b] = round(100 * v / exprimes, 2) if exprimes > 0 else 0.0
        records.append(rec)

    return pd.DataFrame(records)


# ─── Parser 3 : Format TXT 2017 long-flat (Leg 2017, Pres 2017) ──────────────
def parse_txt2017_bdv(filtered, elec_type, circ_map, dep=DEP):
    """
    Parse le format TXT 2017 du Ministère de l'Intérieur :
    - Header avec colonnes structurelles (positions 0-20) puis bloc candidat répété
    - Leg 2017 : bloc de 8 cols (N°Panneau, Sexe, Nom, Prénom, Nuance, Voix, %ins, %exp)
    - Pres 2017 : bloc de 7 cols (N°Panneau, Sexe, Nom, Prénom, Voix, %ins, %exp)
    - Nombre de candidats variable selon BdV pour Leg, fixe = 11 pour Pres
    """
    if not filtered or not filtered.get('rows'):
        return pd.DataFrame()

    header = filtered['header']
    rows = filtered['rows']
    print(f"    {len(rows)} BdV dep {dep}, header={len(header)} cols")

    # Trouver les colonnes structurelles dans le header
    def find_idx(predicate, fallback=None):
        for i, c in enumerate(header):
            if predicate(c.lower().strip()):
                return i
        return fallback

    col_dep_i  = find_idx(lambda c: 'département' in c and 'code' in c and 'libellé' not in c, 0)
    col_circ_i = find_idx(lambda c: 'circonscription' in c and 'code' in c and 'libellé' not in c)
    col_com_i  = find_idx(lambda c: 'commune' in c and 'code' in c and 'libellé' not in c)
    col_nom_i  = find_idx(lambda c: 'commune' in c and ('libellé' in c or 'lib' in c))
    col_bdv_i  = find_idx(lambda c: 'b.vote' in c or 'b.v' in c)
    col_ins_i  = find_idx(lambda c: c == 'inscrits')
    col_vot_i  = find_idx(lambda c: c == 'votants')
    col_exp_i  = find_idx(lambda c: c == 'exprimés')
    base_idx   = find_idx(lambda c: 'panneau' in c)

    if base_idx is None:
        print(f"    ✗ Impossible de trouver 'N°Panneau' dans le header")
        return pd.DataFrame()

    if elec_type == 'leg_txt_2017':
        block_size = 8
        nuance_off_in_block = 4  # N°Panneau=0, Sexe=1, Nom=2, Prénom=3, Nuance=4, Voix=5
        voix_off_in_block   = 5
        BLOCS = LEG17_BLOCS
        id_mode = 'nuance'
    else:  # pres_t1_txt_2017
        block_size = 7
        nom_off_in_block    = 2  # N°Panneau=0, Sexe=1, Nom=2, Prénom=3, Voix=4
        voix_off_in_block   = 4
        BLOCS = PRES17_T1_MAP
        id_mode = 'nom'

    print(f"    base_idx={base_idx}, block_size={block_size}, id_mode={id_mode}")

    records = []
    for vals in rows:
        try:
            code_com_raw = vals[col_com_i].strip()
            code_com     = norm_commune(code_com_raw, dep)
            nom_com      = vals[col_nom_i].strip() if col_nom_i is not None else ''
            bdv_num_raw  = vals[col_bdv_i].strip() if col_bdv_i is not None else ''
            inscrits     = sf(vals[col_ins_i]) if col_ins_i is not None else 0
            votants      = sf(vals[col_vot_i]) if col_vot_i is not None else 0
            exprimes     = sf(vals[col_exp_i]) if col_exp_i is not None else 0
        except IndexError:
            continue

        if exprimes == 0 and inscrits == 0:
            continue

        # Normaliser num_bdv (enlever zéros préfixes)
        try:
            bdv_int = int(bdv_num_raw.lstrip('0') or '0')
            bdv_num = str(bdv_int)
        except ValueError:
            bdv_num = bdv_num_raw

        # Circ via REU au niveau BdV (key composite) ou col_circ du fichier
        key_bdv = f"{code_com}_{bdv_int}" if bdv_num_raw else ''
        if col_circ_i is not None:
            circ_code = vals[col_circ_i].strip()
            # Format 2017 : "04" ou "04ème circonscription" → on garde tel quel pour Leg
        else:
            circ_code = ''
        # Override par REU (plus précis pour communes éclatées)
        if key_bdv in circ_map:
            circ_code = circ_map[key_bdv]

        # Parser les blocs candidats
        scores = {b: 0.0 for b in BLOCS}
        nb_blocks = (len(vals) - base_idx) // block_size
        for k in range(nb_blocks):
            start = base_idx + k * block_size
            if id_mode == 'nuance':
                ident = vals[start + nuance_off_in_block].strip().upper() if start + nuance_off_in_block < len(vals) else ''
            else:
                ident = vals[start + nom_off_in_block].strip().upper() if start + nom_off_in_block < len(vals) else ''
            if ident in ('NAN', 'NONE', '', 'NAT'):
                continue
            voix = sf(vals[start + voix_off_in_block]) if start + voix_off_in_block < len(vals) else 0.0

            for bloc, keys_set in BLOCS.items():
                if id_mode == 'nuance':
                    if ident in keys_set:
                        scores[bloc] += voix
                        break
                else:
                    if any(name_token in ident for name_token in keys_set):
                        scores[bloc] += voix
                        break

        rec = {
            'code_commune':  code_com,
            'nom_commune':   nom_com,
            'num_bdv':       bdv_num,
            'code_circ':     circ_code,
            'inscrits':      int(inscrits),
            'votants':       int(votants),
            'exprimes':      int(exprimes),
            'participation': round(100 * votants / inscrits, 2) if inscrits > 0 else 0.0,
        }
        for b, v in scores.items():
            rec[b] = round(100 * v / exprimes, 2) if exprimes > 0 else 0.0
        records.append(rec)

    return pd.DataFrame(records)


# ─── Construction du circ_map depuis le REU (BdV-level, vérité officielle) ───
def build_circ_map():
    """
    Construit (code_commune, num_bdv) → code_circ depuis le REU
    (data/reu_bv_circ_95.csv généré depuis data.gouv.fr/contours-des-bureaux-de-vote/).

    IMPORTANT : map au niveau BdV, pas commune.
    Les communes éclatées (Cergy 9502/9510) sont correctement gérées.

    Format de la clé : f"{code_commune}_{num_bdv}" avec num_bdv en int (pas zfill).
    Format de la valeur : code circo court (ex: "2" pour 9502, pour cohérence
    avec le format historique de l'ancien circ_map).
    """
    cache = os.path.join(DATA, 'reu_bv_circ_95.csv')
    if not os.path.exists(cache):
        print("  [circ_map] REU absent — fallback commune-level (DEPRECATED, voir INS-011)")
        return _build_circ_map_legacy()
    df = pd.read_csv(cache, dtype={'code_commune': str, 'code_circ_full': str})
    # Clé composite : "code_commune_num_bdv" (num_bdv int, pas de zfill)
    df['key'] = df['code_commune'] + '_' + df['num_bdv'].astype(str)
    # Valeur : code circo court SANS zfill ("1"-"10") pour cohérence avec
    # l'ancien circ_map issu de leg22t1 (compare directement à CIRC="2")
    df['short'] = df['code_circ_full'].str[-2:].astype(int).astype(str)
    circ_map = dict(zip(df['key'], df['short']))
    print(f"  [circ_map] {len(circ_map)} BdV → circ (depuis REU, BdV-level)")
    return circ_map


def _build_circ_map_legacy():
    """Fallback : ancien map commune-level depuis leg22t1 burvot (DEPRECATED)."""
    cache = os.path.join(DATA, '_cache_bdv_leg22t1.xlsx')
    if not os.path.exists(cache):
        return {}
    df = pd.read_excel(cache, header=0)
    df.columns = df.columns.str.strip()
    col_dep  = _find_dep_col(list(df.columns))
    col_circ = next((c for c in df.columns if 'circonscription' in c.lower() and 'code' in c.lower()), None)
    col_com  = next((c for c in df.columns if 'commune' in c.lower() and 'code' in c.lower()
                     and 'libellé' not in c.lower()), None)
    df95 = df[df[col_dep].astype(str).str.strip() == DEP].copy()
    df95['code_full'] = df95[col_com].apply(lambda x: norm_commune(x, DEP))
    return df95.groupby('code_full')[col_circ].first().astype(str).to_dict()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA, exist_ok=True)

    # Construire le circ_map en premier (depuis leg22t1 si déjà en cache)
    circ_map = build_circ_map()

    results = {}

    for label, src in BDV_SOURCES.items():
        print(f"\n{'='*60}")
        print(f"  {label.upper()} ({src['type']})")
        print(f"{'='*60}")

        try:
            raw = download_file(src['url'], label, src['fmt'])
        except Exception as e:
            print(f"  ERREUR téléchargement: {e}")
            results[label] = pd.DataFrame()
            continue

        # raw peut être DataFrame (csv/xlsx) ou dict (txt_2017)
        is_empty = (
            (isinstance(raw, pd.DataFrame) and raw.empty)
            or (isinstance(raw, dict) and not raw.get('rows'))
        )
        if is_empty:
            print(f"  VIDE après filtrage dep={DEP}")
            results[label] = pd.DataFrame()
            continue

        # Parser
        if src['type'] in ('leg_csv', 'eu_csv'):
            df_bdv = parse_modern_csv_bdv(raw, src['type'], circ_map)
        elif src['type'] in ('leg_txt_2017', 'pres_t1_txt_2017'):
            df_bdv = parse_txt2017_bdv(raw, src['type'], circ_map)
        else:
            df_bdv = parse_old_xlsx_bdv(raw, src['type'], circ_map)

        if df_bdv.empty:
            print(f"  VIDE après parsing")
            results[label] = pd.DataFrame()
            continue

        # Mettre à jour circ_map après leg22t1 (en cas de premier run)
        if label == 'leg22t1' and not circ_map:
            circ_map = build_circ_map()

        results[label] = df_bdv

        # Sauvegarde
        out_path = os.path.join(DATA, f"bdv_{label}.csv")
        df_bdv.to_csv(out_path, index=False)
        print(f"  ✓ {len(df_bdv)} BdV → {out_path}")

        # Résumé par circonscription
        _print_circ_summary(df_bdv, label)

    # ─── Résumé global multi-scrutins ─────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  RÉSUMÉ GLOBAL par circonscription × scrutin")
    print(f"{'='*60}")
    rows = []
    for label, df_bdv in results.items():
        if df_bdv.empty or 'code_circ' not in df_bdv.columns: continue
        bloc_cols = [c for c in df_bdv.columns
                     if c not in ('code_commune','nom_commune','num_bdv',
                                  'code_circ','inscrits','votants','exprimes','participation')]
        for circ, grp in df_bdv.groupby('code_circ'):
            ins = grp['inscrits'].sum()
            vot = grp['votants'].sum()
            exp = grp['exprimes'].sum()
            r = {'scrutin': label, 'code_circ': circ,
                 'n_bdv': len(grp), 'inscrits': ins, 'votants': vot, 'exprimes': exp,
                 'participation': round(100*vot/ins, 2) if ins > 0 else 0}
            for bc in bloc_cols:
                voix = (grp[bc] * grp['exprimes'] / 100).sum()
                r[bc] = round(100 * voix / exp, 2) if exp > 0 else 0
            rows.append(r)

    if rows:
        summary_all = pd.DataFrame(rows)
        out_sum = os.path.join(DATA, "bdv_circ_summary.csv")
        summary_all.to_csv(out_sum, index=False)
        # Affichage condensé
        for scrutin, g in summary_all.groupby('scrutin'):
            print(f"\n  {scrutin}:")
            print(g.to_string(index=False))
        print(f"\n✓ Résumé sauvegardé : {out_sum}")

    print("\n✓ Terminé.")


def _print_circ_summary(df_bdv, label):
    if 'code_circ' not in df_bdv.columns: return
    bloc_cols = [c for c in df_bdv.columns
                 if c not in ('code_commune','nom_commune','num_bdv',
                              'code_circ','inscrits','votants','exprimes','participation')]
    rows = []
    for circ, grp in df_bdv.groupby('code_circ'):
        ins = grp['inscrits'].sum()
        vot = grp['votants'].sum()
        exp = grp['exprimes'].sum()
        r = {'circ': circ, 'n_bdv': len(grp), 'inscrits': ins,
             'participation%': round(100*vot/ins,1) if ins>0 else 0}
        for bc in bloc_cols:
            voix = (grp[bc] * grp['exprimes'] / 100).sum()
            r[bc] = round(100*voix/exp, 1) if exp>0 else 0
        rows.append(r)
    if rows:
        print(f"\n  Résumé par circ ({label}):")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()
