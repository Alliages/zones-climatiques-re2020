"""Génère la carte des zones climatiques RE2020 (index.html).

Couches : mers en dégradé, pays voisins, départements, limites de zones, lacs,
fleuves, altitude (classes RE2020 > 400 m et > 800 m), libellés (zones, villes,
départements, pays, mers, massifs), DH médian par zone sur la carte.
Colonne : fiche département, couches, zones, DH médians (open data OPEE),
logements par zone (INSEE, RP 2022).

Usage (depuis la racine du dépôt) :
  python3 scripts/build_map.py                     # écrit index.html
  python3 scripts/build_map.py --apercu apercu.html  # + fragment pour l'aperçu Claude
"""
import argparse
import datetime
import json
import os
import sys

import shapely
from shapely.geometry import Polygon, box, shape
from shapely.ops import linemerge, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_utils import (Projection, chemin_svg, fusionner, lire_json, lire_table, parties,   # noqa: E402
                       plus_grande_partie)

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête pour la lisibilité)
# ---------------------------------------------------------------------------
VERSION = "1.1.2"             # version de la carte (SemVer) — à reporter dans CHANGELOG.md et en tag git
BUILD_DATE = datetime.date.today().strftime("%d/%m/%Y")   # date de génération affichée en pied de page
REPO_URL = "https://github.com/Alliages/zones-climatiques-re2020"

# Fichiers (chemins relatifs à la racine du dépôt)
RACINE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FONDS_DIR = os.path.join(RACINE, "data", "fonds")                  # préparés par preparer_fonds.py
ZONES_PATH = os.path.join(RACINE, "data", "zones_departements.txt")
LOGEMENTS_PATH = os.path.join(RACINE, "data", "logements_insee_2022.txt")
REPERES_PATH = os.path.join(RACINE, "data", "reperes.json")       # villes, pays et mers, fleuves, massifs
ALTITUDE_PATH = os.path.join(RACINE, "data", "altitude_re2020.geojson")
DH_PATH = os.path.join(RACINE, "data", "dh_median_opee.csv")
TEMPLATE_PATH = os.path.join(RACINE, "scripts", "template.html")
INDEX_PATH = os.path.join(RACINE, "index.html")
# Icônes de l'onglet (fichiers à la racine du dépôt, à côté de index.html)
FAVICON_SVG = "favicon.svg"             # navigateurs récents
FAVICON_PNG = "favicon-32.png"          # repli pour les navigateurs sans prise en charge du SVG
APPLE_TOUCH_ICON = "apple-touch-icon.png"   # écran d'accueil iPhone / iPad (180 × 180 px)

# Zones climatiques, dans l'ordre réglementaire (source unique : injectée dans la page)
ZONES = ["H1a", "H1b", "H1c", "H2a", "H2b", "H2c", "H2d", "H3"]
# Palette des zones, du plus clair au plus foncé : attribuée aux zones par DH médian croissant
PALETTE_ZONES = ["#fbdf72", "#f9cf52", "#f6bd3a", "#f4a930", "#f09528", "#e88021", "#da691a", "#c25212"]

# Cadrage et simplification
VIEW_W = 1000                 # largeur du viewBox SVG
LAT0 = 46.5                   # latitude de référence de la projection
PAD = 42                      # marge autour de la France (place pour mers et voisins)
MARGE_CONTEXTE_DEG = 0.3      # débord des couches de contexte au-delà du viewBox
PAS_SVG = 0.5                 # précision des chemins SVG (unités du viewBox ; 1 unité ≈ 1,2 km)
# Simplifications, en unités du viewBox (tolérances choisies pour rester invisibles même zoomé × 3)
SIMPL_DEPARTEMENTS = 1.0      # pavage des départements (frontières communes simplifiées une seule fois)
SIMPL_VOISINS = 0.5           # pays voisins et lacs
SIMPL_HALO = 3.0              # masse terrestre sous le halo côtier (floutée : peut être grossière)
SIMPL_FLEUVES = 0.4           # fleuves
LAC_SURFACE_MIN = 0.005       # lacs plus petits ignorés (degrés²)
FLEUVES_MARGE_DEG = 0.03      # fleuves découpés à la France légèrement élargie (garde le Rhin frontalier)

