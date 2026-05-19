#!/usr/bin/env python3
"""
config_circos.py — Configuration centralisée par circonscription.

POUR AJOUTER UNE NOUVELLE CIRCO :
  1. Copier le bloc d'une circo existante dans le dict CIRCOS
  2. Renseigner les champs (voir gabarit commenté en bas du fichier)
  3. Mettre CIRCO_ACTIVE = "<nouveau code>"
  4. Lancer :  python3 build_bv_contours.py     (extrait les contours BdV du REU)
               python3 build_map_bdv_9502.py    (génère carte_bdv_<code>.html)

  Si la circo est dans un AUTRE département que le 95 :
  - lancer aussi build_bdv_data.py après avoir changé DEP, et générer
    data/reu_bv_circ_<dep>.csv depuis le REU France entière.

CHAMPS QUI DEMANDENT UN TRAVAIL ANALYTIQUE (pas juste du copier-coller) :
  - scenario_cibles      : calibrer sur l'histoire électorale de la circo
  - bdv_type_par_commune : classer chaque commune (règle dans le commentaire)
  - ref_t1_2024          : chiffres officiels MI cirlg pour la validation
  - seuil_t2             : 12.5% inscrits ÷ participation T1 de la circo
"""

# Chemins de base (communs à toutes les circos)
BASE = "/Users/remybajolet/Desktop/datagouv"
DATA = BASE + "/data"

# Circo traitée par défaut quand on lance les scripts sans argument
CIRCO_ACTIVE = "9502"


CIRCOS = {

    # ════════════════════════════════════════════════════════════════════
    "9502": {
        # ─── Identité ───────────────────────────────────────────────────
        "code_circ":       "9502",   # code circo REU (dep 2 chiffres + 2)
        "code_circ_court": "2",      # numéro court (compare à code_circ des CSV BdV)
        "dep":             "95",
        "nom_court":       "2e circ. Val-d'Oise",
        "nom_long":        "2ème circonscription du Val-d'Oise",
        "depute":          "Ayda Hadizadeh (NFP)",

        # ─── Carte ──────────────────────────────────────────────────────
        "map_center":      [49.06, 2.20],
        "map_zoom":        12,

        # ─── Seuil de maintien T2 (% exprimés) ──────────────────────────
        # = 12.5% inscrits ÷ (participation T1 × ratio exprimés/votants)
        "seuil_t2":        19.14,

        # ─── Cibles scénarios 2027 (Δ pts moy. circo) — voir EDR-022/023 ─
        "scenario_cibles": {
            "sursaut":      {"centre_lr": +6.0,  "nfp": -2.5, "rn": -6.0},
            "effondrement": {"centre_lr": -12.0, "nfp": +7.0, "rn": +4.0},
        },
        "lr_retention_sursaut": 0.5,  # fraction de LR conservée en sursaut Philippe

        # ─── Typologie des BdV (niveau commune) — voir EDR-024 ───────────
        # Règle : NFP>45% → urbain_populaire ; ENS 1ère force → bourgeois ;
        #         RN≥40% → rural ; sinon → periurbain.
        "bdv_type_par_commune": {
            "95127": "urbain_populaire",  # Cergy
            "95572": "urbain_populaire",  # Saint-Ouen-l'Aumône
            "95218": "mixte_urbain",      # Éragny
            "95313": "bourgeois",         # L'Isle-Adam
            "95450": "bourgeois",         # Neuville-sur-Oise
            "95394": "periurbain",        # Méry-sur-Oise
            "95392": "periurbain",        # Mériel
            "95480": "periurbain",        # Parmain
            "95504": "periurbain",        # Presles
            "95430": "periurbain",        # Montsoult
            "95042": "periurbain",        # Baillet-en-France
            "95445": "periurbain",        # Nerville-la-Forêt
            "95026": "rural",             # Asnières-sur-Oise
            "95056": "rural",             # Belloy-en-France
            "95652": "rural",             # Viarmes
            "95456": "rural",             # Noisy-sur-Oise
            "95660": "rural",             # Villaines-sous-Bois
            "95353": "rural",             # Maffliers
            "95594": "rural",             # Seugy
            "95678": "rural",             # Villiers-Adam
            "95566": "rural",             # Saint-Martin-du-Tertre
        },

        # ─── Chiffres de référence MI cirlg (pour data-validator) ───────
        "ref_t1_2024": {
            "nfp": 34.4, "rn": 31.2, "ens": 25.3, "lr": 6.3,
            "n_bdv": 80, "inscrits": 78781,
        },
    },

    # ════════════════════════════════════════════════════════════════════
    # GABARIT — copier ce bloc, décommenter, remplir pour une nouvelle circo
    # ════════════════════════════════════════════════════════════════════
    # "9501": {
    #     "code_circ":       "9501",
    #     "code_circ_court": "1",
    #     "dep":             "95",
    #     "nom_court":       "1re circ. Val-d'Oise",
    #     "nom_long":        "1ère circonscription du Val-d'Oise",
    #     "depute":          "...",
    #     "map_center":      [49.0, 2.1],
    #     "map_zoom":        12,
    #     "seuil_t2":        19.0,                       # à recalculer
    #     "scenario_cibles": {
    #         "sursaut":      {"centre_lr": +6.0,  "nfp": -2.5, "rn": -6.0},
    #         "effondrement": {"centre_lr": -12.0, "nfp": +7.0, "rn": +4.0},
    #     },
    #     "lr_retention_sursaut": 0.5,
    #     "bdv_type_par_commune": { ... },               # à classer
    #     "ref_t1_2024": { ... },                        # MI cirlg
    # },

}


# Ratios de transfert du centre+LR érodé → (NFP, RN, abstention) par type.
# GÉNÉRIQUES (sociologie, pas circo-spécifiques) — voir EDR-024.
TRANSFER_RATIOS = {
    "urbain_populaire": (0.75, 0.15, 0.10),
    "mixte_urbain":     (0.60, 0.30, 0.10),
    "bourgeois":        (0.50, 0.35, 0.15),
    "periurbain":       (0.40, 0.50, 0.10),
    "rural":            (0.30, 0.60, 0.10),
}
TRANSFER_DEFAULT = (0.60, 0.35, 0.05)  # fallback commune non classée


def get_active():
    """Retourne la config de la circo active."""
    return CIRCOS[CIRCO_ACTIVE]
