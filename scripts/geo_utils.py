"""Outils géographiques communs aux scripts de la carte (génération, altitude, fonds).

- lecture des données : GeoJSON, tables texte à séparateur « | »
- géométrie : parties d'un polygone, fusion, surface en km², arrondi des coordonnées
- projection lon/lat → viewBox SVG et chemins SVG compacts (coordonnées relatives arrondies)
"""
import json
import math

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import polylabel, unary_union

KM_PAR_DEG = 111.32           # longueur d'un degré de latitude (km)
EPS_FUSION = 0.002            # marge de fusion (degrés) : referme les micro-interstices entre polygones voisins


# ---------------------------------------------------------------------------
# Lecture des données
# ---------------------------------------------------------------------------
def lire_json(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def lire_table(chemin):
    """Fichier texte à séparateur « | » avec ligne d'en-tête → liste de dictionnaires."""
    with open(chemin, encoding="utf-8") as f:
        lignes = f.read().strip().splitlines()
    cles = lignes[0].split("|")
    return [dict(zip(cles, ligne.split("|"))) for ligne in lignes[1:]]


# ---------------------------------------------------------------------------
# Géométrie
# ---------------------------------------------------------------------------
def parties(g):
    """Liste des polygones d'une géométrie (Polygon, MultiPolygon ou collection)."""
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]


def plus_grande_partie(g):
    return max(parties(g), key=lambda p: p.area)


def fusionner(geoms, eps=EPS_FUSION):
    """Union de polygones voisins sans liseré parasite (dilatation puis érosion de eps)."""
    return unary_union([g.buffer(eps) for g in geoms]).buffer(-eps)


def km2(p):
    """Surface approchée d'un polygone lon/lat en km² (correction de latitude au centroïde)."""
    return p.area * KM_PAR_DEG ** 2 * math.cos(math.radians(p.centroid.y))


def arrondir(o, n):
    """Arrondit récursivement les coordonnées d'une géométrie GeoJSON à n décimales."""
    if isinstance(o, (list, tuple)):
        return [arrondir(x, n) for x in o]
    return round(o, n) if isinstance(o, float) else o


# ---------------------------------------------------------------------------
# Chemins SVG compacts
# ---------------------------------------------------------------------------
def _nombre(n, decimales):
    """Entier n (valeur × 10^decimales) → texte le plus court : 12.5, -.5, 3, 0."""
    signe = "-" if n < 0 else ""
    entier, frac = divmod(abs(n), 10 ** decimales)
    texte = str(entier) if entier else ""
    if frac:
        texte += "." + f"{frac:0{decimales}d}".rstrip("0")
    return signe + (texte or "0")


def _suite(nombres):
    """Joint des nombres SVG avec le moins de séparateurs possible (« 1.5.5 », « 2-3 »)."""
    sortie = []
    for i, t in enumerate(nombres):
        if i and not t.startswith("-") and not (t.startswith(".") and "." in nombres[i - 1]):
            sortie.append(" ")
        sortie.append(t)
    return "".join(sortie)


def chemin_svg(g, pas=0.5):
    """Attribut « d » d'une géométrie déjà projetée (pixels du viewBox).

    Coordonnées arrondies au multiple de `pas` (0.5 → 12, 12.5, 13…), premier point absolu
    puis déplacements relatifs ; les points confondus après arrondi sont retirés et les
    anneaux dégénérés ignorés.
    """
    if g.is_empty:
        return ""
    t = g.geom_type
    if t == "Polygon":
        return "".join(_anneau(r.coords, pas, True) for r in [g.exterior, *g.interiors])
    if t == "LineString":
        return _anneau(g.coords, pas, False)
    if t in ("MultiPolygon", "MultiLineString", "GeometryCollection"):
        return "".join(chemin_svg(p, pas) for p in g.geoms)
    return ""                                   # points isolés : rien à tracer


def _anneau(coords, pas, ferme):
    decimales = len(repr(float(pas)).split(".")[1].rstrip("0"))     # 0.5 → 1, 0.25 → 2, 1 → 0
    unite = round(pas * 10 ** decimales)                             # pas exprimé en 10^-decimales
    pts = []
    for x, y in coords:
        q = (round(x / pas) * unite, round(y / pas) * unite)
        if not pts or q != pts[-1]:
            pts.append(q)
    if ferme and len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()                               # « z » referme l'anneau
    if len(pts) < (3 if ferme else 2):
        return ""
    absolu = _suite([_nombre(v, decimales) for v in pts[0]])
    deltas = [_nombre(b[k] - a[k], decimales) for a, b in zip(pts, pts[1:]) for k in (0, 1)]
    return "M" + absolu + "l" + _suite(deltas) + ("z" if ferme else "")


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------
class Projection:
    """Équirectangulaire corrigée en latitude, cadrée sur une emprise avec une marge en pixels."""

    def __init__(self, bounds, largeur, marge, lat0, pas=0.5):
        self.lon0, _, _, self.lat_haut = bounds
        self.coslat = math.cos(math.radians(lat0))
        self.marge = marge
        self.largeur = largeur
        self.pas = pas                          # précision des chemins SVG (unités du viewBox)
        self.echelle = (largeur - 2 * marge) / ((bounds[2] - bounds[0]) * self.coslat)
        self.hauteur = round((bounds[3] - bounds[1]) * self.echelle + 2 * marge)

    def xy(self, lon, lat):
        return ((lon - self.lon0) * self.coslat * self.echelle + self.marge,
                (self.lat_haut - lat) * self.echelle + self.marge)

    def projeter(self, g):
        """Géométrie lon/lat → géométrie en pixels du viewBox."""
        return shapely.transform(g, lambda c: np.column_stack(self.xy(c[:, 0], c[:, 1])))

    def emprise_deg(self):
        """Emprise du viewBox en degrés : (lon min, lat min, lon max, lat max)."""
        return (self.lon0 - self.marge / (self.echelle * self.coslat),
                self.lat_haut - (self.hauteur - self.marge) / self.echelle,
                self.lon0 + (self.largeur - self.marge) / (self.echelle * self.coslat),
                self.lat_haut + self.marge / self.echelle)

    def point_etiquette(self, g, tolerance=0.01):
        """Point d'étiquette (pôle d'inaccessibilité de la plus grande partie), en pixels."""
        pt = polylabel(plus_grande_partie(g), tolerance=tolerance)
        return self.xy(pt.x, pt.y)

    def chemin(self, g, simplification_px=0.0):
        """Attribut « d » d'une géométrie lon/lat, simplifiée de `simplification_px` après projection."""
        g = self.projeter(g)
        if simplification_px:
            g = g.simplify(simplification_px)
        return chemin_svg(g, self.pas)
