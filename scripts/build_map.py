"""Carte des zones climatiques RE2020.

Couches : mers en dégradé, pays voisins, départements, limites de zones,
lacs, fleuves, massifs montagneux, libellés (zones, villes, départements, pays, mers),
nombre de logements (INSEE, RP 2022) par département et par zone.

Usage :
  python3 -I build_map.py <dossier_geo> <zones.txt> <template.html> <sortie_artifact.html>
                          <logements.txt> <sortie_index.html>
"""
import datetime
import json
import math
import sys

from shapely.geometry import shape, box, mapping, Polygon
from shapely.ops import unary_union, polylabel

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête pour la lisibilité)
# ---------------------------------------------------------------------------
VERSION = "1.0.1"             # version de la carte (SemVer) — à reporter dans CHANGELOG.md et en tag git
BUILD_DATE = datetime.date.today().strftime("%d/%m/%Y")   # date de génération affichée en pied de page
REPO_URL = "https://github.com/Alliages/zones-climatiques-re2020"
GEO_DIR, TABLE_PATH, TEMPLATE_PATH, OUT_PATH, LOGEMENTS_PATH, INDEX_PATH = sys.argv[1:7]
DEP_LABEL_CODES_ONLY = {"75", "92", "93", "94", "90"}   # départements trop petits : numéro seul
DEP_LABEL_MAXLEN = 11                                   # au-delà, le nom passe sur deux lignes
VIEW_W = 1000                 # largeur du viewBox SVG
LAT0 = 46.5                   # latitude de référence de la projection
PAD = 42                      # marge autour de la France (place pour mers et voisins)
SIMPLIFY_DEG = 0.004          # simplification des couches de contexte (degrés)

ZONES = ["H1a", "H1b", "H1c", "H2a", "H2b", "H2c", "H2d", "H3"]

# Fleuves retenus (noms tels qu'écrits dans Natural Earth)
RIVERS_MAIN = {"Seine", "Loire", "Garonne", "Rhône", "Rhne", "Rhin", "Rhine", "Rhein",
               "Dordogne", "Mosel", "Maas"}
RIVERS_SECOND = {"Marne", "Yonne", "Saône", "Sane", "Doubs", "Tarn", "Durance", "Vienne",
                 "Lot", "Allier", "Cher", "Creuse", "Charente", "Vilaine", "Adour",
                 "Somme", "Aveyron", "Ariège", "Sarthe", "Mayenne", "Aube", "Eure", "Oise",
                 "Aude", "Ill", "Sarre"}

# Massifs montagneux (nom Natural Earth → libellé affiché)
MASSIFS = {"ALPS": "Alpes", "PYRENEES": "Pyrénées", "Massif Central": "Massif central",
           "Jura": "Jura", "Vosges": "Vosges"}

# Villes repères : (nom, lon, lat, position du libellé : start=droite, end=gauche, below=dessous)
CITIES = [
    ("Paris", 2.35, 48.86, "end"), ("Lille", 3.06, 50.63, "start"),
    ("Rouen", 1.10, 49.44, "end"), ("Caen", -0.37, 49.18, "end"),
    ("Reims", 4.03, 49.26, "start"), ("Strasbourg", 7.75, 48.58, "start"),
    ("Brest", -4.49, 48.39, "start"), ("Rennes", -1.68, 48.11, "start"),
    ("Nantes", -1.55, 47.22, "start"), ("Orléans", 1.91, 47.90, "start"),
    ("Tours", 0.69, 47.39, "end"), ("Dijon", 5.04, 47.32, "start"),
    ("Besançon", 6.02, 47.24, "start"), ("Poitiers", 0.34, 46.58, "start"),
    ("Limoges", 1.26, 45.83, "start"), ("Clermont-Ferrand", 3.09, 45.78, "below"),
    ("Lyon", 4.84, 45.76, "start"), ("Grenoble", 5.72, 45.19, "start"),
    ("Valence", 4.89, 44.93, "start"), ("Avignon", 4.81, 43.95, "end"),
    ("Bordeaux", -0.58, 44.84, "end"), ("Agen", 0.62, 44.20, "start"),
    ("Pau", -0.37, 43.30, "end"),
    ("Toulouse", 1.44, 43.60, "start"), ("Montpellier", 3.88, 43.61, "start"),
    ("Marseille", 5.37, 43.30, "start"), ("Nice", 7.26, 43.70, "end"),
    ("Perpignan", 2.90, 42.70, "start"), ("Ajaccio", 8.74, 41.93, "end"),
]

