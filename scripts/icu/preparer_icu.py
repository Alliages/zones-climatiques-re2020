"""Couche ICU : synthèse par territoire et encarts de zoom, à partir des calculs de calcul_icu.py.

Usage : python3 scripts/icu/preparer_icu.py <dossier_resultats> <dossier_eau> <dossier_communes> <mairies.csv.gz>

- <dossier_resultats> : un <slug>.json par territoire (sortie de calcul_icu.py, non versionné)
- <dossier_eau>       : un <slug>.json par territoire (sortie de extraire_eau.py, non versionné)
- <dossier_communes>  : communes-<dép>-<nom>.geojson de france-geojson (contours simplifiés)
- <mairies.csv.gz>    : « Communes et villes de France » (data.gouv.fr), position des mairies

Écrit dans le dépôt (lu par build_map.py) :
- data/icu/territoires.json : par territoire, centre, surface ICU, nombre d'îlots, commune centre ;
- data/icu/zooms/<slug>.html : encart de zoom (SVG + surfaces), chargé au clic sur la carte ;
- data/icu/synthese_icu.csv : tableau de contrôle.

Seuil appliqué au calcul : seuls les îlots (enveloppes) d'au moins ICU_MIN_HA sont retenus,
dans la surface affichée comme dans le dessin.
"""
import csv
import glob
import gzip
import json
import math
import os
import sys

import numpy as np
import shapely
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import box, shape, Point
from shapely.ops import polylabel

# --- Réglages ---------------------------------------------------------------
DOSSIER_ICU, DOSSIER_EAU, DOSSIER_COMMUNES, MAIRIES_CSV = sys.argv[1:5]
SEULEMENT = set(sys.argv[5:])     # territoires à traiter (vide = tous) — essais sur une ville
DEPOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VILLES_JSON = os.path.join(DEPOT, "data", "icu", "villes_lcz.json")    # centre-ville de chaque territoire
SORTIE_DIR = os.path.join(DEPOT, "data", "icu")
ICU_MIN_HA = 10.0                 # îlots ICU (enveloppes) plus petits écartés, du calcul comme de l'affichage
MAIRIE_R = 2.2                   # rayon du point mairie (px)
MAIRIE_DX = 4.5                   # décalage du nom par rapport au point (px)
ZOOM_W, ZOOM_H = 360, 280         # viewBox de l'encart de zoom
ZOOM_MARGE = 0.3                  # marge autour de la commune centre (fraction de son emprise)
VW, VH = 110, 80                  # vignette (territoire entier), coin haut droit
SIMPL_PX = 0.6                    # simplification des tracés du zoom (px du viewBox)
PARTIE_MIN_PX2 = 3.0              # parties plus petites ignorées dans le zoom (px²)
CADRE_MAX_KM = 25                 # commune centre plus grande : cadrage réduit autour du centre-ville
CADRE_RAYON_KM = 4                #   (rayon du cadrage réduit)
ICU_MIN_PX2 = 0.3                 # seuil plus bas pour les couches ICU (petits îlots visibles)
PAYS_TAMPON_DEG = 0.02           # dilatation des pays voisins (~2 km) avant le test de couverture
PAYS_PART_MIN = 0.5              # part minimale de la zone hors France couverte par un pays pour le griser
NOM_SURFACE_MIN_PX2 = 1800       # partie visible minimale d'une commune pour afficher son nom (px²)
CAR_PX = {"z-nom": 5.4, "z-nom main": 8.2, "z-pays": 8.5}   # largeur moyenne d'un caractère (px)

sys.path.insert(0, os.path.join(DEPOT, "scripts"))
from geo_utils import chemin_svg  # noqa: E402  (même écriture des chemins SVG que la page)

VERS_L93 = Transformer.from_crs(4326, 2154, always_xy=True)


def km2(g):
    """Surface en km² d'une géométrie lon/lat (Lambert 93)."""
    return shapely.transform(g, lambda c: np.column_stack(VERS_L93.transform(c[:, 0], c[:, 1]))).area / 1e6


def fr(v, dec):
    return f"{v:.{dec}f}".replace(".", ",")


def fr_km2(v):
    """Surface lisible : 2 décimales sous 10 km², 1 au-delà."""
    return fr(v, 2) if v < 10 else fr(v, 1)


