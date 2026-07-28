---
id: 759
title: "CLI / self-update command"
status: done
who: "Claude"
due_date: 
classified_at: 2026-06-07T13:42:20
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: cli/commands
section_title: "CLI commands"
---

# #759 — CLI / self-update command

## Contexte

Ajouter une commande `nagioscli self-update` calquée sur les implémentations
existantes de :

- `../kenboard` → `ken self-update` (livré dans le paquet)
- `../semacli` → `sem self-update` (référence directe :
  `semacli/cli/commands/self_update.py`)

L'objectif est d'aligner l'UX : comparer la version installée à la dernière
release sur PyPI (paquet `nachos` — pas `nagioscli`, voir le quirk PyPI dans
`CLAUDE.md`) et lancer un `pip install --upgrade` ciblant l'interpréteur
courant (`sys.executable`).

## Spec attendue

- Fichier : `nagioscli/cli/commands/self_update.py`.
- Endpoint PyPI : `https://pypi.org/pypi/nachos/json`.
- Flags : `--check`, `--pre`, `--dry-run` (mêmes sémantiques que semacli).
- Codes de sortie :
  - `0` à jour ou upgrade OK
  - `1` upgrade dispo (en `--check`) ou échec pip
  - `2` PyPI injoignable
- Utilise `sys.executable -m pip install --upgrade nachos` (et non `pip`
  global).
- Helpers `_fetch_latest_version`, `_is_stable`, `_version_key`,
  `_pip_command` à reprendre tels quels (en remplaçant le nom du paquet).
- Enregistrement via `register_self_update_commands(main_group)` appelé
  depuis `nagioscli/cli/commands/__init__.py`.

## Dépendances

`requests` n'est PAS dans les deps runtime (`core/client.py` utilise
`urllib` exprès — voir `CLAUDE.md` § "Things not to do"). Réutiliser
`urllib.request` pour l'appel PyPI plutôt que d'ajouter `requests`.

## Tests

Tests unitaires dans `tests/unit/test_self_update.py` reprenant la
structure de `../semacli/tests/unit/test_self_update.py` :
- mock de l'appel HTTP (already-up-to-date, upgrade-available, network-fail)
- `--check` retourne 1 quand upgrade dispo
- `--dry-run` n'exécute pas `subprocess.run`

## Garde-fous

- `pdm run check` doit passer (lint + format + typecheck + tests).
- mypy strict : annoter complètement (`disallow_untyped_defs`).
- Couverture ≥ 80 % maintenue.

---

## Résolution

### Modifications

- `nagioscli/cli/commands/self_update.py` (nouveau) : commande Click
  `self-update` avec les flags `--check`, `--pre`, `--dry-run`. Helpers
  `_fetch_latest_version`, `_is_stable`, `_version_key`, `_pip_command`
  calqués sur semacli. Appel PyPI via `urllib.request.urlopen` (pas
  `requests`, conformément à `CLAUDE.md`). Contexte SSL construit avec
  `ssl.create_default_context(cafile=certifi.where())` pour éviter
  `CERTIFICATE_VERIFY_FAILED` sur macOS Python (où le truststore système
  n'est pas câblé par défaut).
- `nagioscli/cli/commands/__init__.py` : import +
  `register_self_update_commands(main_group)`.
- `tests/unit/test_self_update.py` (nouveau) : 18 tests miroirs de
  `../semacli/tests/unit/test_self_update.py`, avec mock de `urlopen`
  via un faux context manager `BytesIO` (au lieu du mock `requests.get`).
- `pyproject.toml` :
  - `dependencies` : ajout de `certifi>=2024.0` (utilisé pour le bundle
    CA dans l'appel PyPI).
  - `[tool.pdm.dev-dependencies]` : ajout du groupe `publish`
    (`twine>=6.2.0`, `keyring>=25.7.0`) pour que `pdm publish` puisse
    lire les credentials du Keychain macOS sans prompter.
  - script `install-dev` : `pdm install -G dev -G publish`.
- `publish.sh` : nouvelle étape 2/10 « Syncing Lockfile » qui exécute
  `pdm lock -G :all` avant l'installation, pour que toute évolution des
  groupes dans `pyproject.toml` soit prise en compte automatiquement
  (publish.sh autonome, sans intervention manuelle sur le lockfile).
- `pdm.lock` : régénéré pour inclure les groupes `default`, `dev`,
  `publish`.

### Comportements obtenus

- `nagioscli self-update` (à jour) : sortie 0, message "Already up to date".
- `nagioscli self-update --check` : exit 1 si upgrade dispo, 0 sinon.
- `nagioscli self-update --dry-run` : imprime
  `<python> -m pip install --upgrade nachos`, n'exécute pas pip.
- `nagioscli self-update --pre` : ajoute `--pre` à la commande pip,
  considère les pré-releases dans la résolution PyPI.
- Smoke test réel contre PyPI : OK (`Latest on PyPI: 0.1.20 — Already
  up to date.`).
- `pdm publish` peut désormais lire le token PyPI depuis le Keychain
  (via `keyring`), sans demander de credential interactivement.

### Garde-fous

- `pdm run lint` : All checks passed.
- `pdm run typecheck` : Success, no issues found in 21 source files.
- `pdm run test-quick` : 150 tests OK (18 nouveaux).
- `pdm run test-cov-xml` : couverture 92.50 % (gate à 80 %).
- Pas de `requests`/`httpx` ajouté en runtime ; uniquement `certifi`,
  dépendance pure data (bundle CA), conforme à l'esprit de la consigne
  "stdlib urllib on purpose".
---

[← retour à cli/commands](index.md) · [voir log](../../log.md)
