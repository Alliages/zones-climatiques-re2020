# Évolutions prévues

Liste des modifications à apporter dans les prochaines versions. Chaque ligne cochée renvoie à la version du `CHANGELOG.md` qui l'a livrée.

## Données et calculs
- [ ] Exploiter les documents complémentaires RE2020 : https://rt-re-batiment.developpement-durable.gouv.fr/documents-complementaires-a706.html
- [ ] Calculer les degrés-heures (DH)
- [ ] Partager le code de calcul des DH
- [x] Afficher les DH médians par zone issus de l'open data OPEE (→ 1.1.0, 1.1.1)
- [x] Couche « DH médian sur la carte » (→ 1.1.2)
- [ ] DH médian par département (nécessite le département ou la commune dans l'extraction OPEE)
- [ ] Préciser les îlots de chaleur urbains (ICU) : couche « Zones soumises à ICU » à partir des zones climatiques locales (LCZ) du Cerema, métropole

## Météo
- [ ] Afficher les courbes des fichiers météo
- [ ] Créer des liens vers le wiki des données météo : https://github.com/Alliages/meteo/wiki/WIKI-Donn%C3%A9es-M%C3%A9t%C3%A9o

## Cartographie
- [ ] Ajouter un lien vers la carte NV50
- [x] Afficher l'altitude : classes 400–800 m et > 800 m en hachures, à la place des massifs (→ 1.0.3)
- [x] Couleurs des zones dans l'ordre du DH médian (→ 1.1.1)
- [ ] Préciser la source du MNT utilisé pour l'altitude dans le pied de page et le README

## Interface
- [x] Favicon de l'application (→ 1.0.2)
- [x] Boîtes dépliables, nouvel ordre de la colonne (→ 1.1.0)
- [ ] Bouton « Télécharger la carte (PNG) » (polices déjà hébergées dans le dépôt depuis la 1.1.3)
- [ ] Option de couleurs sombres pour la palette des zones
- [ ] Ajouter une partie explication

## Outillage
- [x] Revue du code : fonds de carte versionnés, repères en JSON, module commun, page allégée, polices hébergées (→ 1.1.3)
- [ ] GitHub Action : à chaque push sur `main`, lire `VERSION` dans `scripts/build_map.py` et créer automatiquement le tag `vX.Y.Z` et la release (description tirée du `CHANGELOG.md`) si le tag n'existe pas encore
