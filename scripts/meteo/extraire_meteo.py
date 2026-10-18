"""Extrait la température extérieure horaire des scénarios météo RE2020, un CSV par zone.

Source : data/4_scenarios_meteorologiques_th-bc_th-d_re2020.xlsx (DHUP / Météo-France,
données 2000-2018), 16 onglets « <zone>_Th-BC » et « <zone>_Th-D ».
Sortie : data/meteo/meteo_<zone>.csv, une ligne par heure de l'année (8 760 lignes) :
    heure ; th_bc (climat moyen, calcul Besoins / Consommations) ; th_d (scénario caniculaire
    de type 2003, calcul Confort d'été) — température extérieure te0 en °C.
Format identique aux autres CSV du dépôt : séparateur « ; », virgule décimale.

Usage : python3 scripts/meteo/extraire_meteo.py   (nécessite openpyxl)
"""
import csv
import os

import openpyxl

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------
RACINE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SOURCE = os.path.join(RACINE, "data", "4_scenarios_meteorologiques_th-bc_th-d_re2020.xlsx")
SORTIE_DIR = os.path.join(RACINE, "data", "meteo")
ZONES = ["H1a", "H1b", "H1c", "H2a", "H2b", "H2c", "H2d", "H3"]
SCENARIOS = {"th_bc": "Th-BC", "th_d": "Th-D"}   # colonne du CSV → suffixe de l'onglet
COL_HEURE = 0                 # colonne « h » des onglets (0 à 8759)
COL_TEMPERATURE = 1           # colonne « te0 » : température extérieure (°C)
NB_HEURES = 8760
DECIMALES = 3


def fr(x):
    """Nombre au format français (virgule décimale), sans zéros inutiles."""
    return f"{round(x, DECIMALES):g}".replace(".", ",")


def lire_temperatures(classeur, onglet):
    """Température extérieure heure par heure d'un onglet, contrôlée (8 760 heures, dans l'ordre)."""
    lignes = list(classeur[onglet].iter_rows(min_row=2, values_only=True))
    lignes = [l for l in lignes if l[COL_HEURE] is not None]
    heures = [int(l[COL_HEURE]) for l in lignes]
    if heures != list(range(NB_HEURES)):
        raise SystemExit(f"{onglet} : heures inattendues ({len(heures)} lignes)")
    return [float(l[COL_TEMPERATURE]) for l in lignes]


def main():
    os.makedirs(SORTIE_DIR, exist_ok=True)
    classeur = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    for zone in ZONES:
        series = {col: lire_temperatures(classeur, f"{zone}_{suffixe}") for col, suffixe in SCENARIOS.items()}
        chemin = os.path.join(SORTIE_DIR, f"meteo_{zone}.csv")
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["heure", *SCENARIOS])
            for h in range(NB_HEURES):
                w.writerow([h, *(fr(series[col][h]) for col in SCENARIOS)])
        maxi = {col: fr(max(v)) for col, v in series.items()}
        print(f"{zone} : {chemin}  (max Th-BC {maxi['th_bc']} °C, Th-D {maxi['th_d']} °C)")


if __name__ == "__main__":
    main()
