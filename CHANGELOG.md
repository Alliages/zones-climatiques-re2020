# Journal des versions

Numérotation [SemVer](https://semver.org/lang/fr/) :
- **correctif** (1.0.x) : correction de données ou d'affichage ;
- **mineure** (1.x.0) : nouvelle couche, nouvelle fonction ;
- **majeure** (x.0.0) : refonte.

La version est définie par la constante `VERSION` en tête de `scripts/build_map.py`, affichée en pied de page et reportée en tag git (`vX.Y.Z`).

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