# Étiquettes
DEP_LABEL_CODES_ONLY = {"75", "92", "93", "94", "90"}   # départements trop petits : numéro seul
DEP_LABEL_MAXLEN = 11                                   # au-delà, le nom passe sur deux lignes
# Décalages manuels des étiquettes de zones (unités du viewBox)
ZONE_LABEL_NUDGE = {"H2a": (35, 22), "H2b": (-40, 40), "H2c": (-55, 20),
                    "H1b": (-70, -15), "H3": (-10, -6), "H2d": (-35, 35)}

# Altitude : classes RE2020 issues du MNT (voir scripts/altitude/), deux surfaces emboîtées
ALTITUDE_CLASSES = ["400+", "800+"]     # « 400+ » : hachures 45° ; « 800+ » : + hachures 135° (quadrillage)

# Degrés-heures (DH) médians par zone : open data OPEE (bâtiments conformes), synthèse fournie par Guigui
DH_EXTRACTION = "18/10/2026"            # date d'extraction OPEE affichée dans la note de source
DH_REFS = [                             # traits de référence (°C.h), repris dans la boîte DH et le pied de page
    {"v": 350, "court": "pénalité dans le Cep au-delà",
     "info": "au-delà, pénalité forfaitaire de climatisation dans le Cep"},
    {"v": 1250, "court": "DH max", "info": "DH max courant (seuil de conformité)"},
]
DH_SCALE_MAX = 1300                     # borne de l'échelle des barres (°C.h)
# Étiquettes « DH médian » sur la carte (couche optionnelle) : boîte arrondie semi-transparente
DH_LABEL_FONT = 14                      # taille du texte (unités du viewBox)
DH_LABEL_CHAR_W = 0.6                   # largeur d'un caractère en police mono (fraction de la taille)
DH_LABEL_PAD_X, DH_LABEL_H, DH_LABEL_RX = 8, 22, 7
DH_LABEL_DY = 30                        # position sous le nom de zone (centre de la boîte)
DH_LABEL_DY_SPECIAL = {"H2d": -29, "H3": -34}   # au-dessus du nom : évite Avignon et Perpignan


# ---------------------------------------------------------------------------
# Lecture des données
# ---------------------------------------------------------------------------
def fond(nom):
    """Fond de carte de data/fonds/ (préparé par preparer_fonds.py)."""
    return lire_json(os.path.join(FONDS_DIR, f"{nom}.geojson"))


def lire_departements():
    """code → {r: région, n: nom, z: zone, l: logements, rp / rs / lv: % RP, secondaires, vacants}."""
    data = {d["code"]: {"r": d["region"], "n": d["nom"], "z": d["zone"]} for d in lire_table(ZONES_PATH)}
    for d in lire_table(LOGEMENTS_PATH):          # jointure par code ; le nom sert de contrôle
        if data.get(d["code"], {}).get("n") != d["nom"]:
            sys.exit(f"Logements : département {d['code']} {d['nom']} absent ou nommé autrement")
        data[d["code"]].update({"l": int(d["logements"]), "rp": float(d["pct_residences_principales"]),
                                "rs": float(d["pct_residences_secondaires"]), "lv": float(d["pct_vacants"])})
    manquants = [c for c, v in data.items() if "l" not in v or v["z"] not in ZONES]
    if manquants:
        sys.exit(f"Logements ou zone manquants ou inconnus pour : {manquants}")
    return data


