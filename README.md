# Zones climatiques RE2020

Carte interactive des 96 départements de France métropolitaine colorés selon leur zone climatique RE2020 (H1a à H3), avec le nombre de logements par département et par zone.

**Voir la carte : https://alliages.github.io/zones-climatiques-re2020/**

Version actuelle : **1.0.2**. Historique dans [CHANGELOG.md](CHANGELOG.md), évolutions prévues dans [ROADMAP.md](ROADMAP.md).

## Ce que montre la page

- La zone climatique de chaque département, avec les limites et le nom des zones.
- Une fiche par département au survol ou au toucher : région, zone, nombre de logements et répartition résidences principales, secondaires et vacantes.
- Le parc de logements par zone, en millions et en part du total métropolitain.
- Des couches activables : villes, noms des départements (masqués par défaut), mers, fleuves et pays voisins, massifs montagneux.

## Fichiers

| Fichier | Contenu |
|---|---|
| `index.html` | La page, autonome (aucune dépendance hormis les polices Google Fonts) |
| `data/zones_departements.txt` | Région, numéro, département, zone (séparateur `\|`) |
| `data/logements_insee_2022.txt` | Département, logements, % résidences principales, % secondaires, % vacants |
| `scripts/build_map.py` | Génère `index.html` à partir des données et du gabarit |
| `scripts/template.html` | Gabarit HTML/CSS/JS de la page |

## Régénérer la page

Les fonds de carte ne sont pas versionnés : téléchargez-les dans un dossier `geo/`.

```bash
mkdir -p geo
curl -sL -o geo/dep.geojson https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson
B=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
for f in ne_10m_rivers_lake_centerlines ne_10m_rivers_europe ne_50m_admin_0_countries ne_10m_geography_regions_polys ne_10m_lakes; do
  curl -sL -o geo/$f.geojson $B/$f.geojson
done

pip install shapely
python3 scripts/build_map.py geo data/zones_departements.txt scripts/template.html \
  /tmp/apercu.html data/logements_insee_2022.txt index.html
```

## Publier une nouvelle version

1. Modifier `VERSION` en tête de `scripts/build_map.py` (correctif 1.0.x, mineure 1.x.0, majeure x.0.0).
2. Régénérer `index.html` avec la commande ci-dessus.
3. Ajouter l'entrée correspondante dans `CHANGELOG.md`.
4. Committer, puis taguer : `git tag -a vX.Y.Z -m "Version X.Y.Z"` et `git push origin main --tags`.

## Sources

- Zones climatiques : correspondance département → zone RE2020.
- Logements : Insee, recensement de la population 2022, exploitation principale (« Logements selon la catégorie en 2022, comparaisons départementales »). Le nombre de résidences principales par zone est estimé à partir des parts publiées en pourcentage.
- Contours des départements : [france-geojson](https://github.com/gregoiredavid/france-geojson) (Grégoire David).
- Fleuves, lacs, pays voisins, massifs : [Natural Earth](https://www.naturalearthdata.com/).

Les contours des massifs sont indicatifs et ne correspondent pas aux classes d'altitude que la RE2020 applique en plus de la zone climatique.
