# Journal des versions

Numérotation [SemVer](https://semver.org/lang/fr/) :
- **correctif** (1.0.x) : correction de données ou d'affichage ;
- **mineure** (1.x.0) : nouvelle couche, nouvelle fonction ;
- **majeure** (x.0.0) : refonte.

La version est définie par la constante `VERSION` en tête de `scripts/build_map.py`, affichée en pied de page et reportée en tag git (`vX.Y.Z`).

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
