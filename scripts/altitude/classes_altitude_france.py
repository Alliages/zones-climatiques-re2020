"""Classes d'altitude RE2020 sur la France métropolitaine (étape 1 / 2).

Lit le MNT agrégé à ~500 m, vectorise deux classes (400–800 m et > 800 m),
les découpe à la France et écrit un GeoJSON brut, simplifié ensuite par
simplifier_altitude.py.

Usage (depuis la racine du dépôt) :
  python3 scripts/altitude/classes_altitude_france.py <mnt.tif> <dossier_sortie>
"""
import json
import os
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from geo_utils import arrondir, fusionner, km2, lire_json, parties   # noqa: E402

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête)
# ---------------------------------------------------------------------------
MNT_PATH, OUT_DIR = sys.argv[1:3]
DEPARTEMENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                 "data", "fonds", "departements.geojson")
BOUNDS = (-5.3, 41.3, 9.7, 51.2)        # emprise métropole + Corse (lon/lat)
AGREG = 6                               # 90 m × 6 ≈ 500 m : largement suffisant à l'échelle de la carte
SIMPLIFY_DEG = 0.005                    # simplification (~400 m)
NODATA = 0.0
CLASSES = {"400-800": (400, 800), "800+": (800, 10000)}   # nom → (min inclus, max exclu)
DECIMALES = 4                           # précision des coordonnées écrites (~10 m)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Contour de la France (union des départements) pour le découpage
    france = fusionner([shape(f["geometry"]) for f in lire_json(DEPARTEMENTS_PATH)["features"]])

    # Lecture agrégée du MNT (une seule lecture, moyenne par blocs)
    with rasterio.open(MNT_PATH) as src:
        win = from_bounds(*BOUNDS, src.transform)
        h, w = int(win.height) // AGREG, int(win.width) // AGREG
        alt = src.read(1, window=win, out_shape=(h, w), resampling=Resampling.average).astype("float32")
        tr = src.window_transform(win) * rasterio.Affine.scale(win.width / w, win.height / h)
    alt[alt == NODATA] = np.nan
    print(f"  grille {w} × {h} px, altitude max {np.nanmax(alt):.0f} m")

    # Vectorisation des deux classes, découpage à la France
    features = []
    for nom, (amin, amax) in CLASSES.items():
        masque = ((alt >= amin) & (alt < amax)).astype("uint8")
        polys = [shape(g) for g, v in shapes(masque, mask=masque == 1, transform=tr) if v == 1]
        geom = unary_union(polys).simplify(SIMPLIFY_DEG, preserve_topology=True).buffer(0).intersection(france)
        part = 100 * sum(km2(p) for p in parties(geom)) / sum(km2(p) for p in parties(france))
        print(f"  {nom:8s} {part:5.1f} % du territoire")
        m = mapping(geom)
        m["coordinates"] = arrondir(m["coordinates"], DECIMALES)
        features.append({"type": "Feature", "properties": {"classe": nom}, "geometry": m})

    sortie = os.path.join(OUT_DIR, "classes_altitude_re2020.geojson")
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))
    print(f"  GeoJSON : {os.path.getsize(sortie) / 1024:.0f} Ko → {sortie}")


if __name__ == "__main__":
    main()
