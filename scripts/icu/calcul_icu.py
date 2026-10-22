"""Variante 1 « voisines directes » sur un territoire LCZ (Cerema).

Usage : python3 scripts/icu/calcul_icu.py <dossier_shp_du_territoire> <sortie.json>

Méthode (validée sur Annemasse : 0,71 km², 7 enveloppes, 1,06 km²) :
  - noyau = LCZ 1–3 ;
  - voisines = LCZ 4–6 à ≤ 15 m d'un polygone du noyau (pas de propagation) ;
  - groupes = éléments distants de ≤ 15 m ; enveloppe convexe par groupe ;
  - emprise du territoire (contexte du zoom).
Sortie en EPSG:4326 (coordonnées arrondies à 1e-5 °, ~1 m) avec les surfaces en km².
Tous les îlots sont gardés ici ; le seuil de surface (10 ha) est appliqué par preparer_icu.py.
"""
import glob
import json
import sys
import time

import numpy as np
import shapefile
import shapely
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import mapping, shape

# --- Réglages ---------------------------------------------------------------
DOSSIER, SORTIE = sys.argv[1], sys.argv[2]
NOYAU = {1, 2, 3}
VOISINES = {4, 5, 6}
ECART_M = 15.0                 # écart toléré (largeur de rue)
SIMPL_SEL_M = 2.0              # simplification de la sélection et du noyau (zoom)
SIMPL_EMPRISE_M = 30.0         # simplification de l'emprise du territoire
SEUIL_LISSAGE = 20_000           # nombre d'éléments au-delà duquel on lisse avant les unions
SEUIL_EMPRISE = 150_000        # au-delà : emprise par enveloppe concave (contexte du zoom seulement)
LISSAGE_M = 1.0                # tolérance du lissage (m)
DECIMALES = 5                  # arrondi des coordonnées (degrés)

VERS_4326 = Transformer.from_crs(2154, 4326, always_xy=True)


def en_4326(g):
    """Lambert 93 → WGS 84, coordonnées arrondies."""
    g = shapely.transform(g, lambda c: np.column_stack(VERS_4326.transform(c[:, 0], c[:, 1])))
    return shapely.set_precision(g, 10 ** -DECIMALES)


def etape(nom, t0=[time.time()]):
    """Trace du temps écoulé par étape (stderr)."""
    print(f"  {time.time() - t0[0]:7.1f} s  {nom}", file=sys.stderr, flush=True)


def main():
    t0 = time.time()
    shp = glob.glob(f"{DOSSIER}/*.shp")[0]
    r = shapefile.Reader(shp)
    idx = [f[0] for f in r.fields[1:]].index("lcz_int")
    geoms, classes = [], []
    for s, rec in zip(r.iterShapes(), r.iterRecords()):
        if not s.points:
            continue
        geoms.append(shape(s.__geo_interface__))
        classes.append(rec[idx])
    geoms = shapely.make_valid(np.array(geoms, dtype=object))
    classes = np.array(classes)
    etape("lecture")

    noyau = geoms[np.isin(classes, list(NOYAU))]
    voisines = geoms[np.isin(classes, list(VOISINES))]

    # Voisines directes : à ≤ 15 m d'un polygone du noyau
    if len(noyau):
        arbre = STRtree(noyau)
        idx_v, _ = arbre.query(voisines, predicate="dwithin", distance=ECART_M)
        retenues = voisines[np.unique(idx_v)]
    else:
        retenues = voisines[:0]
    etape("voisines")
    elements = np.concatenate([noyau, retenues])
    # Grands territoires : contours en escalier (raster 1,5 m vectorisé) lissés à 1 m avant les unions,
    # qui sinon prennent des dizaines de minutes (Paris) ; écart de surface négligeable
    if len(elements) > SEUIL_LISSAGE:
        elements = shapely.make_valid(shapely.simplify(elements, LISSAGE_M))
        noyau = elements[:len(noyau)]
    selection = shapely.union_all(elements) if len(elements) else shapely.Polygon()
    etape("union sélection")

    # Groupes (≤ 15 m) et enveloppe convexe par groupe
    # Chaque élément est rattaché à sa composante dilatée par index spatial, puis l'enveloppe
    # convexe est prise sur les éléments du groupe : même résultat que l'intersection
    # sélection ∩ composante, sans le coût quadratique (Paris : des milliers de composantes)
    enveloppes = []
    if len(elements):
        dilate = shapely.union_all(shapely.buffer(elements, ECART_M / 2, quad_segs=2))
        comps = np.array(list(getattr(dilate, "geoms", [dilate])), dtype=object)
        etape("dilatation")
        idx_e, idx_c = STRtree(comps).query(shapely.point_on_surface(elements), predicate="intersects")
        groupes = {}
        for e, c in zip(idx_e, idx_c):
            groupes.setdefault(int(c), []).append(int(e))
        for membres in groupes.values():
            enveloppes.append(shapely.convex_hull(shapely.GeometryCollection(list(elements[membres]))))
    union_env = shapely.union_all(enveloppes) if enveloppes else shapely.Polygon()
    etape("enveloppes")

    # Emprise du territoire : polygones simplifiés (10 m) et légèrement dilatés avant l'union,
    # bien plus rapide que l'union brute (Montauban : 17 s au lieu de 270 s), puis refermée
    if len(geoms) <= SEUIL_EMPRISE:
        grossiers = shapely.buffer(shapely.simplify(geoms, 10), 5, quad_segs=1)
        emprise = shapely.union_all(grossiers).buffer(-5).simplify(SIMPL_EMPRISE_M)
    else:   # Paris (156 000 polygones) : l'union ne termine pas, enveloppe concave des polygones
        pts = shapely.MultiPoint(list(shapely.point_on_surface(geoms)))
        emprise = shapely.concave_hull(pts, ratio=0.01).buffer(1000).buffer(-1000).simplify(SIMPL_EMPRISE_M)   # lissée
    etape("emprise")

    out = {
        "stats": {
            "polygones": int(len(geoms)),
            "territoire_km2": round(float(shapely.area(geoms).sum()) / 1e6, 2),   # partition : somme des aires
            "noyau_km2": round(shapely.union_all(noyau).area / 1e6, 3) if len(noyau) else 0,
            "selection_km2": round(selection.area / 1e6, 3),
            "voisines": int(len(retenues)),
            "groupes": len(enveloppes),
            "icu_km2": round(union_env.area / 1e6, 3),
            "duree_s": None,
        },
        "enveloppes": [{"ha": round(e.area / 1e4, 1), "g": mapping(en_4326(e))}
                       for e in sorted(enveloppes, key=lambda e: -e.area)],
        "selection": mapping(en_4326(selection.simplify(SIMPL_SEL_M))),
        "noyau": mapping(en_4326(shapely.union_all(noyau).simplify(SIMPL_SEL_M))) if len(noyau) else None,
        "emprise": mapping(en_4326(emprise)),
    }
    out["stats"]["duree_s"] = round(time.time() - t0, 1)
    with open(SORTIE, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(json.dumps(out["stats"]))


if __name__ == "__main__":
    main()