# Libellés de contexte (pays et mers) : (texte, lon, lat, classe)
CONTEXT_LABELS = [
    ("Royaume-Uni", 0.2, 51.05, "country"), ("Belgique", 4.65, 50.62, "country"),
    ("Allemagne", 8.75, 49.25, "country"), ("Suisse", 7.55, 46.85, "country"),
    ("Italie", 8.25, 44.85, "country"), ("Espagne", -0.9, 41.95, "country"),
    ("Manche", -2.6, 49.95, "sea"), ("Océan Atlantique", -3.7, 45.6, "sea"),
    ("Mer Méditerranée", 6.4, 42.45, "sea"),
]

# Décalages manuels des étiquettes de zones (pixels du viewBox), si besoin
ZONE_LABEL_NUDGE = {"H2a": (35, 22), "H2b": (-40, 40), "H2c": (-55, 20),
                    "H1b": (-70, -15), "H3": (-10, -6), "H2d": (-35, 35)}

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
def load(name):
    return json.load(open(f"{GEO_DIR}/{name}.geojson", encoding="utf-8"))

deps_geo = load("dep")
data = {}
for line in open(TABLE_PATH, encoding="utf-8").read().strip().splitlines():
    reg, code, nom, zone = line.split("|")
    data[code] = {"r": reg, "n": nom, "z": zone}

# Logements INSEE (RP 2022) : nom|total|% résidences principales|% secondaires|% vacants
for line in open(LOGEMENTS_PATH, encoding="utf-8").read().strip().splitlines():
    nom, total, p_rp, p_rs, p_vac = line.split("|")
    code = next(c for c, v in data.items() if v["n"] == nom)
    data[code].update({"l": int(total), "rp": float(p_rp), "rs": float(p_rs), "lv": float(p_vac)})

dep_shapes = {f["properties"]["code"]: shape(f["geometry"]).buffer(0) for f in deps_geo["features"]}
france = unary_union([g.buffer(0.002) for g in dep_shapes.values()]).buffer(-0.002)

# ---------------------------------------------------------------------------
# Projection (équirectangulaire corrigée en latitude) et cadrage
# ---------------------------------------------------------------------------
COSLAT = math.cos(math.radians(LAT0))
fminx, fminy, fmaxx, fmaxy = france.bounds
scale = (VIEW_W - 2 * PAD) / ((fmaxx - fminx) * COSLAT)
VIEW_H = round((fmaxy - fminy) * scale + 2 * PAD)

def proj(lon, lat):
    return ((lon - fminx) * COSLAT * scale + PAD, (fmaxy - lat) * scale + PAD)

# Emprise du viewBox en degrés (pour découper les couches de contexte)
view_lon0 = fminx - PAD / (scale * COSLAT)
view_lon1 = fminx + (VIEW_W - PAD) / (scale * COSLAT)
view_lat1 = fmaxy + PAD / scale
view_lat0 = fmaxy - (VIEW_H - PAD) / scale
VIEW_BOX_DEG = box(view_lon0 - 0.3, view_lat0 - 0.3, view_lon1 + 0.3, view_lat1 + 0.3)

def ring_d(coords, close=True):
    pts = [proj(x, y) for x, y in coords]
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + ("Z" if close else "")

def geom_d(g):
    """Chemin SVG pour un polygone, multipolygone, ligne ou multiligne."""
    if g.is_empty:
        return ""
    t = g.geom_type
    if t == "Polygon":
        return ring_d(g.exterior.coords) + "".join(ring_d(i.coords) for i in g.interiors)
    if t in ("MultiPolygon", "GeometryCollection", "MultiLineString"):
        return "".join(geom_d(p) for p in g.geoms)
    if t == "LineString":
        return ring_d(g.coords, close=False)
    return ""

def boundary_d(g):
    """Contour (lignes) d'une surface."""
    return geom_d(g.boundary)

# ---------------------------------------------------------------------------
# Couches
# ---------------------------------------------------------------------------
# 1. Départements
# Les enclaves (ex. Enclave des Papes : îlot du Vaucluse entouré par la Drôme) sont
# détectées automatiquement : le département hôte est dessiné sans son trou, et
# l'îlot est posé par-dessus dans un chemin à part, sans liseré (classe « enclave »).
def polygon_parts(g):
    return list(g.geoms) if g.geom_type == "MultiPolygon" else [g]

hosts = {c: Polygon(max(polygon_parts(g), key=lambda p: p.area).exterior)
         for c, g in dep_shapes.items()}