def lire_dh(path):
    """DH par zone (CSV « ; » à virgule décimale, UTF-8 avec BOM, export OPEE).

    Retourne {zones: {zone: {m: médiane, n: nb bâtiments}}, all: ligne « Toutes zones »}.
    """
    zones, total = {}, None
    with open(path, encoding="utf-8-sig") as f:
        lignes = f.read().strip().splitlines()
    for ligne in lignes[1:]:
        zone, nb, med = ligne.split(";")[:3]
        val = {"m": round(float(med.replace(",", "."))), "n": int(nb)}
        if zone in ZONES:
            zones[zone] = val
        else:
            total = val
    if sorted(zones) != sorted(ZONES):
        sys.exit(f"DH manquant pour : {sorted(set(ZONES) - set(zones))}")
    return {"zones": zones, "all": total}


# ---------------------------------------------------------------------------
# Couches
# ---------------------------------------------------------------------------
def couche_departements(dep_px, data):
    """Un chemin par département, coloré par zone (géométries du pavage simplifié, en pixels).

    Les enclaves (ex. Enclave des Papes : îlot du Vaucluse entouré par la Drôme) sont
    détectées automatiquement : le département hôte est dessiné sans son trou, et
    l'îlot est posé par-dessus dans un chemin à part, sans liseré (classe « enclave »).
    """
    contours = {c: Polygon(plus_grande_partie(g).exterior) for c, g in dep_px.items()}
    enclaves, hotes = [], set()                # (code de l'enclave, polygone), départements hôtes
    for c, g in dep_px.items():
        for part in parties(g):
            for h, contour in contours.items():
                if h != c and contour.contains(part.representative_point()) and contour.area > part.area:
                    enclaves.append((c, part))
                    hotes.add(h)
                    break

    def a_dessiner(c, g):
        """Géométrie dessinée : sans les îlots enclavés, et sans trou pour un hôte."""
        morceaux = [p for p in parties(g) if not any(e.equals(p) for _, e in enclaves)]
        if c in hotes:
            morceaux = [Polygon(p.exterior) for p in morceaux]
        return unary_union(morceaux)

    print("Enclaves détectées :", [(c, round(p.area)) for c, p in enclaves], "hôtes :", sorted(hotes))
    return "\n".join(
        [f'<path class="dep z-{data[c]["z"]}" data-code="{c}" d="{chemin_svg(a_dessiner(c, g), PAS_SVG)}"/>'
         for c, g in dep_px.items()]
        + [f'<path class="dep enclave z-{data[c]["z"]}" data-code="{c}" d="{chemin_svg(p, PAS_SVG)}"/>'
           for c, p in enclaves])


def couche_zones(proj, dep_shapes, dep_px, data):
    """Limites entre zones (sans le trait de côte) et position des noms de zones.

    Les limites sont les frontières communes des départements du pavage simplifié : elles
    tombent exactement sur les bords des aplats. Les étiquettes sont placées sur les
    contours d'origine (positions indépendantes de la simplification).
    """
    zone_px = {z: shapely.coverage_union_all([dep_px[c] for c in data if data[c]["z"] == z]) for z in ZONES}
    lignes = []
    for i, a in enumerate(ZONES):
        for b in ZONES[i + 1:]:
            commun = zone_px[a].boundary.intersection(zone_px[b].boundary)
            # Lignes seules (une collection peut contenir des points de contact ou des multilignes)
            traits = [g for g in shapely.get_parts(shapely.get_parts(commun))
                      if g.geom_type == "LineString" and not g.is_empty]
            if traits:
                lignes.append(chemin_svg(linemerge(traits), PAS_SVG))
    zone_union = {z: fusionner([dep_shapes[c] for c in data if data[c]["z"] == z]) for z in ZONES}
    positions = {}                             # position finale du nom de chaque zone (réutilisée pour le DH)
    for z in ZONES:
        x, y = proj.point_etiquette(zone_union[z])
        dx, dy = ZONE_LABEL_NUDGE.get(z, (0, 0))
        positions[z] = (x + dx, y + dy)
    etiquettes = [f'<text class="zlabel" x="{x:.1f}" y="{y:.1f}">{z}</text>' for z, (x, y) in positions.items()]
    return "".join(lignes), etiquettes, positions


