# Zones climatiques RE2020

Carte interactive des 96 départements de France métropolitaine colorés selon leur zone climatique RE2020 (H1a à H3), avec le DH médian et le nombre de logements par zone.

**Voir la carte : https://alliages.github.io/zones-climatiques-re2020/**

Réalisée avec l'aide du [Hub des Prescripteurs Bas Carbone](https://www.ifpeb.fr/nos-expertises/la-technique/le-hub-des-prescripteurs-bas-carbone/).

Version actuelle : **1.1.6**. Historique dans [CHANGELOG.md](CHANGELOG.md), évolutions prévues dans [ROADMAP.md](ROADMAP.md).

## Ce que montre la page

- La zone climatique de chaque département, avec les limites et le nom des zones. Les couleurs des zones vont du plus clair au plus foncé selon leur DH médian.
- Une fiche par département au survol ou au toucher : région, zone, DH médian de la zone, nombre de logements et répartition résidences principales, secondaires et vacantes.
- Le degré-heures (DH) médian par zone, issu de l'open data OPEE (sélection de logements collectifs conformes), avec les repères 350 et 1 250 °C.h.
- Le parc de logements par zone, en millions et en part du total métropolitain.
- Des boîtes dépliables dans la colonne de droite, dont l'état est mémorisé par le navigateur.
- Les îlots de chaleur urbains (ICU) de 88 territoires de plus de 50 000 habitants, d'après les zones climatiques locales (LCZ) du Cerema : un point par territoire, proportionnel à la surface ICU ; au clic, un zoom sur la commune centre (îlots, communes voisines, cours et plans d'eau, mairie) avec la surface ICU et celle de la ville.
- Des couches activables : îlots de chaleur urbains, stations météo de référence RE2020 (une par zone), villes, noms des départements (masqués par défaut), DH médian sur la carte (masqué par défaut), mers, fleuves et pays voisins, altitude (400–800 m et plus de 800 m).

La page est autonome et légère : environ 245 Ko (66 Ko compressés) plus 78 Ko de polices hébergées dans le dépôt, sans appel à un service tiers. Les zooms ICU (40 Ko en moyenne, 500 Ko pour Paris) ne sont chargés qu'au clic.

## Fichiers

| Fichier | Contenu |
|---|---|
| `index.html` | La page, générée (ne pas modifier à la main) |
| `polices/` | Polices WOFF2 (sous-ensemble latin) et leurs licences SIL OFL |
| `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` | Icônes de l'onglet et de l'écran d'accueil |
| `data/zones_departements.txt` | Région, code, nom, zone (séparateur `\|`, avec en-tête) |
| `data/logements_insee_2022.txt` | Code, nom, logements, % résidences principales, secondaires, vacants |
| `data/dh_median_opee.csv` | DH médian et Q3 par zone, nombre de bâtiments (export OPEE, `;` et virgule décimale) |
| `data/reperes.json` | Stations météo, villes, libellés des pays et des mers, fleuves et massifs affichés |
| `data/meteo/meteo_<zone>.csv` | Température extérieure horaire (°C) : `heure`, `th_bc` (climat moyen), `th_d` (canicule) ; `;` et virgule décimale |
| `data/altitude_re2020.geojson` | Classes d'altitude > 400 m et > 800 m (issues du MNT, simplifiées) |
| `data/icu/territoires.json` | Par territoire LCZ : centre, surface ICU, nombre d'îlots, commune centre et sa surface |
| `data/icu/zooms/<territoire>.html` | Encart de zoom (SVG) chargé au clic sur un point ICU |
| `data/icu/synthese_icu.csv` | Tableau de contrôle des 88 territoires (`;` et virgule décimale) |
| `data/icu/villes_lcz.json` | Centre-ville de chaque territoire (position du point sur la carte) |
| `data/fonds/` | Fonds de carte : départements, pays, lacs, fleuves, massifs (extraits figés) |
| `scripts/build_map.py` | Génère `index.html` à partir des données et du gabarit |
| `scripts/template.html` | Gabarit HTML / CSS / JS de la page |
| `scripts/geo_utils.py` | Outils communs : lecture des données, géométrie, projection, chemins SVG |
| `scripts/preparer_fonds.py` | Prépare `data/fonds/` depuis france-geojson et Natural Earth (commits figés) |
| `scripts/preparer_polices.py` | Prépare `polices/` depuis Google Fonts (commit figé) |
| `scripts/altitude/` | Calcul de la couche Altitude depuis un MNT |
| `scripts/icu/` | Couche ICU : téléchargement des LCZ, calcul des îlots, eau, préparation des zooms |
| `scripts/meteo/extraire_meteo.py` | Extrait `data/meteo/` du classeur des scénarios météo RE2020 |

## Régénérer la page

Tout ce qu'il faut est dans le dépôt :

```bash
pip install -r requirements.txt     # shapely et numpy suffisent pour cette étape
python3 scripts/build_map.py        # écrit index.html
```

Option : `--apercu apercu.html` écrit en plus la page sans en-tête HTML (aperçu dans Claude).

Les réglages (version, palette, simplifications, positions des étiquettes, seuils DH) sont regroupés en tête de `scripts/build_map.py` ; les villes et libellés dans `data/reperes.json`.

## Mettre à jour les fonds de carte ou les polices

À ne relancer que pour changer de version des sources (commits figés en tête des scripts) ou de repères :

```bash
python3 scripts/preparer_fonds.py     # → data/fonds/  (téléchargements dans .cache/, non versionné)
python3 scripts/preparer_polices.py   # → polices/
```

