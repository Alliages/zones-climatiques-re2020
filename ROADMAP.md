# Évolutions prévues

Liste des modifications à apporter dans les prochaines versions. Chaque ligne cochée renvoie à la version du `CHANGELOG.md` qui l'a livrée.

## Données et calculs
- [ ] Exploiter les documents complémentaires RE2020 : https://rt-re-batiment.developpement-durable.gouv.fr/documents-complementaires-a706.html
- [ ] Calculer les degrés-heures (DH)
- [ ] Afficher les DH moyens issus de l'open data OPEE
- [ ] Préciser les îlots de chaleur urbains (ICU)

## Météo
- [ ] Afficher les courbes des fichiers météo
- [ ] Créer des liens vers le wiki des données météo : https://github.com/Alliages/meteo/wiki/WIKI-Donn%C3%A9es-M%C3%A9t%C3%A9o

## Cartographie
- [ ] Ajouter un lien vers la carte NV50
- [x] Afficher l'altitude : classes 400–800 m et > 800 m en hachures, à la place des massifs (→ 1.0.3)

## Interface
- [x] Favicon de l'application (→ 1.0.2)
- [ ] Option de couleurs sombres pour la palette des zones
- [ ] Ajouter une partie explication

## Outillage
- [ ] GitHub Action : à chaque push sur `main`, lire `VERSION` dans `scripts/build_map.py` et créer automatiquement le tag `vX.Y.Z` et la release (description tirée du `CHANGELOG.md`) si le tag n'existe pas encore