def nettoyer(g, mini=None):
    """Retire les parties et les trous minuscules (en px²) : allège les tracés et évite les points parasites."""
    mini = PARTIE_MIN_PX2 if mini is None else mini
    parts = []
    for p in getattr(g, "geoms", [g]):
        if p.geom_type != "Polygon" or p.area < mini:
            continue
        trous = [r for r in p.interiors if shapely.Polygon(r).area >= mini]
        parts.append(shapely.Polygon(p.exterior, trous))
    return shapely.MultiPolygon(parts) if parts else shapely.Polygon()


# --- Communes de métropole (france-geojson, contours simplifiés) -----------
communes_g, communes_nom, communes_code = [], [], []
for f in sorted(glob.glob(f"{DOSSIER_COMMUNES}/*.geojson")):
    for ft in json.load(open(f))["features"]:
        communes_g.append(shapely.make_valid(shape(ft["geometry"])))
        communes_nom.append(ft["properties"]["nom"])
        communes_code.append(ft["properties"]["code"])
communes_g = np.array(communes_g, dtype=object)
arbre_communes = STRtree(communes_g)

# Mairies (« Communes et villes de France », data.gouv, Licence Ouverte) : position et population
MAIRIES = {}
for row in csv.DictReader(gzip.open(MAIRIES_CSV, "rt", encoding="utf-8")):
    try:
        MAIRIES[row["code_insee"]] = (float(row["longitude_mairie"]), float(row["latitude_mairie"]),
                                      int(float(row["population"] or 0)))
    except ValueError:
        pass


def communes_dans(zone):
    """Indices des communes qui touchent `zone` (lon/lat)."""
    return arbre_communes.query(zone, predicate="intersects")


# Pays voisins (Natural Earth, fond de la carte) : grisés et nommés dans le zoom ; sinon la mer
PAYS_FR = {"Switzerland": "SUISSE", "Germany": "ALLEMAGNE", "Belgium": "BELGIQUE", "Luxembourg": "LUXEMBOURG",
           "Spain": "ESPAGNE", "Italy": "ITALIE", "Monaco": "MONACO", "Andorra": "ANDORRE"}
PAYS = {f["properties"]["ADMIN"]: shapely.make_valid(shape(f["geometry"]))
        for f in json.load(open(os.path.join(DEPOT, "data", "fonds", "pays.geojson")))["features"]
        if f["properties"]["ADMIN"] in PAYS_FR}


# --- Encart de zoom d'un territoire ------------------------------------------
def cadrage(bounds, w, h, marge):
    """Projection locale équirectangulaire cadrant `bounds` (+ marge) dans w × h."""
    x0, y0, x1, y1 = bounds
    cos_c = math.cos(math.radians((y0 + y1) / 2))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ech = min(w / max((x1 - x0) * cos_c * (1 + 2 * marge), 1e-9),
              h / max((y1 - y0) * (1 + 2 * marge), 1e-9))

    def px(g):
        return shapely.transform(g, lambda c: np.column_stack(((c[:, 0] - cx) * cos_c * ech + w / 2,
                                                               (cy - c[:, 1]) * ech + h / 2)))

    def lonlat(x, y):
        return (x - w / 2) / (ech * cos_c) + cx, cy - (y - h / 2) / ech

    def chemin(g, simpl=SIMPL_PX, mini=None):
        g = px(g).intersection(box(-5, -5, w + 5, h + 5))
        return chemin_svg(nettoyer(g.simplify(simpl), mini), 0.3) if not g.is_empty else ""

    return px, chemin, lonlat, ech


def etiquette(region, texte, classe, places):
    """Nom au pôle d'inaccessibilité de `region`, recadré dans la vue ; ignoré s'il chevauche
    un nom déjà placé (les plus grandes communes sont traitées d'abord)."""
    part = max(getattr(region, "geoms", [region]), key=lambda p: p.area)
    pt = polylabel(part, tolerance=1)
    demi = len(texte) * CAR_PX[classe] / 2 + 3
    x = min(max(pt.x, demi), ZOOM_W - demi)
    cadre = box(x - demi, pt.y - 7, x + demi, pt.y + 7)
    if any(cadre.intersects(b) for b in places):
        return ""
    places.append(cadre)
    return f'<text class="{classe}" x="{x:.1f}" y="{pt.y:.1f}">{texte}</text>'


