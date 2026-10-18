"""Prépare les polices de la page, hébergées dans le dépôt (dossier polices/).

Télécharge les fichiers de Google Fonts (dépôt github.com/google/fonts, commit figé),
restreint les axes variables aux graisses utilisées, ne garde que les caractères
latins utiles et écrit des fichiers WOFF2, avec la licence SIL OFL de chaque famille.
Héberger les polices évite les requêtes vers Google (vie privée), allège la page
et permettra de les intégrer à l'export d'image de la carte.

Usage (depuis la racine du dépôt) : python3 scripts/preparer_polices.py
Dépendances : fonttools, brotli
"""
import io
import os
import shutil
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# ---------------------------------------------------------------------------
# Paramètres (regroupés en tête)
# ---------------------------------------------------------------------------
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CACHE_DIR = os.path.join(RACINE, ".cache", "polices")    # téléchargements bruts (non versionnés)
SORTIE_DIR = os.path.join(RACINE, "polices")
GOOGLE_FONTS = ("https://raw.githubusercontent.com/google/fonts/"
                "47d54ca1ebb14fd864695f1d39dc734f39017c33/ofl")

# Fichier de sortie → (fichier source, axes : valeur fixe ou plage (min, max))
POLICES = {
    "bricolage-grotesque.woff2": ("bricolagegrotesque/BricolageGrotesque[opsz,wdth,wght].ttf",
                                  # titres : 500 à 700 ; taille optique figée (divise le poids par 2,
                                  # titres affichés entre 15 et 48 px)
                                  {"wdth": 100, "opsz": 32, "wght": (500, 700)}),
    "public-sans.woff2": ("publicsans/PublicSans[wght].ttf", {"wght": (400, 600)}),   # texte : 400 à 600
    "public-sans-italique.woff2": ("publicsans/PublicSans-Italic[wght].ttf", {"wght": 400}),
    "ibm-plex-mono.woff2": ("ibmplexmono/IBMPlexMono-Medium.ttf", {}),         # chiffres et codes : 500
}
LICENCES = {"bricolage-grotesque": "bricolagegrotesque", "public-sans": "publicsans",
            "ibm-plex-mono": "ibmplexmono"}

# Caractères gardés : latin de base et latin-1, ligatures françaises, ponctuation et
# espaces typographiques (espace fine insécable des nombres fr-FR), quelques symboles
CARACTERES = ("U+0020-007E,U+00A0-00FF,U+0152-0153,U+0178,U+2009,U+2011,U+2013-2014,"
              "U+2018-201E,U+2022,U+2026,U+202F,U+2039-203A,U+20AC,U+2192,U+2212,U+2264-2265")
FONCTIONS = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "tnum"]   # tnum : chiffres tabulaires


def telecharger(chemin):
    os.makedirs(CACHE_DIR, exist_ok=True)
    local = os.path.join(CACHE_DIR, chemin.replace("/", "_"))
    if not os.path.exists(local):
        url = f"{GOOGLE_FONTS}/{chemin}".replace("[", "%5B").replace("]", "%5D")
        print("  téléchargement :", url)
        urllib.request.urlretrieve(url, local)
    return local


def main():
    os.makedirs(SORTIE_DIR, exist_ok=True)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = FONCTIONS
    options.name_IDs = ["*"]                    # garde les noms (dont la mention de licence)
    options.notdef_outline = True

    for sortie, (source, axes) in POLICES.items():
        police = TTFont(telecharger(source))
        if axes:
            police = instancer.instantiateVariableFont(police, axes)
            tampon = io.BytesIO()                # relecture : le sous-ensemble échoue sur une police
            police.save(tampon)                  # instanciée encore en mémoire (tables chargées à la demande)
            tampon.seek(0)
            police = TTFont(tampon)
        sous = subset.Subsetter(options)
        sous.populate(unicodes=subset.parse_unicodes(CARACTERES))
        sous.subset(police)
        chemin = os.path.join(SORTIE_DIR, sortie)
        subset.save_font(police, chemin, options)
        print(f"  {sortie:28s} {os.path.getsize(chemin) / 1024:5.1f} Ko")

    for nom, dossier in LICENCES.items():           # la licence OFL accompagne les fichiers
        shutil.copy(telecharger(f"{dossier}/OFL.txt"), os.path.join(SORTIE_DIR, f"OFL-{nom}.txt"))


if __name__ == "__main__":
    main()