enclaves = []                      # (code de l'enclave, polygone)
host_codes = set()                 # départements qui contiennent une enclave
for c, g in dep_shapes.items():
    for part in polygon_parts(g):
        for h, hull in hosts.items():
            if h != c and hull.contains(part.representative_point()) and hull.area > part.area:
                enclaves.append((c, part))
                host_codes.add(h)
                break

def dep_geom_for_drawing(c, g):
    """Géométrie dessinée : sans les îlots enclavés, et sans trou pour un hôte."""
    parts = [p for p in polygon_parts(g) if not any(e.equals(p) for _, e in enclaves)]
    if c in host_codes:
        parts = [Polygon(p.exterior) for p in parts]
    return unary_union(parts)

dep_paths = "\n".join(
    [f'<path class="dep z-{data[c]["z"]}" data-code="{c}" d="{geom_d(dep_geom_for_drawing(c, g))}"/>'
     for c, g in dep_shapes.items()]
    + [f'<path class="dep enclave z-{data[c]["z"]}" data-code="{c}" d="{geom_d(p)}"/>'
       for c, p in enclaves])
print("Enclaves détectées :", [(c, round(p.area, 4)) for c, p in enclaves], "hôtes :", sorted(host_codes))

# 2. Zones fusionnées : contours épais + position des étiquettes
zone_union = {}
for z in ZONES:
    parts = [dep_shapes[c].buffer(0.002) for c in data if data[c]["z"] == z]
    zone_union[z] = unary_union(parts).buffer(-0.002)

# Limites entre zones uniquement (pas le trait de côte) : intersection des contours
zone_lines = []
for i, a in enumerate(ZONES):
    for b in ZONES[i + 1:]:
        shared = zone_union[a].buffer(0.004).intersection(zone_union[b].boundary)
        if not shared.is_empty:
            zone_lines.append(geom_d(shared))
zone_border_d = "".join(zone_lines)

zone_labels = []
for z in ZONES:
    g = zone_union[z]
    biggest = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    pt = polylabel(biggest, tolerance=0.01)
    x, y = proj(pt.x, pt.y)
    dx, dy = ZONE_LABEL_NUDGE.get(z, (0, 0))
    zone_labels.append(f'<text class="zlabel" x="{x + dx:.1f}" y="{y + dy:.1f}">{z}</text>')

# 3. Pays voisins (gris) et masse terrestre pour le halo côtier
countries = load("ne_50m_admin_0_countries")
land_parts, neigh_parts = [], []
for f in countries["features"]:
    g = shape(f["geometry"]).buffer(0)
    if not g.intersects(VIEW_BOX_DEG):
        continue
    g = g.intersection(VIEW_BOX_DEG).simplify(SIMPLIFY_DEG)
    land_parts.append(g)
    if f["properties"].get("ADMIN") != "France":
        neigh_parts.append(g)
land_parts.append(france)
land_d = geom_d(unary_union(land_parts))
neigh_d = geom_d(unary_union(neigh_parts))

# 4. Lacs (Léman notamment)
lakes = load("ne_10m_lakes")
lake_d = "".join(
    geom_d(shape(f["geometry"]).buffer(0).intersection(VIEW_BOX_DEG))
    for f in lakes["features"]
    if shape(f["geometry"]).intersects(VIEW_BOX_DEG) and shape(f["geometry"]).area > 0.005)

# 5. Fleuves (découpés à la France légèrement élargie pour garder le Rhin frontalier)
france_buf = france.buffer(0.03)
rivers = {"main": [], "second": []}
for fn in ("ne_10m_rivers_lake_centerlines", "ne_10m_rivers_europe"):
    for f in load(fn)["features"]:
        name = f["properties"].get("name")
        cls = "main" if name in RIVERS_MAIN else "second" if name in RIVERS_SECOND else None
        if not cls:
            continue
        g = shape(f["geometry"])
        if g.intersects(france_buf):
            rivers[cls].append(geom_d(g.intersection(france_buf).simplify(0.002)))

# 6. Massifs montagneux (découpés à la France)
regions = load("ne_10m_geography_regions_polys")
massif_paths, massif_labels = [], []
for f in regions["features"]:
    nm = f["properties"].get("NAME")
    if nm not in MASSIFS:
        continue
    g = shape(f["geometry"]).buffer(0).intersection(france)
    if g.is_empty:
        continue
    massif_paths.append(f'<path d="{geom_d(g)}"/>')
    biggest = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    pt = polylabel(biggest, tolerance=0.01)
    x, y = proj(pt.x, pt.y)
    massif_labels.append(f'<text class="mlabel" x="{x:.1f}" y="{y:.1f}">{MASSIFS[nm]}</text>')