## Recalculer la couche Altitude

À partir d'un MNT GeoTIFF de la France métropolitaine (non versionné, ~140 Mo) :

```bash
python3 scripts/altitude/classes_altitude_france.py France_metropolitaine.tif /tmp/alt      # classes brutes (~4 min)
python3 scripts/altitude/simplifier_altitude.py /tmp/alt/classes_altitude_re2020.geojson data/altitude_re2020.geojson
```

## Recalculer la couche ICU

Données du Cerema (88 archives, seuls les shapefiles sont téléchargés, ~3 Go, non versionnés) :

```bash
python3 scripts/icu/telecharger_lcz.py /tmp/lcz                                  # → /tmp/lcz/<territoire>/ (reprise possible)
for d in /tmp/lcz/*/; do t=$(basename $d)
  python3 scripts/icu/calcul_icu.py $d /tmp/icu/$t.json                            # îlots (le plus long : Paris)
  python3 scripts/icu/extraire_eau.py $d /tmp/eau/$t.json                          # eau (LCZ G ≥ 3 ha)
done
python3 scripts/icu/preparer_icu.py /tmp/icu /tmp/eau <communes_france-geojson> <communes-france-2026.csv.gz>
```

`preparer_icu.py` attend les fichiers `communes-<dép>-<nom>.geojson` de france-geojson (contours des communes) et le fichier « Communes et villes de France » de data.gouv.fr (position des mairies). Le seuil des îlots (`ICU_MIN_HA`, 10 ha) est réglé en tête du script ; il s'applique à la surface affichée comme au dessin.

## Publier une nouvelle version

1. Modifier `VERSION` en tête de `scripts/build_map.py` (correctif 1.0.x, mineure 1.x.0, majeure x.0.0).
2. Régénérer `index.html`.
3. Ajouter l'entrée correspondante dans `CHANGELOG.md` (et cocher `ROADMAP.md`).
4. Committer et pousser, puis créer la release `vX.Y.Z` sur GitHub (Releases → Draft a new release).

## Sources et licences

- **Zones climatiques** : annexe du décret n° 2021-1004 du 29 juillet 2021 (RE2020), répartition des départements en huit zones.
- **Logements** : Insee, recensement de la population 2022, exploitation principale (« Logements selon la catégorie en 2022, comparaisons départementales »), Licence Ouverte. Le nombre de résidences principales par zone est estimé à partir des parts publiées en pourcentage.
- **DH médians** : open data OPEE (RE2020), sélection de logements collectifs conformes, extraction du 18/10/2026.
- **Stations météo** : stations de référence des fichiers météo RE2020, note technique Météo-France / ADEME « Fichiers climatiques prospectifs Bâtiment » (2025), tableau 1 ; remplacement de La Rochelle et Nice (RT2012) par Tours et Marignane présenté en concertation RE2020 (DHUP, 22/07/2020).
- **Températures horaires** : scénarios météorologiques Th-BC et Th-D de la RE2020 (DHUP / Météo-France, mesures 2000-2018), réservés au calcul réglementaire RE2020.
- **Îlots de chaleur urbains** : [zones climatiques locales (LCZ) du Cerema](https://www.cerema.fr/fr/presse/dossier/zones-climatiques-locales-lcz-outil-libre-service-visualiser), cartographie de 93 territoires de plus de 50 000 habitants (images SPOT / Pléiades 2022-2023), [jeu de données sur data.gouv.fr](https://www.data.gouv.fr/datasets/6641c562e5acdb35c0e6051d), Licence Ouverte 2.0 ; les 88 territoires de métropole sont utilisés. Un îlot réunit les LCZ 1 à 3 et les LCZ 4 à 6 situées à moins de 15 m, sous leur enveloppe convexe ; seuls les îlots d'au moins 10 ha sont retenus. L'eau des zooms est la classe LCZ G (plans d'eau d'au moins 3 ha).
- **Communes et mairies (zooms ICU)** : contours des communes via [france-geojson](https://github.com/gregoiredavid/france-geojson), position des mairies d'après [« Communes et villes de France »](https://www.data.gouv.fr/datasets/6745d9ae4524d845d2138193) (data.gouv.fr), Licence Ouverte.
- **Contours des départements** : IGN Admin Express, via [france-geojson](https://github.com/gregoiredavid/france-geojson) (Grégoire David), Licence Ouverte.
- **Fleuves, lacs, pays voisins, massifs** : [Natural Earth](https://www.naturalearthdata.com/), domaine public.
- **Altitude** : modèle numérique de terrain ~90 m (EPSG:4326). Couche indicative : la classe d'altitude RE2020 d'un projet se détermine à l'altitude réelle du terrain.
- **Polices** : [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque), [Public Sans](https://fonts.google.com/specimen/Public+Sans), [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono), licence SIL Open Font License 1.1 (textes dans `polices/`).
- **Bibliothèques Python** (génération uniquement, voir `requirements.txt`) : [Shapely](https://shapely.readthedocs.io/), [NumPy](https://numpy.org/), [fontTools](https://github.com/fonttools/fonttools), [Brotli](https://github.com/google/brotli), [rasterio](https://rasterio.readthedocs.io/), [openpyxl](https://openpyxl.readthedocs.io/), [pyshp](https://github.com/GeospatialPython/pyshp), [pyproj](https://pyproj4.github.io/pyproj/).

Le code est distribué sous licence GNU GPL v3 (voir `LICENSE`). La page publiée n'utilise aucune bibliothèque JavaScript externe.
