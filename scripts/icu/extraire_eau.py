"""Surfaces en eau (LCZ G, lcz_int = 17) d'un territoire LCZ : fleuves, rivières larges, plans d'eau.

Usage : python3 scripts/icu/extraire_eau.py <dossier_shp_du_territoire> <sortie.json>
Sortie : GeoJSON (EPSG:4326) de l'union simplifiée, petites parties écartées.
"""
import glob
import json
import sys

import numpy as np
import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import mapping, shape

# --- Réglages ---------------------------------------------------------------
DOSSIER, SORTIE = sys.argv[1], sys.argv[2]
CLASSE_EAU = 17               # LCZ G
SIMPL_M = 8.0                 # simplification (m)
PARTIE_MIN_M2 = 30_000        # parties plus petites écartées (3 ha)
DECIMALES = 5

VERS_4326 = Transformer.from_crs(2154, 4326, always_xy=True)

r = shapefile.Reader(glob.glob(f"{DOSSIER}/*.shp")[0])
idx = [f[0] for f in r.fields[1:]].index("lcz_int")
# Lecture des seuls enregistrements « eau » (la géométrie n'est lue que pour eux)
eau = [shape(r.shape(i).__geo_interface__) for i, rec in enumerate(r.iterRecords(fields=["lcz_int"]))
       if rec[0] == CLASSE_EAU]
g = shapely.union_all(shapely.make_valid(np.array(eau, dtype=object))) if eau else shapely.Polygon()
g = g.simplify(SIMPL_M)
parts = [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area >= PARTIE_MIN_M2]
g = shapely.MultiPolygon(parts) if parts else shapely.Polygon()
g = shapely.set_precision(shapely.transform(g, lambda c: np.column_stack(VERS_4326.transform(c[:, 0], c[:, 1]))),
                          10 ** -DECIMALES)
json.dump(mapping(g), open(SORTIE, "w"), separators=(",", ":"))
print(f"{len(eau)} polygones eau → {len(parts)} parties, {sum(p.area for p in parts) / 1e6:.2f} km²")
