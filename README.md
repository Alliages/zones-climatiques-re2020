# Zones climatiques RE2020

Carte interactive des 96 départements de France métropolitaine colorés selon leur zone climatique RE2020 (H1a à H3), avec le DH médian et le nombre de logements par zone.

**Voir la carte : https://alliages.github.io/zones-climatiques-re2020/**

Version actuelle : **1.1.3**. Historique dans [CHANGELOG.md](CHANGELOG.md), évolutions prévues dans [ROADMAP.md](ROADMAP.md).

## Ce que montre la page

- La zone climatique de chaque département, avec les limites et le nom des zones. Les couleurs des zones vont du plus clair au plus foncé selon leur DH médian.
- Une fiche par département au survol ou au toucher : région, zone, DH médian de la zone, nombre de logements et répartition résidences principales, secondaires et vacantes.
- Le degré-heures (DH) médian par zone, issu de l'open data OPEE (sélection de logements collectifs conformes), avec les repères 350 et 1 250 °C.h.
- Le parc de logements par zone, en millions et en part du total métropolitain.
- Des boîtes dépliables dans la colonne de droite, dont l'état est mémorisé par le navigateur.
- Des couches activables : villes, noms des départements (masqués par défaut), DH médian sur la carte (masqué par défaut), mers, fleuves et pays voisins, altitude (400–800 m et plus de 800 m).

La page est autonome et légère : environ 215 Ko (57 Ko compressés) plus 78 Ko de polices hébergées dans le dépôt, sans appel à un service tiers.

## Fichiers

| Fichier | Contenu |
|---|---|
| `index.html` | La page, générée (ne pas modifier à la main) |
| `polices/` | Polices WOFF2 (sous-ensemble latin) et leurs licences SIL OFL |
| `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` | Icônes de l'onglet et de l'écran d'accueil |
| `data/zones_departements.txt` | Région, code, nom, zone (séparateur `\|`, avec en-tête) |
| `data/logements_insee_2022.txt` | Code, nom, logements, % résidences principales, secondaires, vacants |
| `data/dh_median_opee.csv` | DH médian et Q3 par zone, nombre de bâtiments (export OPEE, `;` et virgule décimale) |
| `data/reperes.json` | Villes, libellés des pays et des mers, fleuves et massifs affichés |
| `data/altitude_re2020.geojson` | Classes d'altitude > 400 m et > 800 m (issues du MNT, simplifiées) |
| `data/fonds/` | Fonds de carte : départements, pays, lacs, fleuves, massifs (extraits figés) |
| `scripts/build_map.py` | Génère `index.html` à partir des données et du gabarit |
| `scripts/template.html` | Gabarit HTML / CSS / JS de la page |
| `scripts/geo_utils.py` | Outils communs : lecture des données, géométrie, projection, chemins SVG |
| `scripts/preparer_fonds.py` | Prépare `data/fonds/` depuis france-geojson et Natural Earth (commits figés) |
| `scripts/preparer_polices.py` | Prépare `polices/` depuis Google Fonts (commit figé) |
| `scripts/altitude/` | Calcul de la couche Altitude depuis un MNT |

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

## Publier une nouvelle version

1. Modifier `VERSION` en tête de `scripts/build_map.py` (correctif 1.0.x, mineure 1.x.0, majeure x.0.0).
2. Régénérer `index.html`.
3. Ajouter l'entrée correspondante dans `CHANGELOG.md` (et cocher `ROADMAP.md`).
4. Committer et pousser, puis créer la release `vX.Y.Z` sur GitHub (Releases → Draft a new release).

## Sources et licences

- **Zones climatiques** : annexe du décret n° 2021-1004 du 29 juillet 2021 (RE2020), répartition des départements en huit zones.
- **Logements** : Insee, recensement de la population 2022, exploitation principale (« Logements selon la catégorie en 2022, comparaisons départementales »), Licence Ouverte. Le nombre de résidences principales par zone est estimé à partir des parts publiées en pourcentage.
- **DH médians** : open data OPEE (RE2020), sélection de logements collectifs conformes, extraction du 18/10/2026.
- **Contours des départements** : IGN Admin Express, via [france-geojson](https://github.com/gregoiredavid/france-geojson) (Grégoire David), Licence Ouverte.
- **Fleuves, lacs, pays voisins, massifs** : [Natural Earth](https://www.naturalearthdata.com/), domaine public.
- **Altitude** : modèle numérique de terrain ~90 m (EPSG:4326). Couche indicative : la classe d'altitude RE2020 d'un projet se détermine à l'altitude réelle du terrain.
- **Polices** : [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque), [Public Sans](https://fonts.google.com/specimen/Public+Sans), [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono), licence SIL Open Font License 1.1 (textes dans `polices/`).
- **Bibliothèques Python** (génération uniquement, voir `requirements.txt`) : [Shapely](https://shapely.readthedocs.io/), [NumPy](https://numpy.org/), [fontTools](https://github.com/fonttools/fonttools), [Brotli](https://github.com/google/brotli), [rasterio](https://rasterio.readthedocs.io/).

Le code est distribué sous licence GNU GPL v3 (voir `LICENSE`). La page publiée n'utilise aucune bibliothèque JavaScript externe.