def couche_contexte(proj, france, emprise):
    """Masse terrestre (halo côtier), pays voisins et lacs, découpés à l'emprise."""
    terres, voisins = [], []
    for f in fond("pays")["features"]:
        g = shape(f["geometry"]).buffer(0)
        if not g.intersects(emprise):
            continue
        g = g.intersection(emprise)
        terres.append(g)
        if f["properties"].get("ADMIN") != "France":
            voisins.append(g)
    terres.append(france)
    lacs = "".join(
        proj.chemin(shape(f["geometry"]).buffer(0).intersection(emprise), SIMPL_VOISINS)
        for f in fond("lacs")["features"]
        if shape(f["geometry"]).intersects(emprise) and shape(f["geometry"]).area > LAC_SURFACE_MIN)
    return (proj.chemin(unary_union(terres), SIMPL_HALO), proj.chemin(unary_union(voisins), SIMPL_VOISINS),
            lacs)


def couche_fleuves(proj, france, reperes):
    """Fleuves principaux et secondaires (listés dans data/reperes.json)."""
    france_large = france.buffer(FLEUVES_MARGE_DEG)
    fleuves = {"main": [], "second": []}
    for f in fond("fleuves")["features"]:
        cls = "main" if f["properties"]["name"] in reperes["fleuves"]["principaux"] else "second"
        g = shape(f["geometry"])
        if g.intersects(france_large):
            fleuves[cls].append(proj.chemin(g.intersection(france_large), SIMPL_FLEUVES))
    return fleuves


def couche_altitude(proj, france, reperes):
    """Classes d'altitude RE2020 (hachures) et noms des massifs comme repères."""
    geoms = {f["properties"]["classe"]: shape(f["geometry"]) for f in lire_json(ALTITUDE_PATH)["features"]}
    chemins = [f'<path class="alt alt-{c[:3]}" d="{proj.chemin(geoms[c])}"/>' for c in ALTITUDE_CLASSES]
    noms = []
    for f in fond("massifs")["features"]:
        g = shape(f["geometry"]).buffer(0).intersection(france)
        if g.is_empty:
            continue
        x, y = proj.point_etiquette(g)
        noms.append(f'<text class="mlabel" x="{x:.1f}" y="{y:.1f}">{reperes["massifs"][f["properties"]["NAME"]]}</text>')
    return chemins, noms