def etiquette_mairie(x, y, texte, classe, places, zone):
    """Nom posé à côté du point mairie : à droite, sinon à gauche, dessus, dessous.
    Refusé s'il chevauche un nom déjà placé ou sort de la zone autorisée."""
    w = len(texte) * CAR_PX[classe] + 2
    essais = [("start", x + MAIRIE_DX, y + 3.5, box(x + MAIRIE_DX - 1, y - 5, x + MAIRIE_DX + w, y + 6)),
              ("end", x - MAIRIE_DX, y + 3.5, box(x - MAIRIE_DX - w, y - 5, x - MAIRIE_DX + 1, y + 6)),
              ("middle", x, y - 6, box(x - w / 2, y - 16, x + w / 2, y - 4)),
              ("middle", x, y + 13, box(x - w / 2, y + 3, x + w / 2, y + 15))]
    for ancre, tx, ty, cadre in essais:
        if zone.contains(cadre) and not any(cadre.intersects(b) for b in places):
            places.append(cadre)
            return (f'<text class="{classe} m" x="{tx:.1f}" y="{ty:.1f}" '
                    f'style="text-anchor:{ancre}">{texte}</text>')
    return ""


def zoom_territoire(ville, d):
    """Encart HTML (SVG + légende + surfaces) d'un territoire calculé."""
    # Enveloppes déjà filtrées (≥ ICU_MIN_HA) ; sélection et noyau limités aux îlots gardés
    env = shapely.union_all([shape(e["g"]) for e in d["enveloppes"]]) if d["enveloppes"] else shapely.Polygon()
    garde = env.buffer(1e-5)
    selection, emprise = shape(d["selection"]).intersection(garde), shape(d["emprise"])
    noyau = shape(d["noyau"]).intersection(garde) if d["noyau"] else shapely.Polygon()

    # Commune centre : celle qui contient le point de la ville
    centre_pt = Point(ville["lon"], ville["lat"])
    i_c = [i for i in communes_dans(centre_pt) if communes_g[i].contains(centre_pt)]
    i_c = i_c[0] if i_c else int(arbre_communes.nearest(centre_pt))
    commune = communes_g[i_c]
    nom_commune = communes_nom[i_c]

    # Cadrage sur la commune entière, sauf commune immense (Arles, Camargue) : disque autour du centre
    b = commune.bounds
    dim_km = max((b[2] - b[0]) * 111.32 * math.cos(math.radians(ville["lat"])), (b[3] - b[1]) * 111.32)
    if dim_km > CADRE_MAX_KM:
        r_deg = CADRE_RAYON_KM / 111.32
        b = commune.intersection(centre_pt.buffer(r_deg).envelope).bounds
    px, ch, lonlat, ech = cadrage(b, ZOOM_W, ZOOM_H, ZOOM_MARGE)
    cadre_px = box(0, 0, ZOOM_W, ZOOM_H)
    vx, vy = ZOOM_W - VW - 8, 8
    # Zone des noms : hors vignette, hors barre d'échelle et hors ICU (le nom ne masque pas l'îlot)
    zone_noms = (cadre_px.difference(box(vx - 6, 0, ZOOM_W, vy + VH + 6))
                 .difference(box(0, ZOOM_H - 34, 130, ZOOM_H))
                 .difference(px(env).buffer(6) if not env.is_empty else shapely.Polygon()))

    # Communes visibles (contours) et noms, des plus grandes aux plus petites
    (lo0, la1), (lo1, la0) = lonlat(0, 0), lonlat(ZOOM_W, ZOOM_H)
    cadre_ll = box(lo0, la0, lo1, la1)
    visibles = communes_dans(cadre_ll)
    traces, noms, places = [], [], []
    for i in visibles:
        traces.append(f'<path class="z-commune" d="{ch(communes_g[i], 1.0)}"/>')
    # Ville centre : point à la mairie et nom à côté (zone autorisée : hors vignette et barre
    # d'échelle ; le halo garde l'ICU lisible dessous) ; à défaut, nom au centre de la commune
    zone_mairie = (cadre_px.difference(box(vx - 6, 0, ZOOM_W, vy + VH + 6))
                   .difference(box(0, ZOOM_H - 34, 130, ZOOM_H)).buffer(-2))
    m = MAIRIES.get(communes_code[i_c])
    p = px(Point(m[0], m[1])) if m else None
    txt = etiquette_mairie(p.x, p.y, nom_commune.upper(), "z-nom main", places, zone_mairie) \
        if p is not None and zone_mairie.contains(p) else ""
    if txt:
        noms += [f'<circle class="z-mairie main" cx="{p.x:.1f}" cy="{p.y:.1f}" r="{MAIRIE_R * 1.4:.1f}"/>', txt]
    else:
        libre_c = px(commune).intersection(zone_noms)
        if not libre_c.is_empty:
            noms.append(etiquette(libre_c, nom_commune.upper(), "z-nom main", places))
    # Communes voisines : nom au centre de leur partie visible, des plus grandes aux plus petites
    libres = []
    for i in visibles:
        libre = px(communes_g[i]).intersection(zone_noms)
        if i != i_c and libre.area >= NOM_SURFACE_MIN_PX2:
            libres.append((libre.area, i, libre))
    for _, i, libre in sorted(libres, key=lambda t: -t[0]):
        noms.append(etiquette(libre, communes_nom[i], "z-nom", places))

    # Eau (LCZ G) : fleuves, rivières larges, plans d'eau du territoire
    chemin_eau = f"{DOSSIER_EAU}/{ville['slug']}.json"
    eau = shape(json.load(open(chemin_eau))) if os.path.exists(chemin_eau) else shapely.Polygon()
    traces.append(f'<path class="z-eau" d="{ch(eau, 0.4)}"/>')
    # Hors des communes françaises : pays voisin, nommé seulement s'il occupe une part notable
    # Hors des communes françaises : pays voisin (gris, nommé) s'il couvre l'essentiel de cette zone, sinon mer (bleu)
    france = shapely.union_all([px(communes_g[i]) for i in visibles]) if len(visibles) else shapely.Polygon()
    etranger = cadre_px.difference(france.buffer(1))
    pays, part_max = None, 0.0
    for n, g in PAYS.items():
        # Contours des pays grossiers (Natural Earth) : dilatés pour combler l'écart avec les communes
        g = g.buffer(PAYS_TAMPON_DEG)
        if g.intersects(cadre_ll) and etranger.area > 0:
            part = px(g).intersection(etranger).area / etranger.area
            if part > part_max:
                pays, part_max = n, part
    if part_max < PAYS_PART_MIN:
        pays = None
    fond = "z-fond" if pays else "z-fond mer"
    etranger_libre = etranger.intersection(zone_noms)
    if pays and etranger_libre.area > 2 * NOM_SURFACE_MIN_PX2:
        noms.append(etiquette(etranger_libre, PAYS_FR[pays], "z-pays", places))

    # Vignette : territoire LCZ entier, communes, enveloppes, cadre de la vue
    pxv, chv, _, _ = cadrage(emprise.bounds, VW, VH, 0.04)
    a = pxv(Point(lo0, la1)); b = pxv(Point(lo1, la0))
    vign_communes = ""   # vignette allégée : le territoire LCZ suffit (aplat clair)
    vign_env = chv(shapely.union_all([shape(e["g"]).buffer(0.0012) for e in d["enveloppes"]])) if d["enveloppes"] else ""

    km_px = ech / 111.32
    barre_km = next((k for k in (0.5, 1, 2, 5, 10, 20) if k * km_px >= 40), 50)   # barre d'au moins 40 px
    svg = (
        f'<svg viewBox="0 0 {ZOOM_W} {ZOOM_H}" role="img" aria-label="Zoom ICU {ville["nom"]}">'
        f'<rect class="{fond}" width="{ZOOM_W}" height="{ZOOM_H}"/>' + "".join(traces) +
        f'<path class="z-emprise" d="{ch(emprise)}"/>'
        f'<path class="z-env" d="{ch(env, mini=ICU_MIN_PX2)}"/>'
        f'<path class="z-sel" d="{ch(selection, mini=ICU_MIN_PX2)}"/>'
        f'<path class="z-noyau" d="{ch(noyau, mini=ICU_MIN_PX2)}"/>'
        f'<path class="z-ville" d="{ch(commune, 0.6)}"/>' + "".join(noms) +
        f'<g class="z-echelle"><line x1="12" y1="{ZOOM_H - 14}" x2="{12 + barre_km * km_px:.1f}" y2="{ZOOM_H - 14}"/>'
        f'<text x="{12 + barre_km * km_px / 2:.1f}" y="{ZOOM_H - 20}">{fr(barre_km, 0) if barre_km >= 1 else "500 m"}'
        f'{" km" if barre_km >= 1 else ""}</text></g>'
        f'<g transform="translate({vx},{vy})"><g clip-path="url(#z-clip-vignette)">'
        f'<rect class="z-vfond" width="{VW}" height="{VH}"/>' + vign_communes +
        f'<path class="z-vterr" d="{chv(emprise, 0.5)}"/><path class="z-venv" d="{vign_env}"/>'
        f'<rect class="z-cadre" x="{a.x:.1f}" y="{a.y:.1f}" width="{b.x - a.x:.1f}" height="{b.y - a.y:.1f}"/>'
        f'</g><rect class="z-vbord" width="{VW}" height="{VH}" rx="4"/></g></svg>')
    surf_ville = km2(commune)
    pied = (f'<p class="icu-surf"><b>ICU</b> {fr_km2(d["stats"]["icu_km2"])} km² · '
            f'<b>Ville {("d’" if nom_commune[0] in "AEÉÈIOUYH" else "de ")}{nom_commune}</b> {fr_km2(surf_ville)} km²</p>')
    return svg + pied, nom_commune, surf_ville


