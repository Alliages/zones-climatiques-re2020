"""Classes d'altitude RE2020 sur la France métropolitaine (version simple).

Lit le MNT agrégé à ~500 m, vectorise deux classes (400–800 m et > 800 m),
les découpe à la France, écrit un GeoJSON et un aperçu comparant ces classes
aux massifs montagneux de la carte actuelle.

Usage : python3 -I classes_altitude_france.py <mnt.tif> <dossier_geo> <dossier_sortie>
"""
import json
import os
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.windows import from_bounds
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête)
# ---------------------------------------------------------------------------
MNT_PATH, GEO_DIR, OUT_DIR = sys.argv[1:4]
BOUNDS = (-5.3, 41.3, 9.7, 51.2)        # emprise métropole + Corse (lon/lat)
AGREG = 6                               # 90 m × 6 ≈ 500 m : largement suffisant à l'échelle de la carte
SIMPLIFY_DEG = 0.005                    # simplification (~400 m)
NODATA = 0.0
CLASSES = {"400-800": (400, 800), "800+": (800, 10000)}   # nom → (min inclus, max exclu)
MASSIFS = {"ALPS", "PYRENEES", "Massif Central", "Jura", "Vosges"}
COULEUR_RELIEF = "#6b4a2b"              # même brun que la couche « massifs » de la carte
VILLES = [("Paris", 2.35, 48.86), ("Lyon", 4.84, 45.76), ("Grenoble", 5.72, 45.19),
          ("Clermont-Fd", 3.09, 45.78), ("Toulouse", 1.44, 43.60), ("Strasbourg", 7.75, 48.58)]

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Contour de la France (union des départements) pour le découpage
# ---------------------------------------------------------------------------
deps = json.load(open(f"{GEO_DIR}/dep.geojson", encoding="utf-8"))
france = unary_union([shape(f["geometry"]).buffer(0.002) for f in deps["features"]]).buffer(-0.002)

# ---------------------------------------------------------------------------
# Lecture agrégée du MNT (une seule lecture, moyenne par blocs)
# ---------------------------------------------------------------------------
with rasterio.open(MNT_PATH) as src:
    win = from_bounds(*BOUNDS, src.transform)
    h, w = int(win.height) // AGREG, int(win.width) // AGREG
    alt = src.read(1, window=win, out_shape=(h, w), resampling=Resampling.average).astype("float32")
    tr = src.window_transform(win) * rasterio.Affine.scale(win.width / w, win.height / h)
alt[alt == NODATA] = np.nan
print(f"  grille {w} × {h} px, altitude max {np.nanmax(alt):.0f} m")

# ---------------------------------------------------------------------------
# Vectorisation des deux classes, découpage à la France
# ---------------------------------------------------------------------------
features, geoms = [], {}
for nom, (amin, amax) in CLASSES.items():
    masque = ((alt >= amin) & (alt < amax)).astype("uint8")
    polys = [shape(g) for g, v in shapes(masque, mask=masque == 1, transform=tr) if v == 1]
    geom = unary_union(polys).simplify(SIMPLIFY_DEG, preserve_topology=True).buffer(0).intersection(france)
    geoms[nom] = geom
    features.append({"type": "Feature", "properties": {"classe": nom}, "geometry": mapping(geom)})

def arrondir(o, n=4):
    if isinstance(o, (list, tuple)):
        return [arrondir(x, n) for x in o]
    return round(o, n) if isinstance(o, float) else o

for f in features:
    f["geometry"]["coordinates"] = arrondir(f["geometry"]["coordinates"])
gj = os.path.join(OUT_DIR, "classes_altitude_re2020.geojson")
json.dump({"type": "FeatureCollection", "features": features}, open(gj, "w"), separators=(",", ":"))
print(f"  GeoJSON : {os.path.getsize(gj) / 1024:.0f} Ko")

# Part du territoire par classe (approximation en degrés², corrigée de la latitude)
def aire(g):
    return g.area * np.cos(np.radians(46.5))
tot = aire(france)
for nom, g in geoms.items():
    print(f"  {nom:8s} {100 * aire(g) / tot:5.1f} % du territoire")

# ---------------------------------------------------------------------------
# Aperçu : massifs actuels (gauche) / classes d'altitude hachurées (droite)
# ---------------------------------------------------------------------------
def patch(g, **kw):
    """Convertit un (multi)polygone shapely en PathPatch matplotlib (trous compris)."""
    verts, codes = [], []
    for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
        for ring in [p.exterior, *p.interiors]:
            xy = np.asarray(ring.coords)
            verts += xy.tolist()
            codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
    return PathPatch(Path(verts, codes), **kw)

regions = json.load(open(f"{GEO_DIR}/ne_10m_geography_regions_polys.geojson", encoding="utf-8"))
massifs = unary_union([shape(f["geometry"]).buffer(0) for f in regions["features"]
                       if f["properties"].get("NAME") in MASSIFS]).intersection(france)

plt.rcParams["hatch.color"] = COULEUR_RELIEF
fig, axes = plt.subplots(1, 2, figsize=(14, 7.2), dpi=110)
for ax, titre in zip(axes, ["Actuel : massifs (Natural Earth)", "Proposé : classes d'altitude RE2020 (MNT)"]):
    ax.add_patch(patch(france, facecolor="#f6bd3a", alpha=0.35, edgecolor="#46260a", lw=0.8))
    ax.set_xlim(BOUNDS[0], BOUNDS[2]); ax.set_ylim(BOUNDS[1], BOUNDS[3])
    ax.set_aspect(1 / np.cos(np.radians(46.5)))
    ax.set_title(titre, fontsize=12)
    ax.axis("off")
    for nom, lon, lat in VILLES:
        ax.plot(lon, lat, "o", color="#2b2219", ms=3.5)
        ax.annotate(nom, (lon, lat), xytext=(4, 3), textcoords="offset points", fontsize=8.5, color="#2b2219")
axes[0].add_patch(patch(massifs, facecolor="none", edgecolor=COULEUR_RELIEF, hatch="////", lw=1.0, ls="--"))
axes[1].add_patch(patch(geoms["400-800"], facecolor="none", edgecolor="none", hatch="//"))
axes[1].add_patch(patch(geoms["800+"], facecolor="none", edgecolor="none", hatch="//////"))
axes[1].add_patch(patch(unary_union(list(geoms.values())), facecolor="none", edgecolor=COULEUR_RELIEF, lw=0.5))
# Légende manuelle
for y, h, lab in [(0.08, "//", "400 – 800 m"), (0.03, "//////", "> 800 m")]:
    axes[1].add_patch(plt.Rectangle((0.70, y), 0.05, 0.035, transform=axes[1].transAxes,
                                    facecolor="none", edgecolor=COULEUR_RELIEF, hatch=h, lw=0.6))
    axes[1].text(0.77, y + 0.008, lab, transform=axes[1].transAxes, fontsize=9, color="#2b2219")
fig.tight_layout()
png = os.path.join(OUT_DIR, "comparaison_massifs_altitude.png")
fig.savefig(png)
print("  aperçu :", png)