def couche_villes(proj, reperes):
    svg = []
    for v in reperes["villes"]:
        x, y = proj.xy(v["lon"], v["lat"])
        if v["position"] == "below":
            tx, ty, ta = x, y + 24, "middle"
        else:
            tx, ty, ta = x + (9 if v["position"] == "start" else -9), y + 6, v["position"]
        svg.append(f'<g class="city"><circle cx="{x:.1f}" cy="{y:.1f}" r="4.2"/>'
                   f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{ta}">{v["nom"]}</text></g>')
    return svg


def couche_libelles(proj, reperes):
    """Noms des pays et des mers."""
    return [f'<text class="ctx {lib["type"]}" x="{x:.1f}" y="{y:.1f}">{lib["texte"]}</text>'
            for lib in reperes["libelles"] for x, y in [proj.xy(lib["lon"], lib["lat"])]]


def couper_nom(nom):
    """Coupe un nom long au trait d'union le plus proche du milieu."""
    if len(nom) <= DEP_LABEL_MAXLEN or "-" not in nom:
        return [nom]
    coupures = [i for i, ch in enumerate(nom) if ch == "-"]
    i = min(coupures, key=lambda k: abs(k - len(nom) / 2))
    return [nom[: i + 1], nom[i + 1:]]


def couche_noms_departements(proj, dep_shapes, data):
    etiquettes = []
    for code, g in dep_shapes.items():
        x, y = proj.point_etiquette(g, tolerance=0.005)
        if code in DEP_LABEL_CODES_ONLY:
            etiquettes.append(f'<text class="dlabel code" x="{x:.1f}" y="{y + 3:.1f}">{code}</text>')
            continue
        lignes = couper_nom(data[code]["n"])
        y0 = y + 4 - (len(lignes) - 1) * 6
        spans = "".join(f'<tspan x="{x:.1f}" y="{y0 + k * 12:.1f}">{t}</tspan>' for k, t in enumerate(lignes))
        etiquettes.append(f'<text class="dlabel">{spans}</text>')
    return etiquettes


def fr_milliers(n):
    return f"{n:,}".replace(",", " ")          # espace fine insécable comme séparateur


def couche_dh(dh, positions):
    """Étiquettes « DH médian » : boîte arrondie + texte, centrées sous (ou sur) le nom de zone."""
    etiquettes = []
    for z, (x, y) in positions.items():
        texte = f"DH méd. {fr_milliers(dh['zones'][z]['m'])} °C.h"
        w = len(texte) * DH_LABEL_FONT * DH_LABEL_CHAR_W + 2 * DH_LABEL_PAD_X
        cy = y + DH_LABEL_DY_SPECIAL.get(z, DH_LABEL_DY)
        etiquettes.append(
            f'<g class="dhlabel"><rect x="{x - w / 2:.1f}" y="{cy - DH_LABEL_H / 2:.1f}" width="{w:.1f}" '
            f'height="{DH_LABEL_H}" rx="{DH_LABEL_RX}"/><text x="{x:.1f}" y="{cy:.1f}">{texte}</text></g>')
    return etiquettes


def css_zones(dh):
    """Couleurs des zones (dans l'ordre des DH médians, la plus claire pour le DH le plus bas),
    remplissage des départements et mise en avant d'une zone."""
    ordre = sorted(ZONES, key=lambda z: dh["zones"][z]["m"])
    print("Ordre DH :", " < ".join(ordre))
    couleurs = "\n".join(f"  --{z}: {PALETTE_ZONES[i]};" for i, z in enumerate(ordre))
    regles = "\n".join(f".z-{z} {{ fill: var(--{z}); }}" for z in ZONES)
    focus = ",\n".join(f'svg[data-focus="{z}"] .z-{z}' for z in ZONES) + " { opacity: 1; }"
    return couleurs, regles + "\n" + focus


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------
def page_complete(fragment):
    """Document HTML complet pour GitHub Pages autour du fragment généré depuis le gabarit."""
    head, sep, rest = fragment.partition("</style>")
    return ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="description" content="Carte interactive des zones climatiques RE2020 par département, '
            'avec le DH médian et le nombre de logements par zone.">\n'
            # Favicon : PNG en repli déclaré d'abord, SVG ensuite (retenu en priorité
            # par les navigateurs récents), puis icône dédiée pour iOS
            f'<link rel="icon" href="{FAVICON_PNG}" type="image/png" sizes="32x32">\n'
            f'<link rel="icon" href="{FAVICON_SVG}" type="image/svg+xml">\n'
            f'<link rel="apple-touch-icon" href="{APPLE_TOUCH_ICON}">\n'
            + head + "\nbody { margin: 0; }\n" + sep + "\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sortie", default=INDEX_PATH, help="page complète (défaut : index.html)")
    parser.add_argument("--apercu", help="fragment sans en-tête HTML, pour l'aperçu dans Claude (facultatif)")
    args = parser.parse_args()

    # Données
    data = lire_departements()
    reperes = lire_json(REPERES_PATH)
    dh = lire_dh(DH_PATH)
    dep_shapes = {f["properties"]["code"]: shape(f["geometry"]).buffer(0) for f in fond("departements")["features"]}
    france = fusionner(dep_shapes.values())

    # Projection et emprise des couches de contexte
    proj = Projection(france.bounds, VIEW_W, PAD, LAT0, PAS_SVG)
    # Pavage des départements projeté puis simplifié d'un bloc : chaque frontière commune
    # est simplifiée une seule fois, sans jour ni chevauchement entre voisins
    codes = list(dep_shapes)
    simplifies = shapely.coverage_simplify([proj.projeter(dep_shapes[c]) for c in codes], SIMPL_DEPARTEMENTS)
    dep_px = dict(zip(codes, simplifies))
    france_px = shapely.coverage_union_all(simplifies)
    lon0, lat0, lon1, lat1 = proj.emprise_deg()
    m = MARGE_CONTEXTE_DEG
    emprise = box(lon0 - m, lat0 - m, lon1 + m, lat1 + m)

    # Couches
    deps_svg = couche_departements(dep_px, data)
    limites_zones, noms_zones, positions = couche_zones(proj, dep_shapes, dep_px, data)
    terre, voisins, lacs = couche_contexte(proj, france, emprise)
    fleuves = couche_fleuves(proj, france, reperes)
    altitude, massifs = couche_altitude(proj, france, reperes)
    couleurs_zones, regles_zones = css_zones(dh)

    # Synthèses par zone
    counts = {z: sum(1 for v in data.values() if v["z"] == z) for z in ZONES}
    # Logements par zone : total et résidences principales (estimées depuis la part en %)
    logements = {z: {"l": sum(v["l"] for v in data.values() if v["z"] == z),
                     "rp": round(sum(v["l"] * v["rp"] / 100 for v in data.values() if v["z"] == z))}
                 for z in ZONES}
    refs_texte = " et ".join(f"{fr_milliers(r['v'])} °C.h" for r in DH_REFS)

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        html = f.read()
    for cle, val in {
        "__VIEWBOX__": f"0 0 {VIEW_W} {proj.hauteur}",
        "__VW__": str(VIEW_W), "__VH__": str(proj.hauteur),
        "__LAND__": terre, "__NEIGH__": voisins, "__FRANCE__": chemin_svg(france_px, PAS_SVG),
        "__PATHS__": deps_svg, "__ZONEBORDERS__": limites_zones,
        "__LAKES__": lacs,
        "__RIVERS_MAIN__": "".join(fleuves["main"]), "__RIVERS_SECOND__": "".join(fleuves["second"]),
        "__ALTITUDE__": "\n".join(altitude), "__MASSIF_LABELS__": "\n".join(massifs),
        "__ZONELABELS__": "\n".join(noms_zones), "__CITIES__": "\n".join(couche_villes(proj, reperes)),
        "__CONTEXT__": "\n".join(couche_libelles(proj, reperes)),
        "__DEPLABELS__": "\n".join(couche_noms_departements(proj, dep_shapes, data)),
        "__ZONE_COLORS__": couleurs_zones, "__ZONE_RULES__": regles_zones,
        "__DHLABELS__": "\n".join(couche_dh(dh, positions)),
        "__NB_DEPTS__": str(len(data)),
        "__DH__": json.dumps(dh), "__DH_DATE__": DH_EXTRACTION,
        "__DH_REFS__": json.dumps(DH_REFS, ensure_ascii=False), "__DH_REFS_TEXTE__": refs_texte,
        "__DH_SCALE__": str(DH_SCALE_MAX),
        "__VERSION__": VERSION, "__BUILD_DATE__": BUILD_DATE, "__REPO_URL__": REPO_URL,
        "__ZONES__": json.dumps(ZONES),
        "__DATA__": json.dumps(data, ensure_ascii=False), "__COUNTS__": json.dumps(counts),
        "__LOGEMENTS__": json.dumps(logements),
    }.items():
        if cle not in html:
            sys.exit(f"Gabarit : marqueur {cle} absent")
        html = html.replace(cle, val)

    if args.apercu:
        with open(args.apercu, "w", encoding="utf-8") as f:
            f.write(html)
    with open(args.sortie, "w", encoding="utf-8") as f:
        f.write(page_complete(html))
    print("OK", VIEW_W, proj.hauteur, len(html), {k: len(v) for k, v in fleuves.items()}, len(altitude))


if __name__ == "__main__":
    main()
