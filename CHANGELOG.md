# Journal des versions

Numérotation [SemVer](https://semver.org/lang/fr/) :
- **correctif** (1.0.x) : correction de données ou d'affichage ;
- **mineure** (1.x.0) : nouvelle couche, nouvelle fonction ;
- **majeure** (x.0.0) : refonte.

La version est définie par la constante `VERSION` en tête de `scripts/build_map.py`, affichée en pied de page et reportée en tag git (`vX.Y.Z`).

## [1.2.0] — 22/10/2026

Îlots de chaleur urbains (ICU) d'après les zones climatiques locales (LCZ) du Cerema.

### Ajouté
- Couche « Îlots de chaleur urbains (ICU) », visible par défaut et placée en tête de la boîte Couches : un point rouge par territoire LCZ du Cerema (88 territoires de plus de 50 000 habitants, métropole), d'aire proportionnelle à la surface ICU.
- Au clic sur un point, encart de zoom : commune centre (contour noir, mairie), communes voisines nommées, cours et plans d'eau, pays voisin ou mer, vignette du territoire entier, puis « ICU … km² · Ville de … km² ». Sur téléphone, l'encart passe sous la carte. Les encarts sont chargés à la demande (`data/icu/zooms/`).
- Méthode : un îlot réunit les LCZ 1 à 3 (bâti compact) et les LCZ 4 à 6 situées à moins de 15 m (voisines directes), sous leur enveloppe convexe ; seuls les îlots d'au moins 10 ha sont retenus (2 277 îlots, de 0,9 km² à Annemasse à 254 km² à Paris).
- Pied de page et README : source Cerema (avec lien), méthode, contours des communes et position des mairies.

### Outillage
- `scripts/icu/` : `telecharger_lcz.py` (seul le shapefile de chaque archive, par plages d'octets), `calcul_icu.py` (îlots), `extraire_eau.py` (LCZ G), `preparer_icu.py` (synthèse et encarts) ; données préparées dans `data/icu/`.
- `requirements.txt` : pyshp et pyproj (recalcul de la couche ICU seulement).

## [1.1.8] — 22/10/2026

Contours des départements masquables.

### Ajouté
- Couche « Contours des départements » dans la boîte Couches, visible par défaut : désactivée, les départements prennent un trait de la couleur de leur zone (aucun liseré entre voisins) et seules les limites des zones restent tracées. Le survol, le département sélectionné et la fiche département sont inchangés.

## [1.1.6] — 18/10/2026

Stations météo de référence RE2020 et températures horaires par zone.

### Ajouté
- Couche « Stations météo RE2020 », visible par défaut et placée en tête de la boîte Couches : une station par zone (Trappes, Nancy, Mâcon, Rennes, Tours, Agen, Carpentras, Marignane), dessinée en cible bleue reliée à un cartouche translucide « Météo + nom » ; survol : nom et altitude de la station. Rennes, Tours et Agen ne sont plus dessinées comme villes quand la couche est affichée.
- Mention « avec l'aide du Hub des Prescripteurs Bas Carbone » (lien IFPEB) en pied de page et dans le README.
- `data/meteo/meteo_<zone>.csv` : température extérieure horaire (te0, °C, 8 760 heures) des scénarios Th-BC (climat moyen) et Th-D (canicule), extraite par `scripts/meteo/extraire_meteo.py`.

### Modifié
- Paris : libellé à droite du point (la station de Trappes est à l'ouest) ; nom de zone H1c décalé vers l'est (station de Mâcon).

## [1.1.3] — 18/10/2026

Revue du code et allègement de la page, sans changement de contenu.

### Modifié
- Page allégée : 713 Ko → 214 Ko (171 Ko → 57 Ko compressés). Départements simplifiés en pavage (chaque frontière commune simplifiée une seule fois, sans jour entre voisins), limites de zones et contour de la France tirés de ce pavage, chemins SVG en coordonnées relatives arrondies à 0,5 unité.
- Polices hébergées dans le dépôt (`polices/`, WOFF2 réduits aux caractères latins, 78 Ko) : plus aucun appel à Google Fonts.
- Espaces insécables entre les nombres et les unités (%, °C.h, M) : « 29,6 % » ne passe plus à la ligne dans la boîte Logements.
- Pied de page : source réglementaire des zones (décret n° 2021-1004 du 29 juillet 2021), contours IGN Admin Express via france-geojson, polices et licences.

### Outillage
- Fonds de carte versionnés dans `data/fonds/`, préparés par `scripts/preparer_fonds.py` à partir de commits figés de france-geojson et Natural Earth : `python3 scripts/build_map.py` suffit pour régénérer la page.
- Repères (villes, pays et mers, fleuves, massifs) sortis du code vers `data/reperes.json`.
- `scripts/geo_utils.py` : outils communs aux scripts ; `build_map.py` organisé en fonctions avec `main()`.
- Liste des zones, seuils DH et nombre de départements définis une seule fois dans `build_map.py` et injectés dans la page.
- Fichiers texte avec en-tête ; logements joints par code département (contrôle du nom).
- Couche « relief » renommée « altitude » dans le code ; aperçu matplotlib obsolète retiré des scripts d'altitude.
- `requirements.txt`, `scripts/preparer_polices.py`, README réécrit (fichiers, commandes, sources et licences).

## [1.1.2] — 18/10/2026

### Ajouté
- Couche « DH médian sur la carte » (masquée par défaut) : sous le nom de chaque zone, une étiquette « DH méd. xxx °C.h » dans une boîte arrondie sombre semi-transparente, pour se distinguer des noms de villes. Pour H2d et H3, l'étiquette est placée au-dessus du nom afin d'éviter Avignon et Perpignan. Étiquettes générées par `scripts/build_map.py` (paramètres `DH_LABEL_*`) à partir de `data/dh_median_opee.csv`.

## [1.1.1] — 18/10/2026

### Modifié
- Couleurs des zones attribuées dans l'ordre croissant du DH médian, sur toute la page (carte, légende, fiche, boîtes) : la plus claire pour H2a (216 °C.h), puis H1c, H1b, H2c, H1a, H2b, H2d, la plus foncée pour H3 (1 103 °C.h). La palette est générée par `scripts/build_map.py` (`PALETTE_ZONES`) à partir de `data/dh_median_opee.csv`.
- Boîte DH : lignes triées par DH médian croissant, titre « DH médians · collectifs · OPEE », note précisant qu'il s'agit d'une sélection de logements collectifs.

## [1.1.0] — 18/10/2026

### Ajouté
- Boîte « DH médians · OPEE » : degré-heures médian par zone (bâtiments conformes de l'open data OPEE, extraction du 18/10/2026), barre sur une échelle commune avec deux traits de référence, 350 °C.h (au-delà, pénalité forfaitaire de climatisation dans le Cep) et 1 250 °C.h (DH max courant), nombre de bâtiments et ligne « Toutes zones ». Le survol d'une ligne isole la zone sur la carte.
- Fiche département : badge « DH méd. » de la zone, rectangulaire à bord coloré, à côté de la pastille de zone.
- Boîtes de la colonne dépliables (titre cliquable avec chevron), toutes ouvertes par défaut ; l'état plié ou déplié est mémorisé dans le navigateur de chaque visiteur.

### Modifié
- Nouvel ordre de la colonne : Département, Couches, Zones, DH médians, Logements par zone. La fiche département porte désormais le titre « Département ».

### Données
- `data/dh_median_opee.csv` : synthèse par zone (nombre de bâtiments, médiane, Q3), lue par `scripts/build_map.py` (seule la médiane est affichée).

## [1.0.3] — 18/10/2026

### Modifié
- La couche « Massifs montagneux » (contours Natural Earth) est remplacée par une couche « Altitude » issue d'un modèle numérique de terrain : hachures à 45° au-dessus de 400 m, hachures à 135° ajoutées au-dessus de 800 m (quadrillage). Les noms des massifs restent affichés comme repères. Légende intégrée à l'interrupteur.

### Données
- `data/altitude_re2020.geojson` (133 Ko) : MNT France métropolitaine (~90 m, EPSG:4326) agrégé à ~500 m, deux surfaces emboîtées (> 400 m, > 800 m), îlots et creux de moins de 70 km² retirés, contour simplifié à ~1 km. Scripts de calcul dans `scripts/altitude/` (le MNT source, 140 Mo, n'est pas versionné).

## [1.0.2] — 17/10/2026

### Ajouté
- Favicon : l'Hexagone découpé en trois bandes aux couleurs des zones H1, H2 et H3. Fichiers `favicon.svg` (navigateurs récents), `favicon-32.png` (repli) et `apple-touch-icon.png` (écran d'accueil iPhone / iPad), déclarés dans l'en-tête généré par `scripts/build_map.py`.

## [1.0.1] — 17/10/2026

### Corrigé
- Enclave des Papes (îlot du Vaucluse entouré par la Drôme) : l'îlot n'a plus de liseré blanc au repos et se fond dans la zone H2d. Il reste cliquable et ouvre la fiche du Vaucluse. La détection est automatique et s'applique aussi aux autres îlots du fond de carte (Hautes-Pyrénées dans les Pyrénées-Atlantiques, Nord dans le Pas-de-Calais), tous dans la même zone que leur hôte.

### Ajouté
- Villes repères pour la zone H2d : Avignon et Valence.

### Modifié
- Étiquette « H2d » déplacée vers le sud-ouest pour ne pas chevaucher Valence.

## [1.0.0] — 17/10/2026

Première mise en ligne.

### Ajouté
- Carte des 96 départements de France métropolitaine colorés par zone climatique RE2020 (H1a à H3), palette du jaune à l'orange brûlé.
- Limites et noms des zones sur la carte.
- Fiche par département au survol ou au toucher : région, zone, logements.
- Légende interactive : survol ou clic sur une zone pour l'isoler.
- Logements par zone : effectif en millions et part du parc métropolitain.
- Couches activables : villes, noms des départements (masqués par défaut), mers, fleuves et pays voisins, massifs montagneux.
- Thème clair et sombre selon le réglage du navigateur.
- Script de génération `scripts/build_map.py` et gabarit `scripts/template.html`.

### Données
- Zonage climatique par département : tableau fourni (Eure-et-Loir confirmé en H1a).
- Logements : Insee, recensement de la population 2022, exploitation principale (édition juin 2025). Total métropole : 36 568 979 logements (somme des départements, 2 d'écart d'arrondi avec l'agrégat Insee).
- Contours des départements : france-geojson (version simplifiée).
- Fleuves, lacs, pays voisins, massifs : Natural Earth (téléchargés le 17/10/2026).
