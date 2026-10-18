"""Outils géographiques communs aux scripts de la carte (génération, altitude, fonds).

- lecture des données : GeoJSON, tables texte à séparateur « | »
- géométrie : parties d'un polygone, fusion, surface en km², arrondi des coordonnées
- projection lon/lat → viewBox SVG et écriture des chemins SVG
"""
import json
import math

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
# Projection et chemins SVG
# ---------------------------------------------------------------------------
class Projection:
    """Équirectangulaire corrigée en latitude, cadrée sur une emprise avec une marge en pixels."""

    def __init__(self, bounds, largeur, marge, lat0):
        self.lon0, self.lat0_bas, _, self.lat_haut = bounds
        self.coslat = math.cos(math.radians(lat0))
        self.marge = marge
        self.largeur = largeur
        self.echelle = (largeur - 2 * marge) / ((bounds[2] - bounds[0]) * self.coslat)
        self.hauteur = round((bounds[3] - bounds[1]) * self.echelle + 2 * marge)

    def xy(self, lon, lat):
        return ((lon - self.lon0) * self.coslat * self.echelle + self.marge,
                (self.lat_haut - lat) * self.echelle + self.marge)

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

    def _anneau(self, coords, fermer=True):
        pts = [self.xy(x, y) for x, y in coords]
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + ("Z" if fermer else "")

    def chemin(self, g):
        """Attribut « d » SVG d'un polygone, multipolygone, ligne ou multiligne."""
        if g.is_empty:
            return ""
        t = g.geom_type
        if t == "Polygon":
            return self._anneau(g.exterior.coords) + "".join(self._anneau(i.coords) for i in g.interiors)
        if t in ("MultiPolygon", "GeometryCollection", "MultiLineString"):
            return "".join(self.chemin(p) for p in g.geoms)
        if t == "LineString":
            return self._anneau(g.coords, fermer=False)
        return ""