# 7. Villes
city_svg = []
for name, lon, lat, pos in CITIES:
    x, y = proj(lon, lat)
    if pos == "below":
        tx, ty, ta = x, y + 24, "middle"
    else:
        tx, ty, ta = x + (9 if pos == "start" else -9), y + 6, pos
    city_svg.append(f'<g class="city"><circle cx="{x:.1f}" cy="{y:.1f}" r="4.2"/>'
                    f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{ta}">{name}</text></g>')

# 8. Pays et mers
context_svg = []
for txt, lon, lat, cls in CONTEXT_LABELS:
    x, y = proj(lon, lat)
    context_svg.append(f'<text class="ctx {cls}" x="{x:.1f}" y="{y:.1f}">{txt}</text>')

# 9. Noms des départements (couche masquée par défaut)
def split_name(name):
    """Coupe un nom long au trait d'union le plus proche du milieu."""
    if len(name) <= DEP_LABEL_MAXLEN or "-" not in name:
        return [name]
    cuts = [i for i, ch in enumerate(name) if ch == "-"]
    i = min(cuts, key=lambda k: abs(k - len(name) / 2))
    return [name[: i + 1], name[i + 1:]]

dep_labels = []
for code, g in dep_shapes.items():
    biggest = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    pt = polylabel(biggest, tolerance=0.005)
    x, y = proj(pt.x, pt.y)
    if code in DEP_LABEL_CODES_ONLY:
        dep_labels.append(f'<text class="dlabel code" x="{x:.1f}" y="{y + 3:.1f}">{code}</text>')
        continue
    lines = split_name(data[code]["n"])
    y0 = y + 4 - (len(lines) - 1) * 6
    spans = "".join(f'<tspan x="{x:.1f}" y="{y0 + k * 12:.1f}">{t}</tspan>' for k, t in enumerate(lines))
    dep_labels.append(f'<text class="dlabel">{spans}</text>')

# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------
counts = {z: sum(1 for v in data.values() if v["z"] == z) for z in ZONES}
# Logements par zone : total et résidences principales (estimées depuis la part en %)
logements = {z: {"l": sum(v["l"] for v in data.values() if v["z"] == z),
                 "rp": round(sum(v["l"] * v["rp"] / 100 for v in data.values() if v["z"] == z))}
             for z in ZONES}
html = open(TEMPLATE_PATH, encoding="utf-8").read()
for key, val in {
    "__VIEWBOX__": f"0 0 {VIEW_W} {VIEW_H}",
    "__VW__": str(VIEW_W), "__VH__": str(VIEW_H),
    "__LAND__": land_d, "__NEIGH__": neigh_d, "__FRANCE__": geom_d(france),
    "__PATHS__": dep_paths, "__ZONEBORDERS__": zone_border_d,
    "__LAKES__": lake_d,
    "__RIVERS_MAIN__": "".join(rivers["main"]), "__RIVERS_SECOND__": "".join(rivers["second"]),
    "__MASSIFS__": "\n".join(massif_paths), "__MASSIF_LABELS__": "\n".join(massif_labels),
    "__ZONELABELS__": "\n".join(zone_labels), "__CITIES__": "\n".join(city_svg),
    "__CONTEXT__": "\n".join(context_svg),
    "__DEPLABELS__": "\n".join(dep_labels),
    "__VERSION__": VERSION, "__BUILD_DATE__": BUILD_DATE, "__REPO_URL__": REPO_URL,
    "__DATA__": json.dumps(data, ensure_ascii=False), "__COUNTS__": json.dumps(counts),
    "__LOGEMENTS__": json.dumps(logements),
}.items():
    html = html.replace(key, val)
open(OUT_PATH, "w", encoding="utf-8").write(html)

# Version autonome pour GitHub Pages : document HTML complet
head, sep, rest = html.partition("</style>")
index = ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
         '<meta name="description" content="Carte interactive des zones climatiques RE2020 par département, '
         'avec le nombre de logements par zone (INSEE, RP 2022).">\n'
         + head + "\nbody { margin: 0; }\n" + sep + "\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n")
open(INDEX_PATH, "w", encoding="utf-8").write(index)
print("OK", VIEW_W, VIEW_H, len(html), {k: len(v) for k, v in rivers.items()}, len(massif_paths))
