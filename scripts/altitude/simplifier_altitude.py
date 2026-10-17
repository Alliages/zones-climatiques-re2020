"""Simplifie la couche « Altitude » sans relire le MNT.

Part du GeoJSON des classes (400-800 et 800+), reconstruit deux surfaces emboîtées :
  - « 400+ » = tout ce qui dépasse 400 m (porte les hachures à 45°)
  - « 800+ » = ce qui dépasse 800 m (ajoute les hachures à 135°)
puis, pour chacune : supprime les îlots et bouche les trous de moins de SURFACE_MIN_KM2,
simplifie le contour, et garde « 800+ » à l'intérieur de « 400+ ».

Usage : python3 -I simplifier_altitude.py <classes.geojson> <sortie.geojson>
"""
import json
import math
import os
import sys

from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête)
# ---------------------------------------------------------------------------
IN_PATH, OUT_PATH = sys.argv[1:3]
SURFACE_MIN_KM2 = 70          # îlots et trous plus petits que ce seuil : supprimés / bouchés
SIMPLIFY_DEG = 0.01           # tolérance de simplification (~1 km)
KM_PAR_DEG = 111.32           # longueur d'un degré de latitude (km)

def km2(p):
    """Surface approchée d'un polygone lon/lat en km² (correction de latitude au centroïde)."""
    return p.area * KM_PAR_DEG ** 2 * math.cos(math.radians(p.centroid.y))

def parties(g):
    return list(g.geoms) if isinstance(g, MultiPolygon) else ([g] if isinstance(g, Polygon) else
            [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)])

def nettoyer(g):
    """Supprime les petits îlots, bouche les petits trous, simplifie."""
    garde = []
    for p in parties(g):
        if km2(p) < SURFACE_MIN_KM2:
            continue
        trous = [r for r in p.interiors if km2(Polygon(r)) >= SURFACE_MIN_KM2]
        garde.append(Polygon(p.exterior, trous))
    g = unary_union(garde).simplify(SIMPLIFY_DEG, preserve_topology=True).buffer(0)
    # La simplification peut recréer de minuscules morceaux : second filtrage
    return unary_union([p for p in parties(g) if km2(p) >= SURFACE_MIN_KM2])

def arrondir(o, n=3):
    if isinstance(o, (list, tuple)):
        return [arrondir(x, n) for x in o]
    return round(o, n) if isinstance(o, float) else o

# ---------------------------------------------------------------------------
# Traitement
# ---------------------------------------------------------------------------
classes = {f["properties"]["classe"]: shape(f["geometry"]) for f in json.load(open(IN_PATH))["features"]}
brut = {"400+": unary_union([classes["400-800"], classes["800+"]]).buffer(0), "800+": classes["800+"]}

net = {k: nettoyer(g) for k, g in brut.items()}
net["800+"] = net["800+"].intersection(net["400+"])          # 800+ toujours inclus dans 400+

features = []
for k, g in net.items():
    print(f"  {k:5s} polygones {len(parties(brut[k])):6d} → {len(parties(g)):4d}   "
          f"surface {sum(km2(p) for p in parties(brut[k])):8.0f} → {sum(km2(p) for p in parties(g)):8.0f} km²")
    m = mapping(g)
    m["coordinates"] = arrondir(m["coordinates"])
    features.append({"type": "Feature", "properties": {"classe": k}, "geometry": m})

json.dump({"type": "FeatureCollection", "features": features}, open(OUT_PATH, "w"), separators=(",", ":"))
print(f"  GeoJSON : {os.path.getsize(IN_PATH) / 1024:.0f} Ko → {os.path.getsize(OUT_PATH) / 1024:.0f} Ko")
