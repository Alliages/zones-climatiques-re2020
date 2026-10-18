"""Carte des zones climatiques RE2020.

Couches : mers en dégradé, pays voisins, départements, limites de zones,
lacs, fleuves, altitude (classes RE2020 > 400 m et > 800 m), libellés (zones, villes, départements, pays, mers),
nombre de logements (INSEE, RP 2022) par département et par zone,
DH médians par zone (open data OPEE).

Usage :
  python3 -I build_map.py <dossier_geo> <zones.txt> <template.html> <sortie_artifact.html>
                          <logements.txt> <sortie_index.html>
"""
import datetime
import json
import math
import os
import sys

from shapely.geometry import shape, box, mapping, Polygon
from shapely.ops import unary_union, polylabel

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête pour la lisibilité)
# ---------------------------------------------------------------------------
VERSION = "1.1.2"             # version de la carte (SemVer) — à reporter dans CHANGELOG.md et en tag git
BUILD_DATE = datetime.date.today().strftime("%d/%m/%Y")   # date de génération affichée en pied de page
REPO_URL = "https://github.com/Alliages/zones-climatiques-re2020"
# Icônes de l'onglet (fichiers à la racine du dépôt, à côté de index.html)
FAVICON_SVG = "favicon.svg"             # navigateurs récents
FAVICON_PNG = "favicon-32.png"          # repli pour les navigateurs sans prise en charge du SVG
APPLE_TOUCH_ICON = "apple-touch-icon.png"   # écran d'accueil iPhone / iPad (180 × 180 px)
GEO_DIR, TABLE_PATH, TEMPLATE_PATH, OUT_PATH, LOGEMENTS_PATH, INDEX_PATH = sys.argv[1:7]
DEP_LABEL_CODES_ONLY = {"75", "92", "93", "94", "90"}   # départements trop petits : numéro seul
DEP_LABEL_MAXLEN = 11                                   # au-delà, le nom passe sur deux lignes
VIEW_W = 1000                 # largeur du viewBox SVG
LAT0 = 46.5                   # latitude de référence de la projection
PAD = 42                      # marge autour de la France (place pour mers et voisins)
SIMPLIFY_DEG = 0.004          # simplification des couches de contexte (degrés)

ZONES = ["H1a", "H1b", "H1c", "H2a", "H2b", "H2c", "H2d", "H3"]

# Altitude : classes RE2020 issues du MNT (voir scripts/altitude/), deux surfaces emboîtées
ALTITUDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "altitude_re2020.geojson")
ALTITUDE_CLASSES = ["400+", "800+"]     # « 400+ » : hachures 45° ; « 800+ » : + hachures 135° (quadrillage)

# Degrés-heures (DH) médians par zone : open data OPEE (bâtiments conformes), synthèse fournie par Guigui
REPERES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reperes.json")
# Repères (villes, pays et mers, fleuves, massifs) : voir data/reperes.json

DH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "dh_median_opee.csv")
DH_EXTRACTION = "18/10/2026"            # date d'extraction OPEE affichée dans la note de source
DH_REFS = [350, 1250]                   # traits de référence (°C.h) : seuil bas et DH max courant
DH_SCALE_MAX = 1300                     # borne de l'échelle des barres (°C.h)
# Étiquettes « DH médian » sur la carte (couche optionnelle) : boîte arrondie semi-transparente
DH_LABEL_FONT = 14                      # taille du texte (unités du viewBox)
DH_LABEL_CHAR_W = 0.6                   # largeur d'un caractère en police mono (fraction de la taille)
DH_LABEL_PAD_X, DH_LABEL_H, DH_LABEL_RX = 8, 22, 7
DH_LABEL_DY = 30                        # position sous le nom de zone (centre de la boîte)
DH_LABEL_DY_SPECIAL = {"H2d": -29, "H3": -34}   # au-dessus du nom : évite Avignon et Perpignan
# Palette des zones, du plus clair au plus foncé : attribuée aux zones par DH médian croissant
PALETTE_ZONES = ["#fbdf72", "#f9cf52", "#f6bd3a", "#f4a930", "#f09528", "#e88021", "#da691a", "#c25212"]

