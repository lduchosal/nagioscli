---
id: 747
title: "CLI / nagioscli self-update command"
status: done
who: "Claude"
due_date: 
classified_at: 2026-07-28T08:56:56
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: cli/commands
section_title: "CLI commands"
---

# #747 — CLI / nagioscli self-update command

## Contexte

`nagioscli` est distribué sur PyPI sous le nom `nachos`. Aujourd'hui,
mettre à jour l'outil impose à l'utilisateur de connaître ce détail
(`pip install -U nachos`, et pas `pip install -U nagioscli`), ce qui
est un piège récurrent vu le décalage repo / module / binaire vs.
distribution.

## Objectif

Ajouter une commande `nagioscli self-update` qui met à jour le binaire
vers la dernière version publiée sur PyPI sans que l'utilisateur ait à
mémoriser le nom de la distribution.

## Comportement attendu

- `nagioscli self-update` interroge PyPI pour récupérer la dernière
  version de la distribution `nachos`.
- Compare avec `nagioscli.__version__` :
  - si déjà à jour : message clair (`Already on latest: X.Y.Z`) et
    code de sortie 0.
  - sinon : annonce `Updating nachos X.Y.Z -> A.B.C` puis exécute
    `pip install --upgrade nachos` (via `sys.executable -m pip`) dans
    le bon interpréteur (pipx / venv / system).
- `--check` : n'effectue pas la mise à jour, imprime juste la version
  disponible et termine avec un code de sortie != 0 si une mise à jour
  est disponible (utile pour les hooks shell / CI).
- `--pre` : autorise les pré-releases lors du lookup et du `pip
  install`.
- Détection pipx : si `nagioscli` tourne dans un environnement géré
  par pipx (variable `PIPX_HOME` ou chemin contenant `/pipx/venvs/`),
  préférer `pipx upgrade nachos` et retomber sur `pip` si pipx est
  introuvable. Afficher la commande effectivement lancée avant
  exécution.
- En cas d'échec réseau / 404 / HTTP non-200 : message d'erreur clair,
  code de sortie 1, pas de traceback brut.

## Contraintes

- Pas de nouvelle dépendance runtime : utiliser `urllib` de la stdlib
  pour interroger `https://pypi.org/pypi/nachos/json` (cohérent avec
  `core/client.py`).
- Respecter le quirk de nommage : le code doit explicitement mettre
  à jour la distribution `nachos`, pas `nagioscli`. Documenter ce
  point en commentaire court à l'endroit où le nom est codé en dur.
- Couverture de test :
  - mock de la réponse PyPI JSON (cas à jour, cas update disponible,
    cas pré-release filtrée),
  - mock de `subprocess.run` pour vérifier la commande construite
    (pip vs. pipx, `--pre` ou pas),
  - cas erreur réseau.

## Pistes d'implémentation

- Nouveau fichier `nagioscli/cli/commands/self_update.py` avec un
  handler Click, enregistré dans le groupe principal.
- Helper `nagioscli/services/self_update.py` pour la logique pure
  (fetch PyPI, comparaison de versions, construction de la commande
  d'upgrade) afin de garder le handler CLI mince et testable.
- Comparaison de versions : `packaging.version.Version` est déjà tiré
  transitivement par PDM ; vérifier avant d'ajouter `packaging` comme
  dépendance explicite — sinon implémenter un comparateur SemVer
  minimal local.

## Hors scope

- Auto-update silencieux au démarrage.
- Vérification de signatures / hashes PyPI.
- Downgrade vers une version arbitraire (`--version X.Y.Z`).
---

[← retour à cli/commands](index.md) · [voir log](../../log.md)
