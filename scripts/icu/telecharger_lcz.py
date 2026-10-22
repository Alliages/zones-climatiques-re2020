"""Télécharge le seul shapefile de chaque archive LCZ du Cerema (métropole), par plages d'octets.

Usage : python3 scripts/icu/telecharger_lcz.py <dossier_sortie> [slug ...]

- Liste des archives : API data.gouv.fr du jeu « Cartographie des zones climatiques locales (LCZ) »
  (6641c562e5acdb35c0e6051d). Seules les 88 archives « lcz-spot-2022-<ville>.zip » (métropole)
  sont traitées ; les 5 archives des DOM (lcz-sat-2022-*) sont exclues.
- Pour chaque archive : lecture du répertoire central à distance, puis téléchargement des seuls
  membres .shp/.shx/.dbf/.prj (le raster 1,5 m et les PDF, très lourds, sont ignorés) :
  environ 3 Go au lieu de 8,5 Go.
- Connexion instable : morceaux de 2 Mo repris chacun jusqu'à 12 fois ; un territoire déjà complet
  (fichier OK) est sauté, il suffit de relancer après un incident.
"""
import concurrent.futures as cf
import json
import os
import struct
import subprocess
import sys
import time
import zlib

# --- Réglages ---------------------------------------------------------------
API = "https://www.data.gouv.fr/api/1/datasets/6641c562e5acdb35c0e6051d/"
PREFIXE = "lcz-spot-2022-"                       # archives métropole (les DOM sont en lcz-sat-2022-)
EXTENSIONS = (".shp", ".shx", ".dbf", ".prj")
MORCEAU = 2 * 1024 * 1024                        # taille d'une requête (octets)
ESSAIS = 12                                      # reprises par requête
PARALLELE = 8                                    # territoires téléchargés en même temps
TAILLE_FIN = 65_536                              # fin d'archive lue pour trouver l'EOCD
CURL = ["curl", "-s", "--http1.1", "--max-time", "90"]   # HTTP/1.1 : plus stable derrière un proxy


def requete(url, plage=None):
    """Contenu de `url` (ou des octets `plage` = (début, fin) inclus), avec reprises."""
    attendu = None if plage is None else plage[1] - plage[0] + 1
    for essai in range(ESSAIS):
        cmd = CURL + (["-r", f"{plage[0]}-{plage[1]}"] if plage else []) + [url]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and r.stdout and (attendu is None or len(r.stdout) == attendu):
            return r.stdout
        time.sleep(min(2 * (essai + 1), 10))
    raise RuntimeError(f"échec {url} {plage}")


def plage_longue(url, debut, fin):
    """Plage découpée en morceaux (chacun repris indépendamment)."""
    return b"".join(requete(url, (a, min(a + MORCEAU - 1, fin))) for a in range(debut, fin + 1, MORCEAU))


def membres_zip(url, total):
    """Liste (nom, méthode, taille compressée, offset) lue dans le répertoire central (Zip64 compris)."""
    fin = requete(url, (max(0, total - TAILLE_FIN), total - 1))
    i = fin.rfind(b"PK\x05\x06")
    cd_taille, cd_offset = struct.unpack("<II", fin[i + 12:i + 20])
    j = fin.rfind(b"PK\x06\x06")
    if j != -1:
        cd_taille, cd_offset = struct.unpack("<QQ", fin[j + 40:j + 56])
    cd = plage_longue(url, cd_offset, cd_offset + cd_taille - 1)
    p, membres = 0, []
    while cd[p:p + 4] == b"PK\x01\x02":
        meth, = struct.unpack("<H", cd[p + 10:p + 12])
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nl, el, kl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off, = struct.unpack("<I", cd[p + 42:p + 46])
        nom = cd[p + 46:p + 46 + nl].decode("utf-8", "replace")
        extra = cd[p + 46 + nl:p + 46 + nl + el]
        q = 0
        while q < len(extra):
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:                         # Zip64 : taille réelle, taille compressée, offset
                vals, k = extra[q + 4:q + 4 + hl], 0
                if usize == 0xFFFFFFFF:
                    usize, = struct.unpack("<Q", vals[k:k + 8]); k += 8
                if csize == 0xFFFFFFFF:
                    csize, = struct.unpack("<Q", vals[k:k + 8]); k += 8
                if off == 0xFFFFFFFF:
                    off, = struct.unpack("<Q", vals[k:k + 8]); k += 8
            q += 4 + hl
        membres.append((nom, meth, csize, off))
        p += 46 + nl + el + kl
    return membres


def telecharger(slug, url, total, sortie):
    """Shapefile d'un territoire → <sortie>/<slug>/lcz.{shp,shx,dbf,prj}."""
    dossier = os.path.join(sortie, slug)
    if os.path.exists(os.path.join(dossier, "OK")):
        return slug, "déjà présent"
    os.makedirs(dossier, exist_ok=True)
    t0, octets = time.time(), 0
    for nom, meth, csize, off in membres_zip(url, total):
        if not nom.lower().endswith(EXTENSIONS):
            continue
        entete = requete(url, (off, off + 29))
        nl, el = struct.unpack("<HH", entete[26:30])
        debut = off + 30 + nl + el
        brut = plage_longue(url, debut, debut + csize - 1)
        data = zlib.decompress(brut, -15) if meth == 8 else brut
        with open(os.path.join(dossier, "lcz" + os.path.splitext(nom)[1].lower()), "wb") as f:
            f.write(data)
        octets += csize
    open(os.path.join(dossier, "OK"), "w").close()
    return slug, f"{octets / 1e6:.1f} Mo en {time.time() - t0:.0f} s"


def main():
    sortie, choix = sys.argv[1], set(sys.argv[2:])
    archives = [(r["title"][len(PREFIXE):-4], r["url"], r["filesize"])
                for r in json.loads(requete(API))["resources"]
                if r["title"].startswith(PREFIXE) and r["title"].endswith(".zip")]
    if choix:
        archives = [a for a in archives if a[0] in choix]
    archives.sort(key=lambda a: -a[2])           # les plus grosses d'abord : elles fixent la durée
    print(f"{len(archives)} archives", flush=True)
    erreurs = []
    with cf.ThreadPoolExecutor(PARALLELE) as ex:
        futurs = {ex.submit(telecharger, s, u, t, sortie): s for s, u, t in archives}
        for n, f in enumerate(cf.as_completed(futurs), 1):
            try:
                slug, info = f.result()
                print(f"[{n}/{len(archives)}] {slug} : {info}", flush=True)
            except Exception as e:                # on continue : relancer reprend les manquants
                erreurs.append(futurs[f])
                print(f"[{n}/{len(archives)}] {futurs[f]} : ERREUR {e}", flush=True)
    print("Terminé ; erreurs :", erreurs or "aucune", flush=True)


if __name__ == "__main__":
    main()
