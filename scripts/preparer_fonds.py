"""Prépare les fonds de carte versionnés dans data/fonds/.

Télécharge les sources à des commits figés (résultat reproductible), garde
uniquement ce qui sert à la carte (emprise autour de la métropole, fleuves
et massifs listés dans data/reperes.json) et écrit de petits GeoJSON.

Sources :
  - départements : france-geojson (Grégoire David), version simplifiée ;
  - pays, lacs, fleuves, massifs : Natural Earth (domaine public).

Usage : python3 scripts/preparer_fonds.py
        (à relancer seulement pour changer de version des sources ou de repères)
"""
import json
import os
import urllib.request

from shapely.geometry import box, mapping, shape

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête)
# ---------------------------------------------------------------------------
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CACHE_DIR = os.path.join(RACINE, ".cache", "fonds")      # téléchargements bruts (non versionnés)
SORTIE_DIR = os.path.join(RACINE, "data", "fonds")
REPERES_PATH = os.path.join(RACINE, "data", "reperes.json")

# Commits figés des dépôts sources (à changer volontairement pour mettre à jour les fonds)
FRANCE_GEOJSON = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
                  "5d34ee6d0140c29f785fdb047d9329f1aab58833")
NATURAL_EARTH = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
                 "ca96624a56bd078437bca8184e78163e5039ad19/geojson")
SOURCES = {
    "dep": f"{FRANCE_GEOJSON}/departements-version-simplifiee.geojson",
    "pays": f"{NATURAL_EARTH}/ne_50m_admin_0_countries.geojson",
    "lacs": f"{NATURAL_EARTH}/ne_10m_lakes.geojson",
    "fleuves_monde": f"{NATURAL_EARTH}/ne_10m_rivers_lake_centerlines.geojson",
    "fleuves_europe": f"{NATURAL_EARTH}/ne_10m_rivers_europe.geojson",
    "regions": f"{NATURAL_EARTH}/ne_10m_geography_regions_polys.geojson",
}

# Emprise des extraits (lon/lat), plus large que la carte affichée
EMPRISE = box(-8.0, 39.0, 12.5, 53.0)

# Noms abîmés dans Natural Earth (accents perdus) → nom correct
NOMS_CORRIGES = {"Rhne": "Rhône", "Sane": "Saône"}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def telecharger(nom):
    """Télécharge une source dans le cache (une seule fois) et la retourne lue."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    chemin = os.path.join(CACHE_DIR, f"{nom}.geojson")
    if not os.path.exists(chemin):
        print("  téléchargement :", SOURCES[nom])
        urllib.request.urlretrieve(SOURCES[nom], chemin)
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def extraire(geo, proprietes, garder=lambda p: True):
    """Garde les objets dans l'emprise (découpés) et seulement les propriétés utiles."""
    objets = []
    for f in geo["features"]:
        props = f["properties"]
        if not garder(props):
            continue
        g = shape(f["geometry"]).buffer(0) if "Polygon" in f["geometry"]["type"] else shape(f["geometry"])
        if not g.intersects(EMPRISE):
            continue
        objets.append({"type": "Feature",
                       "properties": {k: props.get(k) for k in proprietes},
                       "geometry": mapping(g.intersection(EMPRISE))})
    return objets


def ecrire(nom, objets):
    chemin = os.path.join(SORTIE_DIR, f"{nom}.geojson")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": objets}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"  {nom:12s} {len(objets):4d} objets  {os.path.getsize(chemin) / 1024:6.0f} Ko")


# ---------------------------------------------------------------------------
# Traitement
# ---------------------------------------------------------------------------
def main():
    os.makedirs(SORTIE_DIR, exist_ok=True)
    with open(REPERES_PATH, encoding="utf-8") as f:
        reperes = json.load(f)
    fleuves = set(reperes["fleuves"]["principaux"]) | set(reperes["fleuves"]["secondaires"])

    # Départements : copie telle quelle (déjà simplifiée à la source)
    ecrire("departements", telecharger("dep")["features"])
    ecrire("pays", extraire(telecharger("pays"), ["ADMIN"]))
    ecrire("lacs", extraire(telecharger("lacs"), ["name"]))
    ecrire("massifs", extraire(telecharger("regions"), ["NAME"],
                               lambda p: p.get("NAME") in reperes["massifs"]))

    # Fleuves : les deux fichiers Natural Earth, noms corrigés, seulement ceux listés
    objets = []
    for source in ("fleuves_monde", "fleuves_europe"):
        geo = telecharger(source)
        for f in geo["features"]:
            nom = f["properties"].get("name")
            f["properties"]["name"] = NOMS_CORRIGES.get(nom, nom)
        objets += extraire(geo, ["name"], lambda p: p.get("name") in fleuves)
    ecrire("fleuves", objets)


if __name__ == "__main__":
    main()