# Décalages manuels des étiquettes de zones (pixels du viewBox), si besoin
ZONE_LABEL_NUDGE = {"H2a": (35, 22), "H2b": (-40, 40), "H2c": (-55, 20),
                    "H1b": (-70, -15), "H3": (-10, -6), "H2d": (-35, 35)}

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
def load(name):
    """Lit un fond de carte de data/fonds/ (préparé par preparer_fonds.py)."""
    with open(f"{GEO_DIR}/{name}.geojson", encoding="utf-8") as f:
        return json.load(f)

def load_path(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def lire_table(path):
    """Lit un fichier texte à séparateur « | » et ligne d'en-tête → liste de dictionnaires."""
    with open(path, encoding="utf-8") as f:
        lignes = f.read().strip().splitlines()
    cles = lignes[0].split("|")
    return [dict(zip(cles, l.split("|"))) for l in lignes[1:]]

with open(REPERES_PATH, encoding="utf-8") as f:
    reperes = json.load(f)
deps_geo = load("departements")
data = {d["code"]: {"r": d["region"], "n": d["nom"], "z": d["zone"]} for d in lire_table(TABLE_PATH)}

# Logements INSEE (RP 2022), jointure par code ; le nom sert de contrôle
for d in lire_table(LOGEMENTS_PATH):
    assert data[d["code"]]["n"] == d["nom"], f"Nom différent pour le département {d['code']}"
    data[d["code"]].update({"l": int(d["logements"]), "rp": float(d["pct_residences_principales"]),
                            "rs": float(d["pct_residences_secondaires"]), "lv": float(d["pct_vacants"])})
assert all("l" in v for v in data.values()), "Logements manquants pour un département"

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
zone_pos = {}                           # position finale du nom de chaque zone (réutilisée pour le DH)
for z in ZONES:
    g = zone_union[z]
    biggest = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    pt = polylabel(biggest, tolerance=0.01)
    x, y = proj(pt.x, pt.y)
    dx, dy = ZONE_LABEL_NUDGE.get(z, (0, 0))
    zone_labels.append(f'<text class="zlabel" x="{x + dx:.1f}" y="{y + dy:.1f}">{z}</text>')
    zone_pos[z] = (x + dx, y + dy)

# 3. Pays voisins (gris) et masse terrestre pour le halo côtier
countries = load("pays")
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
lakes = load("lacs")
lake_d = "".join(
    geom_d(shape(f["geometry"]).buffer(0).intersection(VIEW_BOX_DEG))
    for f in lakes["features"]
    if shape(f["geometry"]).intersects(VIEW_BOX_DEG) and shape(f["geometry"]).area > 0.005)

# 5. Fleuves (découpés à la France légèrement élargie pour garder le Rhin frontalier)
france_buf = france.buffer(0.03)
rivers = {"main": [], "second": []}
for f in load("fleuves")["features"]:
    name = f["properties"].get("name")
    cls = "main" if name in reperes["fleuves"]["principaux"] else "second"
    g = shape(f["geometry"])
    if g.intersects(france_buf):
        rivers[cls].append(geom_d(g.intersection(france_buf).simplify(0.002)))

# 6. Altitude (classes RE2020 > 400 m et > 800 m) + noms des massifs comme repères
alt_geo = load_path(ALTITUDE_PATH)
alt_geoms = {f["properties"]["classe"]: shape(f["geometry"]) for f in alt_geo["features"]}
altitude_paths = [f'<path class="alt alt-{c[:3]}" d="{geom_d(alt_geoms[c])}"/>' for c in ALTITUDE_CLASSES]

regions = load("massifs")
massif_labels = []
for f in regions["features"]:
    nm = f["properties"].get("NAME")
    g = shape(f["geometry"]).buffer(0).intersection(france)
    if g.is_empty:
        continue
    biggest = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    pt = polylabel(biggest, tolerance=0.01)
    x, y = proj(pt.x, pt.y)
    massif_labels.append(f'<text class="mlabel" x="{x:.1f}" y="{y:.1f}">{reperes["massifs"][nm]}</text>')

# 7. Villes
city_svg = []
for v in reperes["villes"]:
    name, pos = v["nom"], v["position"]
    x, y = proj(v["lon"], v["lat"])
    if pos == "below":
        tx, ty, ta = x, y + 24, "middle"
    else:
        tx, ty, ta = x + (9 if pos == "start" else -9), y + 6, pos
    city_svg.append(f'<g class="city"><circle cx="{x:.1f}" cy="{y:.1f}" r="4.2"/>'
                    f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{ta}">{name}</text></g>')

# 8. Pays et mers
context_svg = []
for lib in reperes["libelles"]:
    txt, cls = lib["texte"], lib["type"]
    x, y = proj(lib["lon"], lib["lat"])
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

# 10. DH médians par zone (CSV « ; » à virgule décimale, encodé UTF-8 avec BOM)
def lire_dh(path):
    """Retourne {zone: {m: médiane, n: nb bâtiments}} et la ligne « Toutes zones »."""
    zones, total = {}, None
    lignes = open(path, encoding="utf-8-sig").read().strip().splitlines()
    for ligne in lignes[1:]:
        zone, nb, med = ligne.split(";")[:3]
        val = {"m": round(float(med.replace(",", "."))), "n": int(nb)}
        if zone in ZONES:
            zones[zone] = val
        else:
            total = val
    return {"zones": zones, "all": total}

dh = lire_dh(DH_PATH)

# Couleurs des zones dans l'ordre du DH médian (la plus claire pour le DH le plus bas)
ordre_dh = sorted(dh["zones"], key=lambda z: dh["zones"][z]["m"])
assert sorted(ordre_dh) == sorted(ZONES), "DH manquant pour une zone"
zone_colors_css = "\n".join(f"  --{z}: {PALETTE_ZONES[i]};" for i, z in enumerate(ordre_dh))
print("Ordre DH :", " < ".join(ordre_dh))

# Étiquettes DH médian : boîte arrondie + texte, centrées sous (ou sur) le nom de zone
def fr_milliers(n):
    return f"{n:,}".replace(",", "\u202f")          # espace fine insécable comme séparateur

dh_labels = []
for z, (x, y) in zone_pos.items():
    if z not in dh["zones"]:
        continue
    texte = f"DH méd. {fr_milliers(dh['zones'][z]['m'])} °C.h"
    w = len(texte) * DH_LABEL_FONT * DH_LABEL_CHAR_W + 2 * DH_LABEL_PAD_X
    cy = y + DH_LABEL_DY_SPECIAL.get(z, DH_LABEL_DY)
    dh_labels.append(
        f'<g class="dhlabel"><rect x="{x - w / 2:.1f}" y="{cy - DH_LABEL_H / 2:.1f}" width="{w:.1f}" '
        f'height="{DH_LABEL_H}" rx="{DH_LABEL_RX}"/><text x="{x:.1f}" y="{cy:.1f}">{texte}</text></g>')

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
    "__ALTITUDE__": "\n".join(altitude_paths), "__MASSIF_LABELS__": "\n".join(massif_labels),
    "__ZONELABELS__": "\n".join(zone_labels), "__CITIES__": "\n".join(city_svg),
    "__CONTEXT__": "\n".join(context_svg),
    "__DEPLABELS__": "\n".join(dep_labels),
    "__ZONE_COLORS__": zone_colors_css,
    "__DHLABELS__": "\n".join(dh_labels),
    "__DH__": json.dumps(dh), "__DH_DATE__": DH_EXTRACTION,
    "__DH_REFS__": json.dumps(DH_REFS), "__DH_SCALE__": str(DH_SCALE_MAX),
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
         # Favicon : PNG en repli déclaré d'abord, SVG ensuite (retenu en priorité
         # par les navigateurs récents), puis icône dédiée pour iOS
         f'<link rel="icon" href="{FAVICON_PNG}" type="image/png" sizes="32x32">\n'
         f'<link rel="icon" href="{FAVICON_SVG}" type="image/svg+xml">\n'
         f'<link rel="apple-touch-icon" href="{APPLE_TOUCH_ICON}">\n'
         + head + "\nbody { margin: 0; }\n" + sep + "\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n")
open(INDEX_PATH, "w", encoding="utf-8").write(index)
print("OK", VIEW_W, VIEW_H, len(html), {k: len(v) for k, v in rivers.items()}, len(altitude_paths))