# --- Données ------------------------------------------------------------------
villes = json.load(open(VILLES_JSON, encoding="utf-8"))
resultats = {slug: json.load(open(f"{DOSSIER_ICU}/{slug}.json"))
             for slug in villes if os.path.exists(f"{DOSSIER_ICU}/{slug}.json")
             and (not SEULEMENT or slug in SEULEMENT)}
manquants = sorted(set(villes) - set(resultats))
# Seuil appliqué au calcul : seuls les îlots ≥ ICU_MIN_HA comptent (surface, carte et zoom)
for d in resultats.values():
    d["enveloppes"] = [e for e in d["enveloppes"] if e["ha"] >= ICU_MIN_HA]
    d["stats"]["groupes"] = len(d["enveloppes"])
    d["stats"]["icu_km2"] = km2(shapely.union_all([shape(e["g"]) for e in d["enveloppes"]])) \
        if d["enveloppes"] else 0.0

# --- Encarts de zoom et synthèse --------------------------------------------------
os.makedirs(os.path.join(SORTIE_DIR, "zooms"), exist_ok=True)
territoires = {}
for slug in sorted(resultats):
    v = dict(villes[slug], slug=slug)
    s = resultats[slug]["stats"]
    html, nom_c, surf_ville = zoom_territoire(v, resultats[slug])
    with open(os.path.join(SORTIE_DIR, "zooms", f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)
    territoires[slug] = {
        "nom": v["nom"], "lon": v["lon"], "lat": v["lat"],
        "icu_km2": round(s["icu_km2"], 3), "ilots": s["groupes"],
        "commune": nom_c, "commune_km2": round(surf_ville, 2),
        "territoire_km2": s["territoire_km2"],
    }
    print(f"{slug} : ICU {fr_km2(s['icu_km2'])} km², {s['groupes']} îlots", flush=True)

if not SEULEMENT:   # un essai partiel ne remplace pas la synthèse complète
    meta = {"source": "Cerema, LCZ 2022-2023 (Licence Ouverte 2.0)",
            "methode": "LCZ 1-3 + LCZ 4-6 à ≤ 15 m, enveloppe convexe par îlot",
            "ilot_min_ha": ICU_MIN_HA, "manquants": manquants}
    with open(os.path.join(SORTIE_DIR, "territoires.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "territoires": territoires}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(SORTIE_DIR, "synthese_icu.csv"), "w", encoding="utf-8") as f:
        f.write("territoire;commune_centre;territoire_km2;ilots;icu_km2;commune_km2\n")
        for t in sorted(territoires.values(), key=lambda t: -t["icu_km2"]):
            f.write(f'{t["nom"]};{t["commune"]};{fr(t["territoire_km2"], 1)};{t["ilots"]};'
                    f'{fr(t["icu_km2"], 2)};{fr(t["commune_km2"], 2)}\n')
print("OK", len(territoires), "territoires ; manquants :", manquants)
